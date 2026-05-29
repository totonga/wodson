"""AtfxStore: main public class for loading and querying ATFX files."""

from __future__ import annotations

import logging
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

import odsbox.proto.ods_pb2 as ods

from ._base_model import load_base_model
from ._data_read import data_read
from ._db import create_schema, fix_complex_values, load_instances
from ._instance_parser import ExternalComponentRef, parse_instances, resolve_external_component_refs
from ._model_builder import build_model, detect_ods_version
from ._xml_utils import _find, _findall, _text

_log = logging.getLogger(__name__)


class AtfxStore:
    """Load an ATFX file into an in-memory SQLite database and provide ODS API access.

    Usage::

        store = AtfxStore("path/to/file.atfx")
        model = store.model()
        result = store.data_read(select_statement)
    """

    def __init__(self, file_path: str | Path, base_model_path: Path | None = None) -> None:
        """Initialize the store by parsing and loading the ATFX file.

        Args:
            file_path: Path to the .atfx file.
            base_model_path: Optional path to the base model JSON. Defaults to shipped version.
        """
        self._file_path = Path(file_path).resolve()
        self._atfx_dir = self._file_path.parent
        _log.info("Loading ATFX file: %s", self._file_path)

        # Parse XML
        tree = ET.parse(self._file_path)  # noqa: S314
        root = tree.getroot()
        _log.debug("XML parsed successfully")

        # Extract version metadata from the XML
        self._ods_version: str = detect_ods_version(root)
        self._base_model_version: str = _text(root, "base_model_version")
        _log.debug(
            "ODS version: %s, base model version: %s",
            self._ods_version or "(not detected)",
            self._base_model_version or "(not set)",
        )

        # Load base model
        self._base_model = load_base_model(base_model_path)

        # Build application model
        self._model = build_model(root, self._base_model)

        # Parse file map from <files> section
        self._file_map = self._parse_file_map(root)
        if self._file_map:
            _log.debug("%d external file(s) mapped", len(self._file_map))

        # Parse instances
        instances = parse_instances(root, self._model)

        # Resolve AoExternalComponent references (third value-reference pattern)
        resolve_external_component_refs(self._model, instances, self._file_map, self._atfx_dir)

        # Register identifiers for inline <component> refs (pattern 1: embedded in lc <Values>).
        # resolve_external_component_refs handles pattern 2 (separate AoExternalComponent entity)
        # and registers those identifiers.  Pattern 1 refs are produced by parse_instances via
        # _parse_component_ref but that code has no access to file_map, so they may be absent
        # here when the ATFX <files> section is missing or incomplete.  We register them now so
        # the binary reader can find them.
        for entity_instances in instances.values():
            for inst in entity_instances:
                for val in inst.values():
                    if (
                        isinstance(val, ExternalComponentRef)
                        and val.identifier
                        and val.identifier not in self._file_map
                    ):
                        self._file_map[val.identifier] = self._atfx_dir / val.identifier

        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        create_schema(self._conn, self._model)
        load_instances(self._conn, self._model, instances, self._file_map)
        fix_complex_values(self._conn, self._model)

        # Pre-compute AID → entity map once; reused by every data_read call.
        self._aid_to_entity: dict[int, ods.Model.Entity] = {
            self._model.entities[ename].aid: self._model.entities[ename] for ename in self._model.entities
        }

        _log.info(
            "AtfxStore ready: %d entities, %d instance groups",
            len(self._model.entities),
            len(instances),
        )

    def model(self) -> ods.Model:
        """Return the application model as an ods.Model protobuf."""
        return self._model

    def data_read(self, select_statement: ods.SelectStatement) -> ods.DataMatrices:
        """Execute a SelectStatement and return DataMatrices.

        This matches the ASAM ODS HTTP API data-read method semantics.

        Args:
            select_statement: The ODS SelectStatement protobuf.

        Returns:
            ods.DataMatrices containing the query results.
        """
        return data_read(self._conn, self._model, select_statement, self._aid_to_entity)

    def context_read(self) -> ods.ContextVariables:
        """Return context variables for this ATFX session.

        Populated variables:

        * ``ASAM-ODS-VERSION`` -- ODS schema version extracted from the XML
          namespace, e.g. ``"6.1.0"``.
        * ``BASE-MODEL-VERSION`` -- value of ``<base_model_version>`` in the
          ATFX file, e.g. ``"asam35"``.
        """
        ctx = ods.ContextVariables()
        if self._ods_version:
            ctx.variables["ASAM-ODS-VERSION"].string_array.values.append(self._ods_version)
        if self._base_model_version:
            ctx.variables["BASE-MODEL-VERSION"].string_array.values.append(self._base_model_version)
        return ctx

    def close(self) -> None:
        """Close the SQLite connection."""
        _log.debug("Closing AtfxStore for %s", self._file_path)
        self._conn.close()

    def __enter__(self) -> AtfxStore:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _parse_file_map(self, root: ET.Element) -> dict[str, Path]:
        """Parse the <files> section to build identifier -> file path mapping."""
        file_map: dict[str, Path] = {}
        files_el = _find(root, "files")
        if files_el is None:
            return file_map

        for comp_el in _findall(files_el, "component"):
            identifier = _text(comp_el, "identifier")
            filename = _text(comp_el, "filename")
            if identifier and filename:
                file_map[identifier] = self._atfx_dir / filename

        return file_map
