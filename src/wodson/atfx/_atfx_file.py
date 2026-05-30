"""Convenience wrapper for simplified ATFX file access via JAQueL and DataFrames.

Provides :class:`AtfxFile`, a high-level context manager that wraps
:class:`AtfxSession` and :class:`odsbox.con_i.ConI` to eliminate boilerplate
for common DataFrame-based workflows.

Usage::

    from wodson.atfx import AtfxFile

    with AtfxFile("path/to/file.atfx") as atfx:
        # Navigate the measurement hierarchy
        tests_df = atfx.tests()
        meas_df  = atfx.measurements()
        grps_df  = atfx.groups(meas_df.iloc[0]["Measurement.Id"])
        ch_df    = atfx.channels(grps_df.iloc[0]["Submatrix.Id"])

        # Read bulk channel values for a group
        df = atfx.read_channels(grps_df.iloc[0]["Submatrix.Id"])

        # Flexible metadata queries via JAQueL
        df = atfx.query({"AoMeasurement": {}, "$attributes": {"name": 1, "id": 1}})

        # Low-level ConI for advanced SelectStatement access
        raw_result = atfx.con_i.data_read(select_statement)
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

    :param filepath: Path to an ATFX file to open.

    Example::

        with AtfxFile("data.atfx") as atfx:

            groups = atfx.groups()
            for group_id in groups["id"].to_list():
                df = atfx.read_channels(group_id)
                display(df.head())
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
                for entity in atfx.mc.model().entities.values():
                    print(entity.name, entity.aid)

                # Look up specific entity
                mea = atfx.mc.entity_by_base_name("AoMeasurement")
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
                        "name": {"$like": "My_Mea*"}
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

    def measurements(
        self,
        *,
        name_filter: str | None = None,
        conditions: dict[str, Any] | None = None,
        limit: int = 10000,
    ) -> pd.DataFrame:
        """List measurement entries (AoMeasurement) as a DataFrame.

        When the application model includes an AoTest entity, the parent test id
        and name are automatically added via a JAQueL join.

        :param name_filter: Optional :code:`$like` pattern to filter by measurement
            name (e.g. ``"Run_*"``). ``None`` returns all measurements.
        :param conditions: Extra JAQueL filter conditions merged into the
            AoMeasurement clause (e.g. ``{"measurement_begin": {"$gte": "20240101"}}``).  
        :param limit: Maximum number of rows to return. ``0`` means no limit.
        :return: DataFrame with one row per measurement.

        Example::

            with AtfxFile("data.atfx") as atfx:
                df = atfx.measurements()
                df = atfx.measurements(name_filter="Run_*", limit=50)
                df = atfx.measurements(conditions={"date_created": {"$gte": "20240101"}})
        """
        mea_conditions: dict[str, Any] = {}
        if name_filter is not None:
            mea_conditions["name"] = {"$like": name_filter}
        if conditions is not None:
            mea_conditions.update(conditions)

        options: dict[str, Any] = {}
        if limit > 0:
            options["$rowlimit"] = limit

        mea_e = self.mc.entity_by_base_name("AoMeasurement")
        
        attributes = [attr.base_name for attr in mea_e.attributes.values() if attr.base_name]

        q: dict[str, Any] = {"AoMeasurement": mea_conditions, "$attributes": {attr: 1 for attr in attributes}}
        if options:
            q["$options"] = options
        
        return self.query(q, mode="query")

    def groups(
            self, 
            measurement_id: int| None = None,
            *,
            conditions: dict[str, Any] | None = None,
            limit: int = 10000) -> pd.DataFrame:
        """List channel groups (AoSubmatrix) belonging to a measurement.

        Each group is an independent set of channels that share one x-axis
        (e.g. one sweep of time-sampled signals or a frequency run).

        :param measurement_id: Instance ID (``id``) of the parent AoMeasurement.
        :param conditions: Extra JAQueL filter conditions merged into the
            AoSubmatrix clause (e.g. ``{"number_of_rows": {"$lte": 1000000}}``).  
        :param limit: Maximum number of rows to return. ``0`` means no limit.
        :return: DataFrame with one row per group.

        Example::

            with AtfxFile("data.atfx") as atfx:
                meas = atfx.measurements()
                groups = atfx.groups(meas.iloc[0]["Measurement.Id"])
                groups = atfx.groups(meas.iloc[0]["id"])
        """
        submatrix_conditions: dict[str, Any] = {}
        if measurement_id is not None:
            submatrix_conditions["measurement"] = {"id": measurement_id}
        if conditions is not None:
            submatrix_conditions.update(conditions)

        q: dict[str, Any] = {
            "AoSubmatrix": submatrix_conditions,
            "$attributes": {"id": 1, "name": 1, "number_of_rows": 1, "measurement": {"id": 1, "name": 1}},
        }
        if limit > 0:
            q["$options"] = {"$rowlimit": limit}

        return self.query(q, mode="query")

    def channels(self, group_id: int, *, limit: int = 10000) -> pd.DataFrame:
        """List channel metadata (AoLocalColumn) belonging to a group.

        Returns metadata only — name, data type, and whether the channel is
        the independent axis. Use :meth:`read_channels` to fetch the actual
        signal values.

        :param group_id: Instance ID (``id``) of the parent AoSubmatrix (group).
    :param limit: Maximum number of rows to return. ``0`` means no limit.
        :return: DataFrame with one row per channel.

        Example::

            with AtfxFile("data.atfx") as atfx:
                groups = atfx.groups(measurement_id)
                ch   = atfx.channels(groups.iloc[0]["Submatrix.Id"])
                ch   = atfx.channels(groups.iloc[0]["id"])
        """
        q: dict[str, Any] = {
            "AoLocalColumn": {"submatrix": group_id},
            "$attributes": {"id": 1, "name": 1, "independent": 1, "measurement_quantity": {"id": 1, "datatype": 1, "unit:OUTER": {"name": 1}}},
        }
        if limit > 0:
            q["$options"] = {"$rowlimit": limit}

        df = self.query(q, mode="query")

        df = df.rename(columns={
            "measurement_quantity.datatype": "datatype",
            "measurement_quantity.unit:OUTER.name": "unit_string"
        })

        return df

    def read_channels(
        self,
        group_id: int,
        column_patterns: list[str] | None = None,
        column_patterns_case_insensitive: bool = True,
        date_as_timestamp: bool = True,
        set_independent_as_index: bool = True,
        values_start: int = 0,
        values_limit: int = 0,
    ) -> pd.DataFrame:
        """Read bulk channel values from a group (AoSubmatrix) as a DataFrame.

        Each column in the returned DataFrame corresponds to one AoLocalColumn
        within the group. The independent channel (e.g. time, RPM, frequency)
        is set as the DataFrame index by default.

        This is a pass-through to :meth:`odsbox.bulk_reader.BulkReader.data_read`.

        :param group_id: Instance ID (``id``) of the AoSubmatrix / group.
        :param column_patterns: Channel name patterns to select (supports ``*`` wildcards).
            ``None`` reads all channels.
        :param column_patterns_case_insensitive: Whether patterns are case-insensitive.
        :param date_as_timestamp: Return date channels as timestamps.
        :param set_independent_as_index: Use independent channel as DataFrame index.
        :param values_start: Start index for reading values (0-based).
        :param values_limit: Maximum number of values to read. ``0`` = no limit.
        :return: DataFrame with one column per channel and one row per sample.

        Example::

            with AtfxFile("data.atfx") as atfx:
                meas  = atfx.measurements()
                groups  = atfx.groups(meas.iloc[0]["id"])
                group_id = groups.iloc[0]["id"]

                # Read all channels
                df = atfx.read_channels(group_id)

                # Read only channels matching a pattern
                df = atfx.read_channels(group_id, column_patterns=["Time", "Speed*"])
        """
        return self.con_i.bulk.data_read(
            submatrix_iid=group_id,
            column_patterns=column_patterns,
            column_patterns_case_insensitive=column_patterns_case_insensitive,
            date_as_timestamp=date_as_timestamp,
            set_independent_as_index=set_independent_as_index,
            values_start=values_start,
            values_limit=values_limit,
        )
