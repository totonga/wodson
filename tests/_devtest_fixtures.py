"""Devtest-only fixtures for spec example files.

These fixtures intentionally live outside ``conftest.py`` so tests must opt in
explicitly via ``pytest_plugins`` before they can access the local
``docs/spec/examples`` corpus.
"""

from collections.abc import Generator
from pathlib import Path

import pytest

from wodson.atfx import AtfxStore

SPEC_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "docs" / "spec" / "examples"


@pytest.fixture
def spec_examples_dir() -> Path:
    return SPEC_EXAMPLES_DIR


@pytest.fixture
def simple_atfx() -> Path:
    return SPEC_EXAMPLES_DIR / "Example_Simple.atfx"


@pytest.fixture
def alltypes_atfx() -> Path:
    return SPEC_EXAMPLES_DIR / "Example_AllTypes.atfx"


@pytest.fixture
def nonnumbers_atfx() -> Path:
    return SPEC_EXAMPLES_DIR / "Example_NonNumbers.atfx"


@pytest.fixture
def common_typespecs_atfx() -> Path:
    return SPEC_EXAMPLES_DIR / "Example_CommonTypespecs.atfx"


@pytest.fixture
def cast_typespecs_atfx() -> Path:
    return SPEC_EXAMPLES_DIR / "Example_CastTypespecs.atfx"


@pytest.fixture
def descriptive_atfx() -> Path:
    return SPEC_EXAMPLES_DIR / "Example_DescriptiveData.atfx"


@pytest.fixture
def geometry_atfx() -> Path:
    return SPEC_EXAMPLES_DIR / "Example_Geometry.atfx"


@pytest.fixture
def simple_store(simple_atfx: Path) -> Generator[AtfxStore]:
    with AtfxStore(simple_atfx) as store:
        yield store


@pytest.fixture
def alltypes_store(alltypes_atfx: Path) -> Generator[AtfxStore]:
    with AtfxStore(alltypes_atfx) as store:
        yield store


@pytest.fixture
def nonnumbers_store(nonnumbers_atfx: Path) -> Generator[AtfxStore]:
    with AtfxStore(nonnumbers_atfx) as store:
        yield store
