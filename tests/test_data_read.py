"""Tests for data_read (SelectStatement -> SQL -> DataMatrices)."""

import math
from pathlib import Path

import odsbox.proto.ods_pb2 as ods
import pytest

from wodson.atfx import AtfxStore
from wodson.atfx._data_read import _extract_condition_values, _to_float

pytestmark = pytest.mark.devtest

_OPENATFX_DIR = Path(__file__).resolve().parent / "data" / "openatfx"


def test_simple_query_all_measurements(simple_store):
    """Query all measurements with wildcard."""
    model = simple_store.model()
    mea = model.entities["Measurement"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=mea.aid, attribute="*")
    result = simple_store.data_read(stmt)

    assert len(result.matrices) == 1
    assert result.matrices[0].aid == mea.aid
    assert result.matrices[0].name == "Measurement"
    assert result.matrices[0].base_name == "AoMeasurement"


def test_query_specific_attributes(simple_store):
    """Query specific attributes only."""
    model = simple_store.model()
    mea = model.entities["Measurement"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=mea.aid, attribute="Id")
    stmt.columns.add(aid=mea.aid, attribute="Name")
    result = simple_store.data_read(stmt)

    assert len(result.matrices) == 1
    matrix = result.matrices[0]
    assert len(matrix.columns) == 2

    id_col = matrix.columns[0]
    assert id_col.name == "Id"
    assert id_col.longlong_array.values[0] == 93

    name_col = matrix.columns[1]
    assert name_col.name == "Name"
    assert name_col.string_array.values[0] == "MyMeasurement"


def test_query_with_condition_eq(simple_store):
    """Query with equality condition."""
    model = simple_store.model()
    mq = model.entities["Measurementquantity"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=mq.aid, attribute="Id")
    stmt.columns.add(aid=mq.aid, attribute="Name")

    # Add condition: Name = "MyMqFloat"
    cond_item = stmt.where.add()
    cond_item.condition.aid = mq.aid
    cond_item.condition.attribute = "Name"
    cond_item.condition.operator = ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_EQ
    cond_item.condition.string_array.values.append("MyMqFloat")

    result = simple_store.data_read(stmt)
    matrix = result.matrices[0]
    name_col = next(c for c in matrix.columns if c.name == "Name")
    assert len(name_col.string_array.values) == 1
    assert name_col.string_array.values[0] == "MyMqFloat"


def test_query_with_condition_like(simple_store):
    """Query with LIKE condition."""
    model = simple_store.model()
    mq = model.entities["Measurementquantity"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=mq.aid, attribute="Name")

    cond_item = stmt.where.add()
    cond_item.condition.aid = mq.aid
    cond_item.condition.attribute = "Name"
    cond_item.condition.operator = ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_LIKE
    cond_item.condition.string_array.values.append("MyMq%")

    result = simple_store.data_read(stmt)
    matrix = result.matrices[0]
    name_col = next(c for c in matrix.columns if c.name == "Name")
    assert len(name_col.string_array.values) == 5


def test_query_with_condition_inset(simple_store):
    """Query with INSET condition."""
    model = simple_store.model()
    mq = model.entities["Measurementquantity"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=mq.aid, attribute="Name")

    cond_item = stmt.where.add()
    cond_item.condition.aid = mq.aid
    cond_item.condition.attribute = "Id"
    cond_item.condition.operator = ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_INSET
    cond_item.condition.longlong_array.values.extend([94, 95])

    result = simple_store.data_read(stmt)
    matrix = result.matrices[0]
    name_col = next(c for c in matrix.columns if c.name == "Name")
    assert len(name_col.string_array.values) == 2


def test_query_with_row_limit(simple_store):
    """Query with row limit."""
    model = simple_store.model()
    mq = model.entities["Measurementquantity"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=mq.aid, attribute="Name")
    stmt.row_limit = 2

    result = simple_store.data_read(stmt)
    matrix = result.matrices[0]
    name_col = next(c for c in matrix.columns if c.name == "Name")
    assert len(name_col.string_array.values) == 2


def test_query_with_order_by(simple_store):
    """Query with ordering."""
    model = simple_store.model()
    mq = model.entities["Measurementquantity"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=mq.aid, attribute="Name")
    stmt.order_by.add(
        aid=mq.aid,
        attribute="Name",
        order=ods.SelectStatement.OrderByItem.OrderEnum.OD_ASCENDING,
    )

    result = simple_store.data_read(stmt)
    matrix = result.matrices[0]
    name_col = next(c for c in matrix.columns if c.name == "Name")
    names = list(name_col.string_array.values)
    assert names == sorted(names)


def test_query_with_join(simple_store):
    """Query with a join across entities."""
    model = simple_store.model()
    mea = model.entities["Measurement"]
    subtest = model.entities["Subtest"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=mea.aid, attribute="Name")
    stmt.columns.add(aid=subtest.aid, attribute="Name")

    # Join Measurement -> Subtest via "Subtest" relation
    stmt.joins.add(
        aid_from=mea.aid,
        aid_to=subtest.aid,
        relation="Subtest",
        join_type=ods.SelectStatement.JoinItem.JoinTypeEnum.JT_DEFAULT,
    )

    result = simple_store.data_read(stmt)
    assert len(result.matrices) == 2

    mea_matrix = next(m for m in result.matrices if m.name == "Measurement")
    sub_matrix = next(m for m in result.matrices if m.name == "Subtest")

    mea_names = mea_matrix.columns[0].string_array.values
    sub_names = sub_matrix.columns[0].string_array.values

    assert len(mea_names) == 1
    assert mea_names[0] == "MyMeasurement"
    assert len(sub_names) == 1
    assert sub_names[0] == "MySubtest"


def test_query_aggregate_count(simple_store):
    """Query with COUNT aggregate."""
    model = simple_store.model()
    mq = model.entities["Measurementquantity"]

    stmt = ods.SelectStatement()
    stmt.columns.add(
        aid=mq.aid,
        attribute="Id",
        aggregate=ods.AggregateEnum.AG_COUNT,
    )

    result = simple_store.data_read(stmt)
    matrix = result.matrices[0]
    count_col = matrix.columns[0]
    # COUNT should return 5
    assert count_col.longlong_array.values[0] == 5


def test_empty_select_statement(simple_store):
    """Empty select statement returns empty DataMatrices."""
    stmt = ods.SelectStatement()
    result = simple_store.data_read(stmt)
    assert len(result.matrices) == 0


def test_query_users(simple_store):
    """Query users in simple example."""
    model = simple_store.model()
    user = model.entities["User"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=user.aid, attribute="Id")
    stmt.columns.add(aid=user.aid, attribute="Name")
    result = simple_store.data_read(stmt)

    matrix = result.matrices[0]
    name_col = next(c for c in matrix.columns if c.name == "Name")
    names = list(name_col.string_array.values)
    assert "Peter Sellers" in names
    assert "Todd Martin" in names


def test_alltypes_values_unknown_array_dtypes(alltypes_store):
    """Values column of Localcolumn carries correct UnknownArray.data_type per XML tag."""
    model = alltypes_store.model()
    lc = model.entities["Localcolumn"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=lc.aid, attribute="Id")
    stmt.columns.add(aid=lc.aid, attribute="Values")
    result = alltypes_store.data_read(stmt)

    matrix = result.matrices[0]
    id_col = next(c for c in matrix.columns if c.name == "Id")
    values_col = next(c for c in matrix.columns if c.name == "Values")

    id_to_dt: dict[int, int] = {}
    for i, iid in enumerate(id_col.longlong_array.values):
        ua = values_col.unknown_arrays.values[i]
        id_to_dt[int(iid)] = ua.data_type

    # Each XML tag must map to the right ODS DataTypeEnum
    assert id_to_dt[251] == ods.DataTypeEnum.DT_BOOLEAN  # A_BOOLEAN
    assert id_to_dt[252] == ods.DataTypeEnum.DT_BYTE  # A_INT8
    assert id_to_dt[253] == ods.DataTypeEnum.DT_SHORT  # A_INT16
    assert id_to_dt[254] == ods.DataTypeEnum.DT_LONG  # A_INT32
    assert id_to_dt[255] == ods.DataTypeEnum.DT_LONGLONG  # A_INT64
    assert id_to_dt[256] == ods.DataTypeEnum.DT_FLOAT  # A_FLOAT32
    assert id_to_dt[257] == ods.DataTypeEnum.DT_DOUBLE  # A_FLOAT64
    assert id_to_dt[258] == ods.DataTypeEnum.DT_COMPLEX  # A_COMPLEX32
    assert id_to_dt[259] == ods.DataTypeEnum.DT_DCOMPLEX  # A_COMPLEX64
    assert id_to_dt[260] == ods.DataTypeEnum.DT_DATE  # A_TIMESTRING
    assert id_to_dt[261] == ods.DataTypeEnum.DT_STRING  # A_UTF8STRING
    assert id_to_dt[262] == ods.DataTypeEnum.DT_BYTESTR  # A_BYTEFIELD

    ids = list(id_col.longlong_array.values)

    # Spot-check boolean values
    ua_bool = values_col.unknown_arrays.values[ids.index(251)]
    assert list(ua_bool.boolean_array.values) == [True, False, True, False, True]

    # Spot-check byte values (DT_BYTE → byte_array)
    ua_byte = values_col.unknown_arrays.values[ids.index(252)]
    assert ua_byte.byte_array.values == bytes([1, 2, 3, 0, 255])

    # Spot-check string values
    ua_str = values_col.unknown_arrays.values[ids.index(261)]
    assert list(ua_str.string_array.values) == ["val1", "val2", "val3", "val4", "val5"]

    # Spot-check bytestr values (A_BYTEFIELD → DT_BYTESTR → bytestr_array)
    ua_bstr = values_col.unknown_arrays.values[ids.index(262)]
    assert ua_bstr.bytestr_array.values[0] == bytes([11, 0, 255, 73])
    assert ua_bstr.bytestr_array.values[1] == bytes([2, 4, 8, 16, 32, 64, 128])


def test_nonnumbers_process_attributes(nonnumbers_atfx):
    """Process scalar and sequence float attributes accept -INF, INF, NaN."""
    with AtfxStore(nonnumbers_atfx) as store:
        model = store.model()
        proc = model.entities["Process"]

        stmt = ods.SelectStatement()
        stmt.columns.add(aid=proc.aid, attribute="AA_DT_FLOAT")
        stmt.columns.add(aid=proc.aid, attribute="AA_DT_DOUBLE")
        stmt.columns.add(aid=proc.aid, attribute="AA_DT_COMPLEX")
        stmt.columns.add(aid=proc.aid, attribute="AA_DT_DCOMPLEX")
        stmt.columns.add(aid=proc.aid, attribute="AA_DS_FLOAT")
        stmt.columns.add(aid=proc.aid, attribute="AA_DS_DOUBLE")
        stmt.columns.add(aid=proc.aid, attribute="AA_DS_COMPLEX")
        stmt.columns.add(aid=proc.aid, attribute="AA_DS_DCOMPLEX")
        result = store.data_read(stmt)

        m = result.matrices[0]

        def col(name: str):  # type: ignore[no-untyped-def]
            return next(c for c in m.columns if c.name == name)

        # Scalar DT_FLOAT: AA_DT_FLOAT = -INF
        f32 = list(col("AA_DT_FLOAT").float_array.values)
        assert len(f32) == 1
        assert math.isinf(f32[0]) and f32[0] < 0

        # Scalar DT_DOUBLE: AA_DT_DOUBLE = -INF
        f64 = list(col("AA_DT_DOUBLE").double_array.values)
        assert len(f64) == 1
        assert math.isinf(f64[0]) and f64[0] < 0

        # Scalar DT_COMPLEX (2 floats): AA_DT_COMPLEX = -INF INF
        cx32 = list(col("AA_DT_COMPLEX").float_array.values)
        assert len(cx32) == 2
        assert math.isinf(cx32[0]) and cx32[0] < 0
        assert math.isinf(cx32[1]) and cx32[1] > 0

        # Scalar DT_DCOMPLEX (2 doubles): AA_DT_DCOMPLEX = -INF INF
        cx64 = list(col("AA_DT_DCOMPLEX").double_array.values)
        assert len(cx64) == 2
        assert math.isinf(cx64[0]) and cx64[0] < 0
        assert math.isinf(cx64[1]) and cx64[1] > 0

        # Sequence DS_FLOAT: AA_DS_FLOAT = -INF INF NaN
        ds_f32 = list(col("AA_DS_FLOAT").float_arrays.values[0].values)
        assert len(ds_f32) == 3
        assert math.isinf(ds_f32[0]) and ds_f32[0] < 0
        assert math.isinf(ds_f32[1]) and ds_f32[1] > 0
        assert math.isnan(ds_f32[2])

        # Sequence DS_DOUBLE: AA_DS_DOUBLE = -INF INF NaN
        ds_f64 = list(col("AA_DS_DOUBLE").double_arrays.values[0].values)
        assert len(ds_f64) == 3
        assert math.isinf(ds_f64[0]) and ds_f64[0] < 0
        assert math.isinf(ds_f64[1]) and ds_f64[1] > 0
        assert math.isnan(ds_f64[2])

        # Sequence DS_COMPLEX (6 floats = 3 complex pairs): AA_DS_COMPLEX = -INF -INF INF INF NaN NaN
        ds_cx32 = list(col("AA_DS_COMPLEX").float_arrays.values[0].values)
        assert len(ds_cx32) == 6
        assert math.isinf(ds_cx32[0]) and ds_cx32[0] < 0
        assert math.isinf(ds_cx32[2]) and ds_cx32[2] > 0
        assert math.isnan(ds_cx32[4])

        # Sequence DS_DCOMPLEX (6 doubles = 3 complex pairs): AA_DS_DCOMPLEX = -INF -INF INF INF NaN NaN
        ds_cx64 = list(col("AA_DS_DCOMPLEX").double_arrays.values[0].values)
        assert len(ds_cx64) == 6
        assert math.isinf(ds_cx64[0]) and ds_cx64[0] < 0
        assert math.isinf(ds_cx64[2]) and ds_cx64[2] > 0
        assert math.isnan(ds_cx64[4])


def test_nonnumbers_localcolumn_values(nonnumbers_atfx):
    """Localcolumn Values with -INF/INF/NaN are preserved through DT_UNKNOWN pipeline."""
    with AtfxStore(nonnumbers_atfx) as store:
        model = store.model()
        lc = model.entities["Localcolumn"]

        stmt = ods.SelectStatement()
        stmt.columns.add(aid=lc.aid, attribute="Id")
        stmt.columns.add(aid=lc.aid, attribute="Values")
        result = store.data_read(stmt)

        m = result.matrices[0]
        id_col = next(c for c in m.columns if c.name == "Id")
        values_col = next(c for c in m.columns if c.name == "Values")
        ids = list(id_col.longlong_array.values)

        def ua(iid: int):  # type: ignore[no-untyped-def]
            return values_col.unknown_arrays.values[ids.index(iid)]

        # lc 251: A_FLOAT32 → DT_FLOAT, values: -INF INF NaN
        ua251 = ua(251)
        assert ua251.data_type == ods.DataTypeEnum.DT_FLOAT
        f32 = list(ua251.float_array.values)
        assert len(f32) == 3
        assert math.isinf(f32[0]) and f32[0] < 0
        assert math.isinf(f32[1]) and f32[1] > 0
        assert math.isnan(f32[2])

        # lc 252: A_FLOAT64 → DT_DOUBLE, values: -INF INF NaN
        ua252 = ua(252)
        assert ua252.data_type == ods.DataTypeEnum.DT_DOUBLE
        f64 = list(ua252.double_array.values)
        assert len(f64) == 3
        assert math.isinf(f64[0]) and f64[0] < 0
        assert math.isinf(f64[1]) and f64[1] > 0
        assert math.isnan(f64[2])

        # lc 253: A_COMPLEX32 → DT_COMPLEX (6 floats = 3 pairs), values: (-INF -INF) (INF INF) (NaN NaN)
        ua253 = ua(253)
        assert ua253.data_type == ods.DataTypeEnum.DT_COMPLEX
        cx32 = list(ua253.float_array.values)
        assert len(cx32) == 6
        assert math.isinf(cx32[0]) and cx32[0] < 0
        assert math.isinf(cx32[2]) and cx32[2] > 0
        assert math.isnan(cx32[4])

        # lc 254: A_COMPLEX64 → DT_DCOMPLEX (6 doubles = 3 pairs), values: (-INF -INF) (INF INF) (NaN NaN)
        ua254 = ua(254)
        assert ua254.data_type == ods.DataTypeEnum.DT_DCOMPLEX
        cx64 = list(ua254.double_array.values)
        assert len(cx64) == 6
        assert math.isinf(cx64[0]) and cx64[0] < 0
        assert math.isinf(cx64[2]) and cx64[2] > 0
        assert math.isnan(cx64[4])


def test_common_typespecs_localcolumn_values():
    """Example_CommonTypespecs.atfx (openatfx corpus): all 18 explicit LocalColumns
    covering every common binary encoding must load non-empty values with correct
    data types and spot-check first values.
    """
    atfx_path = _OPENATFX_DIR / "Example_CommonTypespecs.atfx"
    with AtfxStore(atfx_path) as store:
        model = store.model()
        lc_ent = model.entities["Localcolumn"]

        stmt = ods.SelectStatement()
        stmt.columns.add(aid=lc_ent.aid, attribute="Id")
        stmt.columns.add(aid=lc_ent.aid, attribute="Name")
        stmt.columns.add(aid=lc_ent.aid, attribute="Values")
        result = store.data_read(stmt)

        m = result.matrices[0]
        _id_col = next(c for c in m.columns if c.name == "Id")
        name_col = next(c for c in m.columns if c.name == "Name")
        values_col = next(c for c in m.columns if c.name == "Values")

        names = list(name_col.string_array.values)
        # Every LC must have a populated UnknownArray entry
        assert len(values_col.unknown_arrays.values) == len(names), (
            "Number of value sub-arrays does not match number of LocalColumns"
        )

        def ua(lc_name: str):  # type: ignore[no-untyped-def]
            return values_col.unknown_arrays.values[names.index(lc_name)]

        # --- Boolean ---
        ua_bool = ua("MyMqBoolean")
        assert ua_bool.data_type == ods.DataTypeEnum.DT_BOOLEAN
        assert list(ua_bool.boolean_array.values)[:3] == [True, True, True]

        # --- Byte ---
        ua_byte = ua("MyMqByte")
        assert ua_byte.data_type == ods.DataTypeEnum.DT_BYTE
        raw = ua_byte.byte_array.values
        assert raw[0] == 1 and raw[1] == 2 and raw[2] == 3
        assert raw[-1] == 255  # unsigned 0xFF

        # --- Short (little-endian) → stored in long_array ---
        ua_short = ua("MyMqShort")
        assert ua_short.data_type == ods.DataTypeEnum.DT_SHORT
        assert list(ua_short.long_array.values)[:3] == [10, 20, 30]

        # --- Long (little-endian) ---
        ua_long = ua("MyMqLong")
        assert ua_long.data_type == ods.DataTypeEnum.DT_LONG
        assert list(ua_long.long_array.values)[:3] == [100, 200, 300]

        # --- Longlong (little-endian) ---
        ua_ll = ua("MyMqLonglong")
        assert ua_ll.data_type == ods.DataTypeEnum.DT_LONGLONG
        assert list(ua_ll.longlong_array.values)[:3] == [1000, 2000, 3000]

        # --- Float (little-endian) ---
        ua_float = ua("MyMqFloat")
        assert ua_float.data_type == ods.DataTypeEnum.DT_FLOAT
        f32 = list(ua_float.float_array.values)
        assert math.isclose(f32[0], 123.456, rel_tol=1e-4)
        assert math.isclose(f32[1], 789.012, rel_tol=1e-4)
        assert math.isclose(f32[2], -3333.0, rel_tol=1e-4)

        # --- Double (little-endian) ---
        ua_double = ua("MyMqDouble")
        assert ua_double.data_type == ods.DataTypeEnum.DT_DOUBLE
        f64 = list(ua_double.double_array.values)
        assert math.isclose(f64[0], 456.789012, rel_tol=1e-6)
        assert math.isclose(f64[1], 345.678901, rel_tol=1e-6)
        assert math.isclose(f64[2], -6666666.0, rel_tol=1e-6)

        # --- Complex (little-endian) — stored as interleaved float pairs (DT_FLOAT) ---
        ua_cx = ua("MyMqComplex")
        assert ua_cx.data_type == ods.DataTypeEnum.DT_FLOAT
        cx = list(ua_cx.float_array.values)
        assert math.isclose(cx[0], 1.1, rel_tol=1e-4)  # real part of first pair
        assert math.isclose(cx[1], 0.1, rel_tol=1e-4)  # imag part of first pair

        # --- Dcomplex (little-endian) — stored as interleaved double pairs (DT_DOUBLE) ---
        ua_dcx = ua("MyMqDcomplex")
        assert ua_dcx.data_type == ods.DataTypeEnum.DT_DOUBLE
        dcx = list(ua_dcx.double_array.values)
        assert math.isclose(dcx[0], 1.11, rel_tol=1e-8)
        assert math.isclose(dcx[1], 0.11, rel_tol=1e-8)

        # --- Date — stored as DT_STRING in this file ---
        ua_date = ua("MyMqDate")
        assert ua_date.data_type in (ods.DataTypeEnum.DT_DATE, ods.DataTypeEnum.DT_STRING)
        dates = list(ua_date.string_array.values)
        assert dates[0] == "20050130121532123789"

        # --- String ---
        ua_str = ua("MyMqString")
        assert ua_str.data_type == ods.DataTypeEnum.DT_STRING
        assert list(ua_str.string_array.values)[:3] == ["val1", "val2", "val3"]

        # --- Big-endian variants must match their little-endian counterparts ---
        for le_name, be_name in (
            ("MyMqShort", "MyMqShortBeo"),
            ("MyMqLong", "MyMqLongBeo"),
            ("MyMqLonglong", "MyMqLonglongBeo"),
            ("MyMqFloat", "MyMqFloatBeo"),
            ("MyMqDouble", "MyMqDoubleBeo"),
        ):
            ua_le = ua(le_name)
            ua_be = ua(be_name)
            assert ua_be.data_type == ua_le.data_type, (
                f"{be_name} data_type {ua_be.data_type} != {le_name} data_type {ua_le.data_type}"
            )
            if ua_le.data_type == ods.DataTypeEnum.DT_FLOAT:
                le_vals = list(ua_le.float_array.values)
                be_vals = list(ua_be.float_array.values)
            elif ua_le.data_type == ods.DataTypeEnum.DT_DOUBLE:
                le_vals = list(ua_le.double_array.values)
                be_vals = list(ua_be.double_array.values)
            elif ua_le.data_type in (ods.DataTypeEnum.DT_SHORT, ods.DataTypeEnum.DT_LONG):
                le_vals = list(ua_le.long_array.values)
                be_vals = list(ua_be.long_array.values)
            elif ua_le.data_type == ods.DataTypeEnum.DT_LONGLONG:
                le_vals = list(ua_le.longlong_array.values)
                be_vals = list(ua_be.longlong_array.values)
            else:
                continue
            assert len(le_vals) == len(be_vals), f"{be_name} length {len(be_vals)} != {le_name} length {len(le_vals)}"
            for j, (lv, bv) in enumerate(zip(le_vals, be_vals)):
                assert math.isclose(lv, bv, rel_tol=1e-5, abs_tol=1e-10), f"{be_name}[{j}]={bv} != {le_name}[{j}]={lv}"


def test_example_atfx_localcolumn_values():
    """tests/data/openatfx/example.atfx (PAK corpus): 17 LocalColumns with mixed
    explicit and external_component sequence representations.  Three channels
    reference truncated offsets in the binary and legitimately return empty values;
    the remaining 14 channels must have non-empty numeric data.
    """
    atfx_path = _OPENATFX_DIR / "example.atfx"
    with AtfxStore(atfx_path) as store:
        model = store.model()
        lc_ent = model.entities["lc"]

        id_attr = next(a for a, x in lc_ent.attributes.items() if x.base_name == "id")
        name_attr = next(a for a, x in lc_ent.attributes.items() if x.base_name == "name")
        sr_attr = next(
            (a for a, x in lc_ent.attributes.items() if x.base_name == "sequence_representation"),
            None,
        )
        val_attr = next(a for a, x in lc_ent.attributes.items() if x.base_name == "values")

        stmt = ods.SelectStatement()
        stmt.columns.add(aid=lc_ent.aid, attribute=id_attr)
        stmt.columns.add(aid=lc_ent.aid, attribute=name_attr)
        if sr_attr:
            stmt.columns.add(aid=lc_ent.aid, attribute=sr_attr)
        stmt.columns.add(aid=lc_ent.aid, attribute=val_attr)
        result = store.data_read(stmt)

        assert len(result.matrices) == 1
        m = result.matrices[0]
        id_col = next(c for c in m.columns if c.name == id_attr)
        name_col = next(c for c in m.columns if c.name == name_attr)
        sr_col = next((c for c in m.columns if c.name == sr_attr), None) if sr_attr else None
        val_col = next(c for c in m.columns if c.name == val_attr)

        ids = list(id_col.longlong_array.values)
        _names = list(name_col.string_array.values)
        srs = list(sr_col.string_array.values) if sr_col else ["explicit"] * len(ids)

        # Row counts must match
        assert len(ids) == 17
        assert len(val_col.unknown_arrays.values) == 17

        def ua(lc_id: int):  # type: ignore[no-untyped-def]
            return val_col.unknown_arrays.values[ids.index(lc_id)]

        # --- Channels with known truncated binary data return empty (acceptable) ---
        _TRUNCATED_IDS = {61, 72, 112}
        for lc_id in _TRUNCATED_IDS:
            assert ua(lc_id).WhichOneof("UnknownOneOf") is None, (
                f"lc_id={lc_id}: expected empty values for truncated channel"
            )

        # --- All other channels must have non-empty values ---
        for lc_id, sr in zip(ids, srs):
            if lc_id in _TRUNCATED_IDS:
                continue
            w = ua(lc_id).WhichOneof("UnknownOneOf")
            assert w is not None, f"lc_id={lc_id} sr={sr!r}: expected non-empty values"

        # --- Spot-checks ---
        # Time channel (lc=45): DT_DOUBLE, first value ≈ 4.6e-4 s
        ua_time = ua(45)
        assert ua_time.data_type == ods.DataTypeEnum.DT_DOUBLE
        t = list(ua_time.double_array.values)
        assert len(t) > 0
        assert math.isclose(t[0], 4.613e-4, rel_tol=1e-3)

        # LS.Right Side (lc=39): DT_FLOAT, explicit
        ua_ls = ua(39)
        assert ua_ls.data_type == ods.DataTypeEnum.DT_FLOAT
        ls = list(ua_ls.float_array.values)
        assert len(ls) > 0
        assert math.isclose(ls[0], 0.02715, rel_tol=1e-3)

        # signed_b (lc=115): external_component, DT_SHORT stored in long_array
        ua_sb = ua(115)
        assert ua_sb.data_type == ods.DataTypeEnum.DT_SHORT
        sb = list(ua_sb.long_array.values)
        assert sb[:3] == [1, 0, -1]

        # unsigned_b (lc=118): external_component, DT_BYTE stored in byte_array
        ua_ub = ua(118)
        assert ua_ub.data_type == ods.DataTypeEnum.DT_BYTE
        assert len(ua_ub.byte_array.values) > 0

        # All explicit channels must have the correct sequence representation
        _EXTERNAL_IDS = {115, 118}
        for lc_id, sr in zip(ids, srs):
            expected_sr = "external_component" if lc_id in _EXTERNAL_IDS else "explicit"
            assert sr == expected_sr, f"lc_id={lc_id}: expected sr={expected_sr!r}, got {sr!r}"


# ---- Unit tests for helpers ----


class TestToFloat:
    def test_none_returns_nan(self):
        assert math.isnan(_to_float(None))

    def test_int(self):
        assert _to_float(42) == 42.0

    def test_float(self):
        assert _to_float(3.14) == 3.14

    def test_string_number(self):
        assert _to_float("2.5") == 2.5


class TestExtractConditionValues:
    def test_string_array(self):
        cond = ods.SelectStatement.ConditionItem.Condition()
        cond.string_array.values.append("hello")
        assert _extract_condition_values(cond) == ["hello"]

    def test_longlong_array(self):
        cond = ods.SelectStatement.ConditionItem.Condition()
        cond.longlong_array.values.append(42)
        assert _extract_condition_values(cond) == [42]

    def test_float_array(self):
        cond = ods.SelectStatement.ConditionItem.Condition()
        cond.float_array.values.append(1.5)
        assert _extract_condition_values(cond) == [1.5]

    def test_double_array(self):
        cond = ods.SelectStatement.ConditionItem.Condition()
        cond.double_array.values.append(2.5)
        assert _extract_condition_values(cond) == [2.5]

    def test_boolean_array(self):
        cond = ods.SelectStatement.ConditionItem.Condition()
        cond.boolean_array.values.append(True)
        assert _extract_condition_values(cond) == [True]

    def test_empty_returns_empty(self):
        cond = ods.SelectStatement.ConditionItem.Condition()
        assert _extract_condition_values(cond) == []
