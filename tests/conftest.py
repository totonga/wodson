"""Shared pytest fixtures for ATFX example files."""

from pathlib import Path

import pytest

from asamatfx import AtfxStore

DATA_DIR = Path(__file__).resolve().parent.parent / "docs" / "spec" / "examples"


@pytest.fixture
def data_dir():
    return DATA_DIR


@pytest.fixture
def simple_atfx():
    return DATA_DIR / "Example_Simple.atfx"


@pytest.fixture
def alltypes_atfx():
    return DATA_DIR / "Example_AllTypes.atfx"


@pytest.fixture
def nonnumbers_atfx():
    return DATA_DIR / "Example_NonNumbers.atfx"


@pytest.fixture
def common_typespecs_atfx():
    return DATA_DIR / "Example_CommonTypespecs.atfx"


@pytest.fixture
def cast_typespecs_atfx():
    return DATA_DIR / "Example_CastTypespecs.atfx"


@pytest.fixture
def descriptive_atfx():
    return DATA_DIR / "Example_DescriptiveData.atfx"


@pytest.fixture
def geometry_atfx():
    return DATA_DIR / "Example_Geometry.atfx"


@pytest.fixture
def simple_store(simple_atfx):
    with AtfxStore(simple_atfx) as store:
        yield store


@pytest.fixture
def alltypes_store(alltypes_atfx):
    with AtfxStore(alltypes_atfx) as store:
        yield store


@pytest.fixture
def nonnumbers_store(nonnumbers_atfx):
    with AtfxStore(nonnumbers_atfx) as store:
        yield store
