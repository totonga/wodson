"""Tests for the two file-map registration fixes.

Fix 1 (_instance_parser.py): ``resolve_external_component_refs`` must use the
relation definition's ``entity_name`` to find the AoFile entity for the
``ao_values_file`` fallback rather than scanning all entities by base_name.
When multiple entities share base_name "AoFile", the old scan could pick the
wrong one.

Fix 2 (_atfx_store.py): Inline ``<component>`` refs (pattern 1 — embedded in
lc ``<Values>``) whose identifiers are missing from the ``<files>`` section must
still be resolvable.  AtfxStore now registers ``identifier -> atfx_dir/identifier``
for every ExternalComponentRef that is absent from the parsed file map.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import odsbox.proto.ods_pb2 as ods
import pytest

from wodson.atfx import AtfxStore
from wodson.atfx._instance_parser import ExternalComponentRef, resolve_external_component_refs

DATA_DIR = Path(__file__).resolve().parent / "data" / "openatfx"
COMMON_TYPESPECS_ATFX = DATA_DIR / "Example_CommonTypespecs.atfx"
COMMON_TYPESPECS_DAT = DATA_DIR / "Example_CommonTypespecs.dat"


# ---------------------------------------------------------------------------
# Helpers: build a minimal ods.Model for unit-testing resolve_external_component_refs
# ---------------------------------------------------------------------------


def _build_model_two_aofile_entities() -> ods.Model:
    """Return a model with two AoFile entities to expose the base_name-scan bug.

    Layout
    ------
    - MyLc (AoLocalColumn): values attr (DT_UNKNOWN), ec_ref relation
    - MyEc (AoExternalComponent): id, filename_url, component_length,
      start_offset, block_size, valuesperblock, value_type attrs;
      ao_values_file_rel relation → CorrectAoFile
    - DecoyAoFile (AoFile, aid=3): id attr ONLY — no ao_location.
      Listed *before* CorrectAoFile so the old base_name scan would pick it.
    - CorrectAoFile (AoFile, aid=4): id attr + location (ao_location).
      This is the actual relation target; the fix must choose this one.
    """
    model = ods.Model()

    # typespec_enum
    ts_enum = model.enumerations["typespec_enum"]
    ts_enum.name = "typespec_enum"
    ts_enum.items["ieeefloat4"] = 5

    # --- MyLc (AoLocalColumn) ---
    lc = model.entities["MyLc"]
    lc.name = "MyLc"
    lc.base_name = "AoLocalColumn"
    lc.aid = 1

    lc_id = lc.attributes["lc_id"]
    lc_id.name = "lc_id"
    lc_id.base_name = "id"
    lc_id.data_type = ods.DataTypeEnum.DT_LONGLONG

    lc_vals = lc.attributes["values"]
    lc_vals.name = "values"
    lc_vals.base_name = "values"
    lc_vals.data_type = ods.DataTypeEnum.DT_UNKNOWN

    lc_ec_rel = lc.relations["ec_ref"]
    lc_ec_rel.name = "ec_ref"
    lc_ec_rel.base_name = "external_component"
    lc_ec_rel.entity_name = "MyEc"
    lc_ec_rel.range_max = 1

    # --- MyEc (AoExternalComponent) ---
    ec = model.entities["MyEc"]
    ec.name = "MyEc"
    ec.base_name = "AoExternalComponent"
    ec.aid = 2

    for aname, base, dt in [
        ("ec_id", "id", ods.DataTypeEnum.DT_LONGLONG),
        ("filename_url", "filename_url", ods.DataTypeEnum.DT_STRING),
        ("component_length", "component_length", ods.DataTypeEnum.DT_LONGLONG),
        ("start_offset", "start_offset", ods.DataTypeEnum.DT_LONGLONG),
        ("block_size", "block_size", ods.DataTypeEnum.DT_LONGLONG),
        ("valuesperblock", "valuesperblock", ods.DataTypeEnum.DT_LONGLONG),
    ]:
        a = ec.attributes[aname]
        a.name = aname
        a.base_name = base
        a.data_type = dt

    ec_vtype = ec.attributes["value_type"]
    ec_vtype.name = "value_type"
    ec_vtype.base_name = "value_type"
    ec_vtype.data_type = ods.DataTypeEnum.DT_ENUM
    ec_vtype.enumeration = "typespec_enum"

    ec_file_rel = ec.relations["ao_values_file_rel"]
    ec_file_rel.name = "ao_values_file_rel"
    ec_file_rel.base_name = "ao_values_file"
    ec_file_rel.entity_name = "CorrectAoFile"
    ec_file_rel.range_max = 1

    # --- DecoyAoFile (AoFile, listed FIRST — would be picked by old base_name scan) ---
    decoy = model.entities["DecoyAoFile"]
    decoy.name = "DecoyAoFile"
    decoy.base_name = "AoFile"
    decoy.aid = 3

    decoy_id = decoy.attributes["decoy_id"]
    decoy_id.name = "decoy_id"
    decoy_id.base_name = "id"
    decoy_id.data_type = ods.DataTypeEnum.DT_LONGLONG
    # No ao_location attribute — old code would find this entity and then fail to
    # resolve aofile_location_attr, silently skipping the fallback.

    # --- CorrectAoFile (AoFile — the actual relation target) ---
    correct = model.entities["CorrectAoFile"]
    correct.name = "CorrectAoFile"
    correct.base_name = "AoFile"
    correct.aid = 4

    correct_id = correct.attributes["correct_id"]
    correct_id.name = "correct_id"
    correct_id.base_name = "id"
    correct_id.data_type = ods.DataTypeEnum.DT_LONGLONG

    correct_loc = correct.attributes["location"]
    correct_loc.name = "location"
    correct_loc.base_name = "ao_location"
    correct_loc.data_type = ods.DataTypeEnum.DT_STRING

    return model


def _make_instances() -> dict[str, list[dict[str, Any]]]:
    """Return minimal instances matching the model from ``_build_model_two_aofile_entities``."""
    return {
        "MyLc": [
            {
                "lc_id": 1,
                "values": None,  # no inline values — must be resolved via ec
                "ec_ref": 10,
            }
        ],
        "MyEc": [
            {
                "ec_id": 10,
                "filename_url": "",  # empty → ao_values_file fallback must kick in
                "component_length": 4,
                "start_offset": 0,
                "block_size": 4,
                "valuesperblock": 1,
                "value_type": 5,  # ieeefloat4 in typespec_enum
                "ao_values_file_rel": 20,
            }
        ],
        # Only CorrectAoFile has an instance — DecoyAoFile has none.
        "CorrectAoFile": [
            {
                "correct_id": 20,
                "location": "data.bin",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Fix 1: resolve_external_component_refs must use relation target, not base_name scan
# ---------------------------------------------------------------------------


def test_aofile_entity_resolved_via_relation_target() -> None:
    """ao_values_file fallback must use the relation's entity_name, not base_name scan.

    The model has two entities with base_name "AoFile":
      - "DecoyAoFile" (listed first, no ao_location attribute)
      - "CorrectAoFile" (the actual relation target, has ao_location)

    The old code scanned entities in dict-insertion order and would pick
    DecoyAoFile first, leaving aofile_location_attr=None and producing an
    ExternalComponentRef with an empty identifier.

    After the fix, the relation definition is consulted directly so
    CorrectAoFile is used and the identifier is populated from its ao_location.
    """
    model = _build_model_two_aofile_entities()
    instances = _make_instances()

    file_map: dict[str, Path] = {}
    atfx_dir = Path("/fake/atfx/dir")

    resolve_external_component_refs(model, instances, file_map, atfx_dir)

    lc_inst = instances["MyLc"][0]
    ref = lc_inst.get("values")

    assert isinstance(ref, ExternalComponentRef), "values attribute of MyLc must be resolved to an ExternalComponentRef"
    assert ref.identifier == "data.bin", (
        f"Expected identifier='data.bin' from CorrectAoFile.location, got {ref.identifier!r}. "
        "DecoyAoFile (no ao_location) may have been used instead of the relation target."
    )
    assert ref.datatype == "ieeefloat4"
    assert ref.length == 4


def test_aofile_entity_registers_file_map_entry() -> None:
    """resolve_external_component_refs registers identifier -> atfx_dir/identifier in file_map."""
    model = _build_model_two_aofile_entities()
    instances = _make_instances()

    file_map: dict[str, Path] = {}
    atfx_dir = Path("/fake/atfx/dir")

    resolve_external_component_refs(model, instances, file_map, atfx_dir)

    assert "data.bin" in file_map, "identifier 'data.bin' must be registered in file_map after resolution"
    assert file_map["data.bin"] == atfx_dir / "data.bin"


def test_decoy_aofile_entity_has_no_ao_location_attr() -> None:
    """Sanity check: DecoyAoFile must not have ao_location so the test is valid."""
    model = _build_model_two_aofile_entities()
    decoy = model.entities["DecoyAoFile"]
    ao_location_attrs = [a for a, attr in decoy.attributes.items() if attr.base_name == "ao_location"]
    assert ao_location_attrs == [], "DecoyAoFile must have no ao_location attribute"


# ---------------------------------------------------------------------------
# Fix 2: inline component refs with no <files> section must be resolvable
# ---------------------------------------------------------------------------


@pytest.fixture
def common_typespecs_no_files(tmp_path: Path) -> Path:
    """Return path to a modified copy of Example_CommonTypespecs.atfx with empty <files>.

    The original file maps identifier "bin" to filename "Example_CommonTypespecs.dat"
    in its <files> section.  This fixture strips that section so the file_map from
    _parse_file_map is empty.  The binary data file is copied to tmp_path/bin so that
    Fix 2's fallback (identifier == filename) can resolve it.
    """
    if not COMMON_TYPESPECS_ATFX.exists():
        pytest.skip("Example_CommonTypespecs.atfx not present")
    if not COMMON_TYPESPECS_DAT.exists():
        pytest.skip("Example_CommonTypespecs.dat not present")

    content = COMMON_TYPESPECS_ATFX.read_text(encoding="utf-8")

    # Replace the <files>...</files> block with an empty element
    content = re.sub(r"<files>.*?</files>", "<files></files>", content, flags=re.DOTALL)

    atfx_path = tmp_path / "test.atfx"
    atfx_path.write_text(content, encoding="utf-8")

    # Copy the .dat file as "bin" — the identifier used in inline <component> refs
    shutil.copy(COMMON_TYPESPECS_DAT, tmp_path / "bin")

    return atfx_path


def test_inline_component_ref_loads_without_files_section(common_typespecs_no_files: Path) -> None:
    """AtfxStore must open successfully when <files> section is absent.

    Fix 2 registers inline component ref identifiers in the file_map so the
    binary reader can locate them even without a <files> section.
    """
    with AtfxStore(common_typespecs_no_files) as store:
        model = store.model()
        assert len(model.entities) > 0


def test_inline_component_ref_values_resolved_without_files_section(common_typespecs_no_files: Path) -> None:
    """Local column values must be non-empty when <files> section is stripped.

    Without Fix 2 the file_map stays empty for identifier "bin", causing
    read_external_component_typed to raise FileNotFoundError (caught internally),
    and all values would be stored as None.  With Fix 2 the path is registered
    as atfx_dir/bin and the binary is read successfully.
    """
    with AtfxStore(common_typespecs_no_files) as store:
        model = store.model()
        lc_name = next(n for n, e in model.entities.items() if e.base_name == "AoLocalColumn")
        lc_entity = model.entities[lc_name]

        values_attr = next(
            (a for a, attr in lc_entity.attributes.items() if attr.base_name == "values"),
            None,
        )
        assert values_attr is not None

        stmt = ods.SelectStatement()
        stmt.columns.add(aid=lc_entity.aid, attribute=values_attr)
        result = store.data_read(stmt)

        assert len(result.matrices) == 1
        val_col = result.matrices[0].columns[0]

        has_any_values = any(
            len(ua.long_array.values) > 0
            or len(ua.double_array.values) > 0
            or len(ua.float_array.values) > 0
            or len(ua.longlong_array.values) > 0
            or len(ua.byte_array.values) > 0
            for ua in val_col.unknown_arrays.values
        )
        assert has_any_values, (
            "No LocalColumn has non-empty values — "
            "Fix 2 (file_map registration for inline component refs) may not be working"
        )


def test_inline_component_ref_same_values_as_original(tmp_path: Path) -> None:
    """Values from the stripped-files ATFX must match the original file's values.

    This confirms Fix 2 resolves to the correct binary data, not just any data.
    """
    if not COMMON_TYPESPECS_ATFX.exists():
        pytest.skip("Example_CommonTypespecs.atfx not present")
    if not COMMON_TYPESPECS_DAT.exists():
        pytest.skip("Example_CommonTypespecs.dat not present")

    # Build the no-<files> variant
    content = COMMON_TYPESPECS_ATFX.read_text(encoding="utf-8")
    content = re.sub(r"<files>.*?</files>", "<files></files>", content, flags=re.DOTALL)
    stripped_atfx = tmp_path / "stripped.atfx"
    stripped_atfx.write_text(content, encoding="utf-8")
    shutil.copy(COMMON_TYPESPECS_DAT, tmp_path / "bin")

    def _collect_values(atfx_path: Path) -> list[list[float]]:
        with AtfxStore(atfx_path) as store:
            model = store.model()
            lc_name = next(n for n, e in model.entities.items() if e.base_name == "AoLocalColumn")
            lc_entity = model.entities[lc_name]
            values_attr = next(a for a, attr in lc_entity.attributes.items() if attr.base_name == "values")
            stmt = ods.SelectStatement()
            stmt.columns.add(aid=lc_entity.aid, attribute=values_attr)
            result = store.data_read(stmt)
            val_col = result.matrices[0].columns[0]
            out = []
            for ua in val_col.unknown_arrays.values:
                vals = (
                    list(ua.float_array.values)
                    or list(ua.double_array.values)
                    or list(ua.long_array.values)
                    or list(ua.longlong_array.values)
                )
                out.append(vals)
            return out

    original_values = _collect_values(COMMON_TYPESPECS_ATFX)
    stripped_values = _collect_values(stripped_atfx)

    assert stripped_values == original_values, (
        "Values from stripped-files ATFX differ from original — Fix 2 may be mapping to the wrong binary file"
    )
