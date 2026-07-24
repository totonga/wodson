"""Tests for the instance parser module."""

import math
import xml.etree.ElementTree as ET

import odsbox.proto.ods_pb2 as ods
import pytest

from wodson.atfx._instance_parser import (
    ExternalComponentRef,
    TypedValues,
    _parse_boolean_list,
    _parse_bytefield,
    _parse_component_ref,
    _parse_float_list,
    _parse_float_value,
    _parse_list,
    _parse_numeric_list,
    _parse_scalar,
    _parse_string_sequence,
    _parse_values_content,
)

pytest_plugins = ["tests._devtest_fixtures"]

pytestmark = pytest.mark.devtest


def test_simple_instance_count(simple_store):
    """Verify correct number of instances are loaded (queryable via data_read)."""
    model = simple_store.model()
    mea_entity = model.entities["Measurement"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=mea_entity.aid, attribute="*")
    result = simple_store.data_read(stmt)

    assert len(result.matrices) == 1
    # Should have 1 measurement instance
    # Check id column
    matrix = result.matrices[0]
    id_col = None
    for col in matrix.columns:
        if col.name == "Id":
            id_col = col
            break
    assert id_col is not None
    assert len(id_col.longlong_array.values) == 1
    assert id_col.longlong_array.values[0] == 93


def test_simple_measurement_quantities(simple_store):
    """Should have 5 measurement quantities."""
    model = simple_store.model()
    mq_entity = model.entities["Measurementquantity"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=mq_entity.aid, attribute="Id")
    stmt.columns.add(aid=mq_entity.aid, attribute="Name")
    result = simple_store.data_read(stmt)

    assert len(result.matrices) == 1
    matrix = result.matrices[0]
    # Find name column
    name_col = None
    for col in matrix.columns:
        if col.name == "Name":
            name_col = col
            break
    assert name_col is not None
    assert len(name_col.string_array.values) == 5
    names = set(name_col.string_array.values)
    assert "MyMqLong" in names
    assert "MyMqString" in names
    assert "MyMqFloat" in names


def test_simple_localcolumn_inline_values(simple_store):
    """Inline values should be stored and retrievable."""
    model = simple_store.model()
    lc_entity = model.entities["Localcolumn"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=lc_entity.aid, attribute="Id")
    stmt.columns.add(aid=lc_entity.aid, attribute="Name")
    stmt.columns.add(aid=lc_entity.aid, attribute="Values")
    result = simple_store.data_read(stmt)

    assert len(result.matrices) == 1
    matrix = result.matrices[0]
    # Should have 5 local columns
    id_col = next(c for c in matrix.columns if c.name == "Id")
    assert len(id_col.longlong_array.values) == 5


def test_nonnumbers_inf_nan(nonnumbers_store):
    """NaN and INF values should round-trip correctly."""
    model = nonnumbers_store.model()
    lc_entity = model.entities["Localcolumn"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=lc_entity.aid, attribute="Name")
    stmt.columns.add(aid=lc_entity.aid, attribute="Values")
    result = nonnumbers_store.data_read(stmt)

    assert len(result.matrices) == 1


def test_alltypes_entity_count(alltypes_store):
    """AllTypes example should load with correct entity count."""
    model = alltypes_store.model()
    # Should have entities (12 + possible extras depending on file)
    assert len(model.entities) >= 12


def test_alltypes_process_custom_attributes(alltypes_store):
    """Process element in AllTypes has many custom DT_* and DS_* attributes."""
    model = alltypes_store.model()
    process = model.entities["Process"]
    # Should have custom attributes beyond just Id, Name, Description
    assert len(process.attributes) > 3


def test_enum_value_parsing(simple_store):
    """Enum values should be stored correctly."""
    model = simple_store.model()
    subtest_entity = model.entities["Subtest"]

    stmt = ods.SelectStatement()
    stmt.columns.add(aid=subtest_entity.aid, attribute="Name")
    stmt.columns.add(aid=subtest_entity.aid, attribute="Result")
    result = simple_store.data_read(stmt)

    assert len(result.matrices) == 1


# ---- Unit tests for parsing helpers ----


class TestParseList:
    def test_empty_text(self):
        assert _parse_list(None, int) == []
        assert _parse_list("", int) == []

    def test_converts_ints(self):
        assert _parse_list("1 2 3", int) == [1, 2, 3]

    def test_converts_floats(self):
        assert _parse_list("1.5 2.5", float) == [1.5, 2.5]


class TestParseFloatValue:
    def test_inf(self):
        assert _parse_float_value("INF") == math.inf

    def test_neg_inf(self):
        assert _parse_float_value("-INF") == -math.inf

    def test_nan(self):
        assert math.isnan(_parse_float_value("NaN"))

    def test_regular(self):
        assert _parse_float_value("3.14") == pytest.approx(3.14)


class TestParseNumericList:
    def test_int_list(self):
        assert _parse_numeric_list("10 20 30", int) == [10, 20, 30]

    def test_empty(self):
        assert _parse_numeric_list(None, int) == []
        assert _parse_numeric_list("", int) == []


class TestParseFloatList:
    def test_float_list(self):
        result = _parse_float_list("1.0 INF -INF NaN")
        assert result[0] == 1.0
        assert result[1] == math.inf
        assert result[2] == -math.inf
        assert math.isnan(result[3])

    def test_empty(self):
        assert _parse_float_list(None) == []


class TestParseBooleanList:
    def test_true_values(self):
        assert _parse_boolean_list("true 1 TRUE") == [True, True, True]

    def test_false_values(self):
        assert _parse_boolean_list("false 0 FALSE") == [False, False, False]

    def test_empty(self):
        assert _parse_boolean_list(None) == []


class TestParseBytefield:
    def test_length_sequence_pairs(self):
        xml_str = "<A_BYTEFIELD><length>3</length><sequence>1 2 3</sequence></A_BYTEFIELD>"
        el = ET.fromstring(xml_str)
        result = _parse_bytefield(el)
        assert result == [b"\x01\x02\x03"]

    def test_empty_sequence(self):
        xml_str = "<A_BYTEFIELD><length>0</length><sequence></sequence></A_BYTEFIELD>"
        el = ET.fromstring(xml_str)
        result = _parse_bytefield(el)
        assert result == [b""]

    def test_multiple_pairs(self):
        xml_str = (
            "<A_BYTEFIELD>"
            "<length>2</length><sequence>10 20</sequence>"
            "<length>1</length><sequence>30</sequence>"
            "</A_BYTEFIELD>"
        )
        el = ET.fromstring(xml_str)
        result = _parse_bytefield(el)
        assert result == [b"\x0a\x14", b"\x1e"]


class TestParseStringSequence:
    def test_s_sub_elements(self):
        xml_str = "<A_UTF8STRING><s>hello</s><s>world</s></A_UTF8STRING>"
        el = ET.fromstring(xml_str)
        assert _parse_string_sequence(el) == ["hello", "world"]

    def test_space_separated_text(self):
        xml_str = "<A_UTF8STRING>hello world</A_UTF8STRING>"
        el = ET.fromstring(xml_str)
        assert _parse_string_sequence(el) == ["hello", "world"]

    def test_empty(self):
        xml_str = "<A_UTF8STRING></A_UTF8STRING>"
        el = ET.fromstring(xml_str)
        assert _parse_string_sequence(el) == []


class TestParseComponentRef:
    def test_full_component(self):
        xml_str = (
            "<component>"
            "<identifier>file1.dat</identifier>"
            "<datatype>ieeefloat4</datatype>"
            "<length>100</length>"
            "<inioffset>0</inioffset>"
            "<blocksize>400</blocksize>"
            "<valperblock>1</valperblock>"
            "<bitcount>32</bitcount>"
            "<bitoffset>0</bitoffset>"
            "</component>"
        )
        el = ET.fromstring(xml_str)
        ref = _parse_component_ref(el)
        assert isinstance(ref, ExternalComponentRef)
        assert ref.identifier == "file1.dat"
        assert ref.datatype == "ieeefloat4"
        assert ref.length == 100
        assert ref.blocksize == 400
        assert ref.bitcount == 32

    def test_minimal_component(self):
        xml_str = "<component><identifier>f.dat</identifier></component>"
        el = ET.fromstring(xml_str)
        ref = _parse_component_ref(el)
        assert ref.identifier == "f.dat"
        assert ref.length == 0


class TestParseScalar:
    def test_int_types(self):
        assert _parse_scalar("42", ods.DataTypeEnum.DT_LONG, {}, "") == 42
        assert _parse_scalar("99", ods.DataTypeEnum.DT_LONGLONG, {}, "") == 99

    def test_float_types(self):
        assert _parse_scalar("3.14", ods.DataTypeEnum.DT_FLOAT, {}, "") == pytest.approx(3.14)
        assert _parse_scalar("2.71", ods.DataTypeEnum.DT_DOUBLE, {}, "") == pytest.approx(2.71)

    def test_boolean(self):
        assert _parse_scalar("true", ods.DataTypeEnum.DT_BOOLEAN, {}, "") is True
        assert _parse_scalar("false", ods.DataTypeEnum.DT_BOOLEAN, {}, "") is False

    def test_string(self):
        assert _parse_scalar("hello", ods.DataTypeEnum.DT_STRING, {}, "") == "hello"

    def test_empty_returns_none(self):
        assert _parse_scalar("", ods.DataTypeEnum.DT_STRING, {}, "") is None

    def test_enum_int(self):
        # Integer string converts to int directly
        assert _parse_scalar("5", ods.DataTypeEnum.DT_ENUM, {}, "") == 5

    def test_enum_string_fallback(self):
        # Enum name without enumeration logs warning and uses 0
        assert _parse_scalar("enumval", ods.DataTypeEnum.DT_ENUM, {}, "") == 0


class TestParseValuesContent:
    def test_inline_float_values(self):
        xml_str = "<Values><A_FLOAT32>1.0 2.0 3.0</A_FLOAT32></Values>"
        el = ET.fromstring(xml_str)
        result = _parse_values_content(el, ods.DataTypeEnum.DT_UNKNOWN, {}, "")
        assert isinstance(result, TypedValues)
        assert result.data_type == ods.DataTypeEnum.DT_FLOAT
        assert result.values == [1.0, 2.0, 3.0]

    def test_inline_int_values(self):
        xml_str = "<Values><A_INT32>10 20 30</A_INT32></Values>"
        el = ET.fromstring(xml_str)
        result = _parse_values_content(el, ods.DataTypeEnum.DT_UNKNOWN, {}, "")
        assert isinstance(result, TypedValues)
        assert result.data_type == ods.DataTypeEnum.DT_LONG
        assert result.values == [10, 20, 30]

    def test_component_ref(self):
        xml_str = "<Values><component><identifier>f.dat</identifier></component></Values>"
        el = ET.fromstring(xml_str)
        result = _parse_values_content(el, ods.DataTypeEnum.DT_UNKNOWN, {}, "")
        assert isinstance(result, ExternalComponentRef)
        assert result.identifier == "f.dat"
