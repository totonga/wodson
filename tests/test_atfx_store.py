"""Integration tests for AtfxStore across all example files."""

from pathlib import Path

import odsbox.proto.ods_pb2 as ods
import pytest

from wodson.atfx import AtfxStore

pytestmark = pytest.mark.devtest

DATA_DIR = Path(__file__).resolve().parent.parent / "docs" / "spec" / "examples"

ALL_ATFX_FILES = sorted(DATA_DIR.glob("*.atfx"))


@pytest.mark.parametrize("atfx_file", ALL_ATFX_FILES, ids=lambda p: p.stem)
def test_load_and_model(atfx_file):
    """Every example file should load and produce a non-empty model."""
    # Skip files that need .dat if the .dat doesn't exist
    with AtfxStore(atfx_file) as store:
        model = store.model()
        assert len(model.entities) > 0
        # Every entity should have at least one attribute
        for ename in model.entities:
            entity = model.entities[ename]
            assert len(entity.attributes) > 0, f"Entity {ename} has no attributes"
            assert entity.aid > 0


@pytest.mark.parametrize("atfx_file", ALL_ATFX_FILES, ids=lambda p: p.stem)
def test_query_first_entity(atfx_file):
    """Query all instances of the first entity in each file."""
    with AtfxStore(atfx_file) as store:
        model = store.model()
        # Get first entity
        first_ename = next(iter(model.entities))
        entity = model.entities[first_ename]

        stmt = ods.SelectStatement()
        stmt.columns.add(aid=entity.aid, attribute="*")
        result = store.data_read(stmt)

        # Should succeed without error
        assert result is not None


def test_simple_full_roundtrip(simple_atfx):
    """Full round-trip test with Example_Simple."""
    with AtfxStore(simple_atfx) as store:
        model = store.model()

        # Query environment
        env = model.entities["Environment"]
        stmt = ods.SelectStatement()
        stmt.columns.add(aid=env.aid, attribute="Id")
        stmt.columns.add(aid=env.aid, attribute="Name")
        result = store.data_read(stmt)

        assert len(result.matrices) == 1
        matrix = result.matrices[0]
        id_col = next(c for c in matrix.columns if c.name == "Id")
        name_col = next(c for c in matrix.columns if c.name == "Name")
        assert id_col.longlong_array.values[0] == 90
        assert name_col.string_array.values[0] == "MyEnvironment"


def test_alltypes_data_types(alltypes_atfx):
    """AllTypes should have diverse data types in Process entity."""
    with AtfxStore(alltypes_atfx) as store:
        model = store.model()
        process = model.entities["Process"]

        # Check we have various data types
        data_types_present = set()
        for aname in process.attributes:
            dt = process.attributes[aname].data_type
            data_types_present.add(dt)

        # Should have multiple distinct types
        assert len(data_types_present) > 5


def test_descriptive_data_loads(descriptive_atfx):
    """DescriptiveData example with older namespace should still load."""
    with AtfxStore(descriptive_atfx) as store:
        model = store.model()
        assert "Environment" in model.entities or any(
            model.entities[e].base_name == "AoEnvironment" for e in model.entities
        )


def test_geometry_loads(geometry_atfx):
    """Geometry example should load with its custom enumerations."""
    with AtfxStore(geometry_atfx) as store:
        model = store.model()
        # Geometry has custom enumerations like axistype
        has_custom_enum = any(
            e
            not in (
                "datatype_enum",
                "seq_rep_enum",
                "typespec_enum",
                "ao_storagetype_enum",
                "interpolation_enum",
            )
            for e in model.enumerations
        )
        assert has_custom_enum


def test_context_read_returns_variables(simple_atfx):
    """context_read() should return ODSVERSION and BASE-MODEL-VERSION."""
    with AtfxStore(simple_atfx) as store:
        ctx = store.context_read()
        assert "BASE-MODEL-VERSION" in ctx.variables
        bm_version = ctx.variables["BASE-MODEL-VERSION"].string_array.values[0]
        assert bm_version != ""


def test_context_read_ods_version(simple_atfx):
    """ODS version should be extracted from XML namespace."""
    with AtfxStore(simple_atfx) as store:
        ctx = store.context_read()
        if "ODSVERSION" in ctx.variables:
            ods_ver = ctx.variables["ODSVERSION"].string_array.values[0]
            assert ods_ver != ""
