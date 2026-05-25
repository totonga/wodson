"""Example tests for AtfxSession — readable as usage documentation.

These tests demonstrate the typical patterns for using ``AtfxSession`` as a
drop-in replacement for ``AtfxServer`` when no HTTP server is needed.  They are
intentionally verbose so that each test reads as a standalone usage example.

Quick reference::

    from asamatfx import AtfxSession, CONTEXT_VAR_ATFX_FILE
    from odsbox.con_i import ConI

    # Pattern 1 — pass the file path directly to AtfxSession
    with AtfxSession(default_file="path/to/file.atfx") as session:
        with ConI(url=session.url, custom_session=session) as con:
            model = con.model_read()

    # Pattern 2 — pass the file path through ConI context variables (mirrors AtfxServer)
    with AtfxSession() as session:
        with ConI(
            url=session.url,
            custom_session=session,
            context_variables={CONTEXT_VAR_ATFX_FILE: "path/to/file.atfx"},
        ) as con:
            model = con.model_read()
"""

from pathlib import Path

import odsbox.proto.ods_pb2 as ods
from odsbox.con_i import ConI

from asamatfx import CONTEXT_VAR_ATFX_FILE, AtfxSession

# ---------------------------------------------------------------------------
# Fixture file: the same ATFX used throughout the docs examples
# ---------------------------------------------------------------------------
SIMPLE_ATFX = Path(__file__).resolve().parent.parent / "docs" / "spec" / "examples" / "Example_Simple.atfx"


# ---------------------------------------------------------------------------
# Example 1 — connect using default_file
# ---------------------------------------------------------------------------


def test_connect_with_default_file():
    """AtfxSession(default_file=...) lets ConI connect without a context variable.

    This is the simplest pattern: pass the ATFX path once to the session and
    then create a ConI with no extra arguments.
    """
    with AtfxSession(default_file=str(SIMPLE_ATFX)) as session:
        with ConI(
            url=session.url,     # "http://asamatfx.local" — no real HTTP
            auth=None,           # no authentication needed
            custom_session=session,
            load_model=True,     # cache the model on connect
        ) as con:
            model = con.model()

    # The parsed model should contain the expected application entities
    assert len(model.entities) > 0
    assert "Environment" in model.entities
    assert "Measurement" in model.entities


# ---------------------------------------------------------------------------
# Example 2 — connect using the ATFX_FILE context variable
# ---------------------------------------------------------------------------


def test_connect_with_context_variable():
    """Passing ATFX_FILE via ConI context_variables mirrors AtfxServer behaviour.

    Use this pattern when you want the same code to work with both
    ``AtfxSession`` (in-process) and ``AtfxServer`` (over HTTP).
    """
    with AtfxSession() as session:          # no default_file on the session
        with ConI(
            url=session.url,
            auth=None,
            custom_session=session,
            context_variables={CONTEXT_VAR_ATFX_FILE: str(SIMPLE_ATFX)},
            load_model=False,
        ) as con:
            model = con.model_read()

    assert "Environment" in model.entities


# ---------------------------------------------------------------------------
# Example 3 — query data via ConI.data_read()
# ---------------------------------------------------------------------------


def test_query_data_via_coni():
    """Use ConI.data_read() to execute a SelectStatement in-process.

    The result is the same ``ods.DataMatrices`` you would get from a real
    ASAM ODS HTTP server, so existing parsing code can be reused unchanged.
    """
    with AtfxSession(default_file=str(SIMPLE_ATFX)) as session:
        with ConI(
            url=session.url,
            auth=None,
            custom_session=session,
            load_model=False,
        ) as con:
            model = con.model_read()

            # Select the Name attribute of the Environment entity
            env_entity = model.entities["Environment"]
            stmt = ods.SelectStatement()
            stmt.columns.add(aid=env_entity.aid, attribute="Id")
            stmt.columns.add(aid=env_entity.aid, attribute="Name")

            result = con.data_read(stmt)

    assert len(result.matrices) == 1
    matrix = result.matrices[0]
    assert matrix.name == "Environment"

    name_col = next(c for c in matrix.columns if c.name == "Name")
    assert name_col.string_array.values[0] == "MyEnvironment"


# ---------------------------------------------------------------------------
# Example 4 — use ConI.query_data() with JAQueL
# ---------------------------------------------------------------------------


def test_query_data_jaquel():
    """Use the higher-level ConI.query_data() with a JAQueL dict query.

    ``query_data`` converts the dict to a ``SelectStatement`` and returns
    a pandas DataFrame.  The in-process session is transparent to the caller.
    """
    with AtfxSession(default_file=str(SIMPLE_ATFX)) as session:
        with ConI(
            url=session.url,
            auth=None,
            custom_session=session,
        ) as con:
            df = con.query_data({"AoEnvironment": {}, "$attributes": {"name": 1, "id": 1}})

    assert not df.empty
    assert "Environment.Name" in df.columns
    assert "MyEnvironment" in df["Environment.Name"].values

# ---------------------------------------------------------------------------
# Example 5 — context-manager cleanup
# ---------------------------------------------------------------------------


def test_context_manager_cleanup():
    """Both AtfxSession and ConI release resources cleanly on exit.

    No exceptions should be raised when the nested ``with`` blocks exit,
    even when ``load_model=True`` triggers an extra round-trip on connect.
    """
    with AtfxSession(default_file=str(SIMPLE_ATFX)) as session:
        with ConI(
            url=session.url,
            auth=None,
            custom_session=session,
            load_model=True,
        ):
            pass  # work would go here

    # After both context managers exit the adapter should have no open sessions
    # (ConI sends DELETE on __exit__; AtfxSession.close() handles the rest)
    assert len(session._adapter._sessions) == 0
