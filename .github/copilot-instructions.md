# asamatfx - Copilot Instructions

## Project Purpose

**asamatfx** is a Python library that reads ASAM ATFX files (XML + optional binary `.dat` files), loads data into an in-memory SQLite database, and exposes it via the ASAM ODS protobuf API. It also provides an HTTP server (`AtfxServer`) compatible with the `odsbox.ConI` client.

## Module Map

All implementation lives under `src/asamatfx/atfx/`. The top-level `src/asamatfx/` package contains only the CLI entry point and the `py.typed` marker.

| Module | Role |
|--------|------|
| `_cli.py` | Top-level CLI entry point — registers `atfx` subcommand group |
| `atfx/__init__.py` | Public API — exports `AtfxStore`, `AtfxServer`, `AtfxSession`, `CONTEXT_VAR_ATFX_FILE` |
| `atfx/_cli.py` | `atfx` subcommand logic — `asamatfx atfx serve --file FILE [--host H] [--port P] [--loglevel L]` |
| `atfx/_atfx_store.py` | Main `AtfxStore` class — parses ATFX, builds model, loads instances |
| `atfx/_server.py` | `AtfxServer` HTTP server — read-only ASAM ODS HTTP API |
| `atfx/_session.py` | `AtfxSession` — in-process requests adapter (no TCP) |
| `atfx/_base_model.py` | Loads `ODSBaseModel_asam37.protobuf.json` into `ods.BaseModel` |
| `atfx/_model_builder.py` | Builds `ods.Model` from `<application_model>` XML |
| `atfx/_instance_parser.py` | Parses `<instance_data>` (inline + external references) |
| `atfx/_binary_reader.py` | Reads external `.dat` binary files via numpy |
| `atfx/_db.py` | SQLite schema creation + instance loading |
| `atfx/_data_read.py` | Translates `ods.SelectStatement` → SQL → `ods.DataMatrices` |
| `atfx/_xml_utils.py` | Namespace-aware XML element lookup helpers |
| `atfx/_naming.py` | ODS name → SQLite identifier conversion utilities |

## Public API

```python
from asamatfx.atfx import AtfxStore, AtfxServer, AtfxSession, CONTEXT_VAR_ATFX_FILE
```

### AtfxStore (embedded usage)

```python
with AtfxStore("path/to/file.atfx") as store:
    model = store.model()                    # ods.Model
    result = store.data_read(select_stmt)    # ods.DataMatrices
```

### AtfxServer (HTTP server for odsbox ConI)

```python
from odsbox.con_i import ConI

with AtfxServer(host="127.0.0.1", port=0) as server:
    with ConI(
        url=server.url,
        auth=None,
        context_variables={CONTEXT_VAR_ATFX_FILE: "/path/to/file.atfx"},
        load_model=False,
    ) as con:
        model = con.model_read()
        matrices = con.data_read(select_statement)
```

The context variable key `ATFX_FILE` passes the ATFX file path to the server on session creation.

## HTTP Endpoints

| Method | Path | Request | Response |
|--------|------|---------|----------|
| POST | `/ods` | `ods.ContextVariables` | 201 + `Location` header |
| POST | `/ods/{id}/context-read` | (empty) | `ods.ContextVariables` |
| POST | `/ods/{id}/model-read` | (empty) | `ods.Model` |
| POST | `/ods/{id}/data-read` | `ods.SelectStatement` | `ods.DataMatrices` |
| DELETE | `/ods/{id}` | (none) | 200 |

## Content Types

Both are accepted as `Content-Type` and `Accept`:
- `application/x-asamods+protobuf` (default, binary protobuf)
- `application/x-asamods+json` (google.protobuf JSON encoding)

## Running Tests & Linters

```bash
uv run pytest tests/ -v          # run all tests
uv run ruff check src/ tests/    # linting
uv run mypy --strict src/        # type checking
```

## Conventions

- Python ≥ 3.14, type annotations everywhere in `src/`
- `mypy --strict` must pass (ANN401 is ignored in ruff)
- Tests exempt from annotation requirements (`ANN` rules)
- No authorization handling in the HTTP server
- Read-only API only (no data-create, data-update, transactions)
