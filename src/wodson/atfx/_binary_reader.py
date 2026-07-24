"""Read external binary .dat files referenced by ATFX local columns."""

from __future__ import annotations

import logging
import struct
from pathlib import Path
from typing import Any

import numpy as np
import odsbox.proto.ods_pb2 as ods
from numpy.typing import NDArray

from ._instance_parser import ExternalComponentRef, TypedValues

_log = logging.getLogger(__name__)

# Mapping: typespec_enum string -> (numpy dtype, element_size_bytes)
_TYPESPEC_MAP: dict[str, tuple[str, int]] = {
    "dt_boolean": ("|b1", 1),
    "dt_byte": ("|u1", 1),
    "dt_sbyte": ("|i1", 1),
    "dt_short": ("<i2", 2),
    "dt_long": ("<i4", 4),
    "dt_longlong": ("<i8", 8),
    "ieeefloat4": ("<f4", 4),
    "ieeefloat8": ("<f8", 8),
    "dt_short_beo": (">i2", 2),
    "dt_long_beo": (">i4", 4),
    "dt_longlong_beo": (">i8", 8),
    "ieeefloat4_beo": (">f4", 4),
    "ieeefloat8_beo": (">f8", 8),
    "dt_ushort": ("<u2", 2),
    "dt_ushort_beo": (">u2", 2),
    "dt_ulong": ("<u4", 4),
    "dt_ulong_beo": (">u4", 4),
    "dt_string": ("|S1", 1),
    "dt_string_utf8": ("|S1", 1),
    "dt_bytestr_leo": ("|u1", 1),
    "dt_bytestr_beo": ("|u1", 1),
    # Bit types — raw-byte fallback; use _read_bit_values for actual decoding
    "dt_bit_int": ("|u1", 1),
    "dt_bit_int_beo": ("|u1", 1),
    "dt_bit_uint": ("|u1", 1),
    "dt_bit_uint_beo": ("|u1", 1),
    "dt_bit_ieeefloat": ("|u1", 1),
    "dt_bit_ieeefloat_beo": ("|u1", 1),
}

# Mapping: typespec_enum string -> ODS DataTypeEnum (for DT_UNKNOWN columns)
_TYPESPEC_TO_ODS_DT: dict[str, int] = {
    "dt_boolean": ods.DataTypeEnum.DT_BOOLEAN,
    "dt_byte": ods.DataTypeEnum.DT_BYTE,
    # dt_sbyte: ASAM ODS has no signed-byte type; promote to DT_SHORT
    "dt_sbyte": ods.DataTypeEnum.DT_SHORT,
    "dt_short": ods.DataTypeEnum.DT_SHORT,
    "dt_long": ods.DataTypeEnum.DT_LONG,
    "dt_longlong": ods.DataTypeEnum.DT_LONGLONG,
    "ieeefloat4": ods.DataTypeEnum.DT_FLOAT,
    "ieeefloat8": ods.DataTypeEnum.DT_DOUBLE,
    "dt_short_beo": ods.DataTypeEnum.DT_SHORT,
    "dt_long_beo": ods.DataTypeEnum.DT_LONG,
    "dt_longlong_beo": ods.DataTypeEnum.DT_LONGLONG,
    "ieeefloat4_beo": ods.DataTypeEnum.DT_FLOAT,
    "ieeefloat8_beo": ods.DataTypeEnum.DT_DOUBLE,
    # Unsigned types: promote to signed type that can hold the full value range
    "dt_ushort": ods.DataTypeEnum.DT_LONG,
    "dt_ushort_beo": ods.DataTypeEnum.DT_LONG,
    "dt_ulong": ods.DataTypeEnum.DT_LONGLONG,
    "dt_ulong_beo": ods.DataTypeEnum.DT_LONGLONG,
    "dt_string": ods.DataTypeEnum.DT_STRING,
    "dt_string_utf8": ods.DataTypeEnum.DT_STRING,
    "dt_bytestr_leo": ods.DataTypeEnum.DT_BYTESTR,
    "dt_bytestr_beo": ods.DataTypeEnum.DT_BYTESTR,
    # Bit types are resolved dynamically from bitcount — DT_UNKNOWN is the fallback
}

# Typespecs that require bit-level extraction
_BIT_TYPESPECS: frozenset[str] = frozenset(
    {
        "dt_bit_int",
        "dt_bit_int_beo",
        "dt_bit_uint",
        "dt_bit_uint_beo",
        "dt_bit_ieeefloat",
        "dt_bit_ieeefloat_beo",
    }
)

# Typespecs that require specialized string/bytestr parsing
_STRING_TYPESPECS: frozenset[str] = frozenset({"dt_string", "dt_string_utf8"})
_BYTESTR_TYPESPECS: frozenset[str] = frozenset({"dt_bytestr_leo", "dt_bytestr_beo"})


def _bit_ods_dt(typespec: str, bitcount: int) -> int:
    """Return the ODS DataTypeEnum for a bit-extraction typespec given its bitcount."""
    if "ieeefloat" in typespec:
        return ods.DataTypeEnum.DT_FLOAT if bitcount <= 32 else ods.DataTypeEnum.DT_DOUBLE
    elif "uint" in typespec:
        if bitcount <= 8:
            return ods.DataTypeEnum.DT_BYTE
        elif bitcount <= 16:
            return ods.DataTypeEnum.DT_SHORT
        elif bitcount <= 32:
            return ods.DataTypeEnum.DT_LONG
        else:
            return ods.DataTypeEnum.DT_LONGLONG
    else:  # signed int
        if bitcount <= 16:
            return ods.DataTypeEnum.DT_SHORT
        elif bitcount <= 32:
            return ods.DataTypeEnum.DT_LONG
        else:
            return ods.DataTypeEnum.DT_LONGLONG


def infer_external_component_data_type(ref: ExternalComponentRef) -> int:
    """Infer the ODS data type for an external component without reading binary data."""
    typespec = ref.datatype.lower()
    if typespec in _BIT_TYPESPECS:
        return _bit_ods_dt(typespec, ref.bitcount)
    return _TYPESPEC_TO_ODS_DT.get(typespec, ods.DataTypeEnum.DT_UNKNOWN)


def _read_bit_values(
    data: bytes,
    ref: ExternalComponentRef,
    signed: bool,
    is_float: bool,
    big_endian: bool,
) -> list[Any]:
    """Extract bit-field values from a binary buffer.

    Supports LE/BE, signed/unsigned integers, and IEEE floats of arbitrary
    bit-width packed at a given bit offset within multi-byte blocks.
    """
    count = ref.length
    bitcount = ref.bitcount
    bitoffset = ref.bitoffset
    blocksize = ref.blocksize if ref.blocksize > 0 else (bitoffset + bitcount + 7) // 8
    valperblock = ref.valperblock if ref.valperblock > 0 else 1
    inioffset = ref.inioffset
    byte_offset_in_block = ref.valoffsets[0] if ref.valoffsets else 0
    mask = (1 << bitcount) - 1

    results: list[Any] = []
    remaining = count
    block_num = 0

    while remaining > 0:
        n = min(valperblock, remaining)
        block_start = inioffset + block_num * blocksize
        block = data[block_start : block_start + blocksize]

        for j in range(n):
            # Absolute bit address within block
            bit_addr = byte_offset_in_block * 8 + bitoffset + j * bitcount
            byte_addr = bit_addr // 8
            local_bit = bit_addr % 8
            word_bytes_needed = (local_bit + bitcount + 7) // 8
            word = block[byte_addr : byte_addr + word_bytes_needed]

            if big_endian:
                # BEO stores bytes in big-endian order; reverse to LE then
                # apply the same LSB-first bit extraction as the LE case.
                word = word[::-1]
            word_int = int.from_bytes(word, "little")
            value_bits = (word_int >> local_bit) & mask

            if is_float:
                if bitcount == 32:
                    (value,) = struct.unpack("f", struct.pack("I", value_bits))
                elif bitcount == 64:
                    (value,) = struct.unpack("d", struct.pack("Q", value_bits))
                else:
                    value = float(value_bits)
            elif signed:
                value = value_bits - (1 << bitcount) if value_bits & (1 << (bitcount - 1)) else value_bits
            else:
                value = value_bits

            results.append(value)

        remaining -= n
        block_num += 1

    return results


def _read_null_terminated_strings(data: bytes, offset: int, total_bytes: int) -> list[str]:
    """Parse null-terminated strings packed sequentially in a byte buffer."""
    segment = data[offset : offset + total_bytes]
    results: list[str] = []
    start = 0
    while start < len(segment):
        end = segment.find(b"\x00", start)
        if end == -1:
            s = segment[start:].decode("utf-8", errors="replace").rstrip("\x00")
            if s:
                results.append(s)
            break
        results.append(segment[start:end].decode("utf-8", errors="replace"))
        start = end + 1
    return results


def _read_bytestr_sequence(data: bytes, offset: int, total_bytes: int, big_endian: bool) -> list[bytes]:
    """Parse length-prefixed (4-byte) byte strings packed in a byte buffer."""
    fmt = ">I" if big_endian else "<I"
    segment = data[offset : offset + total_bytes]
    results: list[bytes] = []
    pos = 0
    while pos + 4 <= len(segment):
        (length,) = struct.unpack_from(fmt, segment, pos)
        pos += 4
        results.append(segment[pos : pos + length])
        pos += length
    return results


def read_external_component_typed(ref: ExternalComponentRef, file_map: dict[str, Path]) -> TypedValues:
    """Read binary values and return them with the corresponding ODS DataTypeEnum.

    Handles string and bytestr types that require specialized parsing,
    in addition to all numeric/boolean types.
    """
    typespec = ref.datatype.lower()
    ods_dt = _TYPESPEC_TO_ODS_DT.get(typespec, ods.DataTypeEnum.DT_UNKNOWN)

    file_path = file_map.get(ref.identifier)
    if file_path is None:
        msg = f"External component identifier '{ref.identifier}' not found in file map"
        raise FileNotFoundError(msg)

    _log.debug(
        "Reading external component %s (typespec=%s, length=%d)",
        ref.identifier,
        typespec,
        ref.length,
    )
    data = file_path.read_bytes()

    if typespec in _BIT_TYPESPECS:
        is_float = "ieeefloat" in typespec
        signed = not ("uint" in typespec or is_float)
        big_endian = typespec.endswith("_beo")
        ods_dt = _bit_ods_dt(typespec, ref.bitcount)
        values = _read_bit_values(data, ref, signed, is_float, big_endian)
        return TypedValues(ods_dt, values)

    if typespec in _STRING_TYPESPECS:
        strings = _read_null_terminated_strings(data, ref.inioffset, ref.length)
        return TypedValues(ods_dt, strings)

    if typespec in _BYTESTR_TYPESPECS:
        big_endian = typespec == "dt_bytestr_beo"
        bytestrings = _read_bytestr_sequence(data, ref.inioffset, ref.length, big_endian)
        return TypedValues(ods_dt, bytestrings)

    # Numeric / boolean: use numpy reader
    arr = read_external_component(ref, file_map)
    return TypedValues(ods_dt, arr.tolist())


def read_external_component(ref: ExternalComponentRef, file_map: dict[str, Path]) -> NDArray[Any]:
    """Read binary values from an external file using the component reference.

    Args:
        ref: The external component reference with offset/size metadata.
        file_map: Mapping from component identifier to resolved file path.

    Returns:
        Numpy array of decoded values.
    """
    file_path = file_map.get(ref.identifier)
    if file_path is None:
        msg = f"External component identifier '{ref.identifier}' not found in file map"
        raise FileNotFoundError(msg)

    typespec = ref.datatype.lower()
    if typespec not in _TYPESPEC_MAP:
        # Fallback: read raw bytes
        dtype_str, elem_size = "|u1", 1
    else:
        dtype_str, elem_size = _TYPESPEC_MAP[typespec]
    dtype = np.dtype(dtype_str)

    count = ref.length
    if count <= 0:
        return np.array([], dtype=dtype)

    data = file_path.read_bytes()

    blocksize = ref.blocksize if ref.blocksize > 0 else elem_size
    valperblock = ref.valperblock if ref.valperblock > 0 else 1
    inioffset = ref.inioffset
    valoffset = ref.valoffsets[0] if ref.valoffsets else 0

    if blocksize == elem_size and valperblock == 1 and valoffset == 0:
        # Simple contiguous case: values packed sequentially from inioffset
        start = inioffset
        end = start + count * elem_size
        return np.frombuffer(data[start:end], dtype=dtype, count=count)

    # General case: values interleaved in blocks
    values: list[Any] = []
    offset = inioffset
    remaining = count
    while remaining > 0:
        n = min(valperblock, remaining)
        for i in range(n):
            val_start = offset + valoffset + i * elem_size
            val_end = val_start + elem_size
            val = np.frombuffer(data[val_start:val_end], dtype=dtype, count=1)[0]
            values.append(val)
        remaining -= n
        offset += blocksize

    return np.array(values, dtype=dtype)
