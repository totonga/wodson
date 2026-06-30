"""Tests for wodson.data_matrix — DataFrame ↔ DataMatrix conversion."""

from __future__ import annotations

import numpy as np
import odsbox.proto.ods_pb2 as ods
import pandas as pd
import pytest
from odsbox.model_cache import ModelCache

from wodson.data_matrix import (
    dataframe_to_datamatrix,
    dataframe_to_unknown_array_datamatrix,
    merge_into_datamatrix,
)
from wodson.data_matrix._pandas_writer import _is_null, _matrix_row_count
from wodson.data_matrix._resolve import (
    parse_column_prefix,
    resolve_entity_and_columns,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_model() -> ods.Model:
    """Build a minimal ODS model used by both fixtures."""
    model = ods.Model()
    e = model.entities["Measurement"]
    e.name = "Measurement"
    e.base_name = "AoMeasurement"
    e.aid = 10

    attrs: list[tuple[str, str, int]] = [
        ("Id", "id", ods.DataTypeEnum.DT_LONGLONG),
        ("Name", "name", ods.DataTypeEnum.DT_STRING),
        ("Version", "version", ods.DataTypeEnum.DT_STRING),
        ("SomeFloat", "some_float", ods.DataTypeEnum.DT_FLOAT),
        ("SomeDouble", "some_double", ods.DataTypeEnum.DT_DOUBLE),
        ("SomeInt", "some_int", ods.DataTypeEnum.DT_LONG),
        ("SomeShort", "some_short", ods.DataTypeEnum.DT_SHORT),
        ("SomeBool", "some_bool", ods.DataTypeEnum.DT_BOOLEAN),
        ("SomeByte", "some_byte", ods.DataTypeEnum.DT_BYTE),
        ("SomeByteStr", "some_byte_str", ods.DataTypeEnum.DT_BYTESTR),
        ("SomeComplex", "some_complex", ods.DataTypeEnum.DT_COMPLEX),
        ("SomeDComplex", "some_dcomplex", ods.DataTypeEnum.DT_DCOMPLEX),
        ("Values", "values", ods.DataTypeEnum.DT_UNKNOWN),
    ]
    for app_name, base_name, dt in attrs:
        a = e.attributes[app_name]
        a.name = app_name
        a.base_name = base_name
        a.data_type = dt  # type: ignore[assignment]

    return model


@pytest.fixture()
def simple_model() -> ModelCache:
    """ModelCache wrapping a minimal single-entity ODS model."""
    return ModelCache(_make_model())


@pytest.fixture()
def two_entity_model() -> ModelCache:
    """ModelCache with Measurement and a second Submatrix entity."""
    model = _make_model()
    e2 = model.entities["Submatrix"]
    e2.name = "Submatrix"
    e2.base_name = "AoSubmatrix"
    e2.aid = 20
    a2 = e2.attributes["Id"]
    a2.name = "Id"
    a2.base_name = "id"
    a2.data_type = ods.DataTypeEnum.DT_LONGLONG
    return ModelCache(model)


# ---------------------------------------------------------------------------
# _resolve tests
# ---------------------------------------------------------------------------


def test_parse_column_prefix_with_separator() -> None:
    assert parse_column_prefix("Measurement.Name") == ("Measurement", "Name")


def test_parse_column_prefix_no_separator() -> None:
    assert parse_column_prefix("Name") == (None, "Name")


def test_parse_column_prefix_custom_separator() -> None:
    assert parse_column_prefix("Measurement/Name", "/") == ("Measurement", "Name")


def test_parse_column_prefix_multiple_separators() -> None:
    # Only the first separator is used as split point
    assert parse_column_prefix("A.B.C") == ("A", "B.C")


def test_resolve_entity_and_columns_explicit_entity(simple_model: ModelCache) -> None:
    cols = ["Id", "Name"]
    entity, resolved = resolve_entity_and_columns(cols, simple_model, "Measurement")
    assert entity.name == "Measurement"
    assert len(resolved) == 2
    assert resolved[0][0] == "Id"
    assert resolved[1][0] == "Name"


def test_resolve_entity_and_columns_prefix(simple_model: ModelCache) -> None:
    cols = ["Measurement.Id", "Measurement.Name"]
    entity, resolved = resolve_entity_and_columns(cols, simple_model, None)
    assert entity.name == "Measurement"
    assert resolved[0][0] == "Id"
    assert resolved[1][0] == "Name"


def test_resolve_entity_and_columns_explicit_wins_over_prefix(
    simple_model: ModelCache,
) -> None:
    # Prefix uses the base name; explicit entity_name uses the app name — app wins
    cols = ["AoMeasurement.Id", "AoMeasurement.Name"]
    entity, resolved = resolve_entity_and_columns(cols, simple_model, "Measurement")
    assert entity.name == "Measurement"
    assert resolved[0][0] == "Id"


def test_resolve_entity_by_base_name_in_prefix(simple_model: ModelCache) -> None:
    cols = ["AoMeasurement.Id"]
    entity, resolved = resolve_entity_and_columns(cols, simple_model, None)
    assert entity.name == "Measurement"
    assert resolved[0][0] == "Id"


def test_resolve_attr_by_base_name_in_prefix(simple_model: ModelCache) -> None:
    cols = ["Measurement.name"]  # attr is base name "name"
    entity, resolved = resolve_entity_and_columns(cols, simple_model, None)
    assert resolved[0][0] == "Name"  # returned as app name


def test_resolve_no_prefix_no_entity_raises(simple_model: ModelCache) -> None:
    with pytest.raises(ValueError, match="entity prefix"):
        resolve_entity_and_columns(["Name"], simple_model, None)


def test_resolve_empty_columns_raises(simple_model: ModelCache) -> None:
    with pytest.raises(ValueError, match="No columns"):
        resolve_entity_and_columns([], simple_model, "Measurement")


def test_resolve_entity_not_found_raises(simple_model: ModelCache) -> None:
    with pytest.raises(ValueError, match="No entity named"):
        resolve_entity_and_columns(["Id"], simple_model, "NonExistent")


def test_resolve_attribute_not_found_raises(simple_model: ModelCache) -> None:
    with pytest.raises(ValueError, match="has no attribute named"):
        resolve_entity_and_columns(["Measurement.NoSuchAttr"], simple_model, None)


def test_resolve_mixed_entities_raises(two_entity_model: ModelCache) -> None:
    with pytest.raises(ValueError, match="same entity"):
        resolve_entity_and_columns(
            ["Measurement.Id", "Submatrix.Id"],
            two_entity_model,
            None,
        )


# ---------------------------------------------------------------------------
# _is_null tests
# ---------------------------------------------------------------------------


def test_is_null_none() -> None:
    assert _is_null(None) is True


def test_is_null_nan() -> None:
    assert _is_null(float("nan")) is True


def test_is_null_numpy_nan() -> None:
    assert _is_null(np.nan) is True


def test_is_null_pd_na() -> None:
    assert _is_null(pd.NA) is True


def test_is_null_pd_nat() -> None:
    assert _is_null(pd.NaT) is True


def test_is_null_scalar_false() -> None:
    assert _is_null(42) is False
    assert _is_null("hello") is False
    assert _is_null(0) is False
    assert _is_null(False) is False


def test_is_null_list_never_null() -> None:
    assert _is_null([]) is False
    assert _is_null([None, np.nan]) is False


def test_is_null_numpy_array_never_null() -> None:
    assert _is_null(np.array([1, 2, 3])) is False


# ---------------------------------------------------------------------------
# dataframe_to_datamatrix — basic and metadata
# ---------------------------------------------------------------------------


def test_dataframe_to_datamatrix_metadata(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Id": [1], "Measurement.Name": ["a"]})
    matrix = dataframe_to_datamatrix(df, simple_model)
    assert matrix.name == "Measurement"
    assert matrix.base_name == "AoMeasurement"
    assert matrix.aid == 10
    assert len(matrix.columns) == 2


def test_dataframe_to_datamatrix_explicit_entity(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Id": [10, 20], "Name": ["x", "y"]})
    matrix = dataframe_to_datamatrix(df, simple_model, entity_name="Measurement")
    assert matrix.aid == 10
    assert list(matrix.columns[0].longlong_array.values) == [10, 20]


def test_dataframe_to_datamatrix_entity_by_base_name_prefix(
    simple_model: ModelCache,
) -> None:
    df = pd.DataFrame({"AoMeasurement.Name": ["test"]})
    matrix = dataframe_to_datamatrix(df, simple_model)
    assert matrix.name == "Measurement"
    assert list(matrix.columns[0].string_array.values) == ["test"]


def test_dataframe_to_datamatrix_attr_base_name_in_column(
    simple_model: ModelCache,
) -> None:
    # Column uses attribute base name "name" → resolved to app name "Name"
    df = pd.DataFrame({"Measurement.name": ["z"]})
    matrix = dataframe_to_datamatrix(df, simple_model)
    assert matrix.columns[0].name == "Name"
    assert matrix.columns[0].base_name == "name"


# ---------------------------------------------------------------------------
# dataframe_to_datamatrix — scalar data types
# ---------------------------------------------------------------------------


def test_dataframe_to_datamatrix_longlong(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Id": [1, 2, 3]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_LONGLONG
    assert list(col.longlong_array.values) == [1, 2, 3]


def test_dataframe_to_datamatrix_string(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Name": ["a", "b", "c"]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_STRING
    assert list(col.string_array.values) == ["a", "b", "c"]


def test_dataframe_to_datamatrix_float(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeFloat": [1.0, 2.0]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_FLOAT
    assert list(col.float_array.values) == pytest.approx([1.0, 2.0])


def test_dataframe_to_datamatrix_double(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeDouble": [1.5, 2.5]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_DOUBLE
    assert list(col.double_array.values) == pytest.approx([1.5, 2.5])


def test_dataframe_to_datamatrix_long(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeInt": [10, 20]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_LONG
    assert list(col.long_array.values) == [10, 20]


def test_dataframe_to_datamatrix_short(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeShort": [3, 7]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_SHORT
    assert list(col.long_array.values) == [3, 7]


def test_dataframe_to_datamatrix_boolean(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeBool": [True, False, True]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_BOOLEAN
    assert list(col.boolean_array.values) == [True, False, True]


def test_dataframe_to_datamatrix_byte(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeByte": [1, 2, 255]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_BYTE
    assert col.byte_array.values == bytes([1, 2, 255])


def test_dataframe_to_datamatrix_bytestr(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeByteStr": [b"hello", b"world"]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_BYTESTR
    assert list(col.bytestr_array.values) == [b"hello", b"world"]


def test_dataframe_to_datamatrix_complex(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeComplex": [1 + 2j, 3 + 4j]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_COMPLEX
    assert list(col.float_array.values) == pytest.approx([1.0, 2.0, 3.0, 4.0])


def test_dataframe_to_datamatrix_dcomplex(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeDComplex": [1 + 2j]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_DCOMPLEX
    assert list(col.double_array.values) == pytest.approx([1.0, 2.0])


# ---------------------------------------------------------------------------
# dataframe_to_datamatrix — null / NaN / pd.NA handling
# ---------------------------------------------------------------------------


def test_null_none_in_string_column(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Name": ["a", None, "c"]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert list(col.is_null) == [False, True, False]
    assert list(col.string_array.values) == ["a", "", "c"]


def test_null_nan_in_double_column(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeDouble": [1.0, float("nan"), 3.0]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert list(col.is_null) == [False, True, False]
    assert col.double_array.values[0] == pytest.approx(1.0)
    assert col.double_array.values[1] == pytest.approx(0.0)  # zero placeholder
    assert col.double_array.values[2] == pytest.approx(3.0)


def test_null_pd_na_in_int_column(simple_model: ModelCache) -> None:
    df = pd.DataFrame(
        {
            "Measurement.Id": pd.array([1, pd.NA, 3], dtype="Int64"),
        }
    )
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert list(col.is_null) == [False, True, False]
    assert col.longlong_array.values[0] == 1
    assert col.longlong_array.values[1] == 0  # zero placeholder
    assert col.longlong_array.values[2] == 3


def test_null_in_boolean_column(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeBool": pd.array([True, pd.NA, False], dtype="boolean")})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert list(col.is_null) == [False, True, False]
    assert list(col.boolean_array.values) == [True, False, False]


def test_null_in_byte_column(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeByte": [1, None, 3]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert list(col.is_null) == [False, True, False]
    assert col.byte_array.values == bytes([1, 0, 3])


def test_null_in_bytestr_column(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeByteStr": [b"a", None, b"b"]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert list(col.is_null) == [False, True, False]
    assert list(col.bytestr_array.values) == [b"a", b"", b"b"]


def test_null_in_complex_column(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeComplex": [1 + 2j, None]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert list(col.is_null) == [False, True]
    assert list(col.float_array.values) == pytest.approx([1.0, 2.0, 0.0, 0.0])


def test_null_in_dcomplex_column(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.SomeDComplex": [None, 3 + 4j]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert list(col.is_null) == [True, False]
    assert list(col.double_array.values) == pytest.approx([0.0, 0.0, 3.0, 4.0])


def test_all_rows_valid_no_is_null_set_false(simple_model: ModelCache) -> None:
    # Even when all values are valid, is_null is populated (all False)
    df = pd.DataFrame({"Measurement.Name": ["x", "y"]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert list(col.is_null) == [False, False]


# ---------------------------------------------------------------------------
# dataframe_to_datamatrix — type inference (DT_UNKNOWN in model)
# ---------------------------------------------------------------------------


def test_infer_float64_from_dtype(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": np.array([1.0, 2.0], dtype=np.float64)})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_DOUBLE
    assert list(col.double_array.values) == pytest.approx([1.0, 2.0])


def test_infer_int64_from_dtype(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": np.array([1, 2], dtype=np.int64)})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_LONGLONG


def test_infer_int16_from_dtype(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": np.array([1, 2], dtype=np.int16)})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_SHORT


def test_infer_float32_from_dtype(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": np.array([1.0, 2.0], dtype=np.float32)})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_FLOAT


def test_infer_bool_from_dtype(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": np.array([True, False], dtype=np.bool_)})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_BOOLEAN


def test_infer_uint8_from_dtype(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": np.array([1, 2], dtype=np.uint8)})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_BYTE


def test_infer_string_from_object_dtype(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": ["hello", "world"]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_STRING


def test_infer_bytes_from_object_dtype(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": [b"abc", b"def"]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_BYTESTR


def test_infer_int_from_object_dtype(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": [1, 2, 3]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_LONGLONG


def test_infer_float_from_object_dtype(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": [1.5, 2.5]})
    col = dataframe_to_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_DOUBLE


def test_data_type_hint_overrides_model(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Id": [1, 2]})
    col = dataframe_to_datamatrix(
        df,
        simple_model,
        entity_name="Measurement",
        data_type_hints={"Id": ods.DataTypeEnum.DT_LONG},
    ).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_LONG
    assert list(col.long_array.values) == [1, 2]


def test_data_type_hint_overrides_inferred(simple_model: ModelCache) -> None:
    # Values column has DT_UNKNOWN in model; hint forces DT_LONG
    df = pd.DataFrame({"Measurement.Values": [10, 20]})
    col = dataframe_to_datamatrix(
        df,
        simple_model,
        entity_name="Measurement",
        data_type_hints={"Values": ods.DataTypeEnum.DT_LONG},
    ).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_LONG


# ---------------------------------------------------------------------------
# dataframe_to_unknown_array_datamatrix
# ---------------------------------------------------------------------------


def test_ua_matrix_metadata(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": [[1.0, 2.0]]})
    matrix = dataframe_to_unknown_array_datamatrix(df, simple_model)
    assert matrix.name == "Measurement"
    assert matrix.base_name == "AoMeasurement"
    assert matrix.aid == 10


def test_ua_double_inferred(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": [[1.0, 2.0, 3.0], [4.0, 5.0]]})
    col = dataframe_to_unknown_array_datamatrix(df, simple_model).columns[0]
    assert col.data_type == ods.DataTypeEnum.DT_UNKNOWN
    assert len(col.unknown_arrays.values) == 2
    assert list(col.unknown_arrays.values[0].double_array.values) == pytest.approx([1.0, 2.0, 3.0])
    assert list(col.unknown_arrays.values[1].double_array.values) == pytest.approx([4.0, 5.0])


def test_ua_int_inferred(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": [[10, 20, 30]]})
    ua = dataframe_to_unknown_array_datamatrix(df, simple_model).columns[0].unknown_arrays.values[0]
    assert ua.data_type == ods.DataTypeEnum.DT_LONGLONG
    assert list(ua.longlong_array.values) == [10, 20, 30]


def test_ua_string_inferred(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": [["hello", "world"]]})
    ua = dataframe_to_unknown_array_datamatrix(df, simple_model).columns[0].unknown_arrays.values[0]
    assert ua.data_type == ods.DataTypeEnum.DT_STRING
    assert list(ua.string_array.values) == ["hello", "world"]


def test_ua_bytes_inferred(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": [[b"abc", b"def"]]})
    ua = dataframe_to_unknown_array_datamatrix(df, simple_model).columns[0].unknown_arrays.values[0]
    assert ua.data_type == ods.DataTypeEnum.DT_BYTESTR
    assert list(ua.bytestr_array.values) == [b"abc", b"def"]


def test_ua_bool_inferred(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": [[True, False, True]]})
    ua = dataframe_to_unknown_array_datamatrix(df, simple_model).columns[0].unknown_arrays.values[0]
    assert ua.data_type == ods.DataTypeEnum.DT_BOOLEAN
    assert list(ua.boolean_array.values) == [True, False, True]


def test_ua_numpy_array_cell(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": [np.array([1.0, 2.0, 3.0])]})
    col = dataframe_to_unknown_array_datamatrix(df, simple_model).columns[0]
    assert col.is_null[0] is False
    assert len(col.unknown_arrays.values[0].double_array.values) == 3


def test_ua_null_cell_none(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": [[1, 2], None, [3]]})
    col = dataframe_to_unknown_array_datamatrix(df, simple_model).columns[0]
    assert list(col.is_null) == [False, True, False]
    assert len(col.unknown_arrays.values) == 3
    assert col.unknown_arrays.values[1].WhichOneof("UnknownOneOf") is None


def test_ua_null_cell_pd_na(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": [pd.NA, [1.0, 2.0]]})
    col = dataframe_to_unknown_array_datamatrix(df, simple_model).columns[0]
    assert list(col.is_null) == [True, False]


def test_ua_empty_list_cell(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Values": [[]]})
    col = dataframe_to_unknown_array_datamatrix(df, simple_model).columns[0]
    # Empty list is not null but has no values in the UnknownArray
    assert col.is_null[0] is False
    assert col.unknown_arrays.values[0].WhichOneof("UnknownOneOf") is None


def test_ua_explicit_entity_name(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Values": [[1.0, 2.0]]})
    matrix = dataframe_to_unknown_array_datamatrix(df, simple_model, entity_name="Measurement")
    assert matrix.columns[0].name == "Values"


# ---------------------------------------------------------------------------
# merge_into_datamatrix
# ---------------------------------------------------------------------------


def test_merge_adds_new_column(simple_model: ModelCache) -> None:
    df1 = pd.DataFrame({"Measurement.Id": [1, 2, 3]})
    matrix = dataframe_to_datamatrix(df1, simple_model)

    df2 = pd.DataFrame({"Measurement.Name": ["a", "b", "c"]})
    merge_into_datamatrix(matrix, df2, simple_model)

    assert len(matrix.columns) == 2
    assert matrix.columns[1].name == "Name"
    assert list(matrix.columns[1].string_array.values) == ["a", "b", "c"]


def test_merge_collision_raises(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Id": [1, 2]})
    matrix = dataframe_to_datamatrix(df, simple_model)

    with pytest.raises(ValueError, match="already exists"):
        merge_into_datamatrix(matrix, df, simple_model)


def test_merge_row_count_mismatch_raises(simple_model: ModelCache) -> None:
    df1 = pd.DataFrame({"Measurement.Id": [1, 2, 3]})
    matrix = dataframe_to_datamatrix(df1, simple_model)

    df2 = pd.DataFrame({"Measurement.Name": ["a", "b"]})  # 2 rows vs 3
    with pytest.raises(ValueError, match="Row count mismatch"):
        merge_into_datamatrix(matrix, df2, simple_model)


def test_merge_entity_mismatch_raises(two_entity_model: ModelCache) -> None:
    df1 = pd.DataFrame({"Measurement.Id": [1, 2]})
    matrix = dataframe_to_datamatrix(df1, two_entity_model)

    df2 = pd.DataFrame({"Submatrix.Id": [10, 20]})
    with pytest.raises(ValueError, match="Entity mismatch"):
        merge_into_datamatrix(matrix, df2, two_entity_model)


def test_merge_unknown_arrays_mode(simple_model: ModelCache) -> None:
    df1 = pd.DataFrame({"Measurement.Id": [1, 2]})
    matrix = dataframe_to_datamatrix(df1, simple_model)

    df2 = pd.DataFrame({"Measurement.Values": [[1.0, 2.0], [3.0]]})
    merge_into_datamatrix(matrix, df2, simple_model, use_unknown_arrays=True)

    assert len(matrix.columns) == 2
    col = matrix.columns[1]
    assert col.name == "Values"
    assert col.data_type == ods.DataTypeEnum.DT_UNKNOWN
    assert len(col.unknown_arrays.values) == 2


def test_merge_with_null_in_new_column(simple_model: ModelCache) -> None:
    df1 = pd.DataFrame({"Measurement.Id": [1, 2]})
    matrix = dataframe_to_datamatrix(df1, simple_model)

    df2 = pd.DataFrame({"Measurement.Name": ["ok", None]})
    merge_into_datamatrix(matrix, df2, simple_model)

    col = matrix.columns[1]
    assert list(col.is_null) == [False, True]


def test_merge_into_empty_matrix_any_row_count(simple_model: ModelCache) -> None:
    # Empty matrix (no columns) accepts any row count
    matrix = ods.DataMatrix()
    matrix.name = "Measurement"
    matrix.base_name = "AoMeasurement"
    matrix.aid = 10

    df = pd.DataFrame({"Measurement.Name": ["a", "b", "c", "d"]})
    merge_into_datamatrix(matrix, df, simple_model)
    assert len(matrix.columns) == 1


def test_merge_with_data_type_hints(simple_model: ModelCache) -> None:
    matrix = ods.DataMatrix()
    matrix.name = "Measurement"
    matrix.base_name = "AoMeasurement"
    matrix.aid = 10

    df = pd.DataFrame({"Measurement.Id": [1, 2]})
    merge_into_datamatrix(
        matrix,
        df,
        simple_model,
        data_type_hints={"Id": ods.DataTypeEnum.DT_LONG},
    )
    assert matrix.columns[0].data_type == ods.DataTypeEnum.DT_LONG


def test_matrix_row_count_from_is_null(simple_model: ModelCache) -> None:
    df = pd.DataFrame({"Measurement.Id": [1, 2, 3]})
    matrix = dataframe_to_datamatrix(df, simple_model)
    assert _matrix_row_count(matrix) == 3


def test_matrix_row_count_empty_matrix() -> None:
    matrix = ods.DataMatrix()
    assert _matrix_row_count(matrix) is None


# ---------------------------------------------------------------------------
# Roundtrip tests
# ---------------------------------------------------------------------------


def test_roundtrip_scalar_columns(simple_model: ModelCache) -> None:
    """DataMatrix → DataFrame (via to_pandas) → DataMatrix roundtrip."""
    from odsbox.datamatrices_to_pandas import to_pandas

    dm_orig = ods.DataMatrix()
    dm_orig.name = "Measurement"
    dm_orig.base_name = "AoMeasurement"
    dm_orig.aid = 10

    c_id = dm_orig.columns.add()
    c_id.name = "Id"
    c_id.base_name = "id"
    c_id.data_type = ods.DataTypeEnum.DT_LONGLONG
    c_id.longlong_array.values.extend([1, 2, 3])
    c_id.is_null.extend([False, False, False])

    c_name = dm_orig.columns.add()
    c_name.name = "Name"
    c_name.base_name = "name"
    c_name.data_type = ods.DataTypeEnum.DT_STRING
    c_name.string_array.values.extend(["alpha", "beta", "gamma"])
    c_name.is_null.extend([False, False, False])

    c_float = dm_orig.columns.add()
    c_float.name = "SomeFloat"
    c_float.base_name = "some_float"
    c_float.data_type = ods.DataTypeEnum.DT_FLOAT
    c_float.float_array.values.extend([1.0, 2.0, 3.0])
    c_float.is_null.extend([False, False, False])

    dms = ods.DataMatrices()
    dms.matrices.add().CopyFrom(dm_orig)

    df = to_pandas(dms)

    assert "Measurement.Id" in df.columns
    assert "Measurement.Name" in df.columns
    assert "Measurement.SomeFloat" in df.columns

    matrix_back = dataframe_to_datamatrix(df, simple_model)

    assert matrix_back.aid == 10
    assert matrix_back.name == "Measurement"
    assert len(matrix_back.columns) == 3

    id_col = next(c for c in matrix_back.columns if c.name == "Id")
    assert list(id_col.longlong_array.values) == [1, 2, 3]

    name_col = next(c for c in matrix_back.columns if c.name == "Name")
    assert list(name_col.string_array.values) == ["alpha", "beta", "gamma"]

    float_col = next(c for c in matrix_back.columns if c.name == "SomeFloat")
    assert list(float_col.float_array.values) == pytest.approx([1.0, 2.0, 3.0])


def test_roundtrip_preserves_null_markers(simple_model: ModelCache) -> None:
    """Null markers survive the DataMatrix → DataFrame → DataMatrix roundtrip."""
    from odsbox.datamatrices_to_pandas import to_pandas

    dm_orig = ods.DataMatrix()
    dm_orig.name = "Measurement"
    dm_orig.base_name = "AoMeasurement"
    dm_orig.aid = 10

    col = dm_orig.columns.add()
    col.name = "Name"
    col.base_name = "name"
    col.data_type = ods.DataTypeEnum.DT_STRING
    col.string_array.values.extend(["a", "", "c"])
    col.is_null.extend([False, True, False])

    dms = ods.DataMatrices()
    dms.matrices.add().CopyFrom(dm_orig)

    # Use is_null_to_nan so that nulls become NaN in the DataFrame
    df = to_pandas(dms, is_null_to_nan=True)

    matrix_back = dataframe_to_datamatrix(df, simple_model)
    col_back = next(c for c in matrix_back.columns if c.name == "Name")

    assert col_back.is_null[0] is False
    assert col_back.is_null[1] is True
    assert col_back.is_null[2] is False


def test_roundtrip_double_with_nan(simple_model: ModelCache) -> None:
    """NaN in a double column round-trips as is_null=True."""
    from odsbox.datamatrices_to_pandas import to_pandas

    dm_orig = ods.DataMatrix()
    dm_orig.name = "Measurement"
    dm_orig.base_name = "AoMeasurement"
    dm_orig.aid = 10

    col = dm_orig.columns.add()
    col.name = "SomeDouble"
    col.base_name = "some_double"
    col.data_type = ods.DataTypeEnum.DT_DOUBLE
    col.double_array.values.extend([1.0, float("nan"), 3.0])
    col.is_null.extend([False, True, False])

    dms = ods.DataMatrices()
    dms.matrices.add().CopyFrom(dm_orig)

    df = to_pandas(dms, is_null_to_nan=True)
    matrix_back = dataframe_to_datamatrix(df, simple_model)

    col_back = next(c for c in matrix_back.columns if c.name == "SomeDouble")
    assert list(col_back.is_null) == [False, True, False]
    assert col_back.double_array.values[0] == pytest.approx(1.0)
    assert col_back.double_array.values[2] == pytest.approx(3.0)


def test_roundtrip_merge_workflow(simple_model: ModelCache) -> None:
    """Build matrix incrementally via merge then verify full column set."""
    from odsbox.datamatrices_to_pandas import to_pandas

    dm = ods.DataMatrix()
    dm.name = "Measurement"
    dm.base_name = "AoMeasurement"
    dm.aid = 10

    df_ids = pd.DataFrame({"Measurement.Id": [10, 20, 30]})
    merge_into_datamatrix(dm, df_ids, simple_model)

    df_names = pd.DataFrame({"Measurement.Name": ["x", "y", "z"]})
    merge_into_datamatrix(dm, df_names, simple_model)

    assert len(dm.columns) == 2

    dms = ods.DataMatrices()
    dms.matrices.add().CopyFrom(dm)
    df = to_pandas(dms)

    assert list(df["Measurement.Id"]) == [10, 20, 30]
    assert list(df["Measurement.Name"]) == ["x", "y", "z"]
