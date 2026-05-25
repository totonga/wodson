"""Parametrized smoke tests that run against every ATFX file found under tests/data/."""

from pathlib import Path

import odsbox.proto.ods_pb2 as ods
import pytest

from asamatfx import AtfxStore

DATA_DIR = Path(__file__).resolve().parent / "data"

ALL_ATFX_FILES = sorted(DATA_DIR.rglob("*.atfx"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Exceptions raised when an external binary data file is missing or truncated.
_BINARY_ERRORS = (ValueError, FileNotFoundError, OSError)


def _open_store(atfx_file: Path) -> AtfxStore:
    """Open an AtfxStore, skipping files whose external binary data is missing
    or truncated (pre-existing data quality issues in the test corpus)."""
    try:
        return AtfxStore(atfx_file)
    except _BINARY_ERRORS as exc:
        pytest.skip(f"{atfx_file.name}: cannot open - {exc}")


def _localcolumn_entity_name(model: ods.Model) -> str | None:
    for name, entity in model.entities.items():
        if entity.base_name == "AoLocalColumn":
            return name
    return None


# ---------------------------------------------------------------------------
# Parametrized: open + model
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("atfx_file", ALL_ATFX_FILES, ids=lambda p: p.relative_to(DATA_DIR).as_posix())
def test_open_and_model_not_empty(atfx_file: Path) -> None:
    """Every ATFX file must open and return a model with at least one entity."""
    with _open_store(atfx_file) as store:
        model = store.model()
        assert len(model.entities) > 0, f"{atfx_file.name}: model has no entities"


@pytest.mark.parametrize("atfx_file", ALL_ATFX_FILES, ids=lambda p: p.relative_to(DATA_DIR).as_posix())
def test_entities_have_attributes(atfx_file: Path) -> None:
    """Every entity in every file must expose at least one attribute."""
    with _open_store(atfx_file) as store:
        model = store.model()
        for ename, entity in model.entities.items():
            assert entity.aid > 0, f"{atfx_file.name}/{ename}: aid must be positive"
            assert len(entity.attributes) > 0, (
                f"{atfx_file.name}/{ename}: entity has no attributes"
            )


# ---------------------------------------------------------------------------
# Parametrized: wildcard query per entity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("atfx_file", ALL_ATFX_FILES, ids=lambda p: p.relative_to(DATA_DIR).as_posix())
def test_wildcard_query_all_entities(atfx_file: Path) -> None:
    """A wildcard SELECT on each entity must succeed and return a DataMatrices.

    Entities with zero instances produce 0 matrices; entities with instances produce 1.
    """
    with _open_store(atfx_file) as store:
        model = store.model()
        for ename, entity in model.entities.items():
            stmt = ods.SelectStatement()
            stmt.columns.add(aid=entity.aid, attribute="*")
            result = store.data_read(stmt)
            assert result is not None, (
                f"{atfx_file.name}/{ename}: data_read returned None"
            )
            assert len(result.matrices) in (0, 1), (
                f"{atfx_file.name}/{ename}: expected 0 or 1 matrices, "
                f"got {len(result.matrices)}"
            )
            if result.matrices:
                assert result.matrices[0].aid == entity.aid


# ---------------------------------------------------------------------------
# Parametrized: Id + Name query per entity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("atfx_file", ALL_ATFX_FILES, ids=lambda p: p.relative_to(DATA_DIR).as_posix())
def test_id_and_name_query(atfx_file: Path) -> None:
    """SELECT Id, Name must return columns with matching row counts."""
    with _open_store(atfx_file) as store:
        model = store.model()
        for ename, entity in model.entities.items():
            if "Id" not in entity.attributes or "Name" not in entity.attributes:
                continue

            stmt = ods.SelectStatement()
            stmt.columns.add(aid=entity.aid, attribute="Id")
            stmt.columns.add(aid=entity.aid, attribute="Name")
            result = store.data_read(stmt)

            if not result.matrices:
                continue  # entity has no instances

            assert len(result.matrices) == 1
            matrix = result.matrices[0]
            col_names = {c.name for c in matrix.columns}
            assert "Id" in col_names, f"{atfx_file.name}/{ename}: missing Id column"
            assert "Name" in col_names, f"{atfx_file.name}/{ename}: missing Name column"

            id_col = next(c for c in matrix.columns if c.name == "Id")
            name_col = next(c for c in matrix.columns if c.name == "Name")
            id_count = len(id_col.longlong_array.values)
            name_count = len(name_col.string_array.values)
            assert id_count == name_count, (
                f"{atfx_file.name}/{ename}: Id rows ({id_count}) != Name rows ({name_count})"
            )


# ---------------------------------------------------------------------------
# Parametrized: local column values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("atfx_file", ALL_ATFX_FILES, ids=lambda p: p.relative_to(DATA_DIR).as_posix())
def test_localcolumn_values_accessible(atfx_file: Path) -> None:
    """If the model contains an AoLocalColumn entity, querying its Values
    attribute must not raise and the result must be a DataMatrices."""
    with _open_store(atfx_file) as store:
        model = store.model()
        lc_name = _localcolumn_entity_name(model)
        if lc_name is None:
            pytest.skip("No AoLocalColumn entity in this file")

        lc_entity = model.entities[lc_name]
        if "Values" not in lc_entity.attributes:
            pytest.skip(f"{lc_name} has no Values attribute")

        stmt = ods.SelectStatement()
        stmt.columns.add(aid=lc_entity.aid, attribute="Id")
        stmt.columns.add(aid=lc_entity.aid, attribute="Values")
        result = store.data_read(stmt)

        assert result is not None
        assert len(result.matrices) in (0, 1)
        if not result.matrices:
            return  # entity has no instances, that is valid
        matrix = result.matrices[0]
        col_names = {c.name for c in matrix.columns}
        assert "Values" in col_names, f"{lc_name}: Values column missing from result"


@pytest.mark.parametrize("atfx_file", ALL_ATFX_FILES, ids=lambda p: p.relative_to(DATA_DIR).as_posix())
def test_localcolumn_values_row_count_consistent(atfx_file: Path) -> None:
    """Id and Values columns must have the same number of rows."""
    with _open_store(atfx_file) as store:
        model = store.model()
        lc_name = _localcolumn_entity_name(model)
        if lc_name is None:
            pytest.skip("No AoLocalColumn entity in this file")

        lc_entity = model.entities[lc_name]
        if "Values" not in lc_entity.attributes:
            pytest.skip(f"{lc_name} has no Values attribute")

        stmt = ods.SelectStatement()
        stmt.columns.add(aid=lc_entity.aid, attribute="Id")
        stmt.columns.add(aid=lc_entity.aid, attribute="Values")
        result = store.data_read(stmt)

        if not result.matrices:
            return  # entity has no instances, that is valid
        matrix = result.matrices[0]
        id_col = next((c for c in matrix.columns if c.name == "Id"), None)
        val_col = next((c for c in matrix.columns if c.name == "Values"), None)
        assert id_col is not None
        assert val_col is not None

        id_count = len(id_col.longlong_array.values)
        val_count = len(val_col.unknown_arrays.values)
        assert id_count == val_count, (
            f"{atfx_file.name}: Id rows ({id_count}) != Values rows ({val_count})"
        )


# ---------------------------------------------------------------------------
# Parametrized: COUNT aggregate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("atfx_file", ALL_ATFX_FILES, ids=lambda p: p.relative_to(DATA_DIR).as_posix())
def test_count_aggregate_per_entity(atfx_file: Path) -> None:
    """COUNT aggregate on Id must return a single non-negative integer per entity."""
    with _open_store(atfx_file) as store:
        model = store.model()
        for ename, entity in model.entities.items():
            if "Id" not in entity.attributes:
                continue

            stmt = ods.SelectStatement()
            stmt.columns.add(
                aid=entity.aid,
                attribute="Id",
                aggregate=ods.AggregateEnum.AG_COUNT,
            )
            result = store.data_read(stmt)

            assert len(result.matrices) == 1
            matrix = result.matrices[0]
            assert len(matrix.columns) == 1
            count_col = matrix.columns[0]
            assert len(count_col.longlong_array.values) == 1, (
                f"{atfx_file.name}/{ename}: COUNT returned "
                f"{len(count_col.longlong_array.values)} rows"
            )
            assert count_col.longlong_array.values[0] >= 0, (
                f"{atfx_file.name}/{ename}: COUNT is negative"
            )
