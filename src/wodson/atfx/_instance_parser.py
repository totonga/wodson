"""Parse ATFX instance_data XML into Python dicts."""

from __future__ import annotations

import logging
import math
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
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

    # Build lookup: entity_name -> {attr_name -> (base_name, data_type, enumeration), ...}
    entity_attrs: dict[str, dict[str, tuple[str, int, str]]] = {}
    entity_rels: dict[str, set[str]] = {}
    for ename in model.entities:
        entity = model.entities[ename]
        attrs: dict[str, tuple[str, int, str]] = {}
        for aname in entity.attributes:
            a = entity.attributes[aname]
            attrs[aname] = (a.base_name, a.data_type, a.enumeration)
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
                base_name, dt, enum_name = attrs_map[child_tag]
                instance[child_tag] = _parse_attribute_value(child, dt, base_name, model.enumerations, enum_name)
            elif child_tag.lower() in attrs_map_lower:
                key = attrs_map_lower[child_tag.lower()]
                base_name, dt, enum_name = attrs_map[key]
                instance[key] = _parse_attribute_value(child, dt, base_name, model.enumerations, enum_name)
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


def _parse_attribute_value(
    el: ET.Element,
    data_type: int,
    base_name: str,
    enumerations: Any,
    enumeration_name: str,
) -> Any:
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
                    # Each <s> contains a single enum value (not space-separated)
                    return [_convert_enum_to_int((s.text or "").strip(), enumerations, enumeration_name) for s in s_els]
            # Generic inline Values
            return _parse_values_content(el, data_type, enumerations, enumeration_name)
        # Plain text scalar
        text = (el.text or "").strip()
        return _parse_scalar(text, data_type, enumerations, enumeration_name)

    return _parse_values_content(values_el, data_type, enumerations, enumeration_name)


def _parse_values_content(
    values_el: ET.Element,
    data_type: int,
    enumerations: Any,
    enumeration_name: str,
) -> Any:
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
        elif child_tag == "A_ENUM":
            # A_ENUM: convert enum names to integers
            text_list = _parse_numeric_list(child.text, str)
            int_list = [_convert_enum_to_int(val, enumerations, enumeration_name) for val in text_list]
            return TypedValues(xml_dt, int_list)
        else:
            # A_INT*, A_UINT*
            return TypedValues(xml_dt, _parse_numeric_list(child.text, int))

    # Fallback: try text directly
    text = (values_el.text or "").strip()
    if text:
        return _parse_scalar(text, data_type, enumerations, enumeration_name)
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


def _convert_enum_to_int(
    text: str,
    enumerations: Any,
    enumeration_name: str,
) -> int:
    """Convert an enum name string to its integer value.

    If the enumeration is not found or the value is not in it,
    logs a warning and returns the first enumeration value (or 0).
    """
    # If already an integer, return as-is
    try:
        return int(text)
    except ValueError:
        pass

    # Look up in enumeration
    if enumeration_name and enumeration_name in enumerations:
        enum = enumerations[enumeration_name]
        if text in enum.items:
            return int(enum.items[text])
        else:
            # Value not found - warn and use first entry
            first_value = next(iter(enum.items.values())) if enum.items else 0
            _log.warning(
                f"Enum value '{text}' not found in enumeration '{enumeration_name}', "
                f"using first entry (value={first_value})"
            )
            return int(first_value)
    else:
        # Enumeration not found - warn and use 0
        _log.warning(f"Enumeration '{enumeration_name}' not found for enum value '{text}', using 0")
        return 0


def _parse_scalar(
    text: str,
    data_type: int,
    enumerations: Any,
    enumeration_name: str,
) -> Any:
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
        # DS_ENUM: space-separated enum names or integers - convert each to int
        parts = text.split()
        return [_convert_enum_to_int(p, enumerations, enumeration_name) for p in parts]
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
        # DT_ENUM: convert enum name to integer
        return _convert_enum_to_int(text, enumerations, enumeration_name)
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


def resolve_external_component_refs(
    model: ods.Model,
    instances: dict[str, list[dict[str, Any]]],
    file_map: dict[str, Path],
    atfx_dir: Path,
) -> None:
    """Resolve AoExternalComponent references in AoLocalColumn instances.

    For ``lc`` instances whose ``values`` attribute is ``None`` but that hold a
    relation to an ``AoExternalComponent`` entity, build an
    :class:`ExternalComponentRef` from the ``ec`` instance attributes using
    base_name mappings and inject it as the ``values`` attribute value.  The
    ``file_map`` is updated in-place so that the ``filename_url`` entries are
    resolvable during binary data loading.
    """
    # Locate entity names by ODS base_name
    lc_entity_name: str | None = None
    ec_entity_name: str | None = None
    for ename, entity in model.entities.items():
        if entity.base_name == "AoLocalColumn":
            lc_entity_name = ename
        elif entity.base_name == "AoExternalComponent":
            ec_entity_name = ename

    if lc_entity_name is None or ec_entity_name is None:
        return

    lc_entity = model.entities[lc_entity_name]
    ec_entity = model.entities[ec_entity_name]

    # Find relation name on lc whose base_name is "external_component"
    ec_rel_name: str | None = None
    for rname, rel in lc_entity.relations.items():
        if rel.base_name == "external_component":
            ec_rel_name = rname
            break

    if ec_rel_name is None:
        return

    # Find the values attribute name on lc (base_name == "values")
    lc_values_attr: str | None = None
    for aname, attr in lc_entity.attributes.items():
        if attr.base_name == "values":
            lc_values_attr = aname
            break

    if lc_values_attr is None:
        return

    # Build {base_name -> app_attr_name} for ec entity attributes
    ec_base_to_app: dict[str, str] = {}
    typespec_enum_name: str = ""
    for aname, attr in ec_entity.attributes.items():
        if attr.base_name:
            ec_base_to_app[attr.base_name] = aname
        if attr.base_name == "value_type" and attr.enumeration:
            typespec_enum_name = attr.enumeration

    # Build reverse mapping: typespec enum integer value -> string name
    # (value_type is parsed as DT_ENUM integer but _TYPESPEC_MAP uses string keys)
    typespec_int_to_str: dict[int, str] = {}
    if typespec_enum_name and typespec_enum_name in model.enumerations:
        for item_name, item_val in model.enumerations[typespec_enum_name].items.items():
            typespec_int_to_str[int(item_val)] = item_name

    # Build {base_name -> app_rel_name} for ec entity relations (for ao_values_file fallback)
    ec_base_to_rel: dict[str, str] = {}
    for rname, rel in ec_entity.relations.items():
        if rel.base_name:
            ec_base_to_rel[rname] = rel.base_name

    # Invert to {base_relation -> app_rel_name}
    ec_rel_base_to_app: dict[str, str] = {v: k for k, v in ec_base_to_rel.items()}

    # Find ec id attribute name (base_name == "id")
    ec_id_attr: str | None = ec_base_to_app.get("id")
    if ec_id_attr is None:
        return

    # Build {ec_id -> ec_instance} lookup
    ec_by_id: dict[int, dict[str, Any]] = {}
    for ec_inst in instances.get(ec_entity_name, []):
        raw_id = ec_inst.get(ec_id_attr)
        if raw_id is not None:
            ec_by_id[int(raw_id)] = ec_inst

    if not ec_by_id:
        return

    def _ec_val(ec_inst: dict[str, Any], base: str) -> Any:
        app_name = ec_base_to_app.get(base)
        return ec_inst.get(app_name) if app_name is not None else None

    # Prepare AoFile lookup for the ao_values_file fallback:
    # If ExternalComponent.filename_url is empty, follow the ao_values_file relation
    # to an AoFile (base_name "AoFile") instance and read its ao_location attribute.
    ao_values_file_rel: str | None = ec_rel_base_to_app.get("ao_values_file")
    aofile_by_id: dict[int, dict[str, Any]] = {}
    aofile_location_attr: str | None = None
    aofile_id_attr: str | None = None

    if ao_values_file_rel is not None:
        aofile_entity_name: str | None = None
        for ename, entity in model.entities.items():
            if entity.base_name == "AoFile":
                aofile_entity_name = ename
                break
        if aofile_entity_name is not None:
            aofile_entity = model.entities[aofile_entity_name]
            for aname, attr in aofile_entity.attributes.items():
                if attr.base_name == "ao_location":
                    aofile_location_attr = aname
                elif attr.base_name == "id":
                    aofile_id_attr = aname
            if aofile_id_attr is not None:
                for aofile_inst in instances.get(aofile_entity_name, []):
                    raw_id = aofile_inst.get(aofile_id_attr)
                    if raw_id is not None:
                        aofile_by_id[int(raw_id)] = aofile_inst

    # Process lc instances
    for lc_inst in instances.get(lc_entity_name, []):
        if lc_inst.get(lc_values_attr) is not None:
            continue  # already has values — nothing to do

        raw_ec_ref = lc_inst.get(ec_rel_name)
        if raw_ec_ref is None:
            continue

        # Relation may be a single int or a one-element list
        ec_id = raw_ec_ref[0] if isinstance(raw_ec_ref, list) else raw_ec_ref
        found_ec = ec_by_id.get(int(ec_id))
        if found_ec is None:
            _log.warning("AoLocalColumn references ec id=%s which was not found in instances", ec_id)
            continue

        ref = ExternalComponentRef()
        ref.identifier = str(_ec_val(found_ec, "filename_url") or "")
        raw_value_type = _ec_val(found_ec, "value_type")
        if raw_value_type is not None and typespec_int_to_str:
            ref.datatype = typespec_int_to_str.get(int(raw_value_type), str(raw_value_type))
        else:
            ref.datatype = str(raw_value_type or "")
        ref.length = int(_ec_val(found_ec, "component_length") or 0)
        ref.inioffset = int(_ec_val(found_ec, "start_offset") or 0)
        ref.blocksize = int(_ec_val(found_ec, "block_size") or 0)
        ref.valperblock = int(_ec_val(found_ec, "valuesperblock") or 1)
        value_offset = _ec_val(found_ec, "value_offset")
        ref.valoffsets = [int(value_offset)] if value_offset is not None else []
        bit_count = _ec_val(found_ec, "ao_bit_count")
        if bit_count is not None:
            ref.bitcount = int(bit_count)
        bit_offset = _ec_val(found_ec, "ao_bit_offset")
        if bit_offset is not None:
            ref.bitoffset = int(bit_offset)

        # Fallback: if filename_url is empty, follow ao_values_file → AoFile.ao_location
        if not ref.identifier and ao_values_file_rel is not None and aofile_location_attr is not None:
            raw_file_ref = found_ec.get(ao_values_file_rel)
            if raw_file_ref is not None:
                file_id = raw_file_ref[0] if isinstance(raw_file_ref, list) else raw_file_ref
                maybe_aofile = aofile_by_id.get(int(file_id))
                if maybe_aofile is not None:
                    loc = maybe_aofile.get(aofile_location_attr)
                    if loc:
                        ref.identifier = str(loc)

        # Register the filename in the file_map so _binary_reader can find it
        if ref.identifier and ref.identifier not in file_map:
            file_map[ref.identifier] = atfx_dir / ref.identifier

        lc_inst[lc_values_attr] = ref
