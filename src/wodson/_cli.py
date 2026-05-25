"""Top-level command-line interface for wodson.

Usage::

    uv run wodson atfx serve
    uv run wodson atfx serve --file path/to/file.atfx
    uv run wodson atfx serve --file path/to/file.atfx --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import argparse

import wodson.atfx._cli as _atfx_cli


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wodson",
        description="wodson ASAM ODS command-line tools.",
    )
    sub = parser.add_subparsers(dest="module", required=True)
    _atfx_cli.register_atfx_subparser(sub)
    return parser


def main() -> None:
    """Entry point for the ``wodson`` CLI command."""
    parser = _build_parser()
    args = parser.parse_args()
    if args.module == "atfx":
        _atfx_cli.dispatch(args)


if __name__ == "__main__":
    main()
