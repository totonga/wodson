"""In-process requests adapter that routes ConI calls directly to AtfxStore.

Provides :class:`AtfxSession`, a ``requests.Session`` subclass that intercepts
ASAM ODS HTTP calls and dispatches them in-process to an :class:`AtfxStore` —
no socket, no TCP, no port allocation required.

Usage::

    from odsbox.con_i import ConI
    from wodson.atfx import AtfxSession, CONTEXT_VAR_ATFX_FILE

    # Pass the ATFX file as a default (no context variable needed in ConI)
    with AtfxSession(default_file="path/to/file.atfx") as session:
        with ConI(url=session.url, custom_session=session, load_model=False) as con:
            model = con.model_read()
            result = con.data_read(select_statement)

    # Or pass the file via the ATFX_FILE context variable (mirrors AtfxServer)
    with AtfxSession() as session:
        with ConI(
            url=session.url,
            custom_session=session,
            context_variables={CONTEXT_VAR_ATFX_FILE: "path/to/file.atfx"},
            load_model=False,
        ) as con:
            model = con.model_read()
"""

from __future__ import annotations

import datetime
import logging
import threading
import uuid
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

import odsbox.proto.ods_pb2 as ods
import requests
import requests.adapters
from google.protobuf import json_format
from google.protobuf.message import Message
from requests import Response
from requests.cookies import cookiejar_from_dict
from requests.models import PreparedRequest
from requests.structures import CaseInsensitiveDict

from ._atfx_store import AtfxStore
from ._server import CONTENT_TYPE_JSON, CONTENT_TYPE_PROTO, CONTEXT_VAR_ATFX_FILE

_log = logging.getLogger(__name__)

_SYNTHETIC_BASE_URL: str = "http://wodson.local"
"""Synthetic URL prefix used as the mount point for the in-process adapter."""


class AtfxAdapter(requests.adapters.BaseAdapter):
    """In-process transport adapter that handles ASAM ODS requests via AtfxStore.

    Mirrors the routing and serialization logic of :class:`~wodson.atfx._server._AtfxRequestHandler`
    without any network involvement.  Sessions are stored in an internal dict
    keyed by UUID, exactly as in :class:`~wodson.atfx._server._AtfxHttpServer`.

    :param default_file: Path to an ATFX file used when the ``ATFX_FILE``
        context variable is not supplied on session creation.  Mirrors the
        ``default_file`` parameter of :class:`~wodson.atfx.AtfxServer`.
    """

    def __init__(
        self,
        default_file: str | None = None,
        *,
        lazy_load_binary: bool = True,
        strict_binary_load: bool = False,
    ) -> None:
        super().__init__()
        self._default_file: str | None = default_file
        self._lazy_load_binary: bool = lazy_load_binary
        self._strict_binary_load: bool = strict_binary_load
        self._sessions: dict[str, AtfxStore] = {}
        self._lock: threading.Lock = threading.Lock()
        # Cache loaded stores by resolved path; same semantics as the HTTP server.
        self._store_cache: dict[str, AtfxStore] = {}

    def get_or_load_store(self, file_path: str) -> AtfxStore:
        """Return a cached AtfxStore for *file_path*, loading it on first use."""
        resolved = str(Path(file_path).resolve())
        with self._lock:
            if resolved in self._store_cache:
                return self._store_cache[resolved]
        store = AtfxStore(
            file_path,
            lazy_load_binary=self._lazy_load_binary,
            strict_binary_load=self._strict_binary_load,
        )
        with self._lock:
            if resolved not in self._store_cache:
                self._store_cache[resolved] = store
            else:
                store.close()
                store = self._store_cache[resolved]
        return store

    # ------------------------------------------------------------------
    # BaseAdapter interface

    def send(
        self,
        request: PreparedRequest,
        stream: bool = False,  # noqa: FBT001, FBT002
        timeout: float | tuple[float, float] | tuple[float, None] | None = None,
        verify: bool | str = True,  # noqa: FBT001, FBT002
        cert: bytes | str | tuple[bytes | str, bytes | str] | None = None,
        proxies: Mapping[str, str] | None = None,
    ) -> Response:
        """Dispatch a PreparedRequest to the matching in-process handler."""
        path = urlparse(request.url or "").path.lstrip("/")
        parts = path.split("/")

        method = (request.method or "").upper()

        if method == "POST" and parts == ["ods"]:
            return self._handle_connect(request)
        if method == "POST" and len(parts) == 3 and parts[0] == "ods":
            session_id, action = parts[1], parts[2]
            if action == "context-read":
                return self._handle_context_read(request, session_id)
            if action == "model-read":
                return self._handle_model_read(request, session_id)
            if action == "data-read":
                return self._handle_data_read(request, session_id)
        if method == "DELETE" and len(parts) == 2 and parts[0] == "ods":
            return self._handle_logout(request, parts[1])

        return self._error_response(request, 404, "Endpoint not found")

    def close(self) -> None:
        """Close all managed AtfxStore instances."""
        with self._lock:
            for store in self._store_cache.values():
                store.close()
            self._store_cache.clear()
            self._sessions.clear()

    # ------------------------------------------------------------------
    # Endpoint handlers

    def _handle_connect(self, request: PreparedRequest) -> Response:
        body = self._request_body(request)
        ctx = ods.ContextVariables()
        try:
            self._deserialize(ctx, body, self._content_type(request))
        except Exception as exc:  # noqa: BLE001
            return self._error_response(request, 400, str(exc))

        atfx_var = ctx.variables.get(CONTEXT_VAR_ATFX_FILE)
        if atfx_var is not None and atfx_var.string_array.values:
            file_path = atfx_var.string_array.values[0]
        elif self._default_file is not None:
            file_path = self._default_file
        else:
            return self._error_response(request, 400, f"Missing context variable '{CONTEXT_VAR_ATFX_FILE}'")

        try:
            store = self.get_or_load_store(file_path)
        except Exception as exc:  # noqa: BLE001
            return self._error_response(request, 400, f"Failed to load ATFX file: {exc}")

        session_id = str(uuid.uuid4())
        with self._lock:
            self._sessions[session_id] = store

        session_url = f"{_SYNTHETIC_BASE_URL}/ods/{session_id}"
        _log.info("Session created: %s (file: %s)", session_id, file_path)

        r = self._build_response(request, 201, b"")
        r.headers["Location"] = session_url
        return r

    def _handle_context_read(self, request: PreparedRequest, session_id: str) -> Response:
        store = self._get_session(session_id)
        if store is None:
            return self._error_response(request, 404, f"Session '{session_id}' not found")
        return self._message_response(request, store.context_read())

    def _handle_model_read(self, request: PreparedRequest, session_id: str) -> Response:
        store = self._get_session(session_id)
        if store is None:
            return self._error_response(request, 404, f"Session '{session_id}' not found")
        return self._message_response(request, store.model())

    def _handle_data_read(self, request: PreparedRequest, session_id: str) -> Response:
        store = self._get_session(session_id)
        if store is None:
            return self._error_response(request, 404, f"Session '{session_id}' not found")

        body = self._request_body(request)
        stmt = ods.SelectStatement()
        try:
            self._deserialize(stmt, body, self._content_type(request))
        except Exception as exc:  # noqa: BLE001
            return self._error_response(request, 400, f"Failed to parse SelectStatement: {exc}")

        try:
            result = store.data_read(stmt)
        except Exception as exc:  # noqa: BLE001
            _log.debug("Query error in session %s: %s", session_id, exc)
            return self._error_response(request, 500, f"Query error: {exc}")

        return self._message_response(request, result)

    def _handle_logout(self, request: PreparedRequest, session_id: str) -> Response:
        with self._lock:
            self._sessions.pop(session_id, None)
        # The AtfxStore is owned by the cache; do not close it here.
        _log.info("Session closed: %s", session_id)
        return self._build_response(request, 200, b"")

    # ------------------------------------------------------------------
    # Helpers

    def _get_session(self, session_id: str) -> AtfxStore | None:
        with self._lock:
            return self._sessions.get(session_id)

    @staticmethod
    def _request_body(request: PreparedRequest) -> bytes:
        body = request.body
        if body is None:
            return b""
        if isinstance(body, bytes):
            return body
        return body.encode("utf-8")

    @staticmethod
    def _content_type(request: PreparedRequest) -> str:
        headers: CaseInsensitiveDict[str] = request.headers or CaseInsensitiveDict()
        return str(headers.get("Content-Type", CONTENT_TYPE_PROTO))

    @staticmethod
    def _accept(request: PreparedRequest) -> str:
        headers: CaseInsensitiveDict[str] = request.headers or CaseInsensitiveDict()
        return str(headers.get("Accept", CONTENT_TYPE_PROTO))

    @staticmethod
    def _deserialize(msg: Message, body: bytes, content_type: str) -> None:
        if not body:
            return
        if CONTENT_TYPE_JSON in content_type:
            json_format.Parse(body.decode("utf-8"), msg)
        else:
            msg.ParseFromString(body)

    @staticmethod
    def _serialize(msg: Message, accept: str) -> tuple[bytes, str]:
        if CONTENT_TYPE_JSON in accept:
            return json_format.MessageToJson(msg).encode("utf-8"), CONTENT_TYPE_JSON
        return msg.SerializeToString(), CONTENT_TYPE_PROTO

    def _message_response(self, request: PreparedRequest, msg: Message) -> Response:
        body, content_type = self._serialize(msg, self._accept(request))
        r = self._build_response(request, 200, body)
        r.headers["Content-Type"] = content_type
        return r

    def _error_response(self, request: PreparedRequest, status: int, reason: str) -> Response:
        _log.debug("Error %d: %s", status, reason)
        error_info = ods.ErrorInfo()
        error_info.reason = reason
        body = error_info.SerializeToString()
        r = self._build_response(request, status, body)
        r.headers["Content-Type"] = CONTENT_TYPE_PROTO
        return r

    @staticmethod
    def _build_response(request: PreparedRequest, status: int, body: bytes) -> Response:
        r = Response()
        r.status_code = status
        r.headers = CaseInsensitiveDict({"Content-Length": str(len(body))})
        r.url = request.url or ""
        r.request = request
        r._content = body
        r._content_consumed = True  # type: ignore[attr-defined]
        r.reason = ""
        r.cookies = cookiejar_from_dict({})  # type: ignore[no-untyped-call]
        r.history = []
        r.elapsed = datetime.timedelta(0)
        r.encoding = "utf-8"
        return r


class AtfxSession(requests.Session):
    """A ``requests.Session`` that routes ASAM ODS calls in-process via AtfxStore.

    Replaces the HTTP transport with an in-process adapter so that
    :class:`~odsbox.con_i.ConI` can be used without starting an
    :class:`~wodson.atfx.AtfxServer`.  All serialization, content-type
    negotiation, and session management are handled identically to the HTTP
    server — only the network layer is removed.

    :param default_file: Path to an ATFX file used when the ``ATFX_FILE``
        context variable is not supplied to :class:`~odsbox.con_i.ConI`.

    Usage::

        from odsbox.con_i import ConI
        from wodson.atfx import AtfxSession

        with AtfxSession(default_file="path/to/file.atfx") as session:
            with ConI(url=session.url, custom_session=session) as con:
                model = con.model_read()
    """

    def __init__(
        self,
        default_file: str | None = None,
        *,
        lazy_load_binary: bool = True,
        strict_binary_load: bool = False,
    ) -> None:
        super().__init__()
        self._adapter = AtfxAdapter(
            default_file,
            lazy_load_binary=lazy_load_binary,
            strict_binary_load=strict_binary_load,
        )
        self.mount(_SYNTHETIC_BASE_URL + "/", self._adapter)

    @property
    def url(self) -> str:
        """Base URL to pass as the ``url`` argument to :class:`~odsbox.con_i.ConI`."""
        return _SYNTHETIC_BASE_URL
