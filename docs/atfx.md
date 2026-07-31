# ATFX Reader — Quick Start

The `wodson.atfx` package reads [ASAM ATFX](https://www.asam.net/standards/detail/atfx/) files
and exposes their content through the [ASAM ODS](https://www.asam.net/standards/detail/ods/)
protobuf API.

See [USAGE.md](USAGE.md) for the full API reference.

---

## Embedded library

```python
from wodson.atfx import AtfxStore
import odsbox.proto.ods_pb2 as ods

with AtfxStore("path/to/file.atfx") as store:
    model = store.model()  # ods.Model

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=model.entities["Measurement"].aid, attribute="*")
    result = store.data_read(stmt)  # ods.DataMatrices
```

## HTTP server + odsbox ConI

```python
from odsbox.con_i import ConI
from wodson.atfx import AtfxServer, CONTEXT_VAR_ATFX_FILE

with AtfxServer(host="127.0.0.1", port=8080) as server:
    with ConI(
        url=server.url,
        auth=None,
        context_variables={CONTEXT_VAR_ATFX_FILE: "path/to/file.atfx"},
        load_model=False,
    ) as con:
        model = con.model_read()
        df = con.query({"AoMeasurement": {"$attributes": {"name": 1}}})
```

## High-level DataFrame API

```python
from wodson.atfx import AtfxFile

with AtfxFile("path/to/file.atfx") as atfx:
    measurements = atfx.measurements()
    print(measurements.head())
```

## CLI

```bash
uv run wodson atfx serve --file path/to/file.atfx --host 0.0.0.0 --port 8080
```

Then connect any `odsbox.ConI` client to `http://localhost:8080` and set the
`ATFX_FILE` context variable to the file path.
