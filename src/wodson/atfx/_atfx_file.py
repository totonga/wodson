"""Convenience wrapper for file-backed measurement access via AtfxSession.

Provides :class:`AtfxFile`, a context manager that builds a ConI connection
from a file path and exposes generic helpers inherited from
:class:`wodson.simple.measurements.Measurements`.

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
from typing import Any

from odsbox.con_i import ConI

from wodson.simple.measurements import Measurements

from ._session import AtfxSession

_log = logging.getLogger(__name__)


class AtfxFile(Measurements):
    """File-backed high-level ATFX reader with DataFrame query helpers.

    :param filepath: Path to an ATFX file to open.

    Example::

        with AtfxFile("data.atfx") as atfx:

            groups = atfx.groups()
            for group_id in groups["id"].to_list():
                df = atfx.read_channels(group_id)
                display(df.head())
    """

    def __init__(
        self,
        filepath: str | Path,
        *,
        lazy_load_binary: bool = True,
        strict_binary_load: bool = False,
    ) -> None:
        """Initialize AtfxFile with the given ATFX file path.

        :param filepath: Path to an ATFX file to open.
        :param lazy_load_binary: When true, defer external binary reads until
            the relevant values are queried. Set to false to eagerly load the
            referenced binary payloads while opening the file.
        :param strict_binary_load: When true together with
            ``lazy_load_binary=False``, fail open if any referenced external
            binary payload is unreadable.
        """
        self._filepath = str(filepath)
        self._lazy_load_binary = lazy_load_binary
        self._strict_binary_load = strict_binary_load
        self._session: AtfxSession | None = None
        self._atfx_con_i: ConI | None = None

    def __enter__(self) -> AtfxFile:
        """Open the ATFX file and initialize the ConI connection."""
        _log.debug("Opening ATFX file: %s", self._filepath)

        # Create and enter AtfxSession
        self._session = AtfxSession(
            default_file=self._filepath,
            lazy_load_binary=self._lazy_load_binary,
            strict_binary_load=self._strict_binary_load,
        )
        self._session.__enter__()

        # Create and enter ConI with immediate model loading
        self._atfx_con_i = ConI(
            url=self._session.url,
            auth=None,
            custom_session=self._session,
            load_model=True,  # Load model immediately for .mc access
        )
        self._atfx_con_i.__enter__()

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Clean up ConI and AtfxSession resources."""
        # Exit in reverse order: ConI first, then session
        if self._atfx_con_i is not None:
            try:
                self._atfx_con_i.__exit__(exc_type, exc_val, exc_tb)
            except Exception:
                _log.exception("Error closing ConI connection")
            finally:
                self._atfx_con_i = None

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

        :raises RuntimeError: If accessed outside of a context manager.
        """
        if self._atfx_con_i is None:
            raise RuntimeError("AtfxFile must be used as a context manager")
        return self._atfx_con_i
