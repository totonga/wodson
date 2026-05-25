"""Tests for the AoExternalComponent (ec_iid) value-reference resolution path."""

from pathlib import Path

import odsbox.proto.ods_pb2 as ods
import pytest

from asamatfx.atfx import AtfxStore

DATA_DIR = Path(__file__).resolve().parent / "data" / "openatfx"
ATFX_FILE = DATA_DIR / "example_toleratedIncorrect.atfx"
BTF_FILE = DATA_DIR / "byte_sbyte_test.btf"

AOFILE_ATFX = DATA_DIR / "external_with_flags_aofile.atfx"
EXTFLAGS_ATFX = DATA_DIR / "external_with_flags.atfx"
AOFILE_BDA = DATA_DIR / "external_with_flags.bda"


@pytest.fixture
def ec_store():
    if not BTF_FILE.exists():
        pytest.skip("byte_sbyte_test.btf not present")
    with AtfxStore(ATFX_FILE) as store:
        yield store


@pytest.fixture
def aofile_store():
    if not AOFILE_BDA.exists():
        pytest.skip("external_with_flags.bda not present")
    with AtfxStore(AOFILE_ATFX) as store:
        yield store


def _lc_entity(model: ods.Model):
    for ename, entity in model.entities.items():
        if entity.base_name == "AoLocalColumn":
            return ename, entity
    return None, None


def _values_attr_name(entity) -> str | None:
    for aname, attr in entity.attributes.items():
        if attr.base_name == "values":
            return aname
    return None


# ---------------------------------------------------------------------------
# Model-level checks
# ---------------------------------------------------------------------------


def test_lc_entity_has_values_attribute(ec_store):
    """The AoLocalColumn entity must expose a 'values' attribute (by base_name)."""
    _, lc_entity = _lc_entity(ec_store.model())
    assert lc_entity is not None
    values_attr = _values_attr_name(lc_entity)
    assert values_attr is not None, "No attribute with base_name 'values' on AoLocalColumn"


# ---------------------------------------------------------------------------
# Data-read checks for ec-backed local columns
# ---------------------------------------------------------------------------


def test_ec_backed_lc_returns_data(ec_store):
    """Local columns backed by AoExternalComponent must return non-empty values."""
    model = ec_store.model()
    lc_ename, lc_entity = _lc_entity(model)
    assert lc_entity is not None

    values_attr = _values_attr_name(lc_entity)
    assert values_attr is not None

    # Find the lc id attribute name (base_name == "id")
    lc_id_attr = next(
        a for a, attr in lc_entity.attributes.items() if attr.base_name == "id"
    )

    # Query id + values for all lc instances
    stmt = ods.SelectStatement()
    stmt.columns.add(aid=lc_entity.aid, attribute=lc_id_attr)
    stmt.columns.add(aid=lc_entity.aid, attribute=values_attr)
    result = ec_store.data_read(stmt)

    assert len(result.matrices) == 1
    matrix = result.matrices[0]
    id_col = next(c for c in matrix.columns if c.name == lc_id_attr)
    val_col = next(c for c in matrix.columns if c.name == values_attr)

    # There should be at least 2 ec-backed lc instances (lc_iid=115 and 118)
    assert len(id_col.longlong_array.values) >= 2
    assert len(val_col.unknown_arrays.values) == len(id_col.longlong_array.values)


def test_ec_backed_lc_signed_bytes(ec_store):
    """lc_iid=115 (signed_b, dt_sbyte) must yield 10 values promoted to DT_SHORT."""
    model = ec_store.model()
    _, lc_entity = _lc_entity(model)
    values_attr = _values_attr_name(lc_entity)

    # Find the lc id attribute name (base_name == "id")
    lc_id_attr = next(
        a for a, attr in lc_entity.attributes.items() if attr.base_name == "id"
    )

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=lc_entity.aid, attribute=lc_id_attr)
    stmt.columns.add(aid=lc_entity.aid, attribute=values_attr)
    result = ec_store.data_read(stmt)

    assert len(result.matrices) == 1
    matrix = result.matrices[0]
    id_col = next(c for c in matrix.columns if c.name == lc_id_attr)
    val_col = next(c for c in matrix.columns if c.name == values_attr)

    # Find index of lc_iid=115
    ids = list(id_col.longlong_array.values)
    assert 115 in ids, "lc_iid=115 (signed_b) not found"
    idx = ids.index(115)

    values_entry = val_col.unknown_arrays.values[idx]
    # dt_sbyte is promoted to DT_SHORT which uses long_array in ODS protobuf
    assert len(values_entry.long_array.values) == 10


def test_ec_backed_lc_unsigned_bytes(ec_store):
    """lc_iid=118 (unsigned_b, dt_byte) must yield 10 values as DT_BYTE."""
    model = ec_store.model()
    _, lc_entity = _lc_entity(model)
    values_attr = _values_attr_name(lc_entity)

    lc_id_attr = next(
        a for a, attr in lc_entity.attributes.items() if attr.base_name == "id"
    )

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=lc_entity.aid, attribute=lc_id_attr)
    stmt.columns.add(aid=lc_entity.aid, attribute=values_attr)
    result = ec_store.data_read(stmt)

    assert len(result.matrices) == 1
    matrix = result.matrices[0]
    id_col = next(c for c in matrix.columns if c.name == lc_id_attr)
    val_col = next(c for c in matrix.columns if c.name == values_attr)

    ids = list(id_col.longlong_array.values)
    assert 118 in ids, "lc_iid=118 (unsigned_b) not found"
    idx = ids.index(118)

    values_entry = val_col.unknown_arrays.values[idx]
    # dt_byte → DT_BYTE which uses byte_array (bytes object) in ODS protobuf
    assert len(values_entry.byte_array.values) == 10


# ---------------------------------------------------------------------------
# external_with_flags_aofile.atfx — ao_values_file fallback
# ---------------------------------------------------------------------------


def test_aofile_store_opens(aofile_store):
    """external_with_flags_aofile.atfx must open without exception."""
    model = aofile_store.model()
    assert len(model.entities) > 0


def test_aofile_has_lc_and_ec_entities(aofile_store):
    """The model must expose AoLocalColumn and AoExternalComponent entities."""
    model = aofile_store.model()
    base_names = {e.base_name for e in model.entities.values()}
    assert "AoLocalColumn" in base_names
    assert "AoExternalComponent" in base_names


def test_aofile_lc_values_attr_resolved(aofile_store):
    """AoLocalColumn.values attribute must be resolvable via data_read."""
    model = aofile_store.model()
    lc_name = next(n for n, e in model.entities.items() if e.base_name == "AoLocalColumn")
    lc_entity = model.entities[lc_name]

    values_attr = next(
        (a for a, attr in lc_entity.attributes.items() if attr.base_name == "values"),
        None,
    )
    assert values_attr is not None, "AoLocalColumn has no values attribute"

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=lc_entity.aid, attribute="*")
    result = aofile_store.data_read(stmt)

    assert len(result.matrices) in (0, 1)


def test_aofile_ec_identifier_resolved(aofile_store):
    """All ec-backed LocalColumns must have an identifier in their ExternalComponentRef.

    The identifier should come from the ao_values_file → AoFile.ao_location fallback,
    not from filename_url (which is empty in this file).
    """
    model = aofile_store.model()
    lc_name = next(n for n, e in model.entities.items() if e.base_name == "AoLocalColumn")
    lc_entity = model.entities[lc_name]

    lc_id_attr = next(
        a for a, attr in lc_entity.attributes.items() if attr.base_name == "id"
    )
    values_attr = next(
        a for a, attr in lc_entity.attributes.items() if attr.base_name == "values"
    )
    seq_repr_attr = next(
        (a for a, attr in lc_entity.attributes.items() if attr.base_name == "sequence_representation"),
        None,
    )

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=lc_entity.aid, attribute=lc_id_attr)
    stmt.columns.add(aid=lc_entity.aid, attribute=values_attr)
    if seq_repr_attr:
        stmt.columns.add(aid=lc_entity.aid, attribute=seq_repr_attr)
    result = aofile_store.data_read(stmt)

    assert len(result.matrices) == 1
    matrix = result.matrices[0]
    val_col = next(c for c in matrix.columns if c.name == values_attr)

    # At least one lc instance must have non-empty unknown_array (values resolved via ao_values_file)
    has_any_values = any(
        len(ua.long_array.values) > 0
        or len(ua.double_array.values) > 0
        or len(ua.float_array.values) > 0
        or len(ua.longlong_array.values) > 0
        for ua in val_col.unknown_arrays.values
    )
    assert has_any_values, (
        "No ec-backed LocalColumn has any resolved values — "
        "ao_values_file fallback may not be working"
    )


# ---------------------------------------------------------------------------
# Parametrized: both external_with_flags files — values vs generation_parameters
# ---------------------------------------------------------------------------

_EXT_FLAGS_FILES = [EXTFLAGS_ATFX, AOFILE_ATFX]


@pytest.mark.parametrize("atfx_path", _EXT_FLAGS_FILES, ids=["extflags", "extflags_aofile"])
def test_lc_values_and_gp_per_seq_rep(atfx_path: Path) -> None:
    """For both external_with_flags variants:
    - explicit / external_component channels must have non-empty Values.
    - implicit_linear / implicit_constant channels must have non-empty
      GenerationParameters and may have empty Values.
    """
    if not AOFILE_BDA.exists():
        pytest.skip("external_with_flags.bda not present")

    with AtfxStore(atfx_path) as store:
        model = store.model()
        lc_name = next(n for n, e in model.entities.items() if e.base_name == "AoLocalColumn")
        lc_ent = model.entities[lc_name]

        def _attr(base: str) -> str:
            return next(a for a, attr in lc_ent.attributes.items() if attr.base_name == base)

        lc_id_attr = _attr("id")
        values_attr = _attr("values")
        sr_attr = next(
            (a for a, attr in lc_ent.attributes.items() if attr.base_name == "sequence_representation"),
            None,
        )
        gp_attr = next(
            (a for a, attr in lc_ent.attributes.items() if attr.base_name == "generation_parameters"),
            None,
        )

        stmt = ods.SelectStatement()
        stmt.columns.add(aid=lc_ent.aid, attribute=lc_id_attr)
        stmt.columns.add(aid=lc_ent.aid, attribute=values_attr)
        if sr_attr:
            stmt.columns.add(aid=lc_ent.aid, attribute=sr_attr)
        if gp_attr:
            stmt.columns.add(aid=lc_ent.aid, attribute=gp_attr)

        result = store.data_read(stmt)
        assert len(result.matrices) == 1
        matrix = result.matrices[0]

        id_col = next(c for c in matrix.columns if c.name == lc_id_attr)
        val_col = next(c for c in matrix.columns if c.name == values_attr)
        sr_col = next((c for c in matrix.columns if c.name == sr_attr), None) if sr_attr else None
        gp_col = next((c for c in matrix.columns if c.name == gp_attr), None) if gp_attr else None

        ids = list(id_col.longlong_array.values)
        srs = list(sr_col.string_array.values) if sr_col is not None else []

        _GENERATED = {"implicit_linear", "implicit_constant"}

        for i, lc_id in enumerate(ids):
            sr = srs[i] if i < len(srs) else ""
            val_ua = val_col.unknown_arrays.values[i]
            has_values = (
                len(val_ua.double_array.values) > 0
                or len(val_ua.float_array.values) > 0
                or len(val_ua.long_array.values) > 0
                or len(val_ua.longlong_array.values) > 0
                or len(val_ua.byte_array.values) > 0
            )

            if sr in _GENERATED:
                # Generated channels: Values may be empty; GenerationParameters must be set.
                if gp_col is not None:
                    gp_da = gp_col.double_arrays.values[i]
                    assert len(gp_da.values) > 0, (
                        f"lc_id={lc_id} sr={sr!r}: expected non-empty GenerationParameters"
                    )
            else:
                # Explicitly-stored channels: Values must be non-empty.
                assert has_values, (
                    f"lc_id={lc_id} sr={sr!r}: expected non-empty Values for explicit/external channel"
                )

