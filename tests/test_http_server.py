"""Tests for the ASAM ODS HTTP server (AtfxServer)."""

from pathlib import Path

import odsbox.proto.ods_pb2 as ods
import pytest
import requests
from google.protobuf import json_format
from odsbox.con_i import ConI

from wodson.atfx import CONTEXT_VAR_ATFX_FILE, AtfxServer

DATA_DIR = Path(__file__).resolve().parent / "data" / "openatfx" / "asam600"
SIMPLE_ATFX = DATA_DIR / "Example_Simple.atfx"

CONTENT_TYPE_PROTO = "application/x-asamods+protobuf"
CONTENT_TYPE_JSON = "application/x-asamods+json"


@pytest.fixture(scope="module")
def atfx_server():
    """Start an AtfxServer for the test module."""
    with AtfxServer() as server:
        yield server


def _connect(
    server_url: str,
    file_path: str,
    *,
    content_type: str = CONTENT_TYPE_PROTO,
    accept: str = CONTENT_TYPE_PROTO,
) -> requests.Response:
    """POST /ods to create a session."""
    ctx = ods.ContextVariables()
    ctx.variables[CONTEXT_VAR_ATFX_FILE].string_array.values.append(file_path)

    if CONTENT_TYPE_JSON in content_type:
        body = json_format.MessageToJson(ctx).encode("utf-8")
    else:
        body = ctx.SerializeToString()

    return requests.post(
        f"{server_url}/ods",
        data=body,
        headers={"Content-Type": content_type, "Accept": accept},
        timeout=10,
    )


# ==========================================================================
# Protobuf content-type tests
# ==========================================================================


class TestProtobuf:
    """Tests using application/x-asamods+protobuf."""

    def test_connect_creates_session(self, atfx_server):
        """POST /ods returns 201 with a Location header."""
        resp = _connect(atfx_server.url, str(SIMPLE_ATFX))
        assert resp.status_code == 201
        assert "Location" in resp.headers
        assert "/ods/" in resp.headers["Location"]

    def test_model_read(self, atfx_server):
        """POST model-read returns a valid ods.Model."""
        resp = _connect(atfx_server.url, str(SIMPLE_ATFX))
        session_url = resp.headers["Location"]

        resp = requests.post(
            f"{session_url}/model-read",
            headers={
                "Content-Type": CONTENT_TYPE_PROTO,
                "Accept": CONTENT_TYPE_PROTO,
            },
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == CONTENT_TYPE_PROTO

        model = ods.Model()
        model.ParseFromString(resp.content)
        assert len(model.entities) > 0
        assert "Environment" in model.entities

    def test_data_read(self, atfx_server):
        """POST data-read with SelectStatement returns DataMatrices."""
        resp = _connect(atfx_server.url, str(SIMPLE_ATFX))
        session_url = resp.headers["Location"]

        # First get model to know AIDs
        resp = requests.post(
            f"{session_url}/model-read",
            headers={
                "Content-Type": CONTENT_TYPE_PROTO,
                "Accept": CONTENT_TYPE_PROTO,
            },
            timeout=10,
        )
        model = ods.Model()
        model.ParseFromString(resp.content)
        env_aid = model.entities["Environment"].aid

        # Build a SelectStatement
        stmt = ods.SelectStatement()
        stmt.columns.add(aid=env_aid, attribute="Id")
        stmt.columns.add(aid=env_aid, attribute="Name")

        resp = requests.post(
            f"{session_url}/data-read",
            data=stmt.SerializeToString(),
            headers={
                "Content-Type": CONTENT_TYPE_PROTO,
                "Accept": CONTENT_TYPE_PROTO,
            },
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == CONTENT_TYPE_PROTO

        result = ods.DataMatrices()
        result.ParseFromString(resp.content)
        assert len(result.matrices) == 1
        assert result.matrices[0].name == "Environment"

    def test_session_close(self, atfx_server):
        """DELETE session closes it; subsequent requests return 404."""
        resp = _connect(atfx_server.url, str(SIMPLE_ATFX))
        session_url = resp.headers["Location"]

        # Delete session
        resp = requests.delete(session_url, timeout=10)
        assert resp.status_code == 200

        # Subsequent model-read should fail
        resp = requests.post(
            f"{session_url}/model-read",
            headers={
                "Content-Type": CONTENT_TYPE_PROTO,
                "Accept": CONTENT_TYPE_PROTO,
            },
            timeout=10,
        )
        assert resp.status_code == 404


# ==========================================================================
# JSON content-type tests
# ==========================================================================


class TestJson:
    """Tests using application/x-asamods+json."""

    def test_connect_json_body(self, atfx_server):
        """POST /ods with JSON body creates session."""
        resp = _connect(
            atfx_server.url,
            str(SIMPLE_ATFX),
            content_type=CONTENT_TYPE_JSON,
        )
        assert resp.status_code == 201
        assert "Location" in resp.headers

    def test_model_read_json_accept(self, atfx_server):
        """model-read with Accept: json returns JSON response."""
        resp = _connect(atfx_server.url, str(SIMPLE_ATFX))
        session_url = resp.headers["Location"]

        resp = requests.post(
            f"{session_url}/model-read",
            headers={
                "Content-Type": CONTENT_TYPE_PROTO,
                "Accept": CONTENT_TYPE_JSON,
            },
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == CONTENT_TYPE_JSON

        # Parse JSON response back into Model
        model = ods.Model()
        json_format.Parse(resp.content.decode("utf-8"), model)
        assert len(model.entities) > 0

    def test_data_read_json_body(self, atfx_server):
        """data-read with JSON Content-Type request body."""
        resp = _connect(atfx_server.url, str(SIMPLE_ATFX))
        session_url = resp.headers["Location"]

        # Get model for AID
        resp = requests.post(
            f"{session_url}/model-read",
            headers={
                "Content-Type": CONTENT_TYPE_PROTO,
                "Accept": CONTENT_TYPE_PROTO,
            },
            timeout=10,
        )
        model = ods.Model()
        model.ParseFromString(resp.content)
        env_aid = model.entities["Environment"].aid

        # Send SelectStatement as JSON
        stmt = ods.SelectStatement()
        stmt.columns.add(aid=env_aid, attribute="Name")
        json_body = json_format.MessageToJson(stmt).encode("utf-8")

        resp = requests.post(
            f"{session_url}/data-read",
            data=json_body,
            headers={
                "Content-Type": CONTENT_TYPE_JSON,
                "Accept": CONTENT_TYPE_PROTO,
            },
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == CONTENT_TYPE_PROTO

        result = ods.DataMatrices()
        result.ParseFromString(resp.content)
        assert len(result.matrices) == 1

    def test_data_read_json_accept(self, atfx_server):
        """data-read with Accept: json returns JSON DataMatrices."""
        resp = _connect(atfx_server.url, str(SIMPLE_ATFX))
        session_url = resp.headers["Location"]

        resp = requests.post(
            f"{session_url}/model-read",
            headers={
                "Content-Type": CONTENT_TYPE_PROTO,
                "Accept": CONTENT_TYPE_PROTO,
            },
            timeout=10,
        )
        model = ods.Model()
        model.ParseFromString(resp.content)
        env_aid = model.entities["Environment"].aid

        stmt = ods.SelectStatement()
        stmt.columns.add(aid=env_aid, attribute="*")

        resp = requests.post(
            f"{session_url}/data-read",
            data=stmt.SerializeToString(),
            headers={
                "Content-Type": CONTENT_TYPE_PROTO,
                "Accept": CONTENT_TYPE_JSON,
            },
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == CONTENT_TYPE_JSON

        result = ods.DataMatrices()
        json_format.Parse(resp.content.decode("utf-8"), result)
        assert len(result.matrices) >= 1


# ==========================================================================
# Error handling tests
# ==========================================================================


class TestErrors:
    """Test error responses."""

    def test_missing_context_variable(self, atfx_server):
        """POST /ods without ATFX_FILE returns 400."""
        ctx = ods.ContextVariables()
        resp = requests.post(
            f"{atfx_server.url}/ods",
            data=ctx.SerializeToString(),
            headers={
                "Content-Type": CONTENT_TYPE_PROTO,
                "Accept": CONTENT_TYPE_PROTO,
            },
            timeout=10,
        )
        assert resp.status_code == 400

    def test_invalid_file_path(self, atfx_server):
        """POST /ods with nonexistent file returns 400."""
        resp = _connect(atfx_server.url, "/nonexistent/path.atfx")
        assert resp.status_code == 400

    def test_unknown_session(self, atfx_server):
        """data-read with unknown session returns 404."""
        resp = requests.post(
            f"{atfx_server.url}/ods/fake-session-id/data-read",
            data=ods.SelectStatement().SerializeToString(),
            headers={
                "Content-Type": CONTENT_TYPE_PROTO,
                "Accept": CONTENT_TYPE_PROTO,
            },
            timeout=10,
        )
        assert resp.status_code == 404

        # Body should be a parseable ErrorInfo
        error = ods.ErrorInfo()
        error.ParseFromString(resp.content)
        assert "fake-session-id" in error.reason


# ==========================================================================
# Default-file tests
# ==========================================================================


class TestDefaultFile:
    """Tests for AtfxServer started with a default_file."""

    @pytest.fixture
    def server_with_default(self):
        with AtfxServer(default_file=str(SIMPLE_ATFX)) as server:
            yield server

    def test_connect_without_context_variable(self, server_with_default):
        """POST /ods with empty ContextVariables succeeds when default_file is set."""
        ctx = ods.ContextVariables()
        resp = requests.post(
            f"{server_with_default.url}/ods",
            data=ctx.SerializeToString(),
            headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
            timeout=10,
        )
        assert resp.status_code == 201
        assert "Location" in resp.headers

    def test_model_read_uses_default_file(self, server_with_default):
        """model-read on a default-file session returns the expected model."""
        ctx = ods.ContextVariables()
        resp = requests.post(
            f"{server_with_default.url}/ods",
            data=ctx.SerializeToString(),
            headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
            timeout=10,
        )
        session_url = resp.headers["Location"]

        resp = requests.post(
            f"{session_url}/model-read",
            headers={"Content-Type": CONTENT_TYPE_PROTO, "Accept": CONTENT_TYPE_PROTO},
            timeout=10,
        )
        assert resp.status_code == 200
        model = ods.Model()
        model.ParseFromString(resp.content)
        assert "Environment" in model.entities

    def test_context_variable_overrides_default_file(self, server_with_default):
        """Explicit ATFX_FILE context variable takes precedence over default_file."""
        resp = _connect(server_with_default.url, str(SIMPLE_ATFX))
        assert resp.status_code == 201

    def test_no_default_file_still_requires_context_variable(self):
        """Server without default_file returns 400 when ATFX_FILE is absent."""
        with AtfxServer() as server:
            ctx = ods.ContextVariables()
            resp = requests.post(
                f"{server.url}/ods",
                data=ctx.SerializeToString(),
                headers={
                    "Content-Type": CONTENT_TYPE_PROTO,
                    "Accept": CONTENT_TYPE_PROTO,
                },
                timeout=10,
            )
            assert resp.status_code == 400


# ==========================================================================
# ConI integration tests
# ==========================================================================


class TestConI:
    """Test that odsbox ConI can connect to AtfxServer."""

    def test_coni_model_read(self, atfx_server):
        """ConI.model_read() returns a valid Model via the server."""
        with ConI(
            url=atfx_server.url,
            auth=None,
            context_variables={CONTEXT_VAR_ATFX_FILE: str(SIMPLE_ATFX)},
            load_model=False,
        ) as con:
            model = con.model_read()
            assert len(model.entities) > 0
            assert "Measurement" in model.entities

    def test_coni_data_read(self, atfx_server):
        """ConI.data_read() returns DataMatrices via the server."""
        with ConI(
            url=atfx_server.url,
            auth=None,
            context_variables={CONTEXT_VAR_ATFX_FILE: str(SIMPLE_ATFX)},
            load_model=False,
        ) as con:
            model = con.model_read()
            env = model.entities["Environment"]

            stmt = ods.SelectStatement()
            stmt.columns.add(aid=env.aid, attribute="Id")
            stmt.columns.add(aid=env.aid, attribute="Name")

            result = con.data_read(stmt)
            assert len(result.matrices) == 1
            matrix = result.matrices[0]
            name_col = next(c for c in matrix.columns if c.name == "Name")
            assert name_col.string_array.values[0] == "MyEnvironment"

    def test_model_read_localcolumn_values_attribute(self, atfx_server):
        """model-read must expose the 'Values' attribute on the Localcolumn entity."""
        resp = _connect(atfx_server.url, str(SIMPLE_ATFX))
        session_url = resp.headers["Location"]

        resp = requests.post(
            f"{session_url}/model-read",
            headers={
                "Content-Type": CONTENT_TYPE_PROTO,
                "Accept": CONTENT_TYPE_PROTO,
            },
            timeout=10,
        )
        assert resp.status_code == 200

        model = ods.Model()
        model.ParseFromString(resp.content)

        assert "Localcolumn" in model.entities
        lc = model.entities["Localcolumn"]
        assert "Values" in lc.attributes, (
            f"'Values' attribute missing from Localcolumn; got: {list(lc.attributes.keys())}"
        )
        assert lc.attributes["Values"].base_name == "values"


class TestLocationHeader:
    """The Location header must always be a reachable URL for the client."""

    def test_location_uses_request_host_not_bind_address(self):
        """When bound to 0.0.0.0 the Location header must echo the request Host,
        not the raw bind address — 0.0.0.0 is not a valid outbound destination
        on Windows (WinError 10049)."""
        with AtfxServer(host="127.0.0.1", port=0) as server:
            resp = _connect(server.url, str(SIMPLE_ATFX))
            assert resp.status_code == 201
            location = resp.headers["Location"]
            assert not location.startswith("http://0.0.0.0"), (
                f"Location must not use bind address 0.0.0.0; got: {location}"
            )
            # The returned URL must actually be reachable
            resp2 = requests.post(f"{location}/model-read", headers={"Accept": CONTENT_TYPE_PROTO}, timeout=10)
            assert resp2.status_code == 200
