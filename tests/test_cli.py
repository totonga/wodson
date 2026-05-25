"""Tests for the CLI module."""

from __future__ import annotations

import signal
from unittest.mock import MagicMock, patch

import pytest

from asamatfx._cli import _build_parser, main
from asamatfx.atfx._cli import (
    _LOG_LEVELS,
    _cmd_serve,
    _configure_logging,
    _wait_windows,
)


def test_build_parser_has_atfx_serve_subcommand():
    parser = _build_parser()
    args = parser.parse_args(["atfx", "serve", "--file", "test.atfx"])
    assert args.module == "atfx"
    assert args.command == "serve"
    assert args.file == "test.atfx"
    assert args.host == "127.0.0.1"
    assert args.port == 8080
    assert args.loglevel == "default"


def test_build_parser_custom_host_port():
    parser = _build_parser()
    args = parser.parse_args(["atfx", "serve", "--file", "x.atfx", "--host", "0.0.0.0", "--port", "9090"])
    assert args.host == "0.0.0.0"
    assert args.port == 9090


def test_build_parser_short_flags():
    parser = _build_parser()
    args = parser.parse_args(["atfx", "serve", "-f", "x.atfx", "-p", "1234"])
    assert args.file == "x.atfx"
    assert args.port == 1234


def test_build_parser_file_is_optional():
    parser = _build_parser()
    args = parser.parse_args(["atfx", "serve"])
    assert args.module == "atfx"
    assert args.command == "serve"
    assert args.file is None
    assert args.host == "127.0.0.1"
    assert args.port == 8080


def test_build_parser_requires_module():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_build_parser_requires_subcommand():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["atfx"])


def test_build_parser_loglevel_choices():
    parser = _build_parser()
    for level in ("verbose", "default", "quiet"):
        args = parser.parse_args(["atfx", "serve", "-f", "x.atfx", "--loglevel", level])
        assert args.loglevel == level


def test_build_parser_loglevel_short_flag():
    parser = _build_parser()
    args = parser.parse_args(["atfx", "serve", "-f", "x.atfx", "-l", "verbose"])
    assert args.loglevel == "verbose"


def test_build_parser_invalid_loglevel():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["atfx", "serve", "-f", "x.atfx", "--loglevel", "invalid"])


def test_configure_logging_sets_level():
    import logging

    _configure_logging("quiet")
    assert logging.getLogger("asamatfx").level == logging.WARNING
    _configure_logging("verbose")
    assert logging.getLogger("asamatfx").level == logging.DEBUG
    _configure_logging("default")
    assert logging.getLogger("asamatfx").level == logging.INFO


def test_log_levels_mapping():
    import logging

    assert _LOG_LEVELS["verbose"] == logging.DEBUG
    assert _LOG_LEVELS["default"] == logging.INFO
    assert _LOG_LEVELS["quiet"] == logging.WARNING


@patch("asamatfx.atfx._cli.AtfxServer")
@patch("asamatfx.atfx._cli.signal")
def test_cmd_serve_starts_and_stops(mock_signal, mock_server_cls):
    mock_server = MagicMock()
    mock_server.url = "http://127.0.0.1:8080"
    mock_server_cls.return_value = mock_server

    # Make signal.pause raise to exit the blocking loop
    mock_signal.SIGINT = signal.SIGINT
    mock_signal.SIGTERM = signal.SIGTERM
    mock_signal.pause.side_effect = KeyboardInterrupt

    parser = _build_parser()
    args = parser.parse_args(["atfx", "serve", "--file", "test.atfx"])

    with pytest.raises(KeyboardInterrupt):
        _cmd_serve(args)

    mock_server_cls.assert_called_once_with(host="127.0.0.1", port=8080, default_file="test.atfx")
    mock_server.start.assert_called_once()


def test_wait_windows_joins_thread():
    mock_server = MagicMock()
    mock_thread = MagicMock()
    mock_server._thread = mock_thread
    _wait_windows(mock_server)
    mock_thread.join.assert_called_once()


@patch("asamatfx.atfx._cli.dispatch")
@patch("sys.argv", ["asamatfx", "atfx", "serve", "--file", "test.atfx"])
def test_main_dispatches_atfx(mock_dispatch):
    main()
    mock_dispatch.assert_called_once()
