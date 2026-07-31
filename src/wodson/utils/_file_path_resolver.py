"""ASAM ODS URL path resolution to local file paths.

Implements the ASAM ODS specification section 3.10.6 for resolving external file
URLs using FILE_MODE, FILE_NOTATION, and context-provided root paths.
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from odsbox.proto import ods

# ============================================================================
# Exceptions
# ============================================================================


class PathResolutionError(Exception):
    """Base exception for path resolution errors."""


class InvalidFileModeError(PathResolutionError):
    """FILE_MODE value is invalid or unknown."""


class InvalidFileNotationError(PathResolutionError):
    """FILE_NOTATION value is invalid or unknown."""


class UnknownSourceAttributeError(PathResolutionError):
    """Source attribute is not a recognized file attribute."""


class MissingContextVariableError(PathResolutionError):
    """Required context variable is missing."""


class UnknownSymbolError(PathResolutionError):
    """Symbol referenced in MULTI_VOLUME mode is not in FILE_SYMBOLS.

    Corresponds to ASAM ODS error code: AO_BAD_PARAMETER
    """


class InvalidMultiVolumePathError(PathResolutionError):
    """MULTI_VOLUME path does not follow $(SYMBOL)... syntax."""


# ============================================================================
# Path Resolution Class
# ============================================================================


class FilePathResolver:
    """Resolves ASAM ODS URLs to absolute file paths.

    Implements ASAM ODS specification section 3.10.6 path resolution logic.

    Examples:
        >>> ctx = {"FILE_MODE": "SINGLE_VOLUME", "FILE_NOTATION": "UNC_WIN", "FILE_ROOT": "C:\\data"}
        >>> resolver = FilePathResolver(ctx)
        >>> class _Attr:
        ...     base_name = "filename_url"
        ...     data_type = 7
        ...     name = "filename_url"
        >>> resolver.resolve_url("measurements\\file.dat", _Attr())
        'C:\\data\\measurements\\file.dat'
    """

    class AttrMode(Enum):
        """Internal three-state resolution mode derived from a source attribute."""

        ROOT = "root"
        EXTREF = "extref"
        MANAGED = "managed"

    FILE_MODE_ABSOLUTE = "ABSOLUTE"
    FILE_MODE_SINGLE_VOLUME = "SINGLE_VOLUME"
    FILE_MODE_MULTI_VOLUME = "MULTI_VOLUME"

    FILE_NOTATION_UNC_WIN = "UNC_WIN"
    FILE_NOTATION_UNC_UNIX = "UNC_UNIX"
    FILE_NOTATION_URL = "URL"

    JOIN_BEHAVIOR_DEFAULT = "DEFAULT"
    JOIN_BEHAVIOR_ATTACH = "ATTACH"

    SOURCE_ATTR_FILENAME = "filename_url"
    SOURCE_ATTR_FLAGS_FILENAME = "flags_filename_url"
    SOURCE_ATTR_LOCATION = "location"
    SOURCE_ATTR_AO_LOCATION = "ao_location"

    CTX_FILE_MODE = "FILE_MODE"
    CTX_FILE_NOTATION = "FILE_NOTATION"
    CTX_FILE_SYMBOLS = "FILE_SYMBOLS"
    CTX_FILE_ROOT = "FILE_ROOT"
    CTX_FILE_ROOT_EXTREF = "FILE_ROOT_EXTREF"
    CTX_FILE_ROOT_MANAGED = "FILE_ROOT_MANAGED"

    _log = logging.getLogger(__name__)

    __slots__ = (
        "_context",
        "_join_separator",
        "_join_behavior",
        "_mode",
        "_notation",
        "_root_by_source_mode",
        "_root_key_by_source_mode",
        "_symbols",
    )

    _VALID_FILE_MODES = frozenset((FILE_MODE_ABSOLUTE, FILE_MODE_SINGLE_VOLUME, FILE_MODE_MULTI_VOLUME))
    _VALID_FILE_NOTATIONS = frozenset((FILE_NOTATION_UNC_WIN, FILE_NOTATION_UNC_UNIX, FILE_NOTATION_URL))
    _VALID_JOIN_BEHAVIORS = frozenset((JOIN_BEHAVIOR_DEFAULT, JOIN_BEHAVIOR_ATTACH))
    _VALID_SOURCE_ATTRS = frozenset(
        (
            SOURCE_ATTR_FILENAME,
            SOURCE_ATTR_FLAGS_FILENAME,
            SOURCE_ATTR_LOCATION,
            SOURCE_ATTR_AO_LOCATION,
        )
    )
    _DT_EXTERNALREFERENCE = 15
    _DS_EXTERNALREFERENCE = 16
    _FORWARD_SLASH_RE = re.compile(r"/+")
    _BACKSLASH_RE = re.compile(r"\\+")
    _BACKSLASH_REPLACEMENT = r"\\"
    _URL_PREFIX = "file://"
    _URL_PATH_START = len(_URL_PREFIX)
    _WINDOWS_SEPARATOR = "\\"
    _UNIX_SEPARATOR = "/"
    _UNC_PREFIX = "\\\\"
    _MULTI_VOLUME_PREFIX = "$("

    def __init__(
        self,
        context: dict[str, str],
        join_behavior: Literal["DEFAULT", "ATTACH"] = "DEFAULT",
    ) -> None:
        """Initialize the resolver with a context dict.

        Args:
            context: Context variables dict. Keys are normalized to uppercase.
            join_behavior: Controls how root/path segments are joined when neither
                side provides a separator. DEFAULT inserts one separator, ATTACH
                concatenates directly.
        """
        if not isinstance(context, dict):
            msg = "FilePathResolver context must be provided as dict[str, str]"
            raise TypeError(msg)

        normalized_join_behavior = join_behavior.upper()
        if normalized_join_behavior not in self._VALID_JOIN_BEHAVIORS:
            msg = f"Invalid join_behavior: {join_behavior!r} (must be one of {self._VALID_JOIN_BEHAVIORS})"
            raise ValueError(msg)

        self._context = {key.upper(): value for key, value in context.items()}
        self._join_behavior = normalized_join_behavior

        mode = self._context.get(self.CTX_FILE_MODE)
        if not mode:
            msg = f"Missing required context variable: {self.CTX_FILE_MODE}"
            self._log.error(msg)
            raise MissingContextVariableError(msg)
        self._mode = mode.upper()
        if self._mode not in self._VALID_FILE_MODES:
            msg = f"Invalid FILE_MODE: {mode!r} (must be one of {self._VALID_FILE_MODES})"
            self._log.error(msg)
            raise InvalidFileModeError(msg)

        notation = self._context.get(self.CTX_FILE_NOTATION)
        if not notation:
            msg = f"Missing required context variable: {self.CTX_FILE_NOTATION}"
            self._log.error(msg)
            raise MissingContextVariableError(msg)
        self._notation = notation.upper()
        if self._notation not in self._VALID_FILE_NOTATIONS:
            msg = f"Invalid FILE_NOTATION: {notation!r} (must be one of {self._VALID_FILE_NOTATIONS})"
            self._log.error(msg)
            raise InvalidFileNotationError(msg)

        self._context[self.CTX_FILE_MODE] = self._mode
        self._context[self.CTX_FILE_NOTATION] = self._notation

        file_root = self._context.get(self.CTX_FILE_ROOT)
        file_root_extref = self._context.get(self.CTX_FILE_ROOT_EXTREF)
        file_root_managed = self._context.get(self.CTX_FILE_ROOT_MANAGED)
        ao_root_key = self.CTX_FILE_ROOT_MANAGED if file_root_managed else self.CTX_FILE_ROOT

        self._root_key_by_source_mode = {
            FilePathResolver.AttrMode.ROOT: self.CTX_FILE_ROOT,
            FilePathResolver.AttrMode.EXTREF: self.CTX_FILE_ROOT_EXTREF,
            FilePathResolver.AttrMode.MANAGED: ao_root_key,
        }
        self._root_by_source_mode = {
            FilePathResolver.AttrMode.ROOT: file_root,
            FilePathResolver.AttrMode.EXTREF: file_root_extref,
            FilePathResolver.AttrMode.MANAGED: file_root_managed or file_root,
        }
        self._join_separator = (
            self._WINDOWS_SEPARATOR if self._notation == self.FILE_NOTATION_UNC_WIN else self._UNIX_SEPARATOR
        )
        self._symbols: frozenset[str] | None = None

    def resolve_urls(self, input_urls: list[str], attr_or_mode: ods.Model.Attribute | AttrMode) -> list[str]:
        """Resolve a list of ASAM ODS URLs to absolute file paths."""
        source_mode = (
            attr_or_mode
            if isinstance(attr_or_mode, FilePathResolver.AttrMode)
            else self._get_attribute_path_mode(attr_or_mode)
        )
        return [self._resolve_url_with_source_attr(url, source_mode) for url in input_urls]

    def resolve_url(self, input_url: str, attr_or_mode: ods.Model.Attribute | AttrMode) -> str:
        """Resolve an ASAM ODS URL to an absolute file path."""
        source_mode = (
            attr_or_mode
            if isinstance(attr_or_mode, FilePathResolver.AttrMode)
            else self._get_attribute_path_mode(attr_or_mode)
        )
        return self._resolve_url_with_source_attr(input_url, source_mode)

    @classmethod
    def _get_attribute_path_mode(cls, attribute: ods.Model.Attribute) -> AttrMode:
        """Determine the three-state path resolution mode from an attribute."""
        data_type = getattr(attribute, "data_type", None)
        attr_name = getattr(attribute, "name", "<unknown>")

        if data_type in (cls._DT_EXTERNALREFERENCE, cls._DS_EXTERNALREFERENCE):
            FilePathResolver._log.debug(
                "Attribute %s has datatype DT_EXTERNALREFERENCE -> mode=%s",
                attr_name,
                FilePathResolver.AttrMode.EXTREF.name,
            )
            return FilePathResolver.AttrMode.EXTREF

        raw_base_name = getattr(attribute, "base_name", "")
        base_name = raw_base_name.lower() if isinstance(raw_base_name, str) else ""
        if base_name in (cls.SOURCE_ATTR_FILENAME, cls.SOURCE_ATTR_FLAGS_FILENAME):
            source_mode = FilePathResolver.AttrMode.ROOT
        elif base_name == cls.SOURCE_ATTR_LOCATION:
            source_mode = FilePathResolver.AttrMode.EXTREF
        elif base_name == cls.SOURCE_ATTR_AO_LOCATION:
            source_mode = FilePathResolver.AttrMode.MANAGED
        else:
            source_mode = None

        if source_mode is not None:
            FilePathResolver._log.debug(
                "Attribute %s base_name=%s -> mode=%s",
                attr_name,
                raw_base_name,
                source_mode.name,
            )
            return source_mode

        msg = (
            f"Attribute {attr_name} (base_name={raw_base_name}, "
            f"data_type={data_type}) is not a recognized file attribute"
        )
        FilePathResolver._log.error(msg)
        raise UnknownSourceAttributeError(msg)

    def _resolve_url_with_source_attr(
        self,
        input_url: str,
        source_mode: AttrMode,
    ) -> str:
        self._log.debug(
            "resolve_url: input_url=%r, source_mode=%s, mode=%s, notation=%s",
            input_url,
            source_mode.name,
            self._mode,
            self._notation,
        )

        if self._mode == self.FILE_MODE_ABSOLUTE:
            resolved_path = self._resolve_absolute(input_url)
        elif self._mode == self.FILE_MODE_SINGLE_VOLUME:
            resolved_path = self._resolve_single_volume(input_url, source_mode)
        else:
            resolved_path = self._resolve_multi_volume(input_url)

        normalized = self._normalize_path(resolved_path)

        self._log.info(
            "Resolved path: %r -> %r (mode=%s, notation=%s)",
            input_url,
            normalized,
            self._mode,
            self._notation,
        )
        return normalized

    def _resolve_absolute(self, input_url: str) -> str:
        """BRANCH A: ABSOLUTE mode - return input unchanged."""
        self._log.debug("ABSOLUTE mode: returning input unchanged")
        return input_url

    def _resolve_single_volume(self, input_url: str, source_mode: AttrMode) -> str:
        """BRANCH B: SINGLE_VOLUME mode - concatenate root + relative path."""
        root_key = self._root_key_by_source_mode[source_mode]
        root = self._root_by_source_mode[source_mode]
        if not root:
            msg = f"Missing required context variable for SINGLE_VOLUME mode: {root_key}"
            self._log.error(msg)
            raise MissingContextVariableError(msg)

        if source_mode is FilePathResolver.AttrMode.MANAGED and root_key == self.CTX_FILE_ROOT:
            self._log.debug("FILE_ROOT_MANAGED not set, falling back to FILE_ROOT for ao_location")
        else:
            self._log.debug("SINGLE_VOLUME mode: root_key=%s, root=%r", root_key, root)

        return self._join_path_components(root, input_url)

    def _resolve_multi_volume(self, input_url: str) -> str:
        """BRANCH C: MULTI_VOLUME mode - resolve $(SYMBOL)... syntax."""
        if not input_url.startswith(self._MULTI_VOLUME_PREFIX):
            self._log.debug("MULTI_VOLUME mode: no symbol prefix, returning unchanged")
            return input_url

        end_bracket = input_url.find(")")
        if end_bracket == -1:
            msg = f"Invalid MULTI_VOLUME path syntax (missing closing paren): {input_url!r}"
            self._log.error(msg)
            raise InvalidMultiVolumePathError(msg)

        symbol = input_url[2:end_bracket]
        symbol_key = symbol.upper()
        remainder = input_url[end_bracket + 1 :]
        symbols = self._get_symbols()

        self._log.debug("MULTI_VOLUME mode: symbol=%r, remainder=%r", symbol, remainder)

        if symbol_key not in symbols:
            msg = f"Unknown symbol {symbol!r} in MULTI_VOLUME mode. Known symbols: {sorted(symbols)}"
            self._log.error(msg)
            raise UnknownSymbolError(msg)

        root_value = self._context.get(symbol_key)
        if not root_value:
            msg = f"Symbol {symbol!r} found in FILE_SYMBOLS but not defined in context"
            self._log.error(msg)
            raise MissingContextVariableError(msg)

        self._log.debug("MULTI_VOLUME mode: symbol %r resolved to %r", symbol, root_value)
        return self._join_path_components(root_value, remainder)

    def _get_symbols(self) -> frozenset[str]:
        """Parse FILE_SYMBOLS lazily and cache the normalized symbol set."""
        if self._symbols is None:
            raw_symbols = self._context.get(self.CTX_FILE_SYMBOLS, "")
            self._symbols = frozenset(symbol.strip().upper() for symbol in raw_symbols.split(",") if symbol.strip())
        return self._symbols

    def _join_path_components(self, root: str, path: str) -> str:
        """Join root and path while avoiding duplicate separators at the join."""
        if not root:
            return path
        if not path:
            return root

        root_has_separator = root.endswith((self._WINDOWS_SEPARATOR, self._UNIX_SEPARATOR))
        path_has_separator = path.startswith((self._WINDOWS_SEPARATOR, self._UNIX_SEPARATOR))

        if root_has_separator or path_has_separator:
            return self._join_with_separator(root, path)

        if self._join_behavior == self.JOIN_BEHAVIOR_ATTACH:
            return root + path

        return self._join_with_separator(root, path)

    def _join_with_separator(self, root: str, path: str) -> str:
        """Join path segments with exactly one separator at the boundary."""
        normalized_root = root.rstrip("\\/")
        normalized_path = path.lstrip("\\/")

        if not normalized_root:
            return f"{self._join_separator}{normalized_path}"
        if not normalized_path:
            return normalized_root

        return f"{normalized_root}{self._join_separator}{normalized_path}"

    def _normalize_path(self, path: str) -> str:
        """Normalize path separators according to FILE_NOTATION."""
        if self._notation == self.FILE_NOTATION_UNC_WIN:
            path = path.replace(self._UNIX_SEPARATOR, self._WINDOWS_SEPARATOR)
        elif self._notation == self.FILE_NOTATION_UNC_UNIX:
            path = path.replace(self._WINDOWS_SEPARATOR, self._UNIX_SEPARATOR)
        else:
            path = path.replace(self._WINDOWS_SEPARATOR, self._UNIX_SEPARATOR)
            if not path.startswith(self._URL_PREFIX):
                if path.startswith("//"):
                    path = f"file:{path}"
                elif path.startswith(self._UNIX_SEPARATOR):
                    path = f"{self._URL_PREFIX}{path}"
                else:
                    path = f"{self._URL_PREFIX}/{path}"

        return self._remove_double_separators(path)

    def _remove_double_separators(self, path: str) -> str:
        """Remove duplicate separators while preserving URL and UNC prefixes."""
        if self._notation == self.FILE_NOTATION_URL:
            if path.startswith(self._URL_PREFIX):
                protocol_end = path.find(self._UNIX_SEPARATOR, self._URL_PATH_START)
                if protocol_end == -1:
                    return path
                protocol_part = path[:protocol_end]
                path_part = self._FORWARD_SLASH_RE.sub(
                    self._UNIX_SEPARATOR,
                    path[protocol_end:],
                )
                return protocol_part + path_part
            return self._FORWARD_SLASH_RE.sub(self._UNIX_SEPARATOR, path)

        if self._notation == self.FILE_NOTATION_UNC_WIN:
            if path.startswith(self._UNC_PREFIX):
                return self._UNC_PREFIX + self._BACKSLASH_RE.sub(
                    self._BACKSLASH_REPLACEMENT,
                    path[2:],
                )
            return self._BACKSLASH_RE.sub(self._BACKSLASH_REPLACEMENT, path)

        return self._FORWARD_SLASH_RE.sub(self._UNIX_SEPARATOR, path)
