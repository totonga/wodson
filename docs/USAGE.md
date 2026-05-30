# wodson — Usage Guide

This guide covers how to use **wodson** to read ASAM ATFX files, query their
content, and optionally expose them over an ASAM ODS HTTP interface.

---

## Table of Contents

1. [Installation](#installation)
2. [ATFX File Format](#atfx-file-format)
3. [Embedded Library — AtfxStore](#embedded-library--atfxstore)
4. [HTTP Server — AtfxServer](#http-server--atfxserver)
5. [In-Process Access — AtfxSession](#in-process-access--atfxsession)
6. [CLI — Command Line Interface](#cli--command-line-interface)
7. [Querying with odsbox ConI](#querying-with-odsbox-coni)
8. [Supported Content Types](#supported-content-types)
9. [API Reference](#api-reference)
10. [Error Handling](#error-handling)

---

## Installation

```bash
pip install wodson
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv add wodson
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
from wodson.atfx import AtfxStore

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
from wodson.atfx import AtfxStore

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
from wodson.atfx import AtfxServer

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
from wodson.atfx import CONTEXT_VAR_ATFX_FILE

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

## In-Process Access — AtfxSession

`AtfxSession` is a `requests.Session` subclass that routes `ConI` HTTP calls
directly to an `AtfxStore` — **no socket, no TCP, no port allocation**.
It is the fastest way to use the `odsbox` `ConI` API against a local ATFX
file when you do not need a real network endpoint.

### When to use AtfxSession

| Approach | Network? | Threads? | Best for |
|---|---|---|---|
| `AtfxStore` (direct) | No | No | Python-only, lowest-level access |
| `AtfxSession` + `ConI` | No | No | Re-use existing `ConI` code in-process |
| `AtfxServer` + `ConI` | Yes (localhost) | Yes | Remote clients, multi-process, CLI |

### Basic usage — pass the file to AtfxSession

```python
from odsbox.con_i import ConI
from wodson.atfx import AtfxSession

with AtfxSession(default_file="path/to/file.atfx") as session:
    with ConI(
        url=session.url,       # "http://wodson.local" — no real HTTP
        auth=None,
        custom_session=session,
    ) as con:
        model = con.model_read()
        df = con.query({"AoEnvironment": {}})
        print(df)
```

### Using the ATFX_FILE context variable

Passing the file via `context_variables` mirrors the `AtfxServer` pattern,
making it easy to switch between in-process and HTTP access:

```python
from odsbox.con_i import ConI
from wodson.atfx import AtfxSession, CONTEXT_VAR_ATFX_FILE

with AtfxSession() as session:
    with ConI(
        url=session.url,
        auth=None,
        custom_session=session,
        context_variables={CONTEXT_VAR_ATFX_FILE: "path/to/file.atfx"},
        load_model=False,
    ) as con:
        model = con.model_read()
```

### Switching between AtfxSession and AtfxServer

Because the `url` + `custom_session` interface is identical to the HTTP server
pattern, you can swap in `AtfxServer` with minimal code changes:

```python
# In-process (no network)
with AtfxSession(default_file="file.atfx") as session:
    url, custom_session = session.url, session

# Over HTTP (real server)
# with AtfxServer(default_file="file.atfx") as server:
#     url, custom_session = server.url, None

with ConI(url=url, auth=None, custom_session=custom_session) as con:
    model = con.model_read()
```

---

## CLI — Command Line Interface

Start the HTTP server from the command line:

```bash
uv run wodson atfx serve --file path/to/file.atfx
```

### Options

```
usage: wodson atfx serve [-h] [--file PATH] [--host HOST] [--port PORT]
                           [--loglevel {verbose,default,quiet}]

options:
  --file PATH, -f PATH   Path to the .atfx file to serve  (optional; client can provide via context variables)
  --host HOST            Bind address  (default: 127.0.0.1)
  --port PORT, -p PORT   TCP port      (default: 8080)
  --loglevel, -l         Log verbosity: verbose (DEBUG), default (INFO),
                         quiet (WARNING)  (default: default)
```

### Examples

```bash
# Loopback, default port
uv run wodson atfx serve --file data/Example_Simple.atfx

# All interfaces, custom port
uv run wodson atfx serve --file data/Example_Simple.atfx --host 0.0.0.0 --port 9090

# Verbose logging for debugging
uv run wodson atfx serve --file data/Example_Simple.atfx --loglevel verbose
```

The server prints its URL on startup:

```
wodson server listening on http://127.0.0.1:8080
    Default ATFX file: data/Example_Simple.atfx
Press Ctrl+C to stop.
```

---

## Querying with odsbox ConI

Use [`odsbox.ConI`](https://pypi.org/project/odsbox/) to connect to the server
using the same API as any other ASAM ODS server:

```python
from odsbox.con_i import ConI
from wodson.atfx import CONTEXT_VAR_ATFX_FILE

with ConI(
    url="http://127.0.0.1:8080",
    auth=None,                                              # no auth required
    context_variables={CONTEXT_VAR_ATFX_FILE: "/path/to/file.atfx"},
    load_model=False,
) as con:
    model = con.model_read()

    # High-level JAQueL query → pandas DataFrame
    df = con.query({"AoMeasurement": {"$attributes": {"name": 1, "id": 1}}})
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

### `AtfxSession(default_file=None)`

In-process `requests.Session` transport for `odsbox.ConI`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `default_file` | `str \| None` | ATFX file used when `ATFX_FILE` context variable is omitted |

| Member | Type | Description |
|--------|------|-------------|
| `url` | `str` | Synthetic base URL for ConI (default `http://wodson.local`) |

Use this when you want ConI semantics without opening a TCP port.

---

### `AtfxFile(filepath)`

High-level convenience wrapper around `AtfxSession` + `ConI` for DataFrame-first
workflows.

| Method | Returns | Description |
|--------|---------|-------------|
| `query(jaquel_query, ...)` | `pandas.DataFrame` | Run a JAQueL query |
| `measurements(...)` | `pandas.DataFrame` | Query AoMeasurement rows |
| `groups(measurement_id, ...)` | `pandas.DataFrame` | Query AoSubmatrix rows |
| `channels(group_id, ...)` | `pandas.DataFrame` | Query AoLocalColumn rows |
| `read_channels(group_id, ...)` | `pandas.DataFrame` | Read channel value matrices |

Context manager (`with` statement) manages session lifecycle automatically.

---

### `Measurements(con_i)`

Generic query/navigation helper that operates on an existing `odsbox.ConI`
instance.

| Method | Returns | Description |
|--------|---------|-------------|
| `query(jaquel_query, ...)` | `pandas.DataFrame` | Run a JAQueL query |
| `measurements(...)` | `pandas.DataFrame` | Query AoMeasurement rows |
| `groups(measurement_id, ...)` | `pandas.DataFrame` | Query AoSubmatrix rows |
| `channels(group_id, ...)` | `pandas.DataFrame` | Query AoLocalColumn rows |
| `read_channels(group_id, ...)` | `pandas.DataFrame` | Read channel value matrices |

Import path: `from wodson.simple.measurements import Measurements`.

---

## Error Handling

HTTP error responses are returned as `ods.ErrorInfo` protobuf messages with
`Content-Type: application/x-asamods+protobuf`.

| Status | Condition |
|--------|-----------|
| 400 | Missing `ATFX_FILE` context variable, failed to load ATFX file, or invalid `SelectStatement` |
| 404 | Session ID not found, or unknown endpoint |
| 500 | Query execution error |
