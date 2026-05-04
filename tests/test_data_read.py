"""Tests for data_read (SelectStatement -> SQL -> DataMatrices)."""

import math

import odsbox.proto.ods_pb2 as ods

from asamatfx import AtfxStore
from asamatfx._data_read import _extract_condition_values, _to_float


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
