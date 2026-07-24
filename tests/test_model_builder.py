"""Tests for the model builder module."""

import xml.etree.ElementTree as ET

import odsbox.proto.ods_pb2 as ods
import pytest

from wodson.atfx import AtfxStore
from wodson.atfx._base_model import load_base_model
from wodson.atfx._model_builder import build_model, detect_ods_version
from wodson.atfx._xml_utils import _extract_ns

pytest_plugins = ["tests._devtest_fixtures"]

pytestmark = pytest.mark.devtest


def test_simple_model_entity_count(simple_store):
    """Example_Simple should have 13 application elements."""
    model = simple_store.model()
    assert len(model.entities) == 13


def test_simple_model_entity_names(simple_store):
    """Verify key entity names are present."""
    model = simple_store.model()
    expected = {
        "Environment",
        "Test",
        "Subtest",
        "Measurement",
        "Measurementquantity",
        "Submatrix",
        "Localcolumn",
        "Quantity",
        "Unit",
        "Physicaldimension",
        "User",
        "Usergroup",
    }
    # Process is #12 but expected was listed without it
    actual = set(model.entities.keys())
    # The file also has "Process" as entity #12
    assert expected.issubset(actual)
    assert "Process" in actual


def test_simple_model_aids_sequential(simple_store):
    """AIDs should be sequential starting from 1."""
    model = simple_store.model()
    aids = sorted(model.entities[e].aid for e in model.entities)
    assert aids == list(range(1, len(aids) + 1))


def test_simple_model_base_names(simple_store):
    """Base type should be set from the ATFX basetype attribute."""
    model = simple_store.model()
    assert model.entities["Environment"].base_name == "AoEnvironment"
    assert model.entities["Measurement"].base_name == "AoMeasurement"
    assert model.entities["Localcolumn"].base_name == "AoLocalColumn"
    assert model.entities["Process"].base_name == "AoAny"


def test_simple_model_attributes(simple_store):
    """Verify attribute properties are correctly parsed."""
    model = simple_store.model()
    env = model.entities["Environment"]

    # Should have Id and Name attributes
    assert "Id" in env.attributes
    assert "Name" in env.attributes

    id_attr = env.attributes["Id"]
    assert id_attr.base_name == "id"
    assert id_attr.data_type == ods.DataTypeEnum.DT_LONGLONG
    assert id_attr.obligatory is True
    assert id_attr.unique is True

    name_attr = env.attributes["Name"]
    assert name_attr.base_name == "name"
    assert name_attr.data_type == ods.DataTypeEnum.DT_STRING


def test_simple_model_relations(simple_store):
    """Verify relations are correctly parsed."""
    model = simple_store.model()
    env = model.entities["Environment"]

    assert "Tests" in env.relations
    tests_rel = env.relations["Tests"]
    assert tests_rel.entity_name == "Test"
    assert tests_rel.range_min == 0
    assert tests_rel.range_max == -1
    assert tests_rel.inverse_name == "Environment"


def test_simple_model_enum(simple_store):
    """Application enumerations should be in the model."""
    model = simple_store.model()
    assert "TestResult" in model.enumerations
    tr = model.enumerations["TestResult"]
    assert tr.items["Failed"] == 0
    assert tr.items["Succeeded"] == 1
    assert tr.items["NotExecuted"] == 2


def test_simple_model_base_enums(simple_store):
    """Base model enumerations should also be present."""
    model = simple_store.model()
    assert "datatype_enum" in model.enumerations
    assert "seq_rep_enum" in model.enumerations
    assert "typespec_enum" in model.enumerations


def test_measurement_datatype_from_base_model(simple_store):
    """Attributes without explicit datatype should get it from base model."""
    model = simple_store.model()
    mea = model.entities["Measurement"]
    # StartTime maps to measurement_begin which is DT_DATE in base model
    assert "StartTime" in mea.attributes
    assert mea.attributes["StartTime"].data_type == ods.DataTypeEnum.DT_DATE


def test_localcolumn_values_attribute(simple_store):
    """LocalColumn should have a values attribute from base model."""
    model = simple_store.model()
    lc = model.entities["Localcolumn"]
    assert "Values" in lc.attributes


def test_relation_range_fallback_from_base_model():
    """range_min/range_max should be taken from the base model when XML omits min_occurs/max_occurs."""
    # AoMeasurement.test has rangeMin=1, rangeMax=1 in the base model
    xml_str = (
        '<atfx_file xmlns="http://www.asam.net/ODS/5.3.0/Schema">'
        "<application_model>"
        "<application_element>"
        "<name>Mea</name>"
        "<basetype>AoMeasurement</basetype>"
        "<relation_attribute>"
        "<name>Tst</name>"
        "<ref_to>Tst</ref_to>"
        "<base_relation>test</base_relation>"
        "<inverse_name>Measurements</inverse_name>"
        "</relation_attribute>"
        "</application_element>"
        "<application_element>"
        "<name>Tst</name>"
        "<basetype>AoTest</basetype>"
        "</application_element>"
        "</application_model>"
        "</atfx_file>"
    )
    root = ET.fromstring(xml_str)
    base_model = load_base_model()
    model = build_model(root, base_model)
    rel = model.entities["Mea"].relations["Tst"]
    assert rel.range_min == 1
    assert rel.range_max == 1


# ---- Unit tests for helpers ----


class TestExtractNs:
    def test_with_namespace(self):
        assert _extract_ns("{http://www.example.com}tag") == "http://www.example.com"

    def test_without_namespace(self):
        assert _extract_ns("tag") is None

    def test_empty_string(self):
        assert _extract_ns("") is None


class TestDetectOdsVersion:
    def test_valid_namespace(self):
        root = ET.fromstring('<root xmlns="http://www.asam.net/ODS/6.1.0/Schema"/>')
        assert detect_ods_version(root) == "6.1.0"

    def test_version_5_3(self):
        root = ET.fromstring('<root xmlns="http://www.asam.net/ODS/5.3/Schema"/>')
        assert detect_ods_version(root) == "5.3"

    def test_no_namespace(self):
        root = ET.fromstring("<root/>")
        assert detect_ods_version(root) == ""

    def test_unrelated_namespace(self):
        root = ET.fromstring('<root xmlns="http://www.example.com"/>')
        assert detect_ods_version(root) == ""


def test_relation_type_from_base_model(simple_store):
    """Relation types should be supplemented from base model."""
    model = simple_store.model()
    test_entity = model.entities["Test"]
    env_rel = test_entity.relations["Environment"]
    # AoTest.environment is a FATHER relation
    assert env_rel.relation_type == ods.Model.RelationTypeEnum.RT_FATHER_CHILD
    assert env_rel.relationship == ods.Model.RelationshipEnum.RS_FATHER


def test_all_example_files_load(spec_examples_dir):
    """All example ATFX files should load without error."""
    atfx_files = list(spec_examples_dir.glob("*.atfx"))
    assert len(atfx_files) == 7

    for atfx_file in atfx_files:
        with AtfxStore(atfx_file) as store:
            model = store.model()
            assert len(model.entities) > 0
