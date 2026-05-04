# asamatfx — Usage Guide

This guide covers how to use **asamatfx** to read ASAM ATFX files, query their
content, and optionally expose them over an ASAM ODS HTTP interface.

---

## Table of Contents

1. [Installation](#installation)
2. [ATFX File Format](#atfx-file-format)
3. [Embedded Library — AtfxStore](#embedded-library--atfxstore)
4. [HTTP Server — AtfxServer](#http-server--atfxserver)
5. [CLI — Command Line Interface](#cli--command-line-interface)
6. [Querying with odsbox ConI](#querying-with-odsbox-coni)
7. [Supported Content Types](#supported-content-types)
8. [API Reference](#api-reference)

---

## Installation

```bash
pip install asamatfx
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv add asamatfx
```

---

## ATFX File Format

ATFX (ASAM Test Format XML) files contain:

- An **application model** describing entity types, attributes, and relations
- **Instance data** with actual measurement values
- Optional external **binary `.dat` files** for bulk signal data

The application model is always read and resolved against the ASAM ODS base
model (shipped with this package).  Binary `.dat` files are expected to be in
the same directory as the `.atfx` file.

---

## Embedded Library — AtfxStore

`AtfxStore` loads an ATFX file into an in-memory SQLite database and provides
direct Python access to the ODS API.

### Loading a file

```python
from asamatfx import AtfxStore

# Context manager (recommended)
with AtfxStore("measurement.atfx") as store:
    model = store.model()       # ods.Model
    ...
    # file is closed on exit

# Manual lifecycle
store = AtfxStore("measurement.atfx")
try:
    model = store.model()
finally:
    store.close()
```

### Reading the application model

```python
with AtfxStore("measurement.atfx") as store:
    model = store.model()

    for name, entity in model.entities.items():
        print(f"{name}  (AID={entity.aid}, base={entity.base_name})")
        for attr_name, attr in entity.attributes.items():
            print(f"  {attr_name}: {attr.data_type}")
```

### Querying data

Data is queried using `ods.SelectStatement`, mirroring the ASAM ODS HTTP
`data-read` operation.

```python
import odsbox.proto.ods_pb2 as ods
from asamatfx import AtfxStore

with AtfxStore("measurement.atfx") as store:
    model = store.model()
    mea = model.entities["Measurement"]

    # Select all columns
    stmt = ods.SelectStatement()
    stmt.columns.add(aid=mea.aid, attribute="*")
    result = store.data_read(stmt)   # ods.DataMatrices

    for matrix in result.matrices:
        print(f"Entity: {matrix.name}")
        for col in matrix.columns:
            print(f"  {col.name}: {list(col.string_array.values or col.longlong_array.values)}")
```

#### Selecting specific attributes

```python
stmt = ods.SelectStatement()
stmt.columns.add(aid=mea.aid, attribute="Id")
stmt.columns.add(aid=mea.aid, attribute="Name")
```

#### Filtering with WHERE conditions

```python
cond = stmt.where.add()
cond.condition.aid = mea.aid
cond.condition.attribute = "Name"
cond.condition.operator = ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_EQ
cond.condition.string_array.values.append("MyMeasurement")
```

Available operators: `OP_EQ`, `OP_NEQ`, `OP_LT`, `OP_GT`, `OP_LTE`, `OP_GTE`,
`OP_LIKE`, `OP_NOTLIKE`, `OP_INSET`, `OP_NOTINSET` (plus case-insensitive
`OP_CI_*` variants).

#### Ordering and limiting results

```python
stmt.order_by.add(
    aid=mea.aid,
    attribute="Name",
    order=ods.SelectStatement.OrderByItem.OrderEnum.OD_ASCENDING,
)
stmt.row_limit = 10
stmt.row_start = 0
```

#### Joining entities

```python
stmt = ods.SelectStatement()
stmt.columns.add(aid=mea.aid, attribute="Name")
stmt.columns.add(aid=subtest_aid, attribute="Name")
stmt.joins.add(
    aid_from=mea.aid,
    aid_to=subtest_aid,
    relation="Subtest",
    join_type=ods.SelectStatement.JoinItem.JoinTypeEnum.JT_DEFAULT,
)
```

#### Aggregates

```python
stmt.columns.add(
    aid=mea.aid,
    attribute="Id",
    aggregate=ods.AggregateEnum.AG_COUNT,
)
```

---

## HTTP Server — AtfxServer

`AtfxServer` starts an ASAM ODS-compatible HTTP server.  Each HTTP session
independently loads the requested ATFX file.

### Starting the server

```python
from asamatfx import AtfxServer

# Context manager — starts on entry, stops on exit
with AtfxServer(host="127.0.0.1", port=8080) as server:
    print(f"Listening on {server.url}")
    ...

# Manual lifecycle
server = AtfxServer(host="0.0.0.0", port=8080)
server.start()
# ... do work ...
server.stop()
```

`port=0` lets the OS pick a free port; read it back with `server.port`.

### HTTP Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ods` | Create a session; body: `ods.ContextVariables` |
| `POST` | `/ods/{session_id}/context-read` | Return session context variables |
| `POST` | `/ods/{session_id}/model-read` | Read application model |
| `POST` | `/ods/{session_id}/data-read` | Execute a `SelectStatement` |
| `DELETE` | `/ods/{session_id}` | Close and release the session |

### Creating a session

Send a `POST /ods` with `ods.ContextVariables` containing the `ATFX_FILE` key:

```python
import requests
import odsbox.proto.ods_pb2 as ods
from asamatfx import CONTEXT_VAR_ATFX_FILE

ctx = ods.ContextVariables()
ctx.variables[CONTEXT_VAR_ATFX_FILE].string_array.values.append("/path/to/file.atfx")

resp = requests.post(
    "http://127.0.0.1:8080/ods",
    data=ctx.SerializeToString(),
    headers={"Content-Type": "application/x-asamods+protobuf"},
)
# HTTP 201 — session URL in Location header
session_url = resp.headers["Location"]
```

---

## CLI — Command Line Interface

Start the HTTP server from the command line:

```bash
uv run asamatfx serve --file path/to/file.atfx
```

### Options

```
usage: asamatfx serve [-h] --file PATH [--host HOST] [--port PORT]
                      [--loglevel {verbose,default,quiet}]

options:
  --file PATH, -f PATH   Path to the .atfx file to serve  (required)
  --host HOST            Bind address  (default: 127.0.0.1)
  --port PORT, -p PORT   TCP port      (default: 8080)
  --loglevel, -l         Log verbosity: verbose (DEBUG), default (INFO),
                         quiet (WARNING)  (default: default)
```

### Examples

```bash
# Loopback, default port
uv run asamatfx serve --file data/Example_Simple.atfx

# All interfaces, custom port
uv run asamatfx serve --file data/Example_Simple.atfx --host 0.0.0.0 --port 9090

# Verbose logging for debugging
uv run asamatfx serve --file data/Example_Simple.atfx --loglevel verbose
```

The server prints its URL on startup:

```
asamatfx server listening on http://127.0.0.1:8080
  ATFX_FILE context variable: data/Example_Simple.atfx
Press Ctrl+C to stop.
```

---

## Querying with odsbox ConI

Use [`odsbox.ConI`](https://pypi.org/project/odsbox/) to connect to the server
using the same API as any other ASAM ODS server:

```python
from odsbox.con_i import ConI
from asamatfx import CONTEXT_VAR_ATFX_FILE

with ConI(
    url="http://127.0.0.1:8080",
    auth=None,                                              # no auth required
    context_variables={CONTEXT_VAR_ATFX_FILE: "/path/to/file.atfx"},
    load_model=False,
) as con:
    model = con.model_read()

    # High-level JAQueL query → pandas DataFrame
    df = con.query_data({"AoMeasurement": {"$attributes": {"name": 1, "id": 1}}})
    print(df)

    # Low-level SelectStatement
    import odsbox.proto.ods_pb2 as ods
    mea = model.entities["Measurement"]
    stmt = ods.SelectStatement()
    stmt.columns.add(aid=mea.aid, attribute="*")
    matrices = con.data_read(stmt)
```

> **Note:** Authorization is not enforced. The `auth=None` parameter skips
> credential headers, which the server ignores.

---

## Supported Content Types

Both the library and the HTTP server accept and return:

| Content-Type | Encoding |
|---|---|
| `application/x-asamods+protobuf` | Binary protobuf (default) |
| `application/x-asamods+json` | Google protobuf JSON format |

Set the `Content-Type` header for the request body and the `Accept` header for
the desired response format.

---

## API Reference

### `AtfxStore(file_path, base_model_path=None)`

Load an ATFX file into memory.

| Method | Returns | Description |
|--------|---------|-------------|
| `model()` | `ods.Model` | Application model |
| `data_read(select_statement)` | `ods.DataMatrices` | Execute a query |
| `context_read()` | `ods.ContextVariables` | Session context (`ASAM-ODS-VERSION`, `BASE-MODEL-VERSION`) |
| `close()` | `None` | Release resources |

Context manager (`with` statement) calls `close()` automatically.

---

### `AtfxServer(host="127.0.0.1", port=0, default_file=None)`

Start an ASAM ODS HTTP server.

| Parameter | Type | Description |
|-----------|------|-------------|
| `host` | `str` | Bind address (default `"127.0.0.1"`) |
| `port` | `int` | Port to bind; `0` picks a free port |
| `default_file` | `str \| None` | ATFX file used when `ATFX_FILE` context variable is omitted |

| Member | Type | Description |
|--------|------|-------------|
| `url` | `str` | Base URL (e.g. `http://127.0.0.1:8080`) |
| `port` | `int` | Bound port |
| `start()` | `None` | Start background thread |
| `stop()` | `None` | Shutdown server |

Context manager (`with` statement) calls `start()` / `stop()` automatically.

---

### `CONTEXT_VAR_ATFX_FILE`

String constant `"ATFX_FILE"` — the context variable key used to pass the ATFX
file path when creating a session via `POST /ods`.

---

## Error Handling

HTTP error responses are returned as `ods.ErrorInfo` protobuf messages with
`Content-Type: application/x-asamods+protobuf`.

| Status | Condition |
|--------|-----------|
| 400 | Missing `ATFX_FILE` context variable, failed to load ATFX file, or invalid `SelectStatement` |
| 404 | Session ID not found, or unknown endpoint |
| 500 | Query execution error |
