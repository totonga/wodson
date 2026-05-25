"""Tests for correct parsing of all attribute data types using example.atfx."""

from pathlib import Path

import odsbox.proto.ods_pb2 as ods
import pytest

from wodson.atfx import AtfxStore

EXAMPLE_ATFX = Path(__file__).resolve().parent / "data" / "openatfx" / "example.atfx"

# The 'tstser' entity in example.atfx has application attributes covering every
# ODS data type.  Instance 2 ("Test_Vorbeifahrt") contains non-empty values for
# DT_EXTERNALREFERENCE, DS_EXTERNALREFERENCE, DT_ENUM, and DS_ENUM.


@pytest.fixture(scope="module")
def example_store():
    """Open example.atfx (binary component errors are tolerated with a warning)."""
    with AtfxStore(EXAMPLE_ATFX) as store:
        yield store


@pytest.fixture(scope="module")
def tstser_matrix(example_store):
    """Return the DataMatrix for the 'tstser' entity."""
    model = example_store.model()
    assert "tstser" in model.entities, "tstser entity not found in model"
    entity = model.entities["tstser"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=entity.aid, attribute="*")
    result = example_store.data_read(stmt)

    assert len(result.matrices) == 1, "Expected exactly one matrix for tstser"
    return result.matrices[0]


def _get_col(matrix: ods.DataMatrix, name: str) -> ods.DataMatrix.Column:
    """Return the named column from *matrix*, or raise AssertionError."""
    for col in matrix.columns:
        if col.name.lower() == name.lower():
            return col
    raise AssertionError(f"Column '{name}' not found in matrix")


# ---------------------------------------------------------------------------
# DT_EXTERNALREFERENCE
# ---------------------------------------------------------------------------


def test_dt_externalreference_type(tstser_matrix):
    """DT_EXTERNALREFERENCE attribute is returned as a string column."""
    col = _get_col(tstser_matrix, "appl_attr_dt_externalreference")
    assert col.HasField("string_array"), "DT_EXTERNALREFERENCE must use string_array"


def test_dt_externalreference_value(tstser_matrix):
    """The non-empty instance has the expected pipe-separated external reference."""
    col = _get_col(tstser_matrix, "appl_attr_dt_externalreference")
    values = [v for v in col.string_array.values if v]
    assert len(values) == 1
    assert values[0] == "extref_desc|mime_type|http://www.test.de"


# ---------------------------------------------------------------------------
# DS_EXTERNALREFERENCE
# ---------------------------------------------------------------------------


def test_ds_externalreference_type(tstser_matrix):
    """DS_EXTERNALREFERENCE attribute is returned as a string_arrays column."""
    col = _get_col(tstser_matrix, "appl_attr_ds_externalreference")
    assert len(col.string_arrays.values) > 0, "DS_EXTERNALREFERENCE must use string_arrays"


def test_ds_externalreference_values(tstser_matrix):
    """The non-empty instance has two external reference strings."""
    col = _get_col(tstser_matrix, "appl_attr_ds_externalreference")
    non_empty = [arr for arr in col.string_arrays.values if arr.values]
    assert len(non_empty) == 1
    arr = non_empty[0]
    assert list(arr.values) == [
        "extref_desc1|mime_type1|http://www.test.de1",
        "extref_desc2|mime_type2|http://www.test.de2",
    ]


# ---------------------------------------------------------------------------
# DT_ENUM
# ---------------------------------------------------------------------------


def test_dt_enum_type(tstser_matrix):
    """DT_ENUM attribute is returned as a string column (enum name)."""
    col = _get_col(tstser_matrix, "appl_attr_dt_enum")
    assert col.HasField("string_array"), "DT_ENUM must use string_array"


def test_dt_enum_value(tstser_matrix):
    """The non-empty instance stores the enum item name as a string."""
    col = _get_col(tstser_matrix, "appl_attr_dt_enum")
    values = [v for v in col.string_array.values if v]
    assert len(values) == 1
    assert values[0] == "DT_EXTERNALREFERENCE"


# ---------------------------------------------------------------------------
# DS_ENUM
# ---------------------------------------------------------------------------


def test_ds_enum_type(tstser_matrix):
    """DS_ENUM attribute is returned as a string_arrays column."""
    col = _get_col(tstser_matrix, "appl_attr_ds_enum")
    assert len(col.string_arrays.values) > 0, "DS_ENUM must use string_arrays"


def test_ds_enum_values(tstser_matrix):
    """The non-empty instance has three enum name strings."""
    col = _get_col(tstser_matrix, "appl_attr_ds_enum")
    non_empty = [arr for arr in col.string_arrays.values if arr.values]
    assert len(non_empty) == 1
    assert list(non_empty[0].values) == ["DT_STRING", "DT_DOUBLE", "DT_LONGLONG"]
