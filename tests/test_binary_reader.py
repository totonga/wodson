"""Tests for binary reader with external .dat files."""

import odsbox.proto.ods_pb2 as ods
import pytest

from asamatfx.atfx import AtfxStore


@pytest.fixture
def common_store(common_typespecs_atfx):
    """Store for CommonTypespecs example (has .dat file)."""
    dat_file = common_typespecs_atfx.parent / "Example_CommonTypespecs.dat"
    if not dat_file.exists():
        pytest.skip("Binary .dat file not present")
    with AtfxStore(common_typespecs_atfx) as store:
        yield store


@pytest.fixture
def cast_store(cast_typespecs_atfx):
    """Store for CastTypespecs example (has .dat file)."""
    dat_file = cast_typespecs_atfx.parent / "Example_CastTypespecs.dat"
    if not dat_file.exists():
        pytest.skip("Binary .dat file not present")
    with AtfxStore(cast_typespecs_atfx) as store:
        yield store


def test_common_typespecs_model_loads(common_typespecs_atfx):
    """CommonTypespecs should load model even if .dat is missing."""
    dat_file = common_typespecs_atfx.parent / "Example_CommonTypespecs.dat"
    if not dat_file.exists():
        pytest.skip("Binary .dat file not present")
    with AtfxStore(common_typespecs_atfx) as store:
        model = store.model()
        assert len(model.entities) > 0


def test_common_typespecs_localcolumns(common_store):
    """Should have multiple local columns with binary data."""
    model = common_store.model()
    lc_entity = model.entities["Localcolumn"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=lc_entity.aid, attribute="Id")
    stmt.columns.add(aid=lc_entity.aid, attribute="Name")
    result = common_store.data_read(stmt)

    assert len(result.matrices) == 1
    matrix = result.matrices[0]
    name_col = next(c for c in matrix.columns if c.name == "Name")
    # Should have many local columns (one per typespec)
    assert len(name_col.string_array.values) > 10


def test_cast_typespecs_model_loads(cast_typespecs_atfx):
    """CastTypespecs should load model even if .dat is missing."""
    dat_file = cast_typespecs_atfx.parent / "Example_CastTypespecs.dat"
    if not dat_file.exists():
        pytest.skip("Binary .dat file not present")
    with AtfxStore(cast_typespecs_atfx) as store:
        model = store.model()
        assert len(model.entities) > 0


def test_common_typespecs_values_data_types(common_store):
    """UnknownArray.data_type for each Localcolumn.Values must match the binary typespec."""
    model = common_store.model()
    lc = model.entities["Localcolumn"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=lc.aid, attribute="Id")
    stmt.columns.add(aid=lc.aid, attribute="Values")
    result = common_store.data_read(stmt)

    matrix = result.matrices[0]
    id_col = next(c for c in matrix.columns if c.name == "Id")
    values_col = next(c for c in matrix.columns if c.name == "Values")

    id_to_dt: dict[int, int] = {}
    for i, iid in enumerate(id_col.longlong_array.values):
        ua = values_col.unknown_arrays.values[i]
        id_to_dt[int(iid)] = ua.data_type

    # Little-endian numeric types
    assert id_to_dt[251] == ods.DataTypeEnum.DT_BOOLEAN  # dt_boolean
    assert id_to_dt[252] == ods.DataTypeEnum.DT_BYTE  # dt_byte
    assert id_to_dt[253] == ods.DataTypeEnum.DT_SHORT  # dt_short
    assert id_to_dt[254] == ods.DataTypeEnum.DT_LONG  # dt_long
    assert id_to_dt[255] == ods.DataTypeEnum.DT_LONGLONG  # dt_longlong
    assert id_to_dt[256] == ods.DataTypeEnum.DT_FLOAT  # ieeefloat4
    assert id_to_dt[257] == ods.DataTypeEnum.DT_DOUBLE  # ieeefloat8
    assert id_to_dt[258] == ods.DataTypeEnum.DT_FLOAT  # ieeefloat4 (complex pairs stored as floats)
    assert id_to_dt[259] == ods.DataTypeEnum.DT_DOUBLE  # ieeefloat8 (dcomplex pairs stored as doubles)
    assert id_to_dt[260] == ods.DataTypeEnum.DT_STRING  # dt_string (dates)
    assert id_to_dt[261] == ods.DataTypeEnum.DT_STRING  # dt_string_utf8
    assert id_to_dt[262] == ods.DataTypeEnum.DT_BYTESTR  # dt_bytestr_leo
    # Big-endian numeric types
    assert id_to_dt[263] == ods.DataTypeEnum.DT_SHORT  # dt_short_beo
    assert id_to_dt[264] == ods.DataTypeEnum.DT_LONG  # dt_long_beo
    assert id_to_dt[265] == ods.DataTypeEnum.DT_LONGLONG  # dt_longlong_beo
    assert id_to_dt[266] == ods.DataTypeEnum.DT_FLOAT  # ieeefloat4_beo
    assert id_to_dt[267] == ods.DataTypeEnum.DT_DOUBLE  # ieeefloat8_beo
    assert id_to_dt[268] == ods.DataTypeEnum.DT_BYTESTR  # dt_bytestr_beo

    ids = list(id_col.longlong_array.values)

    # Spot-check values for DT_SHORT (little-endian): 10 20 30 -32768 32767
    ua_short = values_col.unknown_arrays.values[ids.index(253)]
    assert list(ua_short.long_array.values) == [10, 20, 30, -32768, 32767]

    # Spot-check values for DT_SHORT (big-endian): same values
    ua_short_beo = values_col.unknown_arrays.values[ids.index(263)]
    assert list(ua_short_beo.long_array.values) == [10, 20, 30, -32768, 32767]

    # Spot-check string values
    ua_str = values_col.unknown_arrays.values[ids.index(261)]
    assert list(ua_str.string_array.values) == ["val1", "val2", "val3", "val4", "val5"]

    # Spot-check bytestr values (little-endian)
    ua_bstr = values_col.unknown_arrays.values[ids.index(262)]
    assert ua_bstr.bytestr_array.values[0] == bytes([11, 0, 255, 73])
    assert ua_bstr.bytestr_array.values[1] == bytes([2, 4, 8, 16, 32, 64, 128])

    # Spot-check bytestr values (big-endian) — same data different encoding
    ua_bstr_beo = values_col.unknown_arrays.values[ids.index(268)]
    assert ua_bstr_beo.bytestr_array.values[0] == bytes([11, 0, 255, 73])
    assert ua_bstr_beo.bytestr_array.values[1] == bytes([2, 4, 8, 16, 32, 64, 128])


def test_cast_typespecs_values_data_types(cast_store):
    """UnknownArray.data_type and values for each CastTypespecs Localcolumn.Values."""
    model = cast_store.model()
    lc = model.entities["Localcolumn"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=lc.aid, attribute="Id")
    stmt.columns.add(aid=lc.aid, attribute="Values")
    result = cast_store.data_read(stmt)

    matrix = result.matrices[0]
    id_col = next(c for c in matrix.columns if c.name == "Id")
    values_col = next(c for c in matrix.columns if c.name == "Values")

    ids = list(id_col.longlong_array.values)

    def ua(iid: int):  # type: ignore[no-untyped-def]
        return values_col.unknown_arrays.values[ids.index(iid)]

    # --- Cast (non-bit) types ---

    # dt_sbyte: ASAM ODS has no signed-byte type, promoted to DT_SHORT
    assert ua(251).data_type == ods.DataTypeEnum.DT_SHORT
    assert list(ua(251).long_array.values) == [1, 2, 3, -128, 127]

    # dt_ushort: uint16 max 65535 overflows int16, promoted to DT_LONG
    assert ua(252).data_type == ods.DataTypeEnum.DT_LONG
    assert list(ua(252).long_array.values) == [10, 20, 30, 0, 65535]

    # dt_ulong: uint32 max overflows int32, promoted to DT_LONGLONG
    assert ua(253).data_type == ods.DataTypeEnum.DT_LONGLONG
    assert list(ua(253).longlong_array.values) == [100, 200, 300, 0, 4294967295]

    # --- LE bit-int: signed ---
    assert ua(254).data_type == ods.DataTypeEnum.DT_SHORT  # bc=3  → ≤16
    assert list(ua(254).long_array.values) == [1, 2, 3, -4, 3]

    assert ua(255).data_type == ods.DataTypeEnum.DT_SHORT  # bc=12 → ≤16
    assert list(ua(255).long_array.values) == [10, 20, 30, -2048, 2047]

    assert ua(256).data_type == ods.DataTypeEnum.DT_LONG  # bc=17 → ≤32
    assert list(ua(256).long_array.values) == [100, 200, 300, -65536, 65535]

    assert ua(257).data_type == ods.DataTypeEnum.DT_LONG  # bc=24, vpb=2
    assert list(ua(257).long_array.values) == [1000, 2000, 3000, -8388608, 8388607]

    assert ua(258).data_type == ods.DataTypeEnum.DT_LONGLONG  # bc=62 → >32
    assert list(ua(258).longlong_array.values) == [
        10000,
        20000,
        30000,
        -2305843009213693952,
        2305843009213693951,
    ]

    # --- LE bit-uint: unsigned ---
    assert ua(259).data_type == ods.DataTypeEnum.DT_BYTE  # bc=3  → ≤8
    assert list(ua(259).byte_array.values) == [1, 2, 3, 0, 7]

    assert ua(260).data_type == ods.DataTypeEnum.DT_SHORT  # bc=12 → ≤16
    assert list(ua(260).long_array.values) == [10, 20, 30, 0, 4095]

    assert ua(261).data_type == ods.DataTypeEnum.DT_LONG  # bc=17 → ≤32
    assert list(ua(261).long_array.values) == [100, 200, 300, 0, 131071]

    # --- LE bit-ieeefloat: bc=32 → DT_FLOAT ---
    assert ua(262).data_type == ods.DataTypeEnum.DT_FLOAT
    float_vals = list(ua(262).float_array.values)
    assert pytest.approx(float_vals[0], rel=1e-4) == 123.456
    assert pytest.approx(float_vals[1], rel=1e-4) == 789.012
    assert pytest.approx(float_vals[2], rel=1e-4) == -3333.0
    assert pytest.approx(float_vals[3], rel=1e-4) == 1.175494351e-38
    assert float_vals[4] == pytest.approx(3.402823466e38, rel=1e-6)

    # --- BEO variants: same logical values as their LE counterparts ---
    # BEO bit-int (bc=12, 17, 24, 62)
    assert ua(263).data_type == ods.DataTypeEnum.DT_SHORT
    assert list(ua(263).long_array.values) == [10, 20, 30, -2048, 2047]

    assert ua(264).data_type == ods.DataTypeEnum.DT_LONG
    assert list(ua(264).long_array.values) == [100, 200, 300, -65536, 65535]

    assert ua(265).data_type == ods.DataTypeEnum.DT_LONG
    assert list(ua(265).long_array.values) == [1000, 2000, 3000, -8388608, 8388607]

    assert ua(266).data_type == ods.DataTypeEnum.DT_LONGLONG
    assert list(ua(266).longlong_array.values) == [
        10000,
        20000,
        30000,
        -2305843009213693952,
        2305843009213693951,
    ]

    # BEO bit-uint (bc=12, 17)
    assert ua(267).data_type == ods.DataTypeEnum.DT_SHORT
    assert list(ua(267).long_array.values) == [10, 20, 30, 0, 4095]

    assert ua(268).data_type == ods.DataTypeEnum.DT_LONG
    assert list(ua(268).long_array.values) == [100, 200, 300, 0, 131071]

    # BEO bit-ieeefloat (bc=32)
    assert ua(269).data_type == ods.DataTypeEnum.DT_FLOAT
    beo_float_vals = list(ua(269).float_array.values)
    assert pytest.approx(beo_float_vals[0], rel=1e-4) == 123.456
    assert pytest.approx(beo_float_vals[1], rel=1e-4) == 789.012
    assert pytest.approx(beo_float_vals[2], rel=1e-4) == -3333.0
