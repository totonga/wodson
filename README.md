# wodson

A collection of ASAM ODS tools.

## Features

### Experimental ATFX parser

This is an experimental ATFX reader. Target is not correctness or completeness, but a working prototype that can read some real-world ATFX files and be used as a base for further experiments. It currently supports:

- Parses ATFX XML files (ASAM ODS 5.1, 5.3, 6.2 schemas)
- Reads optional external binary `.dat` files (all standard typespecs)
- Loads everything into an in-memory SQLite database
- Exposes `ods.Model` (application model) and `ods.DataMatrices` (data-read)
- Embeddable Python library (`AtfxStore`)
- Standalone HTTP server compatible with `odsbox.ConI` (`AtfxServer`)
- CLI: `uv run wodson atfx serve --file path/to/file.atfx`
- High-level DataFrame convenience API (`AtfxFile`)

## Requirements

- Python ≥ 3.14
- [`odsbox`](https://pypi.org/project/odsbox/) ≥ 1.2.0
- [`numpy`](https://numpy.org/) ≥ 2.0

## Installation

```bash
pip install wodson
# or with uv:
uv add wodson
```

## Quick Start

See [docs/atfx.md](docs/atfx.md) for usage examples (embedded library, HTTP server, CLI).

## Project Layout

```
src/wodson/
    __init__.py          Package root
    _cli.py              CLI entry point (wodson atfx serve …)
    atfx/
        __init__.py          Public API (AtfxFile, AtfxStore, AtfxServer, AtfxSession, …)
        _cli.py              atfx subcommand logic
        base_model/          ASAM ODS base model protobuf JSON files
        _atfx_file.py        AtfxFile — high-level DataFrame + JAQueL wrapper
                  ODSBaseModel_asam37.protobuf.json
        _atfx_store.py       AtfxStore — parses + loads ATFX into SQLite
        _server.py           AtfxServer — ASAM ODS HTTP server
        _session.py          AtfxSession — in-process requests adapter
        _base_model.py       Loads ODSBaseModel JSON → ods.BaseModel
        _model_builder.py    Builds ods.Model from <application_model> XML
        _instance_parser.py  Parses <instance_data> (inline + external)
        _binary_reader.py    Reads external .dat binary files via numpy
        _db.py               SQLite schema creation + instance loading
        _data_read.py        SelectStatement → SQL → DataMatrices
        _xml_utils.py        Namespace-aware XML element lookup helpers
        _naming.py           ODS name → SQLite identifier utilities
docs/
    atfx.md              ATFX reader quick-start guide
    USAGE.md             Full end-user usage guide
    spec/                ASAM schema files and base model JSON
tests/                   pytest test suite
```

## Development

```bash
# Install with dev dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy --strict src/
```

See [docs/USAGE.md](docs/USAGE.md) for detailed end-user documentation.
