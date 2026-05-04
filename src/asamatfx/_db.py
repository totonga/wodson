"""SQLite schema creation and instance loading for ATFX data."""

from __future__ import annotations

import logging
import pickle
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
import odsbox.proto.ods_pb2 as ods

from ._binary_reader import read_external_component, read_external_component_typed
from ._instance_parser import ExternalComponentRef, TypedValues
from ._naming import _col_name, _table_name

_log = logging.getLogger(__name__)

# ODS data types that map to sequence/BLOB storage
_SEQUENCE_TYPES = frozenset(
    {
        ods.DataTypeEnum.DS_STRING,
        ods.DataTypeEnum.DS_SHORT,
        ods.DataTypeEnum.DS_FLOAT,
        ods.DataTypeEnum.DS_BOOLEAN,
        ods.DataTypeEnum.DS_BYTE,
        ods.DataTypeEnum.DS_LONG,
        ods.DataTypeEnum.DS_DOUBLE,
        ods.DataTypeEnum.DS_LONGLONG,
        ods.DataTypeEnum.DS_COMPLEX,
        ods.DataTypeEnum.DS_DCOMPLEX,
        ods.DataTypeEnum.DS_DATE,
        ods.DataTypeEnum.DS_BYTESTR,
        ods.DataTypeEnum.DS_EXTERNALREFERENCE,
        ods.DataTypeEnum.DS_ENUM,
    }
)

_BLOB_TYPES = frozenset(
    {
        ods.DataTypeEnum.DT_BYTESTR,
        ods.DataTypeEnum.DT_BLOB,
        ods.DataTypeEnum.DT_COMPLEX,
        ods.DataTypeEnum.DT_DCOMPLEX,
    }
)


def _sqlite_type(data_type: int) -> str:
    """Map ODS data type to SQLite column type."""
    if data_type in (
        ods.DataTypeEnum.DT_BOOLEAN,
        ods.DataTypeEnum.DT_BYTE,
        ods.DataTypeEnum.DT_SHORT,
        ods.DataTypeEnum.DT_LONG,
        ods.DataTypeEnum.DT_LONGLONG,
        ods.DataTypeEnum.DT_ENUM,
    ):
        return "INTEGER"
    elif data_type in (ods.DataTypeEnum.DT_FLOAT, ods.DataTypeEnum.DT_DOUBLE):
        return "REAL"
    elif data_type in (
        ods.DataTypeEnum.DT_STRING,
        ods.DataTypeEnum.DT_DATE,
        ods.DataTypeEnum.DT_EXTERNALREFERENCE,
    ):
        return "TEXT"
    elif data_type in _SEQUENCE_TYPES or data_type in _BLOB_TYPES:
        return "BLOB"
    elif data_type == ods.DataTypeEnum.DT_UNKNOWN:
        return "BLOB"
    else:
        return "TEXT"


def create_schema(conn: sqlite3.Connection, model: ods.Model) -> None:
    """Create SQLite tables for all entities in the model."""
    cursor = conn.cursor()
    _log.debug("Creating schema for %d entities", len(model.entities))
    for ename in model.entities:
        entity = model.entities[ename]
        table_name = _table_name(ename)
        columns: list[str] = []

        for aname in entity.attributes:
            attr = entity.attributes[aname]
            col_type = _sqlite_type(attr.data_type)
            col_name = _col_name(aname)
            columns.append(f'"{col_name}" {col_type}')

        # Add relation columns (store as INTEGER foreign key IDs)
        for rname in entity.relations:
            rel = entity.relations[rname]
            # Only create a column for to-one relations (range_max == 1)
            # and to-many relations stored inline (space-separated in ATFX)
            col_name = _col_name(rname)
            # Use TEXT for multi-valued relations, INTEGER for single-valued
            if rel.range_max == 1:
                columns.append(f'"{col_name}" INTEGER')
            else:
                columns.append(f'"{col_name}" TEXT')

        if columns:
            cols_sql = ", ".join(columns)
            sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({cols_sql})'
            cursor.execute(sql)

    conn.commit()


def load_instances(
    conn: sqlite3.Connection,
    model: ods.Model,
    instances: dict[str, list[dict[str, Any]]],
    file_map: dict[str, Path],
) -> None:
    """Load parsed instances into the SQLite database."""
    cursor = conn.cursor()

    for ename in model.entities:
        entity = model.entities[ename]
        if ename not in instances:
            continue

        table_name = _table_name(ename)
        inst_list = instances[ename]
        if not inst_list:
            continue
        _log.debug("Loading %d instance(s) into %s", len(inst_list), table_name)

        # Build column list: attributes + relations
        all_col_names: list[str] = []
        all_col_keys: list[str] = []  # original names used in instance dicts
        col_types: list[int] = []  # data types for serialization

        for aname in entity.attributes:
            attr = entity.attributes[aname]
            all_col_names.append(_col_name(aname))
            all_col_keys.append(aname)
            col_types.append(attr.data_type)

        for rname in entity.relations:
            all_col_names.append(_col_name(rname))
            all_col_keys.append(rname)
            col_types.append(-1)  # special marker for relations

        placeholders = ", ".join(["?"] * len(all_col_names))
        cols_sql = ", ".join(f'"{c}"' for c in all_col_names)
        sql = f'INSERT INTO "{table_name}" ({cols_sql}) VALUES ({placeholders})'

        rows: list[tuple[Any, ...]] = []
        for inst in inst_list:
            row_values: list[Any] = []
            for key, dt in zip(all_col_keys, col_types, strict=True):
                val = inst.get(key)
                row_values.append(_serialize_value(val, dt, file_map))
            rows.append(tuple(row_values))

        cursor.executemany(sql, rows)

    conn.commit()


def _serialize_value(val: Any, data_type: int, file_map: dict[str, Path]) -> Any:
    """Serialize a value for SQLite storage."""
    if val is None:
        return None

    # External component: resolve binary data
    if isinstance(val, ExternalComponentRef):
        if data_type == ods.DataTypeEnum.DT_UNKNOWN:
            # Preserve the ODS type from the binary typespec
            tv = read_external_component_typed(val, file_map)
            return pickle.dumps((tv.data_type, tv.values))
        arr = read_external_component(val, file_map)
        return pickle.dumps(arr.tolist())

    # TypedValues carries XML-derived ODS type info
    if isinstance(val, TypedValues):
        if data_type == ods.DataTypeEnum.DT_UNKNOWN:
            # Preserve (data_type, values) so the reader can use the correct type
            return pickle.dumps((val.data_type, val.values))
        # For typed attributes the model already knows the type; just keep values
        val = val.values

    # Relation values
    if data_type == -1:
        if isinstance(val, list):
            return " ".join(str(v) for v in val)
        return val

    # Sequence types: serialize as pickle
    if data_type in _SEQUENCE_TYPES:
        if isinstance(val, (list, np.ndarray)):
            if isinstance(val, np.ndarray):
                return pickle.dumps(val.tolist())
            return pickle.dumps(val)
        return pickle.dumps([val] if val is not None else [])

    # BLOB types
    if data_type in _BLOB_TYPES:
        if isinstance(val, (list, np.ndarray)):
            if isinstance(val, np.ndarray):
                return pickle.dumps(val.tolist())
            return pickle.dumps(val)
        return pickle.dumps(val)

    # DT_UNKNOWN plain-list fallback (e.g. from external component refs)
    if data_type == ods.DataTypeEnum.DT_UNKNOWN and isinstance(val, list):
        return pickle.dumps(val)

    # Scalar types: return as-is for SQLite binding
    if isinstance(val, list):
        return pickle.dumps(val)

    return val
