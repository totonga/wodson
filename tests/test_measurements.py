from pathlib import Path

import pytest
from odsbox.con_i import ConI

from wodson.atfx import AtfxFile
from wodson.atfx._session import AtfxSession
from wodson.simple.measurements import Measurements

_OPENATFX_ASAM600_DIR = Path(__file__).resolve().parent / "data" / "openatfx" / "asam600"
_SIMPLE = _OPENATFX_ASAM600_DIR / "Example_Simple.atfx"


def test_measurements_constructor_takes_con_i() -> None:
    with AtfxSession(default_file=str(_SIMPLE)) as session:
        with ConI(url=session.url, auth=None, custom_session=session, load_model=True) as con:
            m = Measurements(con)
            assert m.con_i is con


def test_measurements_navigation_methods() -> None:
    with AtfxSession(default_file=str(_SIMPLE)) as session:
        with ConI(url=session.url, auth=None, custom_session=session, load_model=True) as con:
            m = Measurements(con)

            meas = m.measurements(limit=1)
            assert len(meas) <= 1
            assert len(meas) > 0

            measurement_id = int(meas.iloc[0]["id"])
            grps = m.groups(measurement_id, limit=1)
            assert len(grps) <= 1
            assert len(grps) > 0

            group_id = int(grps.iloc[0]["id"])
            ch = m.channels(group_id, limit=1)
            assert len(ch) <= 1
            assert len(ch) > 0

            data = m.read_channels(group_id, values_limit=1)
            assert len(data) <= 1


def test_atfxfile_is_measurements_subclass() -> None:
    with AtfxFile(_SIMPLE) as atfx:
        assert isinstance(atfx, Measurements)


def test_atfxfile_con_i_guard_unchanged() -> None:
    atfx = AtfxFile(_SIMPLE)
    with pytest.raises(RuntimeError, match="context manager"):
        _ = atfx.con_i
