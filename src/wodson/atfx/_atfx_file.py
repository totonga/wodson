"""Convenience wrapper for simplified ATFX file access via JAQueL and DataFrames.

Provides :class:`AtfxFile`, a high-level context manager that wraps
:class:`AtfxSession` and :class:`odsbox.con_i.ConI` to eliminate boilerplate
for common DataFrame-based workflows.

Usage::

    from wodson.atfx import AtfxFile

    # Open file and query with JAQueL syntax
    with AtfxFile("path/to/file.atfx") as atfx:
        # Access model cache
        model = atfx.mc

        # Query metadata entities
        df = atfx.query({"AoMeasurement": {}, "$attributes": {"name": 1, "id": 1}})

        # Access low-level ConI for advanced operations
        raw_result = atfx.con_i.data_read(select_statement)

        # Query bulk signal data
        timeseries_df = atfx.timeseries(...)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from odsbox.con_i import ConI

from ._session import AtfxSession

if TYPE_CHECKING:
    import pandas as pd
    from odsbox.model_cache import ModelCache

_log = logging.getLogger(__name__)


class AtfxFile:
    """High-level ATFX file reader with DataFrame-based JAQueL query interface.

    Wraps :class:`AtfxSession` and :class:`odsbox.con_i.ConI` to provide a
    simplified API for common operations. The model is loaded immediately on
    connection so that ``.mc`` property access is fast.

    :param filepath: Path to an ATFX file to open.

    Example::

        with AtfxFile("data.atfx") as atfx:
            # Explore model
            print(atfx.mc.entities)

            # Query data
            measurements = atfx.query({
                "AoMeasurement": {},
                "$attributes": {"name": 1, "id": 1}
            })
            print(measurements)
    """

    def __init__(self, filepath: str | Path) -> None:
        """Initialize AtfxFile with the given ATFX file path.

        :param filepath: Path to an ATFX file to open.
        """
        self._filepath = str(filepath)
        self._session: AtfxSession | None = None
        self._con_i: ConI | None = None

    def __enter__(self) -> AtfxFile:
        """Open the ATFX file and initialize the ConI connection."""
        _log.debug("Opening ATFX file: %s", self._filepath)

        # Create and enter AtfxSession
        self._session = AtfxSession(default_file=self._filepath)
        self._session.__enter__()

        # Create and enter ConI with immediate model loading
        self._con_i = ConI(
            url=self._session.url,
            auth=None,
            custom_session=self._session,
            load_model=True,  # Load model immediately for .mc access
        )
        self._con_i.__enter__()

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Clean up ConI and AtfxSession resources."""
        # Exit in reverse order: ConI first, then session
        if self._con_i is not None:
            try:
                self._con_i.__exit__(exc_type, exc_val, exc_tb)
            except Exception:
                _log.exception("Error closing ConI connection")
            finally:
                self._con_i = None

        if self._session is not None:
            try:
                self._session.__exit__(exc_type, exc_val, exc_tb)
            except Exception:
                _log.exception("Error closing AtfxSession")
            finally:
                self._session = None

    @property
    def con_i(self) -> ConI:
        """Access the underlying ConI instance for advanced operations.

        Use this when you need low-level access to the full ODS API, such as
        constructing custom :class:`ods.SelectStatement` queries or accessing
        other ConI methods not wrapped by :class:`AtfxFile`.

        :return: The ConI instance managing the ATFX file connection.
        :raises RuntimeError: If accessed outside of a context manager.

        Example::

            with AtfxFile("data.atfx") as atfx:
                # Build custom SelectStatement
                stmt = ods.SelectStatement()
                stmt.columns.add(aid=mea_aid, attribute="Name")
                result = atfx.con_i.data_read(stmt)
        """
        if self._con_i is None:
            raise RuntimeError("AtfxFile must be used as a context manager")
        return self._con_i

    @property
    def mc(self) -> ModelCache:
        """Access the model cache for entity and attribute inspection.

        The model cache is populated immediately when the context manager is
        entered (``load_model=True``), so this property is always ready to use.

        :return: The ModelCache instance containing the ATFX application model.
        :raises RuntimeError: If accessed outside of a context manager.

        Example::

            with AtfxFile("data.atfx") as atfx:
                # List all entities
                for entity in atfx.mc.entities.values():
                    print(entity.name, entity.aid)

                # Look up specific entity
                mea = atfx.mc.get_entity_by_name("AoMeasurement")
                print(mea.attributes)
        """
        return self.con_i.mc

    def query(
        self,
        query: str | dict[str, Any],
        *,
        enum_as_string: bool = True,
        date_as_timestamp: bool = True,
        is_null_to_nan: bool = True,
        mode: Literal["model", "query"] = "model",
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Execute a JAQueL query and return results as a pandas DataFrame.

        This is a pass-through to :meth:`odsbox.con_i.ConI.query_data` with
        identical signature. JAQueL (JSON ASAM Query Language) provides a
        dict-based query syntax that's simpler than constructing SelectStatements.

        :param query: JAQueL query dict, SQL string, or ods.SelectStatement.
        :param enum_as_string: Return enumeration values as strings instead of integers.
        :param date_as_timestamp: Return dates as timestamps instead of datetime objects.
        :param is_null_to_nan: Convert NULL values to NaN in the DataFrame.
        :param mode: Column naming mode ('model' or 'query').
        :param kwargs: Additional keyword arguments passed to query_data.
        :return: Query results as a pandas DataFrame.

        Example::

            with AtfxFile("data.atfx") as atfx:
                # Query all measurements with name and id
                df = atfx.query({
                    "AoMeasurement": {},
                    "$attributes": {"name": 1, "id": 1}
                })

                # Query with filters
                df = atfx.query({
                    "AoMeasurement": {
                        "name": {"$like": "Test%"}
                    },
                    "$attributes": {"name": 1, "date_created": 1}
                })
        """
        return self.con_i.query(
            jaquel_query=query,
            enum_as_string=enum_as_string,
            date_as_timestamp=date_as_timestamp,
            is_null_to_nan=is_null_to_nan,
            result_naming_mode=mode,
            **kwargs,
        )

    def timeseries(
        self,
        submatrix_iid: int,
        column_patterns: list[str] | None = None,
        column_patterns_case_insensitive: bool = False,
        date_as_timestamp: bool = True,
        set_independent_as_index: bool = True,
        values_start: int = 0,
        values_limit: int = 0,
    ) -> pd.DataFrame:
        """Query bulk signal data from a Submatrix as a pandas DataFrame.

        This is a pass-through to :meth:`odsbox.bulk_reader.BulkReader.data_read` with
        identical signature. Use this for efficient access to measurement data
        stored in LocalColumns within a Submatrix.

        :param submatrix_iid: Instance ID (iid) of the Submatrix to read.
        :param column_patterns: List of column name patterns (supports wildcards like "Co*").
            If None, reads all columns.
        :param column_patterns_case_insensitive: Whether column patterns are case-insensitive.
        :param date_as_timestamp: Return date columns as timestamps instead of datetime objects.
        :param set_independent_as_index: Set independent columns as DataFrame index.
        :param values_start: Start index for reading values (0-based).
        :param values_limit: Maximum number of values to read (0 = no limit).
        :return: Time series data as a pandas DataFrame.

        Example::

            with AtfxFile("data.atfx") as atfx:
                # First, find a submatrix ID
                submatrices = atfx.query({
                    "AoSubmatrix": {},
                    "$attributes": {"id": 1, "name": 1}
                })
                submatrix_id = submatrices.iloc[0]["Submatrix.Id"]

                # Read all columns from that submatrix
                df = atfx.timeseries(submatrix_id)

                # Read specific columns matching a pattern
                df = atfx.timeseries(submatrix_id, column_patterns=["Time", "Speed*"])
        """
        return self.con_i.bulk.data_read(
            submatrix_iid=submatrix_iid,
            column_patterns=column_patterns,
            column_patterns_case_insensitive=column_patterns_case_insensitive,
            date_as_timestamp=date_as_timestamp,
            set_independent_as_index=set_independent_as_index,
            values_start=values_start,
            values_limit=values_limit,
        )
