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
from typing import Any

import odsbox.proto.ods_pb2 as ods
import requests

from wodson.atfx import CONTEXT_VAR_ATFX_FILE, AtfxServer, AtfxSession, AtfxStore

_DEFAULT_FILE = Path(__file__).parent.parent / "tests" / "data" / "openatfx" / "asam600" / "Example_Simple.atfx"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_id_attr_name(entity: ods.Model.Entity) -> str | None:
    """Return the application attribute name whose base_name is 'id'."""
    for aname, attr in entity.attributes.items():
        if attr.base_name == "id":
            return aname
    return None


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


def _make_where_id_stmt(
    entity: ods.Model.Entity,
    id_val: int,
    *attr_names: str,
) -> ods.SelectStatement:
    """Build SELECT <attr_names> FROM entity WHERE id_attr = id_val.

    Pass a single ``"*"`` as *attr_names* for SELECT *.
    """
    id_attr = _find_id_attr_name(entity) or "Id"
    stmt = ods.SelectStatement()
    for attr in attr_names:
        col = stmt.columns.add()
        col.aid = entity.aid
        col.attribute = attr
    cond_item = stmt.where.add()
    cond = cond_item.condition
    cond.aid = entity.aid
    cond.attribute = id_attr
    cond.operator = ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_EQ
    cond.longlong_array.values.append(id_val)
    return stmt


def _make_where_rel_stmt(
    entity: ods.Model.Entity,
    rel_name: str,
    parent_id: int,
    *attr_names: str,
) -> ods.SelectStatement:
    """Build SELECT <attr_names> FROM entity WHERE rel_name = parent_id."""
    stmt = ods.SelectStatement()
    for attr in attr_names:
        col = stmt.columns.add()
        col.aid = entity.aid
        col.attribute = attr
    cond_item = stmt.where.add()
    cond = cond_item.condition
    cond.aid = entity.aid
    cond.attribute = rel_name
    cond.operator = ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_EQ
    cond.longlong_array.values.append(parent_id)
    return stmt


def _find_child_relations(
    model: ods.Model,
    parent_entity: ods.Model.Entity,
) -> list[tuple[ods.Model.Entity, str]]:
    """Return (child_entity, rel_name) for entities with a to-one FK pointing to parent_entity."""
    result: list[tuple[ods.Model.Entity, str]] = []
    for ename in model.entities:
        child = model.entities[ename]
        for rname, rel in child.relations.items():
            if rel.entity_name == parent_entity.name and rel.range_max == 1:
                result.append((child, rname))
    return result


def _find_child_example(
    model: ods.Model,
    store: AtfxStore,
) -> tuple[ods.Model.Entity, int, ods.Model.Entity, str] | None:
    """Find (parent_entity, parent_id, child_entity, rel_name) for a populated FK relation."""
    for ename in model.entities:
        parent = model.entities[ename]
        child_rels = _find_child_relations(model, parent)
        if not child_rels:
            continue
        id_attr = _find_id_attr_name(parent) or "Id"
        s = ods.SelectStatement()
        s_col = s.columns.add()
        s_col.aid = parent.aid
        s_col.attribute = "*"
        dm = store.data_read(s)
        for matrix in dm.matrices:
            for data_col in matrix.columns:
                if data_col.name == id_attr and data_col.longlong_array.values:
                    parent_id = data_col.longlong_array.values[0]
                    child_entity, rel_name = child_rels[0]
                    return parent, parent_id, child_entity, rel_name
    return None


def _time(label: str, fn: Any, *args: Any, iterations: int = 1, **kwargs: Any) -> Any:
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
    _time("store.data_read(simple SELECT *)", store.data_read, stmt, iterations=iterations)

    # Pick the first entity that has an id attribute; use its real id value.
    target_entity: ods.Model.Entity | None = None
    target_id: int = 0
    for ename in model.entities:
        entity = model.entities[ename]
        if _find_id_attr_name(entity) is not None:
            # Read all rows to find a real id value.
            s = ods.SelectStatement()
            col = s.columns.add()
            col.aid = entity.aid
            col.attribute = "*"
            dm = store.data_read(s)
            for matrix in dm.matrices:
                for column in matrix.columns:
                    id_name = _find_id_attr_name(entity) or "Id"
                    if column.name == id_name and column.longlong_array.values:
                        target_entity = entity
                        target_id = column.longlong_array.values[0]
                        break
                if target_entity is not None:
                    break
        if target_entity is not None:
            break

    if target_entity is not None:
        id_attr = _find_id_attr_name(target_entity) or "Id"
        # Find a second attribute name (e.g. Name) if available
        second_attr: str | None = None
        for aname in target_entity.attributes:
            if aname != id_attr:
                second_attr = aname
                break

        stmt_star = _make_where_id_stmt(target_entity, target_id, "*")
        _time(
            f"store.data_read(SELECT * WHERE {id_attr}={target_id})",
            store.data_read,
            stmt_star,
            iterations=iterations,
        )

        if second_attr is not None:
            stmt_cols = _make_where_id_stmt(target_entity, target_id, id_attr, second_attr)
            _time(
                f"store.data_read(SELECT {id_attr},{second_attr} WHERE {id_attr}={target_id})",
                store.data_read,
                stmt_cols,
                iterations=iterations,
            )

    # Children via relation filter (WHERE rel_col = parent_id) — independent discovery
    child_example = _find_child_example(model, store)
    if child_example is not None:
        _, parent_id_c, child_entity, rel_name = child_example
        id_attr_c = _find_id_attr_name(child_entity) or "Id"
        second_attr_c: str | None = None
        for aname in child_entity.attributes:
            if aname != id_attr_c:
                second_attr_c = aname
                break
        stmt_children = _make_where_rel_stmt(child_entity, rel_name, parent_id_c, "*")
        _time(
            f"store.data_read(SELECT * WHERE {rel_name}={parent_id_c} [children])",
            store.data_read,
            stmt_children,
            iterations=iterations,
        )
        if second_attr_c is not None:
            stmt_children_cols = _make_where_rel_stmt(child_entity, rel_name, parent_id_c, id_attr_c, second_attr_c)
            _time(
                f"store.data_read(SELECT {id_attr_c},{second_attr_c} WHERE {rel_name}={parent_id_c})",
                store.data_read,
                stmt_children_cols,
                iterations=iterations,
            )

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
                headers={"Content-Type": "application/x-asamods+protobuf", "Accept": "application/x-asamods+protobuf"},
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
                headers={"Content-Type": "application/x-asamods+protobuf", "Accept": "application/x-asamods+protobuf"},
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

    # Build all three statement variants ---
    stmt_simple = _make_data_read_stmt(model)

    # Find entity + first id value for WHERE variants
    where_entity: ods.Model.Entity | None = None
    where_id: int = 0
    for ename in model.entities:
        entity = model.entities[ename]
        if _find_id_attr_name(entity) is None:
            continue
        s = ods.SelectStatement()
        col = s.columns.add()
        col.aid = entity.aid
        col.attribute = "*"
        dm = store.data_read(s)
        for matrix in dm.matrices:
            for column in matrix.columns:
                id_name = _find_id_attr_name(entity) or "Id"
                if column.name == id_name and column.longlong_array.values:
                    where_entity = entity
                    where_id = column.longlong_array.values[0]
                    break
            if where_entity is not None:
                break
        if where_entity is not None:
            break

    def _cprofile_run(label: str, stmts: list[ods.SelectStatement]) -> None:
        pr = cProfile.Profile()
        pr.enable()
        for _ in range(iterations):
            for s in stmts:
                store.data_read(s)
        pr.disable()
        stream = io.StringIO()
        ps = pstats.Stats(pr, stream=stream)
        ps.sort_stats("cumulative")
        ps.print_stats(20)
        print(f"--- {label} ---")
        print(stream.getvalue())

    _cprofile_run("SELECT * (no WHERE)", [stmt_simple])

    if where_entity is not None:
        id_attr = _find_id_attr_name(where_entity) or "Id"
        second_attr: str | None = None
        for aname in where_entity.attributes:
            if aname != id_attr:
                second_attr = aname
                break

        stmt_star_where = _make_where_id_stmt(where_entity, where_id, "*")
        _cprofile_run(f"SELECT * WHERE {id_attr}={where_id}", [stmt_star_where])

        if second_attr is not None:
            stmt_cols_where = _make_where_id_stmt(where_entity, where_id, id_attr, second_attr)
            _cprofile_run(
                f"SELECT {id_attr},{second_attr} WHERE {id_attr}={where_id}",
                [stmt_cols_where],
            )

    # Children by relation filter — independent discovery
    child_example_p4 = _find_child_example(model, store)
    if child_example_p4 is not None:
        _, parent_id_p4, child_entity_p4, rel_name_p4 = child_example_p4
        id_attr_p4 = _find_id_attr_name(child_entity_p4) or "Id"
        second_attr_p4: str | None = None
        for aname_p4 in child_entity_p4.attributes:
            if aname_p4 != id_attr_p4:
                second_attr_p4 = aname_p4
                break
        stmt_rel = _make_where_rel_stmt(child_entity_p4, rel_name_p4, parent_id_p4, "*")
        _cprofile_run(
            f"SELECT * WHERE {rel_name_p4}={parent_id_p4} [children]",
            [stmt_rel],
        )
        if second_attr_p4 is not None:
            stmt_rel_cols = _make_where_rel_stmt(child_entity_p4, rel_name_p4, parent_id_p4, id_attr_p4, second_attr_p4)
            _cprofile_run(
                f"SELECT {id_attr_p4},{second_attr_p4} WHERE {rel_name_p4}={parent_id_p4} [children]",
                [stmt_rel_cols],
            )

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
# Phase 6: full tree traversal
# ---------------------------------------------------------------------------


def _find_root_entity(model: ods.Model) -> ods.Model.Entity | None:
    """Find an entity that is a root in the hierarchy (no outgoing to-one FK, most incoming)."""
    incoming_count: dict[str, int] = {}
    for ename in model.entities:
        entity = model.entities[ename]
        for rel in entity.relations.values():
            if rel.range_max == 1 and rel.entity_name:
                incoming_count[rel.entity_name] = incoming_count.get(rel.entity_name, 0) + 1

    best: ods.Model.Entity | None = None
    best_count = -1
    for ename in model.entities:
        entity = model.entities[ename]
        if any(rel.range_max == 1 for rel in entity.relations.values()):
            continue  # has a parent FK — not a root
        count = incoming_count.get(ename, 0)
        if count > best_count:
            best_count = count
            best = entity
    return best


def _collect_traversal_stmts(
    store: AtfxStore,
    model: ods.Model,
    entity: ods.Model.Entity,
    parent_rel: str | None,
    parent_id: int | None,
    max_depth: int,
    depth: int = 0,
) -> list[ods.SelectStatement]:
    """Recursively collect query statements that simulate a tree traversal."""
    if depth >= max_depth:
        return []

    stmts: list[ods.SelectStatement] = []
    id_attr = _find_id_attr_name(entity) or "Id"

    if parent_rel is not None and parent_id is not None:
        list_stmt = _make_where_rel_stmt(entity, parent_rel, parent_id, "*")
    else:
        list_stmt = ods.SelectStatement()
        list_col = list_stmt.columns.add()
        list_col.aid = entity.aid
        list_col.attribute = "*"
    stmts.append(list_stmt)

    # Execute once to discover the actual instance ids
    dm = store.data_read(list_stmt)
    instance_ids: list[int] = []
    for matrix in dm.matrices:
        for data_col in matrix.columns:
            if data_col.name == id_attr:
                instance_ids.extend(data_col.longlong_array.values)

    if not instance_ids:
        return stmts

    first_id = instance_ids[0]
    stmts.append(_make_where_id_stmt(entity, first_id, "*"))

    for child_entity, rel_name in _find_child_relations(model, entity):
        stmts.extend(_collect_traversal_stmts(store, model, child_entity, rel_name, first_id, max_depth, depth + 1))

    return stmts


def profile_traversal(file_path: Path, iterations: int) -> None:
    print(f"\n=== Phase 6: Full tree traversal ({iterations}x) ===")
    store = AtfxStore(file_path)
    model = store.model()

    root = _find_root_entity(model)
    if root is None:
        print("  No root entity found, skipping")
        store.close()
        return

    print(f"  Root entity: {root.name}")
    traversal_stmts = _collect_traversal_stmts(store, model, root, None, None, max_depth=6)
    print(f"  Traversal steps: {len(traversal_stmts)} queries")

    def run_traversal() -> None:
        for stmt in traversal_stmts:
            store.data_read(stmt)

    _time(
        f"Full traversal ({len(traversal_stmts)} queries each)",
        run_traversal,
        iterations=iterations,
    )

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
    profile_traversal(file_path, args.iterations)


if __name__ == "__main__":
    main()
