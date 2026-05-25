"""Translate ods.SelectStatement to SQL and execute against SQLite, returning ods.DataMatrices."""

from __future__ import annotations

import logging
import math
import pickle
import sqlite3
from typing import Any

import odsbox.proto.ods_pb2 as ods

from ._naming import _col_name, _table_name

_log = logging.getLogger(__name__)

# Aggregate mapping
_AGGREGATE_MAP: dict[int, str] = {
    ods.AggregateEnum.AG_NONE: "",
    ods.AggregateEnum.AG_COUNT: "COUNT",
    ods.AggregateEnum.AG_DCOUNT: "COUNT",
    ods.AggregateEnum.AG_MIN: "MIN",
    ods.AggregateEnum.AG_MAX: "MAX",
    ods.AggregateEnum.AG_AVG: "AVG",
    ods.AggregateEnum.AG_SUM: "SUM",
    ods.AggregateEnum.AG_DISTINCT: "COUNT",
}

# Operator mapping
_OP_MAP: dict[int, str] = {
    ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_EQ: "=",
    ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_NEQ: "!=",
    ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_LT: "<",
    ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_GT: ">",
    ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_LTE: "<=",
    ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_GTE: ">=",
    ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_LIKE: "LIKE",
    ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_NOTLIKE: "NOT LIKE",
    ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_IS_NULL: "IS NULL",
    ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_IS_NOT_NULL: "IS NOT NULL",
    ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_INSET: "IN",
    ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_NOTINSET: "NOT IN",
    ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_BETWEEN: "BETWEEN",
}

# CI operator mapping
_CI_OPS: frozenset[int] = frozenset(
    {
        ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_CI_EQ,
        ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_CI_NEQ,
        ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_CI_LT,
        ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_CI_GT,
        ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_CI_LTE,
        ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_CI_GTE,
        ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_CI_LIKE,
        ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_CI_NOTLIKE,
        ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_CI_INSET,
        ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_CI_NOTINSET,
    }
)

_OpEnum = ods.SelectStatement.ConditionItem.Condition.OperatorEnum
_CI_TO_BASE: dict[int, int] = {
    _OpEnum.OP_CI_EQ: _OpEnum.OP_EQ,
    _OpEnum.OP_CI_NEQ: _OpEnum.OP_NEQ,
    _OpEnum.OP_CI_LT: _OpEnum.OP_LT,
    _OpEnum.OP_CI_GT: _OpEnum.OP_GT,
    _OpEnum.OP_CI_LTE: _OpEnum.OP_LTE,
    _OpEnum.OP_CI_GTE: _OpEnum.OP_GTE,
    _OpEnum.OP_CI_LIKE: _OpEnum.OP_LIKE,
    _OpEnum.OP_CI_NOTLIKE: _OpEnum.OP_NOTLIKE,
    _OpEnum.OP_CI_INSET: _OpEnum.OP_INSET,
    _OpEnum.OP_CI_NOTINSET: _OpEnum.OP_NOTINSET,
}


class _QueryContext:
    """Holds state for building a SQL query from a SelectStatement."""

    def __init__(self, model: ods.Model) -> None:
        self.model = model
        # AID -> entity
        self.aid_to_entity: dict[int, ods.Model.Entity] = {}
        # AID -> table alias
        self.aid_to_alias: dict[int, str] = {}
        self.alias_counter = 0

        for ename in model.entities:
            entity = model.entities[ename]
            self.aid_to_entity[entity.aid] = entity

    def get_alias(self, aid: int) -> str:
        """Get or create a table alias for the given AID."""
        if aid not in self.aid_to_alias:
            self.alias_counter += 1
            self.aid_to_alias[aid] = f"t{self.alias_counter}"
        return self.aid_to_alias[aid]

    def get_entity(self, aid: int) -> ods.Model.Entity:
        """Get entity by AID."""
        if aid not in self.aid_to_entity:
            msg = f"Unknown AID: {aid}"
            raise ValueError(msg)
        return self.aid_to_entity[aid]

    def resolve_attribute(self, entity: ods.Model.Entity, attr_name: str) -> tuple[str, int]:
        """Resolve an attribute or relation name (case-insensitive) and return (resolved_name, data_type)."""
        if attr_name in entity.attributes:
            return attr_name, entity.attributes[attr_name].data_type
        if attr_name in entity.relations:
            return attr_name, ods.DataTypeEnum.DT_LONGLONG
        for aname in entity.attributes:
            if aname.lower() == attr_name.lower():
                return aname, entity.attributes[aname].data_type
        for rname in entity.relations:
            if rname.lower() == attr_name.lower():
                return rname, ods.DataTypeEnum.DT_LONGLONG
        return attr_name, ods.DataTypeEnum.DT_UNKNOWN


def data_read(
    conn: sqlite3.Connection,
    model: ods.Model,
    select_statement: ods.SelectStatement,
) -> ods.DataMatrices:
    """Execute a SelectStatement against the SQLite database and return DataMatrices."""
    ctx = _QueryContext(model)
    params: list[Any] = []

    # Determine primary AID from first column
    if not select_statement.columns:
        return ods.DataMatrices()

    primary_aid = select_statement.columns[0].aid
    primary_entity = ctx.get_entity(primary_aid)
    primary_alias = ctx.get_alias(primary_aid)
    primary_table = _table_name(primary_entity.name)

    # Build SELECT clause
    select_parts: list[str] = []
    column_meta: list[tuple[int, str, int, int]] = []  # (aid, attr_name, data_type, aggregate)

    for col in select_statement.columns:
        entity = ctx.get_entity(col.aid)
        alias = ctx.get_alias(col.aid)

        if col.attribute == "*":
            # Expand all attributes
            for aname in entity.attributes:
                attr = entity.attributes[aname]
                col_ref = f'"{alias}"."{_col_name(aname)}"'
                select_parts.append(col_ref)
                column_meta.append((col.aid, aname, attr.data_type, ods.AggregateEnum.AG_NONE))
        else:
            # Single attribute or relation
            attr_name = col.attribute
            resolved_name, dt = ctx.resolve_attribute(entity, attr_name)
            attr_name = resolved_name

            col_ref = f'"{alias}"."{_col_name(attr_name)}"'
            agg = col.aggregate
            agg_func = _AGGREGATE_MAP.get(agg, "")
            if agg_func:
                if agg == ods.AggregateEnum.AG_DISTINCT:
                    col_ref = f"COUNT(DISTINCT {col_ref})"
                else:
                    col_ref = f"{agg_func}({col_ref})"
            select_parts.append(col_ref)
            column_meta.append((col.aid, attr_name, dt, agg))

    # Build FROM clause
    from_clause = f'"{primary_table}" AS "{primary_alias}"'

    # Build JOIN clauses
    join_clauses: list[str] = []
    for join in select_statement.joins:
        from_entity = ctx.get_entity(join.aid_from)
        to_entity = ctx.get_entity(join.aid_to)
        from_alias = ctx.get_alias(join.aid_from)
        to_alias = ctx.get_alias(join.aid_to)
        to_table = _table_name(to_entity.name)

        join_type = "INNER JOIN" if join.join_type == 0 else "LEFT JOIN"

        # Determine join condition from relation
        rel_name = join.relation
        on_clause = ""

        # Check relation on from_entity
        if rel_name in from_entity.relations:
            rel = from_entity.relations[rel_name]
            # If from_entity has a to-one relation (FATHER), from has FK column
            if rel.range_max == 1:
                on_clause = f'"{from_alias}"."{_col_name(rel_name)}" = "{to_alias}"."{_col_name("Id")}"'
            else:
                # to_entity should have the inverse relation as FK
                inv_name = rel.inverse_name
                if inv_name:
                    on_clause = f'"{to_alias}"."{_col_name(inv_name)}" = "{from_alias}"."{_col_name("Id")}"'
                else:
                    on_clause = f'"{to_alias}"."{_col_name(rel_name)}" = "{from_alias}"."{_col_name("Id")}"'
        elif rel_name in to_entity.relations:
            rel = to_entity.relations[rel_name]
            if rel.range_max == 1:
                on_clause = f'"{to_alias}"."{_col_name(rel_name)}" = "{from_alias}"."{_col_name("Id")}"'
            else:
                on_clause = f'"{from_alias}"."{_col_name(rel.inverse_name)}" = "{to_alias}"."{_col_name("Id")}"'

        if not on_clause:
            # Fallback: try id-based join
            on_clause = f'"{from_alias}"."id" = "{to_alias}"."id"'

        join_clauses.append(f'{join_type} "{to_table}" AS "{to_alias}" ON {on_clause}')

    # Build WHERE clause
    where_clause, where_params = _build_where(ctx, select_statement.where)
    params.extend(where_params)

    # Build ORDER BY
    order_parts: list[str] = []
    for ob in select_statement.order_by:
        entity = ctx.get_entity(ob.aid)
        alias = ctx.get_alias(ob.aid)
        resolved_name, _ = ctx.resolve_attribute(entity, ob.attribute)
        direction = "ASC" if ob.order == 0 else "DESC"
        order_parts.append(f'"{alias}"."{_col_name(resolved_name)}" {direction}')

    # Build GROUP BY
    group_parts: list[str] = []
    for gb in select_statement.group_by:
        entity = ctx.get_entity(gb.aid)
        alias = ctx.get_alias(gb.aid)
        resolved_name, _ = ctx.resolve_attribute(entity, gb.attribute)
        group_parts.append(f'"{alias}"."{_col_name(resolved_name)}"')

    # Assemble SQL
    sql = f"SELECT {', '.join(select_parts)} FROM {from_clause}"
    if join_clauses:
        sql += " " + " ".join(join_clauses)
    if where_clause:
        sql += f" WHERE {where_clause}"
    if group_parts:
        sql += f" GROUP BY {', '.join(group_parts)}"
    if order_parts:
        sql += f" ORDER BY {', '.join(order_parts)}"
    if select_statement.row_limit > 0:
        sql += " LIMIT ?"
        params.append(select_statement.row_limit)
    if select_statement.row_start > 0:
        sql += " OFFSET ?"
        params.append(select_statement.row_start)

    # Execute
    cursor = conn.cursor()
    _log.debug("SQL: %s  params=%s", sql, params)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    _log.debug("Query returned %d row(s)", len(rows))

    # Build DataMatrices result
    return _build_data_matrices(rows, column_meta, ctx, select_statement)


def _build_where(
    ctx: _QueryContext,
    where_items: Any,
) -> tuple[str, list[Any]]:
    """Build WHERE clause from ConditionItem list."""
    if not where_items:
        return "", []

    parts: list[str] = []
    params: list[Any] = []

    for item in where_items:
        if item.HasField("conjunction"):
            conj = item.conjunction
            if conj == ods.SelectStatement.ConditionItem.ConjuctionEnum.CO_AND:
                parts.append("AND")
            elif conj == ods.SelectStatement.ConditionItem.ConjuctionEnum.CO_OR:
                parts.append("OR")
            elif conj == ods.SelectStatement.ConditionItem.ConjuctionEnum.CO_NOT:
                parts.append("NOT")
            elif conj == ods.SelectStatement.ConditionItem.ConjuctionEnum.CO_OPEN:
                parts.append("(")
            elif conj == ods.SelectStatement.ConditionItem.ConjuctionEnum.CO_CLOSE:
                parts.append(")")
        elif item.HasField("condition"):
            cond = item.condition
            entity = ctx.get_entity(cond.aid)
            alias = ctx.get_alias(cond.aid)

            resolved_name, _ = ctx.resolve_attribute(entity, cond.attribute)

            col_ref = f'"{alias}"."{_col_name(resolved_name)}"'
            op = cond.operator
            is_ci = op in _CI_OPS

            if is_ci:
                col_ref = f"LOWER({col_ref})"
                op = _CI_TO_BASE[op]

            op_str = _OP_MAP.get(op, "=")
            values = _extract_condition_values(cond)

            if is_ci and values:
                values = [v.lower() if isinstance(v, str) else v for v in values]

            if op in (
                ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_IS_NULL,
                ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_IS_NOT_NULL,
            ):
                parts.append(f"{col_ref} {op_str}")
            elif op in (
                ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_INSET,
                ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_NOTINSET,
            ):
                placeholders = ", ".join(["?"] * len(values))
                parts.append(f"{col_ref} {op_str} ({placeholders})")
                params.extend(values)
            elif op == ods.SelectStatement.ConditionItem.Condition.OperatorEnum.OP_BETWEEN:
                if len(values) >= 2:
                    parts.append(f"{col_ref} BETWEEN ? AND ?")
                    params.extend(values[:2])
            else:
                if values:
                    parts.append(f"{col_ref} {op_str} ?")
                    params.append(values[0])
                else:
                    parts.append(f"{col_ref} {op_str} NULL")

    return " ".join(parts), params


def _extract_condition_values(cond: Any) -> list[Any]:
    """Extract values from a condition's value oneof field."""
    if cond.HasField("string_array"):
        return list(cond.string_array.values)
    elif cond.HasField("long_array"):
        return list(cond.long_array.values)
    elif cond.HasField("float_array"):
        return list(cond.float_array.values)
    elif cond.HasField("double_array"):
        return list(cond.double_array.values)
    elif cond.HasField("longlong_array"):
        return list(cond.longlong_array.values)
    elif cond.HasField("boolean_array"):
        return list(cond.boolean_array.values)
    elif cond.HasField("byte_array"):
        return list(cond.byte_array.values)
    return []


def _build_data_matrices(
    rows: list[Any],
    column_meta: list[tuple[int, str, int, int]],
    ctx: _QueryContext,
    select_statement: ods.SelectStatement,
) -> ods.DataMatrices:
    """Convert SQL result rows into ods.DataMatrices."""
    result = ods.DataMatrices()

    if not rows or not column_meta:
        return result

    # Group columns by AID
    aid_order: list[int] = []
    aid_columns: dict[int, list[tuple[int, str, int, int]]] = {}  # aid -> [(col_idx, name, dt, agg)]
    for col_idx, (aid, name, dt, agg) in enumerate(column_meta):
        if aid not in aid_columns:
            aid_order.append(aid)
            aid_columns[aid] = []
        aid_columns[aid].append((col_idx, name, dt, agg))

    for aid in aid_order:
        entity = ctx.get_entity(aid)
        matrix = result.matrices.add()
        matrix.name = entity.name
        matrix.base_name = entity.base_name
        matrix.aid = aid

        for col_idx, attr_name, dt, agg in aid_columns[aid]:
            column = matrix.columns.add()
            column.name = attr_name
            # Try to set base_name
            if attr_name in entity.attributes:
                column.base_name = entity.attributes[attr_name].base_name
            elif attr_name in entity.relations:
                column.base_name = entity.relations[attr_name].base_name
            column.data_type = dt  # type: ignore[assignment]

            # Extract values from rows
            values_list: list[Any] = [row[col_idx] for row in rows]

            # Apply values_start/values_limit for sequence columns
            _fill_column(column, values_list, dt, select_statement)

    return result


def _fill_column(
    column: Any,
    values: list[Any],
    data_type: int,
    select_statement: ods.SelectStatement,
) -> None:
    """Fill a DataMatrix.Column with typed values."""
    from ._db import _SEQUENCE_TYPES

    if data_type in _SEQUENCE_TYPES or data_type == ods.DataTypeEnum.DT_UNKNOWN:
        # Sequence data stored as pickled BLOBs
        for val in values:
            if val is None:
                # All sequence types share a oneof field; use the same sub-array type
                # for null rows so that null and non-null entries stay in the same field.
                _fill_sequence_column(column, [], data_type, None)
            else:
                raw = pickle.loads(val) if isinstance(val, bytes) else val  # noqa: S301
                # Detect (actual_dt: int, seq_data: list) tuple stored by _serialize_value
                actual_dt: int | None
                seq_data: list[Any]
                if isinstance(raw, tuple) and len(raw) == 2 and isinstance(raw[0], int):
                    actual_dt = raw[0]
                    seq_data = raw[1]
                else:
                    actual_dt = None
                    seq_data = raw
                # Apply values_start/values_limit
                vs = select_statement.values_start
                vl = select_statement.values_limit
                if vs > 0:
                    seq_data = seq_data[vs:]
                if vl > 0:
                    seq_data = seq_data[:vl]
                _fill_sequence_column(column, seq_data, data_type, actual_dt)
        return

    # Scalar data types
    for val in values:
        if val is None:
            column.is_null.append(True)
            _append_default_value(column, data_type)
        else:
            column.is_null.append(False)
            _append_value(column, val, data_type)


def _fill_unknown_array_values(ua: Any, seq_data: list[Any], data_type: int) -> None:
    """Fill an UnknownArray with values using the given concrete ODS data_type."""
    if data_type == ods.DataTypeEnum.DT_BOOLEAN:
        ua.data_type = data_type
        ua.boolean_array.values.extend([bool(v) for v in seq_data])
    elif data_type == ods.DataTypeEnum.DT_BYTE:
        ua.data_type = data_type
        ua.byte_array.values = bytes([int(v) & 0xFF for v in seq_data])
    elif data_type in (
        ods.DataTypeEnum.DT_SHORT,
        ods.DataTypeEnum.DT_LONG,
        ods.DataTypeEnum.DT_ENUM,
    ):
        ua.data_type = data_type
        ua.long_array.values.extend([int(v) for v in seq_data])
    elif data_type == ods.DataTypeEnum.DT_LONGLONG:
        ua.data_type = data_type
        ua.longlong_array.values.extend([int(v) for v in seq_data])
    elif data_type in (ods.DataTypeEnum.DT_FLOAT, ods.DataTypeEnum.DT_COMPLEX):
        ua.data_type = data_type
        ua.float_array.values.extend([_to_float(v) for v in seq_data])
    elif data_type in (ods.DataTypeEnum.DT_DOUBLE, ods.DataTypeEnum.DT_DCOMPLEX):
        ua.data_type = data_type
        ua.double_array.values.extend([_to_float(v) for v in seq_data])
    elif data_type in (
        ods.DataTypeEnum.DT_STRING,
        ods.DataTypeEnum.DT_DATE,
        ods.DataTypeEnum.DT_EXTERNALREFERENCE,
    ):
        ua.data_type = data_type
        ua.string_array.values.extend([str(v) for v in seq_data])
    elif data_type == ods.DataTypeEnum.DT_BYTESTR:
        ua.data_type = data_type
        ua.bytestr_array.values.extend([v if isinstance(v, bytes) else bytes(v) for v in seq_data])
    else:
        # DT_UNKNOWN or unrecognised: infer concrete type from Python values
        if isinstance(seq_data[0], bool):
            ua.data_type = ods.DataTypeEnum.DT_BOOLEAN
            ua.boolean_array.values.extend([bool(v) for v in seq_data])
        elif isinstance(seq_data[0], int):
            ua.data_type = ods.DataTypeEnum.DT_LONGLONG
            ua.longlong_array.values.extend([int(v) for v in seq_data])
        elif isinstance(seq_data[0], float):
            ua.data_type = ods.DataTypeEnum.DT_DOUBLE
            ua.double_array.values.extend([float(v) for v in seq_data])
        else:
            ua.data_type = ods.DataTypeEnum.DT_STRING
            ua.string_array.values.extend([str(v) for v in seq_data])


def _to_float(val: Any) -> float:
    """Convert a value to float, mapping None (SQLite NULL for NaN) back to NaN."""
    if val is None:
        return math.nan
    return float(val)


def _fill_sequence_column(column: Any, seq_data: list[Any], data_type: int, actual_dt: int | None = None) -> None:
    """Fill column with a sequence of values as a sub-array."""
    if data_type in (ods.DataTypeEnum.DS_FLOAT, ods.DataTypeEnum.DS_COMPLEX):
        arr = column.float_arrays.values.add()
        arr.values.extend([_to_float(v) for v in seq_data])
    elif data_type in (ods.DataTypeEnum.DS_DOUBLE, ods.DataTypeEnum.DS_DCOMPLEX):
        arr = column.double_arrays.values.add()
        arr.values.extend([_to_float(v) for v in seq_data])
    elif data_type in (
        ods.DataTypeEnum.DS_LONG,
        ods.DataTypeEnum.DS_SHORT,
    ):
        arr = column.long_arrays.values.add()
        arr.values.extend([int(v) for v in seq_data])
    elif data_type == ods.DataTypeEnum.DS_LONGLONG:
        arr = column.longlong_arrays.values.add()
        arr.values.extend([int(v) for v in seq_data])
    elif data_type in (
        ods.DataTypeEnum.DS_STRING,
        ods.DataTypeEnum.DS_DATE,
        ods.DataTypeEnum.DS_EXTERNALREFERENCE,
        ods.DataTypeEnum.DS_ENUM,
    ):
        arr = column.string_arrays.values.add()
        arr.values.extend([str(v) for v in seq_data])
    elif data_type in (ods.DataTypeEnum.DS_BOOLEAN,):
        arr = column.boolean_arrays.values.add()
        arr.values.extend([bool(v) for v in seq_data])
    elif data_type in (ods.DataTypeEnum.DS_BYTE, ods.DataTypeEnum.DS_BYTESTR):
        arr = column.byte_arrays.values.add()
        arr.values = bytes(seq_data) if seq_data else b""
    elif data_type == ods.DataTypeEnum.DT_UNKNOWN:
        # Store as UnknownArray; use actual_dt when known (from XML tag), else infer
        ua = column.unknown_arrays.values.add()
        if seq_data:
            _fill_unknown_array_values(
                ua,
                seq_data,
                actual_dt if actual_dt is not None else ods.DataTypeEnum.DT_UNKNOWN,
            )
    else:
        arr = column.string_arrays.values.add()
        arr.values.extend([str(v) for v in seq_data])


def _append_value(column: Any, val: Any, data_type: int) -> None:
    """Append a single scalar value to the appropriate column array."""
    if data_type in (
        ods.DataTypeEnum.DT_STRING,
        ods.DataTypeEnum.DT_DATE,
        ods.DataTypeEnum.DT_EXTERNALREFERENCE,
        ods.DataTypeEnum.DT_ENUM,
    ):
        column.string_array.values.append(str(val))
    elif data_type in (ods.DataTypeEnum.DT_SHORT, ods.DataTypeEnum.DT_LONG):
        column.long_array.values.append(int(val))
    elif data_type == ods.DataTypeEnum.DT_LONGLONG:
        column.longlong_array.values.append(int(val))
    elif data_type == ods.DataTypeEnum.DT_FLOAT:
        column.float_array.values.append(_to_float(val))
    elif data_type == ods.DataTypeEnum.DT_DOUBLE:
        column.double_array.values.append(_to_float(val))
    elif data_type == ods.DataTypeEnum.DT_BOOLEAN:
        column.boolean_array.values.append(bool(val))
    elif data_type == ods.DataTypeEnum.DT_BYTE:
        column.byte_array.values += bytes([int(val)])
    elif data_type in (ods.DataTypeEnum.DT_COMPLEX, ods.DataTypeEnum.DT_DCOMPLEX):
        # Stored as pickled blob
        if isinstance(val, bytes):
            data = pickle.loads(val)  # noqa: S301
            if data_type == ods.DataTypeEnum.DT_COMPLEX:
                column.float_array.values.extend([float(v) for v in data])
            else:
                column.double_array.values.extend([float(v) for v in data])
        else:
            column.double_array.values.append(float(val))
    elif data_type in (ods.DataTypeEnum.DT_BYTESTR, ods.DataTypeEnum.DT_BLOB):
        if isinstance(val, bytes):
            column.bytestr_array.values.append(val)
        else:
            column.bytestr_array.values.append(bytes(str(val), "utf-8"))
    else:
        # Unknown type: store as string
        column.string_array.values.append(str(val))


def _append_default_value(column: Any, data_type: int) -> None:
    """Append a default/zero value for NULL handling."""
    if data_type in (
        ods.DataTypeEnum.DT_STRING,
        ods.DataTypeEnum.DT_DATE,
        ods.DataTypeEnum.DT_EXTERNALREFERENCE,
        ods.DataTypeEnum.DT_ENUM,
    ):
        column.string_array.values.append("")
    elif data_type in (ods.DataTypeEnum.DT_SHORT, ods.DataTypeEnum.DT_LONG):
        column.long_array.values.append(0)
    elif data_type == ods.DataTypeEnum.DT_LONGLONG:
        column.longlong_array.values.append(0)
    elif data_type == ods.DataTypeEnum.DT_FLOAT:
        column.float_array.values.append(0.0)
    elif data_type == ods.DataTypeEnum.DT_DOUBLE:
        column.double_array.values.append(0.0)
    elif data_type == ods.DataTypeEnum.DT_BOOLEAN:
        column.boolean_array.values.append(False)
    elif data_type == ods.DataTypeEnum.DT_BYTE:
        column.byte_array.values += b"\x00"
    else:
        column.string_array.values.append("")
