"""Tests for ASAM ODS URL path resolution (_path_resolver.py)."""

import platform
from typing import Any, Literal, cast
from unittest.mock import Mock

import pytest

from wodson.utils._path_resolver import (
    InvalidFileModeError,
    InvalidFileNotationError,
    InvalidMultiVolumePathError,
    MissingContextVariableError,
    PathResolver,
    UnknownSourceAttributeError,
    UnknownSymbolError,
)

FILE_MODE_ABSOLUTE = PathResolver.FILE_MODE_ABSOLUTE
FILE_MODE_SINGLE_VOLUME = PathResolver.FILE_MODE_SINGLE_VOLUME
FILE_MODE_MULTI_VOLUME = PathResolver.FILE_MODE_MULTI_VOLUME

FILE_NOTATION_UNC_WIN = PathResolver.FILE_NOTATION_UNC_WIN
FILE_NOTATION_UNC_UNIX = PathResolver.FILE_NOTATION_UNC_UNIX
FILE_NOTATION_URL = PathResolver.FILE_NOTATION_URL

JOIN_BEHAVIOR_DEFAULT: Literal["DEFAULT"] = cast(
    Literal["DEFAULT"],
    PathResolver.JOIN_BEHAVIOR_DEFAULT,
)
JOIN_BEHAVIOR_ATTACH: Literal["ATTACH"] = cast(
    Literal["ATTACH"],
    PathResolver.JOIN_BEHAVIOR_ATTACH,
)

SOURCE_ATTR_FILENAME = PathResolver.SOURCE_ATTR_FILENAME
SOURCE_ATTR_FLAGS_FILENAME = PathResolver.SOURCE_ATTR_FLAGS_FILENAME
SOURCE_ATTR_LOCATION = PathResolver.SOURCE_ATTR_LOCATION
SOURCE_ATTR_AO_LOCATION = PathResolver.SOURCE_ATTR_AO_LOCATION

CTX_FILE_MODE = PathResolver.CTX_FILE_MODE
CTX_FILE_NOTATION = PathResolver.CTX_FILE_NOTATION
CTX_FILE_SYMBOLS = PathResolver.CTX_FILE_SYMBOLS
CTX_FILE_ROOT = PathResolver.CTX_FILE_ROOT
CTX_FILE_ROOT_EXTREF = PathResolver.CTX_FILE_ROOT_EXTREF
CTX_FILE_ROOT_MANAGED = PathResolver.CTX_FILE_ROOT_MANAGED

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_ods_attribute():
    """Factory for creating mock ods.Attribute objects."""

    def _create(name="test_attr", base_name="filename_url", data_type=7):  # DT_STRING=7
        attr = Mock()
        attr.name = name
        attr.base_name = base_name
        attr.data_type = data_type
        return attr

    return _create


def _make_attribute(base_name: str) -> Mock:
    """Helper to create a mock ods.Attribute from a base_name string."""
    attr = Mock()
    attr.base_name = base_name
    attr.data_type = 7 if base_name.lower() != SOURCE_ATTR_LOCATION else 15
    attr.name = f"attr_{base_name}"
    return attr


# ============================================================================
# Tests: PathResolver._get_attribute_path_mode
# ============================================================================


def test_get_source_attr_from_extref(mock_ods_attribute):
    """ExtRef datatype (15) should return EXTREF mode."""
    attr = mock_ods_attribute(base_name="some_ref", data_type=15)  # DT_EXTERNALREFERENCE
    assert PathResolver._get_attribute_path_mode(attr) is PathResolver.AttrMode.EXTREF


def test_get_source_attr_from_ds_extref(mock_ods_attribute):
    """ExtRef datatype (16) should also return EXTREF mode."""
    attr = mock_ods_attribute(base_name="some_ref", data_type=16)
    assert PathResolver._get_attribute_path_mode(attr) is PathResolver.AttrMode.EXTREF


def test_get_source_attr_from_filename_url(mock_ods_attribute):
    """filename_url base_name should return ROOT mode."""
    attr = mock_ods_attribute(base_name=SOURCE_ATTR_FILENAME)
    assert PathResolver._get_attribute_path_mode(attr) is PathResolver.AttrMode.ROOT


def test_get_source_attr_from_flags_filename_url(mock_ods_attribute):
    """flags_filename_url base_name should return ROOT mode."""
    attr = mock_ods_attribute(base_name=SOURCE_ATTR_FLAGS_FILENAME)
    assert PathResolver._get_attribute_path_mode(attr) is PathResolver.AttrMode.ROOT


def test_get_source_attr_from_ao_location(mock_ods_attribute):
    """ao_location base_name should return MANAGED mode."""
    attr = mock_ods_attribute(base_name=SOURCE_ATTR_AO_LOCATION)
    assert PathResolver._get_attribute_path_mode(attr) is PathResolver.AttrMode.MANAGED


def test_get_source_attr_from_location_base_name(mock_ods_attribute):
    """location base_name should return EXTREF mode without extref datatype."""
    attr = mock_ods_attribute(base_name=SOURCE_ATTR_LOCATION, data_type=7)
    assert PathResolver._get_attribute_path_mode(attr) is PathResolver.AttrMode.EXTREF


def test_get_source_attr_unknown_raises(mock_ods_attribute):
    """Unknown attribute should raise UnknownSourceAttributeError."""
    attr = mock_ods_attribute(base_name="unknown_attr", data_type=7)
    with pytest.raises(UnknownSourceAttributeError, match="not a recognized file attribute"):
        PathResolver._get_attribute_path_mode(attr)


# ============================================================================
# Tests: ABSOLUTE Mode
# ============================================================================


def test_absolute_mode_windows_path():
    """ABSOLUTE mode returns input unchanged (Windows path)."""
    ctx = {CTX_FILE_MODE: FILE_MODE_ABSOLUTE, CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN}
    result = PathResolver(ctx).resolve_url(r"C:\data\file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result == r"C:\data\file.dat"


def test_absolute_mode_unix_path():
    """ABSOLUTE mode returns input unchanged (Unix path)."""
    ctx = {CTX_FILE_MODE: FILE_MODE_ABSOLUTE, CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX}
    result = PathResolver(ctx).resolve_url("/data/file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result == "/data/file.dat"


def test_absolute_mode_unc_path():
    """ABSOLUTE mode returns input unchanged (UNC network path)."""
    ctx = {CTX_FILE_MODE: FILE_MODE_ABSOLUTE, CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN}
    result = PathResolver(ctx).resolve_url(r"\\server\share\file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result == r"\\server\share\file.dat"


# ============================================================================
# Tests: SINGLE_VOLUME Mode
# ============================================================================


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_single_volume_filename_url_windows():
    """SINGLE_VOLUME with filename_url uses FILE_ROOT (Windows)."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT: r"C:\data",
    }
    result = PathResolver(ctx).resolve_url(r"measurements\file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result == r"C:\data\measurements\file.dat"


def test_single_volume_filename_url_unix():
    """SINGLE_VOLUME with filename_url uses FILE_ROOT (Unix)."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX,
        CTX_FILE_ROOT: "/data",
    }
    result = PathResolver(ctx).resolve_url("measurements/file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result == "/data/measurements/file.dat"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_single_volume_flags_filename_url_windows():
    """SINGLE_VOLUME with flags_filename_url uses FILE_ROOT."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT: r"C:\data",
    }
    result = PathResolver(ctx).resolve_url(r"flags\file.btf", _make_attribute(SOURCE_ATTR_FLAGS_FILENAME))
    assert result == r"C:\data\flags\file.btf"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_single_volume_location_windows():
    """SINGLE_VOLUME with location uses FILE_ROOT_EXTREF."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT_EXTREF: r"C:\extref",
    }
    result = PathResolver(ctx).resolve_url(r"refs\doc.pdf", _make_attribute(SOURCE_ATTR_LOCATION))
    assert result == r"C:\extref\refs\doc.pdf"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_single_volume_ao_location_with_managed_windows():
    """SINGLE_VOLUME with ao_location uses FILE_ROOT_MANAGED."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT: r"C:\data",
        CTX_FILE_ROOT_MANAGED: r"C:\managed",
    }
    result = PathResolver(ctx).resolve_url(r"ao\file.dat", _make_attribute(SOURCE_ATTR_AO_LOCATION))
    assert result == r"C:\managed\ao\file.dat"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_single_volume_ao_location_fallback_windows():
    """SINGLE_VOLUME with ao_location falls back to FILE_ROOT if MANAGED not set."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT: r"C:\data",
    }
    result = PathResolver(ctx).resolve_url(r"ao\file.dat", _make_attribute(SOURCE_ATTR_AO_LOCATION))
    assert result == r"C:\data\ao\file.dat"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_single_volume_resolve_url_accepts_source_mode_root_windows():
    """resolve_url accepts PathResolver.AttrMode.ROOT directly."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT: r"C:\data",
    }
    result = PathResolver(ctx).resolve_url(r"measurements\file.dat", PathResolver.AttrMode.ROOT)
    assert result == r"C:\data\measurements\file.dat"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_single_volume_resolve_url_accepts_source_mode_extref_windows():
    """resolve_url accepts PathResolver.AttrMode.EXTREF directly."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT_EXTREF: r"C:\extref",
    }
    result = PathResolver(ctx).resolve_url(r"refs\doc.pdf", PathResolver.AttrMode.EXTREF)
    assert result == r"C:\extref\refs\doc.pdf"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_single_volume_resolve_url_accepts_source_mode_managed_windows():
    """resolve_url accepts PathResolver.AttrMode.MANAGED directly."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT: r"C:\data",
        CTX_FILE_ROOT_MANAGED: r"C:\managed",
    }
    result = PathResolver(ctx).resolve_url(r"ao\file.dat", PathResolver.AttrMode.MANAGED)
    assert result == r"C:\managed\ao\file.dat"


def test_single_volume_missing_root_raises():
    """SINGLE_VOLUME mode raises if required root is missing."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        # Missing FILE_ROOT
    }
    with pytest.raises(MissingContextVariableError, match="FILE_ROOT"):
        PathResolver(ctx).resolve_url(r"file.dat", _make_attribute(SOURCE_ATTR_FILENAME))


def test_single_volume_missing_extref_root_raises():
    """SINGLE_VOLUME location attributes require FILE_ROOT_EXTREF."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT: r"C:\data",
    }
    with pytest.raises(MissingContextVariableError, match="FILE_ROOT_EXTREF"):
        PathResolver(ctx).resolve_url(r"refs\doc.pdf", _make_attribute(SOURCE_ATTR_LOCATION))


# ============================================================================
# Tests: MULTI_VOLUME Mode
# ============================================================================


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_multi_volume_with_symbol_windows():
    """MULTI_VOLUME resolves $(SYMBOL)... syntax (Windows)."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_MULTI_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_SYMBOLS: "ROOT,BACKUP",
        "ROOT": r"C:\primary",
    }
    result = PathResolver(ctx).resolve_url(r"$(ROOT)measurements\file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result == r"C:\primary\measurements\file.dat"


def test_multi_volume_with_symbol_unix():
    """MULTI_VOLUME resolves $(SYMBOL)... syntax (Unix)."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_MULTI_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX,
        CTX_FILE_SYMBOLS: "ROOT,BACKUP",
        "ROOT": "/primary",
    }
    result = PathResolver(ctx).resolve_url("$(ROOT)measurements/file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result == "/primary/measurements/file.dat"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_multi_volume_multiple_symbols_windows():
    """MULTI_VOLUME supports multiple symbols."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_MULTI_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_SYMBOLS: "ROOT,BACKUP,TEMP",
        "BACKUP": r"D:\backup",
    }
    result = PathResolver(ctx).resolve_url(r"$(BACKUP)archive\file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result == r"D:\backup\archive\file.dat"


def test_multi_volume_no_symbol_returns_unchanged():
    """MULTI_VOLUME without symbol prefix returns input unchanged."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_MULTI_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_SYMBOLS: "ROOT",
    }
    result = PathResolver(ctx).resolve_url(r"C:\absolute\file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    # Should be normalized but not resolved
    assert "file.dat" in result


def test_multi_volume_unknown_symbol_raises():
    """MULTI_VOLUME with unknown symbol raises UnknownSymbolError."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_MULTI_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_SYMBOLS: "ROOT",
    }
    with pytest.raises(UnknownSymbolError, match="Unknown symbol 'UNKNOWN'"):
        PathResolver(ctx).resolve_url(r"$(UNKNOWN)file.dat", _make_attribute(SOURCE_ATTR_FILENAME))


def test_multi_volume_symbol_lookup_is_case_insensitive_and_trims_symbols():
    """MULTI_VOLUME normalizes FILE_SYMBOLS entries and symbol lookup."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_MULTI_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_SYMBOLS: " root , backup ",
        "root": r"D:\data",
    }
    result = PathResolver(ctx).resolve_url(r"$(RoOt)folder\file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result == r"D:\data\folder\file.dat"


def test_multi_volume_missing_closing_paren_raises():
    """MULTI_VOLUME with invalid syntax raises InvalidMultiVolumePathError."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_MULTI_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_SYMBOLS: "ROOT",
    }
    with pytest.raises(InvalidMultiVolumePathError, match="missing closing paren"):
        PathResolver(ctx).resolve_url(r"$(ROOTfile.dat", _make_attribute(SOURCE_ATTR_FILENAME))


def test_multi_volume_symbol_not_in_context_raises():
    """MULTI_VOLUME with symbol in FILE_SYMBOLS but not in context raises."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_MULTI_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_SYMBOLS: "ROOT",
        # ROOT not defined in context
    }
    with pytest.raises(MissingContextVariableError, match="not defined in context"):
        PathResolver(ctx).resolve_url(r"$(ROOT)file.dat", _make_attribute(SOURCE_ATTR_FILENAME))


def test_multi_volume_empty_symbol_root_raises():
    """MULTI_VOLUME rejects declared symbols with empty root values."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_MULTI_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_SYMBOLS: "ROOT",
        "ROOT": "",
    }
    with pytest.raises(MissingContextVariableError, match="not defined in context"):
        PathResolver(ctx).resolve_url(r"$(ROOT)file.dat", _make_attribute(SOURCE_ATTR_FILENAME))


# ============================================================================
# Tests: Separator Normalization
# ============================================================================


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_normalize_unc_win_on_windows():
    """UNC_WIN on Windows normalizes to backslashes."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT: r"C:\data",
    }
    # Input with mixed separators
    result = PathResolver(ctx).resolve_url("measurements/file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert "\\" in result
    assert "/" not in result


@pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific test")
def test_normalize_unc_win_on_unix():
    """UNC_WIN on Unix still normalizes to backslashes."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT: "/data",
    }
    # FILE_NOTATION specifies the separator convention, not the platform.
    result = PathResolver(ctx).resolve_url(r"measurements\file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert "\\" in result
    assert "/" not in result


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_normalize_unc_unix_on_windows():
    """UNC_UNIX on Windows keeps forward slashes (respects FILE_NOTATION)."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX,
        CTX_FILE_ROOT: r"C:\data",
    }
    result = PathResolver(ctx).resolve_url("measurements/file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    # FILE_NOTATION specifies the separator convention, not the platform
    # UNC_UNIX means use forward slashes, even on Windows
    assert "/" in result
    assert "\\" not in result


@pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific test")
def test_normalize_unc_unix_on_unix():
    """UNC_UNIX on Unix keeps forward slashes."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX,
        CTX_FILE_ROOT: "/data",
    }
    result = PathResolver(ctx).resolve_url("measurements/file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert "/" in result
    assert "\\" not in result


def test_normalize_url_windows():
    """URL notation creates file:// URLs (Windows)."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_URL,
        CTX_FILE_ROOT: "C:/data",
    }
    result = PathResolver(ctx).resolve_url("measurements/file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result.startswith("file:///")
    assert "/" in result
    assert "\\" not in result


def test_normalize_url_unix():
    """URL notation creates file:// URLs (Unix)."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_URL,
        CTX_FILE_ROOT: "/data",
    }
    result = PathResolver(ctx).resolve_url("measurements/file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result.startswith("file:///")
    assert "/" in result


def test_normalize_url_unc_path():
    """URL notation handles UNC paths."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_ABSOLUTE,
        CTX_FILE_NOTATION: FILE_NOTATION_URL,
    }
    result = PathResolver(ctx).resolve_url("//server/share/file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result.startswith("file://")
    assert "server" in result


# ============================================================================
# Tests: Double Separator Removal
# ============================================================================


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_no_double_separators_windows():
    """No double backslashes in result (Windows)."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT: "C:\\data\\",  # Trailing separator
    }
    result = PathResolver(ctx).resolve_url(r"\measurements\file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result == r"C:\data\measurements\file.dat"


def test_no_double_separators_unix():
    """No double slashes in result (Unix)."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX,
        CTX_FILE_ROOT: "/data/",  # Trailing separator
    }
    result = PathResolver(ctx).resolve_url("/measurements/file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    # Should not have // (except at start for absolute paths)
    assert "//" not in result[1:]  # Skip first char


def test_no_double_separators_url():
    """No double slashes in URL result (except file://)."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_URL,
        CTX_FILE_ROOT: "/data/",
    }
    result = PathResolver(ctx).resolve_url("//measurements/file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    # Should have file:/// but not more slashes
    assert result.startswith("file:///")
    # After file:///, no double slashes
    path_part = result[len("file:///") :]
    assert "//" not in path_part


def test_remove_double_separators_url_without_path_keeps_prefix() -> None:
    """A bare file:// URL is returned unchanged."""
    resolver = PathResolver(
        {
            CTX_FILE_MODE: FILE_MODE_ABSOLUTE,
            CTX_FILE_NOTATION: FILE_NOTATION_URL,
        }
    )
    assert resolver._remove_double_separators("file://") == "file://"


def test_remove_double_separators_url_without_prefix_collapses_slashes() -> None:
    """URL notation collapses duplicate slashes without a file:// prefix."""
    resolver = PathResolver(
        {
            CTX_FILE_MODE: FILE_MODE_ABSOLUTE,
            CTX_FILE_NOTATION: FILE_NOTATION_URL,
        }
    )
    assert resolver._remove_double_separators("folder//child///file.dat") == "folder/child/file.dat"


def test_join_path_components_trims_only_join_boundary():
    """Join helper removes redundant separators at the join boundary."""
    resolver = PathResolver(
        {
            CTX_FILE_MODE: FILE_MODE_ABSOLUTE,
            CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        }
    )
    result = resolver._join_path_components(r"C:\data", r"\\nested\file.dat")
    assert result == r"C:\data\nested\file.dat"


def test_join_path_components_empty_root_returns_path() -> None:
    """Join helper returns the path unchanged when the root is empty."""
    resolver = PathResolver(
        {
            CTX_FILE_MODE: FILE_MODE_ABSOLUTE,
            CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX,
        }
    )
    assert resolver._join_path_components("", "child/file.dat") == "child/file.dat"


def test_join_path_components_empty_path_returns_root() -> None:
    """Join helper returns the root unchanged when the path is empty."""
    resolver = PathResolver(
        {
            CTX_FILE_MODE: FILE_MODE_ABSOLUTE,
            CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX,
        }
    )
    assert resolver._join_path_components("/root/path", "") == "/root/path"


def test_join_with_separator_empty_normalized_root_returns_join_separator() -> None:
    """Join helper preserves one leading separator when the root is only separators."""
    resolver = PathResolver(
        {
            CTX_FILE_MODE: FILE_MODE_ABSOLUTE,
            CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX,
        }
    )
    assert resolver._join_with_separator("///", "child/file.dat") == "/child/file.dat"


def test_join_with_separator_empty_normalized_path_returns_normalized_root() -> None:
    """Join helper returns the normalized root when the path is only separators."""
    resolver = PathResolver(
        {
            CTX_FILE_MODE: FILE_MODE_ABSOLUTE,
            CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX,
        }
    )
    assert resolver._join_with_separator("root///", "///") == "root"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_unc_path_preserves_leading_double_backslash():
    r"""UNC path \\server\share preserves leading \\."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_ABSOLUTE,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
    }
    result = PathResolver(ctx).resolve_url(r"\\server\share\file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result.startswith("\\\\")
    # But should not have triple or more
    assert "\\\\\\" not in result


# ============================================================================
# Tests: Error Handling
# ============================================================================


def test_missing_file_mode_raises():
    """Missing FILE_MODE raises MissingContextVariableError."""
    ctx = {CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN}
    with pytest.raises(MissingContextVariableError, match="FILE_MODE"):
        PathResolver(ctx).resolve_url("file.dat", _make_attribute(SOURCE_ATTR_FILENAME))


def test_invalid_file_mode_raises():
    """Invalid FILE_MODE raises InvalidFileModeError."""
    ctx = {CTX_FILE_MODE: "INVALID", CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN}
    with pytest.raises(InvalidFileModeError, match="Invalid FILE_MODE"):
        PathResolver(ctx).resolve_url("file.dat", _make_attribute(SOURCE_ATTR_FILENAME))


def test_missing_file_notation_raises():
    """Missing FILE_NOTATION raises MissingContextVariableError."""
    ctx = {CTX_FILE_MODE: FILE_MODE_ABSOLUTE}
    with pytest.raises(MissingContextVariableError, match="FILE_NOTATION"):
        PathResolver(ctx).resolve_url("file.dat", _make_attribute(SOURCE_ATTR_FILENAME))


def test_invalid_file_notation_raises():
    """Invalid FILE_NOTATION raises InvalidFileNotationError."""
    ctx = {CTX_FILE_MODE: FILE_MODE_ABSOLUTE, CTX_FILE_NOTATION: "INVALID"}
    with pytest.raises(InvalidFileNotationError, match="Invalid FILE_NOTATION"):
        PathResolver(ctx).resolve_url("file.dat", _make_attribute(SOURCE_ATTR_FILENAME))


def test_invalid_source_attr_raises():
    """Invalid source_attr raises UnknownSourceAttributeError."""
    ctx = {CTX_FILE_MODE: FILE_MODE_ABSOLUTE, CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN}
    # Create an attribute with unknown base_name
    attr = Mock()
    attr.base_name = "invalid_attr"
    attr.data_type = 7
    attr.name = "test"
    with pytest.raises(UnknownSourceAttributeError, match="not a recognized file attribute"):
        PathResolver(ctx).resolve_url("file.dat", attr)


# ============================================================================
# Tests: Constructor Validation
# ============================================================================


def test_non_dict_context_raises_type_error() -> None:
    """PathResolver only accepts plain dict context values."""

    class MockContext:
        def context_read(self) -> dict[str, str]:
            return {
                CTX_FILE_MODE: FILE_MODE_ABSOLUTE,
                CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
            }

    with pytest.raises(TypeError, match="dict\\[str, str\\]"):
        PathResolver(cast(dict[str, str], MockContext()))


def test_invalid_join_behavior_raises_value_error() -> None:
    """PathResolver rejects unsupported join_behavior values."""
    with pytest.raises(ValueError, match="Invalid join_behavior"):
        PathResolver(
            {
                CTX_FILE_MODE: FILE_MODE_ABSOLUTE,
                CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX,
            },
            join_behavior=cast(Any, "invalid"),
        )


# ============================================================================
# Integration Tests: Real-World Scenarios
# ============================================================================


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_real_world_atfx_windows():
    """Realistic ATFX scenario on Windows."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT: r"C:\Measurements\Project1",
        CTX_FILE_ROOT_EXTREF: r"C:\References",
    }
    resolver = PathResolver(ctx)

    # Component file
    comp_result = resolver.resolve_url(r"SubFolder\data.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert comp_result == r"C:\Measurements\Project1\SubFolder\data.dat"

    # External reference
    ref_result = resolver.resolve_url(r"docs\spec.pdf", _make_attribute(SOURCE_ATTR_LOCATION))
    assert ref_result == r"C:\References\docs\spec.pdf"


@pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific test")
def test_real_world_atfx_unix():
    """Realistic ATFX scenario on Unix."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX,
        CTX_FILE_ROOT: "/home/user/measurements/project1",
        CTX_FILE_ROOT_EXTREF: "/home/user/references",
    }
    resolver = PathResolver(ctx)

    # Component file
    comp_result = resolver.resolve_url("subfolder/data.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert comp_result == "/home/user/measurements/project1/subfolder/data.dat"

    # External reference
    ref_result = resolver.resolve_url("docs/spec.pdf", _make_attribute(SOURCE_ATTR_LOCATION))
    assert ref_result == "/home/user/references/docs/spec.pdf"


# ============================================================================
# Tests: PathResolver class
# ============================================================================


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_path_resolver_class_single_volume():
    """PathResolver class resolves paths correctly."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT: r"C:\data",
    }
    resolver = PathResolver(ctx)
    result = resolver.resolve_url("measurements\\file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result == r"C:\data\measurements\file.dat"


def test_path_resolver_class_absolute():
    """PathResolver class handles ABSOLUTE mode."""
    ctx = {CTX_FILE_MODE: FILE_MODE_ABSOLUTE, CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN}
    resolver = PathResolver(ctx)
    result = resolver.resolve_url("C:\\data\\file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result == "C:\\data\\file.dat"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_path_resolver_class_multi_volume():
    """PathResolver class handles MULTI_VOLUME mode."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_MULTI_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_SYMBOLS: "DATA,BACKUP",
        "DATA": r"C:\primary",
        "BACKUP": r"D:\secondary",
    }
    resolver = PathResolver(ctx)
    result = resolver.resolve_url("$(DATA)measurements\\file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result == r"C:\primary\measurements\file.dat"


def test_path_resolver_case_insensitive_context():
    """PathResolver handles case-insensitive keys, values, and source attrs."""
    ctx = {
        "file_mode": "absolute",
        "File_Notation": "unc_win",
    }
    resolver = PathResolver(ctx)
    result = resolver.resolve_url("C:\\data\\file.dat", _make_attribute("FILENAME_URL"))
    assert result == "C:\\data\\file.dat"


@pytest.mark.parametrize(
    ("root", "path", "expected"),
    [
        ("a", "b", "a/b"),
        ("a/", "/b", "a/b"),
        ("a/", "b", "a/b"),
        ("a", "/b", "a/b"),
        ("a", "\\b", "a/b"),
        ("a/", "\\b", "a/b"),
        ("a\\", "b", "a/b"),
        ("a", "\\b", "a/b"),
    ],
)
def test_join_behavior_default_matrix(root: str, path: str, expected: str) -> None:
    """DEFAULT join behavior inserts a separator between bare segments."""
    resolver = PathResolver(
        {
            CTX_FILE_MODE: FILE_MODE_ABSOLUTE,
            CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX,
        },
        join_behavior=JOIN_BEHAVIOR_DEFAULT,
    )
    assert resolver._join_path_components(root, path) == expected


@pytest.mark.parametrize(
    ("root", "path", "expected"),
    [
        ("a", "b", "ab"),
        ("a/", "/b", "a/b"),
        ("a/", "b", "a/b"),
        ("a", "\\b", "a/b"),
        ("a/", "\\b", "a/b"),
        ("a\\", "b", "a/b"),
        ("a", "\\b", "a/b"),
    ],
)
def test_join_behavior_second_matrix(root: str, path: str, expected: str) -> None:
    """ATTACH join behavior skips separator insertion for bare segments only."""
    resolver = PathResolver(
        {
            CTX_FILE_MODE: FILE_MODE_ABSOLUTE,
            CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX,
        },
        join_behavior=JOIN_BEHAVIOR_ATTACH,
    )
    assert resolver._join_path_components(root, path) == expected


def test_single_volume_second_join_behavior_changes_public_result() -> None:
    """ATTACH join behavior is reflected by the public resolve_url API."""
    resolver = PathResolver(
        {
            CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
            CTX_FILE_NOTATION: FILE_NOTATION_UNC_UNIX,
            CTX_FILE_ROOT: "/base",
        },
        join_behavior=JOIN_BEHAVIOR_ATTACH,
    )
    result = resolver.resolve_url("child/file.dat", _make_attribute(SOURCE_ATTR_FILENAME))
    assert result == "/basechild/file.dat"


# ============================================================================
# Tests: resolve_urls function
# ============================================================================


def test_resolve_urls_absolute_mode(mock_ods_attribute):
    """PathResolver.resolve_urls resolves multiple URLs in ABSOLUTE mode."""
    attr = mock_ods_attribute(base_name=SOURCE_ATTR_FILENAME)
    ctx = {CTX_FILE_MODE: FILE_MODE_ABSOLUTE, CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN}
    resolver = PathResolver(ctx)
    urls = ["C:\\data\\file1.dat", "C:\\data\\file2.dat", "C:\\data\\file3.dat"]
    results = resolver.resolve_urls(urls, attr)
    assert results == ["C:\\data\\file1.dat", "C:\\data\\file2.dat", "C:\\data\\file3.dat"]


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_resolve_urls_single_volume(mock_ods_attribute):
    """PathResolver.resolve_urls resolves multiple URLs in SINGLE_VOLUME mode."""
    attr = mock_ods_attribute(base_name=SOURCE_ATTR_FILENAME)
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT: r"C:\data",
    }
    resolver = PathResolver(ctx)
    urls = ["file1.dat", "subdir\\file2.dat", "file3.dat"]
    results = resolver.resolve_urls(urls, attr)
    assert results == [
        r"C:\data\file1.dat",
        r"C:\data\subdir\file2.dat",
        r"C:\data\file3.dat",
    ]


def test_resolve_urls_empty_list(mock_ods_attribute):
    """PathResolver.resolve_urls handles empty list."""
    attr = mock_ods_attribute(base_name=SOURCE_ATTR_FILENAME)
    ctx = {CTX_FILE_MODE: FILE_MODE_ABSOLUTE, CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN}
    resolver = PathResolver(ctx)
    results = resolver.resolve_urls([], attr)
    assert results == []


def test_resolve_urls_with_path_resolver_class(mock_ods_attribute):
    """PathResolver.resolve_urls works correctly."""
    attr = mock_ods_attribute(base_name=SOURCE_ATTR_FILENAME)
    ctx = {CTX_FILE_MODE: FILE_MODE_ABSOLUTE, CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN}
    resolver = PathResolver(ctx)
    urls = ["C:\\data\\file1.dat", "C:\\data\\file2.dat"]
    results = resolver.resolve_urls(urls, attr)
    assert results == ["C:\\data\\file1.dat", "C:\\data\\file2.dat"]


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_resolve_urls_accepts_source_mode_directly():
    """resolve_urls accepts AttrMode directly."""
    ctx = {
        CTX_FILE_MODE: FILE_MODE_SINGLE_VOLUME,
        CTX_FILE_NOTATION: FILE_NOTATION_UNC_WIN,
        CTX_FILE_ROOT: r"C:\data",
    }
    resolver = PathResolver(ctx)
    urls = ["file1.dat", r"subdir\file2.dat"]
    results = resolver.resolve_urls(urls, PathResolver.AttrMode.ROOT)
    assert results == [
        r"C:\data\file1.dat",
        r"C:\data\subdir\file2.dat",
    ]
