"""Parse ATFX instance_data XML into Python dicts."""

from __future__ import annotations

import logging
import math
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import odsbox.proto.ods_pb2 as ods

from ._xml_utils import _find, _findall, _text

_log = logging.getLogger(__name__)


@dataclass
class ExternalComponentRef:
    """Describes a binary external component reference within <Values>."""

    identifier: str = ""
    datatype: str = ""
    length: int = 0
    inioffset: int = 0
    blocksize: int = 0
    valperblock: int = 1
    valoffsets: list[int] = field(default_factory=list)
    bitcount: int = 0
    bitoffset: int = 0


@dataclass
class TypedValues:
    """Inline <Values> data with the ODS data type derived from the XML tag."""

    data_type: int
    values: Any


# Map from ATFX XML value-tag names to ODS DataTypeEnum values
_XML_TAG_TO_DT: dict[str, int] = {
    "A_BOOLEAN": ods.DataTypeEnum.DT_BOOLEAN,
    "A_INT8": ods.DataTypeEnum.DT_BYTE,
    "A_INT16": ods.DataTypeEnum.DT_SHORT,
    "A_INT32": ods.DataTypeEnum.DT_LONG,
    "A_INT64": ods.DataTypeEnum.DT_LONGLONG,
    "A_UINT8": ods.DataTypeEnum.DT_BYTE,
    "A_UINT16": ods.DataTypeEnum.DT_SHORT,
    "A_UINT32": ods.DataTypeEnum.DT_LONG,
    "A_UINT64": ods.DataTypeEnum.DT_LONGLONG,
    "A_FLOAT32": ods.DataTypeEnum.DT_FLOAT,
    "A_FLOAT64": ods.DataTypeEnum.DT_DOUBLE,
    "A_COMPLEX32": ods.DataTypeEnum.DT_COMPLEX,
    "A_COMPLEX64": ods.DataTypeEnum.DT_DCOMPLEX,
    "A_TIMESTRING": ods.DataTypeEnum.DT_DATE,
    "A_UTF8STRING": ods.DataTypeEnum.DT_STRING,
    "A_ASCIISTRING": ods.DataTypeEnum.DT_STRING,
    "A_BYTEFIELD": ods.DataTypeEnum.DT_BYTESTR,
    "A_ENUM": ods.DataTypeEnum.DT_ENUM,
}


def parse_instances(root: ET.Element, model: ods.Model) -> dict[str, list[dict[str, Any]]]:
    """Parse <instance_data> XML into {entity_name: [instance_dict, ...]}."""
    instance_data_el = _find(root, "instance_data")
    if instance_data_el is None:
        _log.debug("No <instance_data> element found")
        return {}

    # Build lookup: entity_name -> {attr_name -> (base_name, data_type), ...}
    entity_attrs: dict[str, dict[str, tuple[str, int]]] = {}
    entity_rels: dict[str, set[str]] = {}
    for ename in model.entities:
        entity = model.entities[ename]
        attrs: dict[str, tuple[str, int]] = {}
        for aname in entity.attributes:
            a = entity.attributes[aname]
            attrs[aname] = (a.base_name, a.data_type)
        entity_attrs[ename] = attrs
        rels: set[str] = set()
        for rname in entity.relations:
            rels.add(rname)
        entity_rels[ename] = rels

    result: dict[str, list[dict[str, Any]]] = {}

    for inst_el in instance_data_el:
        # Strip namespace from tag
        tag = inst_el.tag
        if "}" in tag:
            tag = tag.split("}", 1)[1]

        if tag not in entity_attrs:
            continue

        attrs_map = entity_attrs[tag]
        attrs_map_lower: dict[str, str] = {k.lower(): k for k in attrs_map}
        rels_set = entity_rels[tag]
        instance: dict[str, Any] = {}

        for child in inst_el:
            child_tag = child.tag
            if "}" in child_tag:
                child_tag = child_tag.split("}", 1)[1]

            if child_tag in attrs_map:
                base_name, dt = attrs_map[child_tag]
                instance[child_tag] = _parse_attribute_value(child, dt, base_name)
            elif child_tag.lower() in attrs_map_lower:
                key = attrs_map_lower[child_tag.lower()]
                base_name, dt = attrs_map[key]
                instance[key] = _parse_attribute_value(child, dt, base_name)
            elif child_tag in rels_set:
                # Relation value: space-separated IDs
                text = (child.text or "").strip()
                if text:
                    ids = [int(x) for x in text.split()]
                    instance[child_tag] = ids if len(ids) > 1 else ids[0]
            # else: skip unknown elements (e.g. GlobalFlag content we ignore)

        result.setdefault(tag, []).append(instance)

    return result


def _parse_external_reference_str(ref_el: ET.Element) -> str:
    """Parse an <external_reference> element into a pipe-separated string."""
    description = _text(ref_el, "description") or ""
    mimetype = _text(ref_el, "mimetype") or ""
    location = _text(ref_el, "location") or ""
    return f"{description}|{mimetype}|{location}"


def _parse_attribute_value(el: ET.Element, data_type: int, base_name: str) -> Any:
    """Parse a single attribute element's value based on its ODS data type."""
    # Check for <Values> child containing bulk data or component ref
    values_el = _find(el, "Values")
    if values_el is None:
        # Check if this element itself has children (for Values-like structure)
        children = list(el)
        if children:
            # DT_EXTERNALREFERENCE: single <external_reference> child
            if data_type == ods.DataTypeEnum.DT_EXTERNALREFERENCE:
                ref_el = _find(el, "external_reference")
                if ref_el is not None:
                    return _parse_external_reference_str(ref_el)
            # DS_EXTERNALREFERENCE: multiple <external_reference> children
            elif data_type == ods.DataTypeEnum.DS_EXTERNALREFERENCE:
                return [_parse_external_reference_str(r) for r in _findall(el, "external_reference")]
            # DS_ENUM: <s> child elements with enum name strings
            elif data_type == ods.DataTypeEnum.DS_ENUM:
                s_els = _findall(el, "s")
                if s_els:
                    return [(s.text or "").strip() for s in s_els]
            # Generic inline Values
            return _parse_values_content(el, data_type)
        # Plain text scalar
        text = (el.text or "").strip()
        return _parse_scalar(text, data_type)

    return _parse_values_content(values_el, data_type)


def _parse_values_content(values_el: ET.Element, data_type: int) -> Any:
    """Parse the content of a <Values> element (inline data or component ref)."""
    # Check for <component> child (external binary reference)
    comp_el = _find(values_el, "component")
    if comp_el is not None:
        return _parse_component_ref(comp_el)

    # Inline typed values — each XML tag carries ODS type info
    for child in values_el:
        child_tag = child.tag
        if "}" in child_tag:
            child_tag = child_tag.split("}", 1)[1]

        xml_dt = _XML_TAG_TO_DT.get(child_tag)
        if xml_dt is None:
            continue

        if child_tag == "A_BYTEFIELD":
            return TypedValues(xml_dt, _parse_bytefield(child))
        elif child_tag in ("A_UTF8STRING", "A_ASCIISTRING"):
            return TypedValues(xml_dt, _parse_string_sequence(child))
        elif child_tag == "A_TIMESTRING":
            return TypedValues(xml_dt, _parse_timestring_sequence(child))
        elif child_tag == "A_BOOLEAN":
            return TypedValues(xml_dt, _parse_boolean_list(child.text))
        elif child_tag in ("A_FLOAT32", "A_FLOAT64", "A_COMPLEX32", "A_COMPLEX64"):
            return TypedValues(xml_dt, _parse_float_list(child.text))
        else:
            # A_INT*, A_UINT*, A_ENUM
            return TypedValues(xml_dt, _parse_numeric_list(child.text, int))

    # Fallback: try text directly
    text = (values_el.text or "").strip()
    if text:
        return text
    return None


def _parse_component_ref(comp_el: ET.Element) -> ExternalComponentRef:
    """Parse a <component> element into an ExternalComponentRef."""
    ref = ExternalComponentRef()
    ref.identifier = _text(comp_el, "identifier")
    ref.datatype = _text(comp_el, "datatype")
    length_str = _text(comp_el, "length")
    if length_str:
        ref.length = int(length_str)
    inioffset_str = _text(comp_el, "inioffset")
    if inioffset_str:
        ref.inioffset = int(inioffset_str)
    blocksize_str = _text(comp_el, "blocksize")
    if blocksize_str:
        ref.blocksize = int(blocksize_str)
    valperblock_str = _text(comp_el, "valperblock")
    if valperblock_str:
        ref.valperblock = int(valperblock_str)
    valoffsets_str = _text(comp_el, "valoffsets")
    if valoffsets_str:
        ref.valoffsets = [int(x) for x in valoffsets_str.split()]
    bitcount_str = _text(comp_el, "bitcount")
    if bitcount_str:
        ref.bitcount = int(bitcount_str)
    bitoffset_str = _text(comp_el, "bitoffset")
    if bitoffset_str:
        ref.bitoffset = int(bitoffset_str)
    return ref


def _parse_scalar(text: str, data_type: int) -> Any:
    """Parse a scalar (or inline sequence) text value by ODS data type."""
    if not text:
        return None

    dt = data_type
    # Sequence types: space-separated lists
    if dt in (ods.DataTypeEnum.DS_FLOAT, ods.DataTypeEnum.DS_COMPLEX):
        return _parse_float_list(text)
    elif dt in (ods.DataTypeEnum.DS_DOUBLE, ods.DataTypeEnum.DS_DCOMPLEX):
        return _parse_float_list(text)
    elif dt in (
        ods.DataTypeEnum.DS_SHORT,
        ods.DataTypeEnum.DS_LONG,
        ods.DataTypeEnum.DS_LONGLONG,
        ods.DataTypeEnum.DS_BYTE,
    ):
        return _parse_numeric_list(text, int)
    elif dt == ods.DataTypeEnum.DS_ENUM:
        # Inline text: space-separated integer ordinals (string names handled via child elements)
        return _parse_numeric_list(text, int)
    elif dt == ods.DataTypeEnum.DS_BOOLEAN:
        return _parse_boolean_list(text)
    elif dt in (
        ods.DataTypeEnum.DS_STRING,
        ods.DataTypeEnum.DS_DATE,
        ods.DataTypeEnum.DS_EXTERNALREFERENCE,
        ods.DataTypeEnum.DS_BYTESTR,
    ):
        return text.split()
    if dt in (
        ods.DataTypeEnum.DT_BYTE,
        ods.DataTypeEnum.DT_SHORT,
        ods.DataTypeEnum.DT_LONG,
        ods.DataTypeEnum.DT_LONGLONG,
    ):
        return int(text)
    elif dt == ods.DataTypeEnum.DT_BOOLEAN:
        return text.lower() in ("true", "1")
    elif dt in (ods.DataTypeEnum.DT_FLOAT, ods.DataTypeEnum.DT_DOUBLE):
        return _parse_float_value(text)
    elif dt in (ods.DataTypeEnum.DT_COMPLEX, ods.DataTypeEnum.DT_DCOMPLEX):
        return _parse_float_list(text)
    elif dt == ods.DataTypeEnum.DT_ENUM:
        # Could be string enum name or int
        try:
            return int(text)
        except ValueError:
            return text
    else:
        # DT_STRING, DT_DATE, DT_EXTERNALREFERENCE, etc.
        return text


def _parse_float_value(text: str) -> float:
    """Parse a float value handling INF, -INF, NaN."""
    if text == "INF":
        return math.inf
    elif text == "-INF":
        return -math.inf
    elif text == "NaN":
        return math.nan
    return float(text)


def _parse_list(text: str | None, converter: Callable[[str], Any]) -> list[Any]:
    """Parse a space-separated list with a per-element converter."""
    if not text:
        return []
    return [converter(x) for x in text.strip().split()]


def _parse_numeric_list(text: str | None, converter: type) -> list[Any]:
    """Parse a space-separated numeric list."""
    return _parse_list(text, converter)


def _parse_float_list(text: str | None) -> list[float]:
    """Parse a space-separated float list with INF/NaN support."""
    return _parse_list(text, _parse_float_value)


def _parse_boolean_list(text: str | None) -> list[bool]:
    """Parse a space-separated boolean list."""
    return _parse_list(text, lambda x: x.lower() in ("true", "1"))


def _parse_bytefield(el: ET.Element) -> list[bytes]:
    """Parse <A_BYTEFIELD> with <length>/<sequence> pairs into a list of bytes objects."""
    result: list[bytes] = []
    children = list(el)
    i = 0
    while i < len(children):
        child = children[i]
        ctag = child.tag
        if "}" in ctag:
            ctag = ctag.split("}", 1)[1]
        if ctag == "length" and i + 1 < len(children):
            seq_child = children[i + 1]
            stag = seq_child.tag
            if "}" in stag:
                stag = stag.split("}", 1)[1]
            if stag == "sequence":
                seq_text = (seq_child.text or "").strip()
                result.append(bytes([int(x) for x in seq_text.split()]) if seq_text else b"")
                i += 2
                continue
        i += 1
    return result


def _parse_string_sequence(el: ET.Element) -> list[str]:
    """Parse <A_UTF8STRING> with <s> sub-elements or space-separated text."""
    # Check for <s> sub-elements
    s_elements = _findall(el, "s")
    if s_elements:
        return [(s.text or "") for s in s_elements]
    # Fallback: space-separated text (for TIMESTRING-like)
    text = (el.text or "").strip()
    if text:
        return text.split()
    return []


def _parse_timestring_sequence(el: ET.Element) -> list[str]:
    """Parse <A_TIMESTRING> with space-separated timestamps or <s> sub-elements."""
    s_elements = _findall(el, "s")
    if s_elements:
        return [(s.text or "") for s in s_elements]
    text = (el.text or "").strip()
    if text:
        return text.split()
    return []
