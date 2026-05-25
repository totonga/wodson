"""Tests for the base model loading module."""

from __future__ import annotations

import odsbox.proto.ods_pb2 as ods

from wodson.atfx._base_model import _parse_datatype, load_base_model


def test_load_base_model_returns_valid_model():
    bm = load_base_model()
    assert isinstance(bm, ods.BaseModel)
    assert bm.version != ""
    assert len(bm.entities) > 0
    assert len(bm.enumerations) > 0


def test_load_base_model_has_ao_environment():
    bm = load_base_model()
    assert "AoEnvironment" in bm.entities
    env = bm.entities["AoEnvironment"]
    assert env.name == "AoEnvironment"
    assert "name" in env.attributes
    assert "id" in env.attributes


def test_load_base_model_has_relations():
    bm = load_base_model()
    env = bm.entities["AoEnvironment"]
    assert len(env.relations) > 0


def test_parse_datatype_known_types():
    assert _parse_datatype("DT_STRING") == ods.DataTypeEnum.DT_STRING
    assert _parse_datatype("DT_LONGLONG") == ods.DataTypeEnum.DT_LONGLONG
    assert _parse_datatype("DT_FLOAT") == ods.DataTypeEnum.DT_FLOAT
    assert _parse_datatype("DT_DOUBLE") == ods.DataTypeEnum.DT_DOUBLE
    assert _parse_datatype("DT_BOOLEAN") == ods.DataTypeEnum.DT_BOOLEAN
    assert _parse_datatype("DT_BYTE") == ods.DataTypeEnum.DT_BYTE
    assert _parse_datatype("DT_SHORT") == ods.DataTypeEnum.DT_SHORT
    assert _parse_datatype("DT_LONG") == ods.DataTypeEnum.DT_LONG
    assert _parse_datatype("DT_DATE") == ods.DataTypeEnum.DT_DATE
    assert _parse_datatype("DT_BYTESTR") == ods.DataTypeEnum.DT_BYTESTR
    assert _parse_datatype("DT_BLOB") == ods.DataTypeEnum.DT_BLOB
    assert _parse_datatype("DT_COMPLEX") == ods.DataTypeEnum.DT_COMPLEX
    assert _parse_datatype("DT_DCOMPLEX") == ods.DataTypeEnum.DT_DCOMPLEX
    assert _parse_datatype("DT_EXTERNALREFERENCE") == ods.DataTypeEnum.DT_EXTERNALREFERENCE
    assert _parse_datatype("DT_ENUM") == ods.DataTypeEnum.DT_ENUM


def test_parse_datatype_sequence_types():
    assert _parse_datatype("DS_STRING") == ods.DataTypeEnum.DS_STRING
    assert _parse_datatype("DS_LONGLONG") == ods.DataTypeEnum.DS_LONGLONG
    assert _parse_datatype("DS_FLOAT") == ods.DataTypeEnum.DS_FLOAT
    assert _parse_datatype("DS_DOUBLE") == ods.DataTypeEnum.DS_DOUBLE


def test_parse_datatype_unknown_returns_zero():
    assert _parse_datatype("INVALID") == 0
    assert _parse_datatype("") == 0
