"""ASAM ODS HTTP server backed by AtfxStore.

Implements the ASAM ODS HTTP API subset needed for read-only access:

* ``POST /ods``                           -- create session from context variables
* ``POST /ods/{session_id}/context-read`` -- return session context variables
* ``POST /ods/{session_id}/model-read``   -- return application model
* ``POST /ods/{session_id}/data-read``    -- execute SelectStatement query
* ``DELETE /ods/{session_id}``            -- close session

Accepted / returned content types:

* ``application/x-asamods+protobuf`` (default)
* ``application/x-asamods+json``

Context variable key for the ATFX file path: ``ATFX_FILE``.
"""

from __future__ import annotations

import logging
import socketserver
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import cast

import odsbox.proto.ods_pb2 as ods
from google.protobuf import json_format
from google.protobuf.message import Message

from ._atfx_store import AtfxStore

_log = logging.getLogger(__name__)

CONTENT_TYPE_PROTO: str = "application/x-asamods+protobuf"
"""Content type for binary protobuf encoding."""

CONTENT_TYPE_JSON: str = "application/x-asamods+json"
"""Content type for JSON encoding (google.protobuf.json_format)."""

CONTEXT_VAR_ATFX_FILE: str = "ATFX_FILE"
"""Context variable key used to pass the ATFX file path on connect."""


class _AtfxHttpServer(socketserver.ThreadingMixIn, HTTPServer):
    """Thread-safe HTTP server that stores active AtfxStore sessions."""

    daemon_threads = True  # noqa: RUF012

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
        default_file: str | None = None,
    ) -> None:
        super().__init__(server_address, request_handler_class)
        self._sessions: dict[str, AtfxStore] = {}
        self._lock: threading.Lock = threading.Lock()
        self._default_file: str | None = default_file
        # Cache loaded stores by resolved file path so that reconnects to the
        # same file skip the ~10ms parse+load step.  The store is owned by the
        # cache; session logout does NOT close it.
        self._store_cache: dict[str, AtfxStore] = {}
        # After bind, server_address is updated with the actual port
        bound = cast(tuple[str, int], self.server_address)
        self._host: str = bound[0]
        self._port: int = bound[1]

    def get_or_load_store(self, file_path: str) -> AtfxStore:
        """Return a cached AtfxStore for *file_path*, loading it on first use."""
        resolved = str(Path(file_path).resolve())
        with self._lock:
            if resolved in self._store_cache:
                return self._store_cache[resolved]
        # Load outside the lock to avoid blocking other threads during parsing.
        store = AtfxStore(file_path)
        with self._lock:
            # Re-check after acquiring lock (another thread may have loaded it).
            if resolved not in self._store_cache:
                self._store_cache[resolved] = store
            else:
                store.close()  # discard the duplicate we just created
                store = self._store_cache[resolved]
        return store

    def close_all_stores(self) -> None:
        """Close every cached AtfxStore (called on server shutdown)."""
        with self._lock:
            for store in self._store_cache.values():
                store.close()
            self._store_cache.clear()


class _AtfxRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler implementing the ASAM ODS read subset."""

    @property
    def _srv(self) -> _AtfxHttpServer:
        return cast(_AtfxHttpServer, self.server)

    # ------------------------------------------------------------------
    # HTTP verb handlers

    def do_POST(self) -> None:  # noqa: N802
        """Route POST requests."""
        parts = self.path.lstrip("/").split("/")
        if parts == ["ods"]:
            self._handle_connect()
        elif len(parts) == 3 and parts[0] == "ods" and parts[2] == "context-read":
            self._handle_context_read(parts[1])
        elif len(parts) == 3 and parts[0] == "ods" and parts[2] == "model-read":
            self._handle_model_read(parts[1])
        elif len(parts) == 3 and parts[0] == "ods" and parts[2] == "data-read":
            self._handle_data_read(parts[1])
        else:
            self._send_error(404, "Endpoint not found")

    def do_DELETE(self) -> None:  # noqa: N802
        """Route DELETE requests (session logout)."""
        parts = self.path.lstrip("/").split("/")
        if len(parts) == 2 and parts[0] == "ods":
            self._handle_logout(parts[1])
        else:
            self._send_error(404, "Endpoint not found")

    # ------------------------------------------------------------------
    # Endpoint implementations

    def _handle_connect(self) -> None:
        body = self._read_body()
        ctx = ods.ContextVariables()
        try:
            self._parse_message(ctx, body)
        except Exception as exc:  # noqa: BLE001
            self._send_error(400, str(exc))
            return

        atfx_var = ctx.variables.get(CONTEXT_VAR_ATFX_FILE)
        if atfx_var is not None and atfx_var.string_array.values:
            file_path = atfx_var.string_array.values[0]
        elif self._srv._default_file is not None:
            file_path = self._srv._default_file
        else:
            self._send_error(400, f"Missing context variable '{CONTEXT_VAR_ATFX_FILE}'")
            return
        try:
            store = self._srv.get_or_load_store(file_path)
        except Exception as exc:  # noqa: BLE001
            self._send_error(400, f"Failed to load ATFX file: {exc}")
            return

        session_id = str(uuid.uuid4())
        with self._srv._lock:
            self._srv._sessions[session_id] = store

        # Use the Host request header so the Location URL is always reachable
        # by the client — the bind address (e.g. 0.0.0.0) is not routable.
        request_host = self.headers.get("Host") or f"{self._srv._host}:{self._srv._port}"
        session_url = f"http://{request_host}/ods/{session_id}"
        _log.info("Session created: %s (file: %s)", session_id, file_path)

        self.send_response(201)
        self.send_header("Location", session_url)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _handle_context_read(self, session_id: str) -> None:
        _log.debug("context-read for session %s", session_id)
        store = self._get_session(session_id)
        if store is None:
            return
        self._send_message(store.context_read())

    def _handle_model_read(self, session_id: str) -> None:
        _log.debug("model-read for session %s", session_id)
        store = self._get_session(session_id)
        if store is None:
            return
        self._send_message(store.model())

    def _handle_data_read(self, session_id: str) -> None:
        _log.debug("data-read for session %s", session_id)
        store = self._get_session(session_id)
        if store is None:
            return

        body = self._read_body()
        stmt = ods.SelectStatement()
        try:
            self._parse_message(stmt, body)
        except Exception as exc:  # noqa: BLE001
            self._send_error(400, f"Failed to parse SelectStatement: {exc}")
            return

        try:
            result = store.data_read(stmt)
        except Exception as exc:  # noqa: BLE001
            _log.debug("Query error in session %s: %s", session_id, exc)
            self._send_error(500, f"Query error: {exc}")
            return

        self._send_message(result)

    def _handle_logout(self, session_id: str) -> None:
        with self._srv._lock:
            self._srv._sessions.pop(session_id, None)
        # The AtfxStore is owned by the server cache; do not close it here.
        _log.info("Session closed: %s", session_id)
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ------------------------------------------------------------------
    # Helpers

    def _get_session(self, session_id: str) -> AtfxStore | None:
        with self._srv._lock:
            store = self._srv._sessions.get(session_id)
        if store is None:
            self._send_error(404, f"Session '{session_id}' not found")
        return store

    def _read_body(self) -> bytes:
        length_str = self.headers.get("Content-Length", "0")
        length = int(length_str) if length_str else 0
        return self.rfile.read(length) if length > 0 else b""

    def _parse_message(self, msg: Message, body: bytes) -> None:
        if not body:
            return
        content_type = self.headers.get("Content-Type", CONTENT_TYPE_PROTO)
        if CONTENT_TYPE_JSON in content_type:
            json_format.Parse(body.decode("utf-8"), msg)
        else:
            msg.ParseFromString(body)

    def _send_message(self, msg: Message) -> None:
        accept = self.headers.get("Accept", CONTENT_TYPE_PROTO)
        if CONTENT_TYPE_JSON in accept:
            body = json_format.MessageToJson(msg).encode("utf-8")
            content_type = CONTENT_TYPE_JSON
        else:
            body = msg.SerializeToString()
            content_type = CONTENT_TYPE_PROTO

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, reason: str) -> None:
        _log.debug("HTTP %d: %s", status, reason)
        error_info = ods.ErrorInfo()
        error_info.reason = reason
        body = error_info.SerializeToString()

        self.send_response(status)
        self.send_header("Content-Type", CONTENT_TYPE_PROTO)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Route HTTP log messages through the logging framework."""
        _log.debug(format, *args)


class AtfxServer:
    """ASAM ODS HTTP server that serves ATFX files via the ODS read API.

    Supports a read-only subset of the ASAM ODS HTTP interface: model-read
    and data-read.  Sessions are created by POSTing ``ods.ContextVariables``
    with the ``ATFX_FILE`` key to ``/ods``.

    Usage::

        from odsbox.con_i import ConI
        from wodson.atfx import AtfxServer, CONTEXT_VAR_ATFX_FILE

        with AtfxServer() as server:
            with ConI(
                url=server.url,
                auth=None,
                context_variables={CONTEXT_VAR_ATFX_FILE: "/path/to/file.atfx"},
                load_model=False,
            ) as con:
                model = con.model_read()
                matrices = con.data_read(select_statement)
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0, default_file: str | None = None) -> None:
        """Create the server (does not start serving yet).

        Args:
            host: Bind address. Defaults to loopback.
            port: Port to bind. ``0`` lets the OS pick a free port.
            default_file: Path to an ATFX file used when no ``ATFX_FILE``
                context variable is supplied on session creation.
        """
        self._server = _AtfxHttpServer((host, port), _AtfxRequestHandler, default_file)
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        """Base URL for ConI (e.g. ``http://127.0.0.1:PORT``)."""
        host, port = self._server._host, self._server._port
        return f"http://{host}:{port}"

    @property
    def port(self) -> int:
        """Bound port number."""
        return self._server._port

    def start(self) -> None:
        """Start serving in a daemon background thread."""
        _log.info("Starting server on %s", self.url)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True, name="AtfxServer")
        self._thread.start()

    def stop(self) -> None:
        """Shutdown the server and join the background thread."""
        _log.info("Stopping server")
        self._server.shutdown()
        self._server.close_all_stores()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def __enter__(self) -> AtfxServer:
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop()
