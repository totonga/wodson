"""Convert Pandas DataFrames into ods.DataMatrix protobuf messages."""

from __future__ import annotations

from typing import Any

import numpy as np
import odsbox.proto.ods_pb2 as ods
import pandas as pd
from odsbox.model_cache import ModelCache

from ._resolve import resolve_entity_and_columns

_DT = ods.DataTypeEnum

_DT_BOOLEAN = _DT.DT_BOOLEAN
_DT_BYTE = _DT.DT_BYTE
_DT_SHORT = _DT.DT_SHORT
_DT_LONG = _DT.DT_LONG
_DT_LONGLONG = _DT.DT_LONGLONG
_DT_FLOAT = _DT.DT_FLOAT
_DT_DOUBLE = _DT.DT_DOUBLE
_DT_COMPLEX = _DT.DT_COMPLEX
_DT_DCOMPLEX = _DT.DT_DCOMPLEX
_DT_STRING = _DT.DT_STRING
_DT_DATE = _DT.DT_DATE
_DT_ENUM = _DT.DT_ENUM
_DT_BYTESTR = _DT.DT_BYTESTR
_DT_UNKNOWN = _DT.DT_UNKNOWN

_INT_LIKE: frozenset[int] = frozenset({_DT_SHORT, _DT_LONG, _DT_ENUM})
_STR_LIKE: frozenset[int] = frozenset({_DT_STRING, _DT_DATE})


# ---------------------------------------------------------------------------
# Null detection
# ---------------------------------------------------------------------------


def _is_null(val: Any) -> bool:
    """Return *True* when *val* should be treated as a null/missing entry.

    Handles ``None``, ``float('nan')``, ``numpy.nan``, ``pandas.NA`` and
    ``pandas.NaT``.  Lists and numpy arrays are always considered non-null at
    the cell level, even when they contain NaN elements.
    """
    if val is None:
        return True
    if isinstance(val, (list, np.ndarray)):
        return False
    try:
        result = pd.isna(val)
        if isinstance(result, (bool, np.bool_)):
            return bool(result)
        return False  # array-like result — not a scalar null
    except TypeError, ValueError:
        return False


# ---------------------------------------------------------------------------
# ODS type inference from pandas dtype
# ---------------------------------------------------------------------------


def _infer_ods_type(series: pd.Series[Any]) -> int:
    """Infer an ODS DataTypeEnum integer from a pandas Series dtype."""
    dtype = series.dtype

    if dtype == np.dtype("bool") or isinstance(dtype, pd.BooleanDtype):
        return _DT_BOOLEAN
    if dtype == np.dtype("uint8"):
        return _DT_BYTE
    if dtype == np.dtype("int16") or isinstance(dtype, pd.Int16Dtype):
        return _DT_SHORT
    if dtype in (np.dtype("int8"), np.dtype("int32")) or isinstance(dtype, (pd.Int8Dtype, pd.Int32Dtype)):
        return _DT_LONG
    if dtype == np.dtype("int64") or isinstance(dtype, pd.Int64Dtype):
        return _DT_LONGLONG
    if dtype == np.dtype("float32") or isinstance(dtype, pd.Float32Dtype):
        return _DT_FLOAT
    if dtype == np.dtype("float64") or isinstance(dtype, pd.Float64Dtype):
        return _DT_DOUBLE
    if dtype == np.dtype("complex64"):
        return _DT_COMPLEX
    if dtype == np.dtype("complex128"):
        return _DT_DCOMPLEX
    if isinstance(dtype, pd.StringDtype):
        return _DT_STRING

    # For object dtype, peek at the first non-null value to infer a type.
    if dtype == np.dtype("object"):
        for val in series:
            if not _is_null(val):
                if isinstance(val, bytes):
                    return _DT_BYTESTR
                if isinstance(val, bool):
                    return _DT_BOOLEAN
                if isinstance(val, int):
                    return _DT_LONGLONG
                if isinstance(val, float):
                    return _DT_DOUBLE
                break
        return _DT_STRING

    return _DT_STRING  # safe fallback for any unrecognised dtype


# ---------------------------------------------------------------------------
# Scalar value writers
# ---------------------------------------------------------------------------


def _write_scalar(column: Any, val: Any, data_type: int) -> None:
    """Append one non-null scalar *val* to the appropriate protobuf array."""
    if data_type in _STR_LIKE:
        column.string_array.values.append(str(val))
    elif data_type in _INT_LIKE:
        column.long_array.values.append(int(val))
    elif data_type == _DT_LONGLONG:
        column.longlong_array.values.append(int(val))
    elif data_type == _DT_FLOAT:
        column.float_array.values.append(float(val))
    elif data_type == _DT_DOUBLE:
        column.double_array.values.append(float(val))
    elif data_type == _DT_BOOLEAN:
        column.boolean_array.values.append(bool(val))
    elif data_type == _DT_BYTE:
        column.byte_array.values += bytes([int(val) & 0xFF])
    elif data_type == _DT_BYTESTR:
        bv: bytes = val if isinstance(val, bytes) else str(val).encode()
        column.bytestr_array.values.append(bv)
    elif data_type == _DT_COMPLEX:
        c = complex(val)
        column.float_array.values.append(float(c.real))
        column.float_array.values.append(float(c.imag))
    elif data_type == _DT_DCOMPLEX:
        dc = complex(val)
        column.double_array.values.append(float(dc.real))
        column.double_array.values.append(float(dc.imag))
    else:
        column.string_array.values.append(str(val))


def _write_default(column: Any, data_type: int) -> None:
    """Append a zero/default placeholder for a null row."""
    if data_type in _STR_LIKE:
        column.string_array.values.append("")
    elif data_type in _INT_LIKE:
        column.long_array.values.append(0)
    elif data_type == _DT_LONGLONG:
        column.longlong_array.values.append(0)
    elif data_type == _DT_FLOAT:
        column.float_array.values.append(0.0)
    elif data_type == _DT_DOUBLE:
        column.double_array.values.append(0.0)
    elif data_type == _DT_BOOLEAN:
        column.boolean_array.values.append(False)
    elif data_type == _DT_BYTE:
        column.byte_array.values += b"\x00"
    elif data_type == _DT_BYTESTR:
        column.bytestr_array.values.append(b"")
    elif data_type == _DT_COMPLEX:
        column.float_array.values.append(0.0)
        column.float_array.values.append(0.0)
    elif data_type == _DT_DCOMPLEX:
        column.double_array.values.append(0.0)
        column.double_array.values.append(0.0)
    else:
        column.string_array.values.append("")


# ---------------------------------------------------------------------------
# Column fillers
# ---------------------------------------------------------------------------


def _fill_normal_column(column: Any, series: pd.Series[Any], data_type: int) -> None:
    """Fill a scalar ``DataMatrix.Column`` from a pandas Series.

    ``NaN`` / ``None`` / ``pd.NA`` / ``pd.NaT`` values set
    ``column.is_null[i] = True`` and write a zero placeholder into the data
    array so that all arrays stay aligned.
    """
    for val in series:
        null = _is_null(val)
        column.is_null.append(null)
        if null:
            _write_default(column, data_type)
        else:
            _write_scalar(column, val, data_type)


def _ua_fill_values(ua: Any, seq_data: list[Any]) -> None:
    """Fill an ``UnknownArray`` by inferring the concrete ODS type from values."""
    if not seq_data:
        return

    first: Any = None
    for v in seq_data:
        if not _is_null(v):
            first = v
            break

    if first is None:
        return  # all-null list — leave UnknownArray empty

    if isinstance(first, (bool, np.bool_)):
        ua.data_type = _DT_BOOLEAN
        ua.boolean_array.values.extend([bool(v) for v in seq_data])
    elif isinstance(first, (int, np.integer)):
        ua.data_type = _DT_LONGLONG
        ua.longlong_array.values.extend([int(v) for v in seq_data])
    elif isinstance(first, (float, np.floating)):
        ua.data_type = _DT_DOUBLE
        ua.double_array.values.extend([float(v) for v in seq_data])
    elif isinstance(first, bytes):
        ua.data_type = _DT_BYTESTR
        ua.bytestr_array.values.extend([v if isinstance(v, bytes) else str(v).encode() for v in seq_data])
    else:
        ua.data_type = _DT_STRING
        ua.string_array.values.extend([str(v) for v in seq_data])


def _fill_unknown_array_column(column: Any, series: pd.Series[Any]) -> None:
    """Fill a ``DataMatrix.Column`` with ``UnknownArray`` entries.

    Each cell must be a ``list`` or ``numpy.ndarray`` of values (the
    *sequence-per-row* pattern used by ``AoLocalColumn.Values``).  A cell
    that is ``None`` / ``pd.NA`` / NaN is treated as a null entry: it produces
    an empty ``UnknownArray`` with ``is_null=True``.
    """
    for val in series:
        ua = column.unknown_arrays.values.add()
        null = _is_null(val)
        column.is_null.append(null)
        if not null:
            items: list[Any] = list(val) if not isinstance(val, list) else val
            _ua_fill_values(ua, items)


# ---------------------------------------------------------------------------
# Effective ODS type resolution
# ---------------------------------------------------------------------------


def _resolve_data_type(
    model_type: int,
    attr_name: str,
    series: pd.Series[Any],
    hints: dict[str, int] | None,
) -> int:
    """Return the effective ODS data type for one column.

    Priority order: *hints* > model attribute type > inferred from dtype.
    """
    if hints is not None and attr_name in hints:
        return hints[attr_name]
    if model_type not in (_DT_UNKNOWN, 0):
        return model_type
    return _infer_ods_type(series)


# ---------------------------------------------------------------------------
# Matrix row count helper
# ---------------------------------------------------------------------------


def _matrix_row_count(matrix: ods.DataMatrix) -> int | None:
    """Return the number of data rows in *matrix*, or ``None`` if empty."""
    for col in matrix.columns:
        if col.is_null:
            return len(col.is_null)
        which = col.WhichOneof("ValuesOneOf")
        if which == "string_array":
            return len(col.string_array.values)
        if which == "long_array":
            return len(col.long_array.values)
        if which == "longlong_array":
            return len(col.longlong_array.values)
        if which == "float_array":
            return len(col.float_array.values)
        if which == "double_array":
            return len(col.double_array.values)
        if which == "boolean_array":
            return len(col.boolean_array.values)
        if which == "byte_array":
            return len(col.byte_array.values)
        if which == "bytestr_array":
            return len(col.bytestr_array.values)
        if which == "unknown_arrays":
            return len(col.unknown_arrays.values)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def dataframe_to_datamatrix(
    df: pd.DataFrame,
    model_cache: ModelCache,
    entity_name: str | None = None,
    *,
    name_separator: str = ".",
    data_type_hints: dict[str, int] | None = None,
) -> ods.DataMatrix:
    """Convert a Pandas ``DataFrame`` to an ``ods.DataMatrix``.

    Each DataFrame column maps to one ``DataMatrix.Column``.  Column names
    can be plain attribute names (requires *entity_name*) or prefixed as
    ``'Entity.Attribute'`` (the prefix is overridden when *entity_name* is
    given).

    ``NaN`` / ``None`` / ``pd.NA`` / ``pd.NaT`` values are recorded via
    ``column.is_null``.  A zero-value placeholder is written at the
    corresponding position in the data array so that all arrays remain
    aligned.

    Args:
        df:              Source DataFrame.
        model_cache:     :class:`~odsbox.model_cache.ModelCache` wrapping the
                         ODS application model.  Provides case-insensitive
                         entity/attribute lookup by application or base name.
        entity_name:     Application or base name of the ODS entity.  When
                         provided, wins over any ``Entity.`` prefix in the
                         column names.
        name_separator:  Separator used to split ``'Entity.Attribute'`` names.
        data_type_hints: ``{attr_app_name: DataTypeEnum}`` override map.
                         Wins over both the model type and the inferred dtype.

    Returns:
        ``ods.DataMatrix`` with matrix metadata and one ``Column`` per
        DataFrame column.
    """
    col_names = list(df.columns)
    entity, resolved = resolve_entity_and_columns(col_names, model_cache, entity_name, name_separator)

    matrix = ods.DataMatrix()
    matrix.name = entity.name
    matrix.base_name = entity.base_name
    matrix.aid = entity.aid

    for df_col, (attr_name, attr_base_name, model_dt) in zip(col_names, resolved):
        series: pd.Series[Any] = df[df_col]
        data_type = _resolve_data_type(model_dt, attr_name, series, data_type_hints)

        column = matrix.columns.add()
        column.name = attr_name
        column.base_name = attr_base_name
        column.data_type = data_type  # type: ignore[assignment]

        _fill_normal_column(column, series, data_type)

    return matrix


def dataframe_to_unknown_array_datamatrix(
    df: pd.DataFrame,
    model_cache: ModelCache,
    entity_name: str | None = None,
    *,
    name_separator: str = ".",
) -> ods.DataMatrix:
    """Convert a ``DataFrame`` to a ``DataMatrix`` using ``UnknownArray`` columns.

    Use this for entity attributes that store a sequence of values per row
    (e.g. ``AoLocalColumn.Values``).  Each DataFrame cell must be a ``list``
    or ``numpy.ndarray``; the ODS data type is inferred from the element
    values.

    A cell that is ``None`` / ``pd.NA`` / NaN is treated as null: it produces
    an empty ``UnknownArray`` with ``is_null=True``.

    Args:
        df:             Source DataFrame.  Each cell must be a list, numpy
                        array, or a null value (``None`` / ``pd.NA`` / NaN).
        model_cache:    :class:`~odsbox.model_cache.ModelCache` wrapping the
                        ODS application model.
        entity_name:    Entity application or base name.  Wins over any prefix.
        name_separator: Separator for ``'Entity.Attribute'`` column names.

    Returns:
        ``ods.DataMatrix`` with one ``unknown_arrays``-typed ``Column`` per
        DataFrame column.
    """
    col_names = list(df.columns)
    entity, resolved = resolve_entity_and_columns(col_names, model_cache, entity_name, name_separator)

    matrix = ods.DataMatrix()
    matrix.name = entity.name
    matrix.base_name = entity.base_name
    matrix.aid = entity.aid

    for df_col, (attr_name, attr_base_name, _model_dt) in zip(col_names, resolved):
        series: pd.Series[Any] = df[df_col]

        column = matrix.columns.add()
        column.name = attr_name
        column.base_name = attr_base_name
        column.data_type = _DT_UNKNOWN

        _fill_unknown_array_column(column, series)

    return matrix


def merge_into_datamatrix(
    target: ods.DataMatrix,
    df: pd.DataFrame,
    model_cache: ModelCache,
    entity_name: str | None = None,
    *,
    name_separator: str = ".",
    use_unknown_arrays: bool = False,
    data_type_hints: dict[str, int] | None = None,
) -> None:
    """Append new columns from *df* into *target* in-place.

    Only new (non-duplicate) columns are permitted.

    Args:
        target:            ``DataMatrix`` to extend.  Modified in-place.
        df:                Source DataFrame.
        model_cache:       :class:`~odsbox.model_cache.ModelCache` wrapping
                           the ODS application model.
        entity_name:       Entity name override.  Wins over any prefix.
        name_separator:    Separator for ``'Entity.Attribute'`` column names.
        use_unknown_arrays: When ``True``, each cell must be a list and is
                           stored as an ``UnknownArray`` column.
        data_type_hints:   ``{attr_app_name: DataTypeEnum}`` type override.

    Raises:
        ValueError: If a column already exists in *target*, the entity does
                    not match ``target.aid``, or the DataFrame row count does
                    not match the existing data.
    """
    col_names = list(df.columns)
    entity, resolved = resolve_entity_and_columns(col_names, model_cache, entity_name, name_separator)

    if target.aid and entity.aid != target.aid:
        raise ValueError(
            f"Entity mismatch: incoming columns belong to '{entity.name}' "
            f"(aid={entity.aid}), but target matrix has aid={target.aid}."
        )

    existing_names = {col.name for col in target.columns}
    for attr_name, _, _ in resolved:
        if attr_name in existing_names:
            raise ValueError(
                f"Column '{attr_name}' already exists in the target DataMatrix. "
                "merge_into_datamatrix only appends new columns."
            )

    existing_rows = _matrix_row_count(target)
    if existing_rows is not None and existing_rows > 0 and existing_rows != len(df):
        raise ValueError(
            f"Row count mismatch: target DataMatrix has {existing_rows} rows "
            f"but the incoming DataFrame has {len(df)} rows."
        )

    if use_unknown_arrays:
        for df_col, (attr_name, attr_base_name, _model_dt) in zip(col_names, resolved):
            series: pd.Series[Any] = df[df_col]
            column = target.columns.add()
            column.name = attr_name
            column.base_name = attr_base_name
            column.data_type = _DT_UNKNOWN
            _fill_unknown_array_column(column, series)
    else:
        for df_col, (attr_name, attr_base_name, model_dt) in zip(col_names, resolved):
            series = df[df_col]
            data_type = _resolve_data_type(model_dt, attr_name, series, data_type_hints)
            column = target.columns.add()
            column.name = attr_name
            column.base_name = attr_base_name
            column.data_type = data_type  # type: ignore[assignment]
            _fill_normal_column(column, series, data_type)
