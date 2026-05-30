"""Generic measurement/query helpers over an existing odsbox ConI connection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from odsbox.con_i import ConI

if TYPE_CHECKING:
    import pandas as pd
    from odsbox.model_cache import ModelCache


class Measurements:
    """High-level helpers for JAQueL metadata and channel reads.

    The class is intentionally generic and only depends on an existing
    :class:`odsbox.con_i.ConI` instance.

    :param con_i: Connected ConI instance.
    """

    def __init__(self, con_i: ConI) -> None:
        self._measurements_con_i = con_i

    @property
    def con_i(self) -> ConI:
        """Return the injected ConI instance."""
        return self._measurements_con_i

    @property
    def mc(self) -> ModelCache:
        """Access the model cache exposed by ConI."""
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
        """Execute a JAQueL query and return results as a DataFrame."""
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
        """List AoMeasurement entries as a DataFrame."""
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

        q: dict[str, Any] = {
            "AoMeasurement": mea_conditions,
            "$attributes": {attr: 1 for attr in attributes},
        }
        if options:
            q["$options"] = options

        return self.query(q, mode="query")

    def groups(
        self,
        measurement_id: int | None = None,
        *,
        conditions: dict[str, Any] | None = None,
        limit: int = 10000,
    ) -> pd.DataFrame:
        """List AoSubmatrix entries for a measurement."""
        submatrix_conditions: dict[str, Any] = {}
        if measurement_id is not None:
            submatrix_conditions["measurement"] = {"id": measurement_id}
        if conditions is not None:
            submatrix_conditions.update(conditions)

        q: dict[str, Any] = {
            "AoSubmatrix": submatrix_conditions,
            "$attributes": {
                "id": 1,
                "name": 1,
                "number_of_rows": 1,
                "measurement": {"id": 1, "name": 1},
            },
        }
        if limit > 0:
            q["$options"] = {"$rowlimit": limit}

        return self.query(q, mode="query")

    def channels(self, group_id: int, *, limit: int = 10000) -> pd.DataFrame:
        """List AoLocalColumn metadata for a group."""
        q: dict[str, Any] = {
            "AoLocalColumn": {"submatrix": group_id},
            "$attributes": {
                "id": 1,
                "name": 1,
                "independent": 1,
                "measurement_quantity": {
                    "id": 1,
                    "datatype": 1,
                    "unit:OUTER": {"name": 1},
                },
            },
        }
        if limit > 0:
            q["$options"] = {"$rowlimit": limit}

        df = self.query(q, mode="query")
        return df.rename(
            columns={
                "measurement_quantity.datatype": "datatype",
                "measurement_quantity.unit:OUTER.name": "unit_string",
            }
        )

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
        """Read bulk channel values from an AoSubmatrix as a DataFrame."""
        return self.con_i.bulk.data_read(
            submatrix_iid=group_id,
            column_patterns=column_patterns,
            column_patterns_case_insensitive=column_patterns_case_insensitive,
            date_as_timestamp=date_as_timestamp,
            set_independent_as_index=set_independent_as_index,
            values_start=values_start,
            values_limit=values_limit,
        )
