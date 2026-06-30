"""DataFrame ↔ DataMatrix conversion utilities.

Convert Pandas DataFrames to ``ods.DataMatrix`` protobuf messages.

Two conversion modes are supported:

* **Normal mode** (``dataframe_to_datamatrix``): each DataFrame cell is a
  single scalar value stored in the typed array of the column (e.g.
  ``long_array``, ``string_array``).

* **Unknown-array mode** (``dataframe_to_unknown_array_datamatrix``): each
  DataFrame cell is a ``list`` or ``numpy.ndarray`` of values stored in an
  ``UnknownArray`` sub-message.  Use this for attributes such as
  ``AoLocalColumn.Values`` where every row carries a variable-length sequence.

Column names follow the same ``'Entity.Attribute'`` naming convention used
by ``odsbox.datamatrices_to_pandas.to_pandas``, enabling roundtrips.

Example::

    from wodson.data_matrix import dataframe_to_datamatrix

    matrix = dataframe_to_datamatrix(df, model_cache, entity_name="Measurement")
"""

from ._pandas_writer import (
    dataframe_to_datamatrix,
    dataframe_to_unknown_array_datamatrix,
    merge_into_datamatrix,
)

__all__ = [
    "dataframe_to_datamatrix",
    "dataframe_to_unknown_array_datamatrix",
    "merge_into_datamatrix",
]
