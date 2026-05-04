"""Command-line interface for the asamatfx HTTP server.

Usage::

    uv run asamatfx serve
    uv run asamatfx serve --file path/to/file.atfx
    uv run asamatfx serve --file path/to/file.atfx --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys

from asamatfx._server import AtfxServer

# Mapping from user-facing names to logging levels
_LOG_LEVELS: dict[str, int] = {
    "verbose": logging.DEBUG,
    "default": logging.INFO,
    "quiet": logging.WARNING,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asamatfx",
        description="Serve an ATFX file via the ASAM ODS HTTP API.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser(
        "serve",
        help="Start the ASAM ODS HTTP server for a given ATFX file.",
    )
    serve.add_argument(
        "--file",
        "-f",
        required=False,
        default=None,
        metavar="PATH",
        help="Path to the .atfx file to serve (optional; client can provide via context variables).",
    )
    serve.add_argument(
        "--host",
        default="127.0.0.1",
        metavar="HOST",
        help="Bind address (default: 127.0.0.1).",
    )
    serve.add_argument(
        "--port",
        "-p",
        type=int,
        default=8080,
        metavar="PORT",
        help="TCP port to listen on (default: 8080).",
    )
    serve.add_argument(
        "--loglevel",
        "-l",
        choices=list(_LOG_LEVELS),
        default="default",
        help="Log verbosity: verbose (DEBUG), default (INFO), quiet (WARNING). (default: default)",
    )
    return parser


def _configure_logging(level_name: str) -> None:
    """Configure the ``asamatfx`` logger hierarchy."""
    level = _LOG_LEVELS.get(level_name, logging.INFO)
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        level=level,
    )
    logging.getLogger("asamatfx").setLevel(level)


def _cmd_serve(args: argparse.Namespace) -> None:
    _configure_logging(args.loglevel)
    log = logging.getLogger(__name__)

    host: str = args.host
    port: int = args.port
    file_path: str | None = args.file

    server = AtfxServer(host=host, port=port, default_file=file_path)
    server.start()

    actual_url = server.url
    log.info("asamatfx server listening on %s", actual_url)
    if file_path:
        log.info("  Default ATFX file: %s", file_path)
    else:
        log.info("  No default ATFX file; client must provide ATFX_FILE context variable")
    log.info("Press Ctrl+C to stop.")
    sys.stdout.flush()

    def _shutdown(sig: int, frame: object) -> None:
        log.info("Shutting down…")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Block the main thread until a signal arrives
    signal.pause() if hasattr(signal, "pause") else _wait_windows(server)


def _wait_windows(server: AtfxServer) -> None:
    """On Windows, signal.pause() is not available — block with a join."""
    assert server._thread is not None  # noqa: S101
    server._thread.join()


def main() -> None:
    """Entry point for the ``asamatfx`` CLI command."""
    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "serve":
        _cmd_serve(args)


if __name__ == "__main__":
    main()
