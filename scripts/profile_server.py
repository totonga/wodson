"""Profile AtfxStore and HTTP server performance.

Run with:
    uv run python scripts/profile_server.py [--file PATH] [--iterations N]

Output: sorted cProfile stats + per-phase timing breakdown.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import time
from pathlib import Path

import odsbox.proto.ods_pb2 as ods
import requests
from google.protobuf import json_format

from wodson.atfx import CONTEXT_VAR_ATFX_FILE, AtfxServer, AtfxSession, AtfxStore

_DEFAULT_FILE = (
    Path(__file__).parent.parent
    / "tests"
    / "data"
    / "openatfx"
    / "asam600"
    / "Example_Simple.atfx"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_data_read_stmt(model: ods.Model) -> ods.SelectStatement:
    """Build a simple SELECT * on the first entity that has instances."""
    stmt = ods.SelectStatement()
    for ename in model.entities:
        entity = model.entities[ename]
        col = stmt.columns.add()
        col.aid = entity.aid
        col.attribute = "*"
        break
    return stmt


def _time(label: str, fn, *args, iterations: int = 1, **kwargs):  # type: ignore[no-untyped-def]
    """Run *fn* *iterations* times and report min / avg ms."""
    times: list[float] = []
    result = None
    for _ in range(iterations):
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        times.append((time.perf_counter() - t0) * 1000)
    avg = sum(times) / len(times)
    mn = min(times)
    print(f"  {label:40s}  min={mn:7.1f} ms  avg={avg:7.1f} ms  ({iterations} iter)")
    return result


# ---------------------------------------------------------------------------
# Phase 1: in-process store (no HTTP)
# ---------------------------------------------------------------------------


def profile_store(file_path: Path, iterations: int) -> None:
    print("\n=== Phase 1: AtfxStore (in-process) ===")
    store = _time("AtfxStore.__init__", AtfxStore, file_path)
    assert store is not None

    model = _time("store.model()", store.model, iterations=iterations)
    assert model is not None

    stmt = _make_data_read_stmt(model)
    _time("store.data_read(simple)", store.data_read, stmt, iterations=iterations)

    store.close()


# ---------------------------------------------------------------------------
# Phase 2: AtfxSession (in-process adapter, no TCP)
# ---------------------------------------------------------------------------


def profile_session(file_path: Path, iterations: int) -> None:
    print("\n=== Phase 2: AtfxSession (in-process adapter via ConI, reused) ===")
    from odsbox.con_i import ConI

    session = AtfxSession(default_file=str(file_path))

    # Each ConI open creates a new AtfxStore (parses ATFX) — measure that cost
    def single_connect_and_model_read() -> ods.Model:
        with ConI(url=session.url, custom_session=session, load_model=False) as con:
            return con.model_read()

    _time("ConI open+model_read (new store/call)", single_connect_and_model_read, iterations=5)

    # Reuse a single ConI session across many queries — this is the real perf case
    with ConI(url=session.url, custom_session=session, load_model=False) as con:
        model = _time("model_read() (reused ConI)", con.model_read, iterations=iterations)
        assert model is not None

        stmt = _make_data_read_stmt(model)
        _time("data_read() (reused ConI)", con.data_read, stmt, iterations=iterations)

    session.close()


# ---------------------------------------------------------------------------
# Phase 3: HTTP round-trip
# ---------------------------------------------------------------------------


def profile_http(file_path: Path, iterations: int) -> None:
    print("\n=== Phase 3: HTTP round-trip ===")

    with AtfxServer() as server:
        # Connect (parses ATFX file + builds SQLite)
        ctx = ods.ContextVariables()
        ctx.variables[CONTEXT_VAR_ATFX_FILE].string_array.values.append(str(file_path))

        def connect() -> str:
            resp = requests.post(
                f"{server.url}/ods",
                data=ctx.SerializeToString(),
                headers={"Content-Type": "application/x-asamods+protobuf"},
                timeout=30,
            )
            assert resp.status_code == 201, f"connect failed: {resp.status_code}"
            return resp.headers["Location"]

        session_url = _time("HTTP connect (parse+load, cold)", connect)
        assert session_url is not None

        # Warm reconnect – same file, store now cached
        session_url2 = _time("HTTP connect (cached, warm)", connect, iterations=iterations)

        # model-read
        def model_read() -> ods.Model:
            resp = requests.post(
                f"{session_url}/model-read",
                headers={"Content-Type": "application/x-asamods+protobuf",
                         "Accept": "application/x-asamods+protobuf"},
                timeout=10,
            )
            assert resp.status_code == 200
            m = ods.Model()
            m.ParseFromString(resp.content)
            return m

        model = _time("HTTP model-read (incl. proto serialize)", model_read, iterations=iterations)
        assert model is not None

        # data-read
        stmt = _make_data_read_stmt(model)
        stmt_bytes = stmt.SerializeToString()

        def data_read() -> None:
            resp = requests.post(
                f"{session_url}/data-read",
                data=stmt_bytes,
                headers={"Content-Type": "application/x-asamods+protobuf",
                         "Accept": "application/x-asamods+protobuf"},
                timeout=10,
            )
            assert resp.status_code == 200

        _time("HTTP data-read (simple SELECT *)", data_read, iterations=iterations)

        # Cleanup
        requests.delete(session_url, timeout=5)
        if session_url2:
            requests.delete(session_url2, timeout=5)


# ---------------------------------------------------------------------------
# Phase 4: cProfile deep-dive on data_read hot path
# ---------------------------------------------------------------------------


def profile_cprofile(file_path: Path, iterations: int) -> None:
    print(f"\n=== Phase 4: cProfile deep-dive (data_read x{iterations}) ===")
    store = AtfxStore(file_path)
    model = store.model()
    stmt = _make_data_read_stmt(model)

    pr = cProfile.Profile()
    pr.enable()
    for _ in range(iterations):
        store.data_read(stmt)
    pr.disable()

    stream = io.StringIO()
    ps = pstats.Stats(pr, stream=stream)
    ps.sort_stats("cumulative")
    ps.print_stats(30)
    print(stream.getvalue())

    store.close()


def profile_cprofile_model(file_path: Path, iterations: int) -> None:
    print(f"\n=== Phase 5: cProfile deep-dive (model serialization x{iterations}) ===")
    store = AtfxStore(file_path)
    model = store.model()

    pr = cProfile.Profile()
    pr.enable()
    for _ in range(iterations):
        model.SerializeToString()
    pr.disable()

    stream = io.StringIO()
    ps = pstats.Stats(pr, stream=stream)
    ps.sort_stats("cumulative")
    ps.print_stats(20)
    print(stream.getvalue())

    store.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile AtfxStore / server performance")
    parser.add_argument("--file", type=Path, default=_DEFAULT_FILE, help="ATFX file to load")
    parser.add_argument("--iterations", type=int, default=20, help="Repetitions for timing loops")
    args = parser.parse_args()

    file_path: Path = args.file.resolve()
    if not file_path.exists():
        print(f"ERROR: file not found: {file_path}")
        raise SystemExit(1)

    print(f"Profiling with: {file_path}")
    print(f"Iterations: {args.iterations}")

    profile_store(file_path, args.iterations)
    profile_session(file_path, args.iterations)
    profile_http(file_path, args.iterations)
    profile_cprofile(file_path, args.iterations)
    profile_cprofile_model(file_path, args.iterations)


if __name__ == "__main__":
    main()
