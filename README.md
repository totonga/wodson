# asamatfx

Python library that reads [ASAM ATFX](https://www.asam.net/standards/detail/atfx/) files and exposes
their content through the [ASAM ODS](https://www.asam.net/standards/detail/ods/) protobuf API.

## Features

- Parses ATFX XML files (ASAM ODS 5.1, 5.3, 6.2 schemas)
- Reads optional external binary `.dat` files (all standard typespecs)
- Loads everything into an in-memory SQLite database
- Exposes `ods.Model` (application model) and `ods.DataMatrices` (data-read)
- Embeddable Python library (`AtfxStore`)
- Standalone HTTP server compatible with `odsbox.ConI` (`AtfxServer`)
- CLI: `uv run asamatfx atfx serve --file path/to/file.atfx`

## Requirements

- Python ≥ 3.14
- [`odsbox`](https://pypi.org/project/odsbox/) ≥ 1.2.0
- [`numpy`](https://numpy.org/) ≥ 2.0

## Installation

```bash
pip install asamatfx
# or with uv:
uv add asamatfx
```

## Quick Start

### Embedded library

```python
from asamatfx.atfx import AtfxStore
import odsbox.proto.ods_pb2 as ods

with AtfxStore("path/to/file.atfx") as store:
    model = store.model()                         # ods.Model

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=model.entities["Measurement"].aid, attribute="*")
    result = store.data_read(stmt)                # ods.DataMatrices
```

### HTTP server + odsbox ConI

```python
from odsbox.con_i import ConI
from asamatfx.atfx import AtfxServer, CONTEXT_VAR_ATFX_FILE

with AtfxServer(host="127.0.0.1", port=8080) as server:
    with ConI(
        url=server.url,
        auth=None,
        context_variables={CONTEXT_VAR_ATFX_FILE: "path/to/file.atfx"},
        load_model=False,
    ) as con:
        model = con.model_read()
        df    = con.query_data({"AoMeasurement": {"$attributes": {"name": 1}}})
```

### CLI

```bash
uv run asamatfx atfx serve --file path/to/file.atfx --host 0.0.0.0 --port 8080
```

Then connect any `odsbox.ConI` client to `http://localhost:8080` and set the
`ATFX_FILE` context variable to the file path.

## Project Layout

```
src/asamatfx/
    __init__.py          Package root
    _cli.py              CLI entry point (asamatfx atfx serve …)
    atfx/
        __init__.py          Public API (AtfxStore, AtfxServer, AtfxSession, …)
        _cli.py              atfx subcommand logic
        base_model/          ASAM ODS base model protobuf JSON files
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
    USAGE.md             End-user usage guide
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
