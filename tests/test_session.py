"""Tests for AtfxSession — in-process requests adapter for ConI."""

from pathlib import Path

import odsbox.proto.ods_pb2 as ods
import pytest
import requests
from google.protobuf import json_format
from odsbox.con_i import ConI

from wodson.atfx import CONTEXT_VAR_ATFX_FILE, AtfxSession
from wodson.atfx._session import AtfxAdapter

DATA_DIR = Path(__file__).resolve().parent / "data" / "openatfx" / "asam600"
SIMPLE_ATFX = DATA_DIR / "Example_Simple.atfx"
COMMON_TYPESPECS_ATFX = Path(__file__).resolve().parent / "data" / "openatfx" / "Example_CommonTypespecs.atfx"

# Used only by devtest-marked tests that assert specific instance values from the
# ASAM spec example (docs/spec/examples/, not checked in).
_SPEC_SIMPLE_ATFX = Path(__file__).resolve().parent.parent / "docs" / "spec" / "examples" / "Example_Simple.atfx"

CONTENT_TYPE_PROTO = "application/x-asamods+protobuf"
CONTENT_TYPE_JSON = "application/x-asamods+json"


# ==========================================================================
# Connect / session lifecycle
# ==========================================================================


class TestConnect:
    """Session creation and teardown."""

    def test_connect_default_file_returns_201(self):
        """POST /ods with default_file set returns 201 and Location."""
        with AtfxSession(default_file=str(SIMPLE_ATFX)) as session:
            ctx = ods.ContextVariables()
            resp = session.post(
                f"{session.url}/ods",
                data=ctx.SerializeToString(),
                headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
            )
        assert resp.status_code == 201
        assert "Location" in resp.headers
        assert "/ods/" in resp.headers["Location"]

    def test_connect_context_variable_returns_201(self):
        """POST /ods with ATFX_FILE context variable returns 201."""
        with AtfxSession() as session:
            ctx = ods.ContextVariables()
            ctx.variables[CONTEXT_VAR_ATFX_FILE].string_array.values.append(str(SIMPLE_ATFX))
            resp = session.post(
                f"{session.url}/ods",
                data=ctx.SerializeToString(),
                headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
            )
        assert resp.status_code == 201

    def test_connect_missing_atfx_file_variable_returns_400(self):
        """POST /ods without any file info returns 400."""
        with AtfxSession() as session:
            ctx = ods.ContextVariables()
            resp = session.post(
                f"{session.url}/ods",
                data=ctx.SerializeToString(),
                headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
            )
        assert resp.status_code == 400

    def test_connect_bad_file_path_returns_400(self):
        """POST /ods with a nonexistent file path returns 400."""
        with AtfxSession() as session:
            ctx = ods.ContextVariables()
            ctx.variables[CONTEXT_VAR_ATFX_FILE].string_array.values.append("/nonexistent/file.atfx")
            resp = session.post(
                f"{session.url}/ods",
                data=ctx.SerializeToString(),
                headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
            )
        assert resp.status_code == 400

    def test_connect_strict_eager_binary_validation_returns_400(self, tmp_path: Path) -> None:
        """Strict eager validation fails session creation when a referenced .dat file is missing."""
        if not COMMON_TYPESPECS_ATFX.exists():
            pytest.skip("Binary ATFX fixture not present")

        copied_atfx = tmp_path / COMMON_TYPESPECS_ATFX.name
        copied_atfx.write_bytes(COMMON_TYPESPECS_ATFX.read_bytes())

        with AtfxSession(
            default_file=str(copied_atfx),
            lazy_load_binary=False,
            strict_binary_load=True,
        ) as session:
            ctx = ods.ContextVariables()
            resp = session.post(
                f"{session.url}/ods",
                data=ctx.SerializeToString(),
                headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
            )

        assert resp.status_code == 400

    def test_logout_removes_session(self):
        """DELETE session removes it; subsequent model-read returns 404."""
        with AtfxSession(default_file=str(SIMPLE_ATFX)) as session:
            ctx = ods.ContextVariables()
            resp = session.post(
                f"{session.url}/ods",
                data=ctx.SerializeToString(),
                headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
            )
            session_url = resp.headers["Location"]

            del_resp = session.delete(session_url)
            assert del_resp.status_code == 200

            model_resp = session.post(
                f"{session_url}/model-read",
                headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
            )
            assert model_resp.status_code == 404

    def test_unknown_session_returns_404(self):
        """POST to an unknown session ID returns 404 with ErrorInfo body."""
        with AtfxSession() as session:
            resp = session.post(
                f"{session.url}/ods/no-such-session/model-read",
                headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
            )
        assert resp.status_code == 404
        error = ods.ErrorInfo()
        error.ParseFromString(resp.content)
        assert "no-such-session" in error.reason

    def test_close_cleans_up_stores(self):
        """close() on the session removes all tracked AtfxStore instances."""
        session = AtfxSession(default_file=str(SIMPLE_ATFX))
        ctx = ods.ContextVariables()
        session.post(
            f"{session.url}/ods",
            data=ctx.SerializeToString(),
            headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
        )
        assert len(session._adapter._sessions) == 1
        session.close()
        assert len(session._adapter._sessions) == 0


# ==========================================================================
# Protobuf transport
# ==========================================================================


class TestProtobuf:
    """End-to-end tests using binary protobuf encoding."""

    @pytest.fixture
    def session_url(self):
        """Yield (session, session_url) with an open ODS session."""
        with AtfxSession(default_file=str(SIMPLE_ATFX)) as session:
            ctx = ods.ContextVariables()
            resp = session.post(
                f"{session.url}/ods",
                data=ctx.SerializeToString(),
                headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
            )
            yield session, resp.headers["Location"]

    def test_context_read(self, session_url):
        """context-read returns ContextVariables with version info."""
        session, url = session_url
        resp = session.post(
            f"{url}/context-read",
            headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
        )
        assert resp.status_code == 200
        cv = ods.ContextVariables()
        cv.ParseFromString(resp.content)
        assert "ODSVERSION" in cv.variables

    def test_model_read_returns_entities(self, session_url):
        """model-read returns ods.Model with expected entities."""
        session, url = session_url
        resp = session.post(
            f"{url}/model-read",
            headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == CONTENT_TYPE_PROTO
        model = ods.Model()
        model.ParseFromString(resp.content)
        assert len(model.entities) > 0
        assert "Environment" in model.entities

    def test_data_read_returns_matrices(self, session_url):
        """data-read returns DataMatrices for a valid SelectStatement."""
        session, url = session_url

        model_resp = session.post(
            f"{url}/model-read",
            headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
        )
        model = ods.Model()
        model.ParseFromString(model_resp.content)
        env_aid = model.entities["Environment"].aid

        stmt = ods.SelectStatement()
        stmt.columns.add(aid=env_aid, attribute="Id")
        stmt.columns.add(aid=env_aid, attribute="Name")

        resp = session.post(
            f"{url}/data-read",
            data=stmt.SerializeToString(),
            headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
        )
        assert resp.status_code == 200
        result = ods.DataMatrices()
        result.ParseFromString(resp.content)
        assert len(result.matrices) == 1
        assert result.matrices[0].name == "Environment"


# ==========================================================================
# JSON transport
# ==========================================================================


class TestJson:
    """Tests using application/x-asamods+json encoding."""

    @pytest.fixture
    def open_session(self):
        with AtfxSession(default_file=str(SIMPLE_ATFX)) as session:
            ctx = ods.ContextVariables()
            resp = session.post(
                f"{session.url}/ods",
                data=ctx.SerializeToString(),
                headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
            )
            yield session, resp.headers["Location"]

    def test_connect_json_body(self):
        """POST /ods with JSON-encoded ContextVariables creates session."""
        with AtfxSession() as session:
            ctx = ods.ContextVariables()
            ctx.variables[CONTEXT_VAR_ATFX_FILE].string_array.values.append(str(SIMPLE_ATFX))
            resp = session.post(
                f"{session.url}/ods",
                data=json_format.MessageToJson(ctx).encode("utf-8"),
                headers={"Content-Type": CONTENT_TYPE_JSON, "Accept": CONTENT_TYPE_PROTO},
            )
        assert resp.status_code == 201

    def test_model_read_json_accept(self, open_session):
        """model-read with Accept: json returns JSON-encoded Model."""
        session, url = open_session
        resp = session.post(
            f"{url}/model-read",
            headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_JSON},
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == CONTENT_TYPE_JSON
        model = ods.Model()
        json_format.Parse(resp.content.decode("utf-8"), model)
        assert "Environment" in model.entities

    def test_data_read_json_body_and_accept(self, open_session):
        """data-read accepts JSON request body and returns JSON DataMatrices."""
        session, url = open_session
        model_resp = session.post(
            f"{url}/model-read",
            headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
        )
        model = ods.Model()
        model.ParseFromString(model_resp.content)
        env_aid = model.entities["Environment"].aid

        stmt = ods.SelectStatement()
        stmt.columns.add(aid=env_aid, attribute="Name")

        resp = session.post(
            f"{url}/data-read",
            data=json_format.MessageToJson(stmt).encode("utf-8"),
            headers={"Content-Type": CONTENT_TYPE_JSON, "Accept": CONTENT_TYPE_JSON},
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == CONTENT_TYPE_JSON
        result = ods.DataMatrices()
        json_format.Parse(resp.content.decode("utf-8"), result)
        assert len(result.matrices) >= 1


# ==========================================================================
# ConI integration
# ==========================================================================


class TestConI:
    """Test that odsbox ConI works end-to-end with AtfxSession."""

    def test_coni_model_read_default_file(self):
        """ConI.model_read() returns valid model via AtfxSession (default_file)."""
        with AtfxSession(default_file=str(SIMPLE_ATFX)) as session:
            with ConI(
                url=session.url,
                auth=None,
                custom_session=session,
                load_model=False,
            ) as con:
                model = con.model_read()
        assert len(model.entities) > 0
        assert "Measurement" in model.entities

    def test_coni_model_read_context_variable(self):
        """ConI.model_read() returns valid model via ATFX_FILE context variable."""
        with AtfxSession() as session:
            with ConI(
                url=session.url,
                auth=None,
                custom_session=session,
                context_variables={CONTEXT_VAR_ATFX_FILE: str(SIMPLE_ATFX)},
                load_model=False,
            ) as con:
                model = con.model_read()
        assert "Environment" in model.entities

    @pytest.mark.devtest
    def test_coni_data_read(self):
        """ConI.data_read() returns DataMatrices with expected values."""
        with AtfxSession(default_file=str(_SPEC_SIMPLE_ATFX)) as session:
            with ConI(
                url=session.url,
                auth=None,
                custom_session=session,
                load_model=False,
            ) as con:
                model = con.model_read()
                env = model.entities["Environment"]
                stmt = ods.SelectStatement()
                stmt.columns.add(aid=env.aid, attribute="Id")
                stmt.columns.add(aid=env.aid, attribute="Name")
                result = con.data_read(stmt)

        assert len(result.matrices) == 1
        name_col = next(c for c in result.matrices[0].columns if c.name == "Name")
        assert name_col.string_array.values[0] == "MyEnvironment"

    def test_coni_bad_file_raises_http_error(self):
        """ConI raises HTTPError when ATFX file cannot be loaded."""
        with AtfxSession() as session:
            with pytest.raises(requests.HTTPError):
                ConI(
                    url=session.url,
                    auth=None,
                    custom_session=session,
                    context_variables={CONTEXT_VAR_ATFX_FILE: "/nonexistent/file.atfx"},
                    load_model=False,
                )

    def test_multiple_concurrent_sessions(self):
        """Two ConI instances on one AtfxSession work independently."""
        with AtfxSession(default_file=str(SIMPLE_ATFX)) as session:
            with ConI(
                url=session.url,
                auth=None,
                custom_session=session,
                load_model=False,
            ) as con1:
                with ConI(
                    url=session.url,
                    auth=None,
                    custom_session=session,
                    load_model=False,
                ) as con2:
                    # Both sessions co-exist
                    assert len(session._adapter._sessions) == 2
                    model1 = con1.model_read()
                    model2 = con2.model_read()

        assert set(model1.entities.keys()) == set(model2.entities.keys())

    def test_context_manager_cleanup(self):
        """No errors raised when ConI and AtfxSession exit cleanly."""
        with AtfxSession(default_file=str(SIMPLE_ATFX)) as session:
            with ConI(
                url=session.url,
                auth=None,
                custom_session=session,
                load_model=True,
            ):
                pass  # simply verify no exception on entry/exit


# ==========================================================================
# AtfxAdapter direct tests
# ==========================================================================


class TestAtfxAdapter:
    """Unit tests for AtfxAdapter in isolation."""

    def test_adapter_url_property(self):
        """AtfxSession.url returns the synthetic base URL."""
        session = AtfxSession()
        assert session.url == "http://wodson.local"
        session.close()

    def test_adapter_is_instance_of_base_adapter(self):
        """AtfxAdapter inherits from requests BaseAdapter."""
        adapter = AtfxAdapter()
        assert isinstance(adapter, requests.adapters.BaseAdapter)
        adapter.close()

    def test_unknown_endpoint_returns_404(self):
        """Requests to unknown paths get a 404 error response."""
        with AtfxSession() as session:
            resp = session.post(
                f"{session.url}/ods/abc/unknown-action",
                headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
            )
        assert resp.status_code == 404
