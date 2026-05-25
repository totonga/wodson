"""Top-level command-line interface for asamatfx.

Usage::

    uv run asamatfx atfx serve
    uv run asamatfx atfx serve --file path/to/file.atfx
    uv run asamatfx atfx serve --file path/to/file.atfx --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import argparse

import asamatfx.atfx._cli as _atfx_cli


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asamatfx",
        description="asamatfx command-line tools.",
    )
    sub = parser.add_subparsers(dest="module", required=True)
    _atfx_cli.register_atfx_subparser(sub)
    return parser


def main() -> None:
    """Entry point for the ``asamatfx`` CLI command."""
    parser = _build_parser()
    args = parser.parse_args()
    if args.module == "atfx":
        _atfx_cli.dispatch(args)


if __name__ == "__main__":
    main()
