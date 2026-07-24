"""SQLite schema creation and instance loading for ATFX data."""

from __future__ import annotations

import logging
import pickle
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
import odsbox.proto.ods_pb2 as ods

from ._binary_reader import infer_external_component_data_type, read_external_component, read_external_component_typed
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

_LAZY_EXTERNAL_COMPONENT_TAG = "__wodson_lazy_external_component__"


def _encode_lazy_external_component(ref: ExternalComponentRef, actual_dt: int | None) -> bytes:
    """Serialize an external component reference for deferred binary loading."""
    return pickle.dumps((_LAZY_EXTERNAL_COMPONENT_TAG, ref, actual_dt))


def _decode_lazy_external_component(raw: Any) -> tuple[ExternalComponentRef, int | None] | None:
    """Return the deferred external component payload if *raw* encodes one."""
    if (
        isinstance(raw, tuple)
        and len(raw) == 3
        and raw[0] == _LAZY_EXTERNAL_COMPONENT_TAG
        and isinstance(raw[1], ExternalComponentRef)
        and (raw[2] is None or isinstance(raw[2], int))
    ):
        return raw[1], raw[2]
    return None


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
        # Track to-one relation columns for indexing after table creation.
        to_one_rel_cols: list[str] = []
        for rname in entity.relations:
            rel = entity.relations[rname]
            # Only create a column for to-one relations (range_max == 1)
            # and to-many relations stored inline (space-separated in ATFX)
            col_name = _col_name(rname)
            # Use TEXT for multi-valued relations, INTEGER for single-valued
            if rel.range_max == 1:
                columns.append(f'"{col_name}" INTEGER')
                to_one_rel_cols.append(col_name)
            else:
                columns.append(f'"{col_name}" TEXT')

        if columns:
            cols_sql = ", ".join(columns)
            sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({cols_sql})'
            cursor.execute(sql)

            # Index the ODS id column so WHERE id=N lookups are O(log n).
            id_col: str | None = None
            for aname, attr in entity.attributes.items():
                if attr.base_name == "id":
                    id_col = _col_name(aname)
                    break
            if id_col is not None:
                cursor.execute(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS "idx_{table_name}_{id_col}" ON "{table_name}" ("{id_col}")'
                )

            # Index to-one relation columns (parent/foreign-key lookups).
            for rel_col in to_one_rel_cols:
                cursor.execute(
                    f'CREATE INDEX IF NOT EXISTS "idx_{table_name}_{rel_col}" ON "{table_name}" ("{rel_col}")'
                )

    conn.commit()


def load_instances(
    conn: sqlite3.Connection,
    model: ods.Model,
    instances: dict[str, list[dict[str, Any]]],
    file_map: dict[str, Path],
    *,
    lazy_load_binary: bool = True,
    strict_binary_load: bool = False,
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
                row_values.append(
                    _serialize_value(
                        val,
                        dt,
                        file_map,
                        lazy_load_binary=lazy_load_binary,
                        strict_binary_load=strict_binary_load,
                    )
                )
            rows.append(tuple(row_values))

        cursor.executemany(sql, rows)

    conn.commit()


def _serialize_value(
    val: Any,
    data_type: int,
    file_map: dict[str, Path],
    *,
    lazy_load_binary: bool,
    strict_binary_load: bool,
) -> Any:
    """Serialize a value for SQLite storage."""
    if val is None:
        return None

    # External component: resolve binary data
    if isinstance(val, ExternalComponentRef):
        if lazy_load_binary:
            actual_dt = infer_external_component_data_type(val) if data_type == ods.DataTypeEnum.DT_UNKNOWN else None
            return _encode_lazy_external_component(val, actual_dt)

        try:
            if data_type == ods.DataTypeEnum.DT_UNKNOWN:
                # Preserve the ODS type from the binary typespec
                tv = read_external_component_typed(val, file_map)
                return pickle.dumps((tv.data_type, tv.values))
            arr = read_external_component(val, file_map)
            return pickle.dumps(arr.tolist())
        except (ValueError, OSError) as exc:
            if strict_binary_load:
                raise
            _log.warning("Skipping unreadable external component '%s': %s", val.identifier, exc)
            return None

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


def fix_complex_values(conn: sqlite3.Connection, model: ods.Model) -> None:
    """Post-process LocalColumn values blobs to use correct complex ODS data types.

    ATFX files store complex channels as interleaved doubles in external binary
    files (typespec ``ieeefloat8``). The binary reader has no way to distinguish
    those from ordinary double channels — the correct ODS type (DT_DCOMPLEX or
    DT_COMPLEX) lives on the related AoMeasurementQuantity entity's data_type
    attribute.  This function re-serializes the affected blobs with the correct
    complex data type so that ``unknown_array.data_type`` is set properly and
    odsbox can return numpy complex arrays.
    """
    # Locate AoLocalColumn and AoMeasurementQuantity entities by base_name.
    lc_entity = next((e for e in model.entities.values() if e.base_name == "AoLocalColumn"), None)
    if lc_entity is None:
        return

    meq_rel = next(
        (rel for rel in lc_entity.relations.values() if rel.base_name == "measurement_quantity"),
        None,
    )
    if meq_rel is None:
        return

    meq_entity = next((e for e in model.entities.values() if e.name == meq_rel.entity_name), None)
    if meq_entity is None:
        return

    # Find attribute with base_name "datatype" on the measurement-quantity entity.
    dt_attr_name = next(
        (aname for aname, attr in meq_entity.attributes.items() if attr.base_name == "datatype"),
        None,
    )
    if dt_attr_name is None:
        return

    # Resolve column names used in SQLite.
    lc_pk = next((aname for aname, a in lc_entity.attributes.items() if a.base_name == "id"), None)
    meq_pk = next((aname for aname, a in meq_entity.attributes.items() if a.base_name == "id"), None)
    lc_values_attr = next((aname for aname, a in lc_entity.attributes.items() if a.base_name == "values"), None)
    if not lc_pk or not meq_pk or not lc_values_attr:
        return

    lc_table = _table_name(lc_entity.name)
    meq_table = _table_name(meq_entity.name)
    lc_pk_col = _col_name(lc_pk)
    meq_pk_col = _col_name(meq_pk)
    dt_col = _col_name(dt_attr_name)
    values_col = _col_name(lc_values_attr)
    meq_rel_col = _col_name(meq_rel.name)

    cursor = conn.cursor()

    # Build map: meq_id -> complex ODS data type
    try:
        cursor.execute(f'SELECT "{meq_pk_col}", "{dt_col}" FROM "{meq_table}"')
    except Exception:  # noqa: BLE001
        _log.debug("fix_complex_values: could not query meq table")
        return

    _complex_name_map: dict[str, int] = {
        "DT_COMPLEX": ods.DataTypeEnum.DT_COMPLEX,
        "DT_DCOMPLEX": ods.DataTypeEnum.DT_DCOMPLEX,
    }
    meq_complex: dict[int, int] = {}  # meq_id -> DT_COMPLEX or DT_DCOMPLEX
    for row in cursor.fetchall():
        meq_id, dt_val = row
        if dt_val is None or meq_id is None:
            continue
        complex_dt: int | None = None
        if isinstance(dt_val, str):
            complex_dt = _complex_name_map.get(dt_val.strip().upper())
        elif isinstance(dt_val, int):
            if dt_val in (ods.DataTypeEnum.DT_COMPLEX, ods.DataTypeEnum.DT_DCOMPLEX):
                complex_dt = dt_val
        if complex_dt is not None:
            meq_complex[int(meq_id)] = complex_dt

    if not meq_complex:
        return

    # Read lc rows for those measurement quantities and fix values blobs.
    try:
        cursor.execute(f'SELECT "{lc_pk_col}", "{meq_rel_col}", "{values_col}" FROM "{lc_table}"')
    except Exception:  # noqa: BLE001
        _log.debug("fix_complex_values: could not query lc table")
        return

    updates: list[tuple[bytes, int]] = []
    for row in cursor.fetchall():
        lc_id, meq_id, blob = row
        if meq_id is None or int(meq_id) not in meq_complex or blob is None:
            continue
        complex_dt = meq_complex[int(meq_id)]
        try:
            raw = pickle.loads(blob)  # noqa: S301
            lazy_payload = _decode_lazy_external_component(raw)
            if lazy_payload is not None:
                ref, current_dt = lazy_payload
                if current_dt in (
                    ods.DataTypeEnum.DT_FLOAT,
                    ods.DataTypeEnum.DT_DOUBLE,
                ):
                    updates.append((_encode_lazy_external_component(ref, complex_dt), lc_id))
                continue
            if isinstance(raw, tuple) and len(raw) == 2 and isinstance(raw[0], int):
                current_dt, values = raw
                # Only re-type float/double blobs (not already-correct types).
                if current_dt in (
                    ods.DataTypeEnum.DT_FLOAT,
                    ods.DataTypeEnum.DT_DOUBLE,
                ):
                    updates.append((pickle.dumps((complex_dt, values)), lc_id))
        except Exception:  # noqa: BLE001
            continue

    if updates:
        cursor.executemany(
            f'UPDATE "{lc_table}" SET "{values_col}" = ? WHERE "{lc_pk_col}" = ?',
            updates,
        )
        conn.commit()
        _log.debug("fix_complex_values: re-typed %d lc values blobs as complex", len(updates))
