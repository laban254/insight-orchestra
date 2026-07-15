"""
Unit tests for the /connectors endpoints: input validation, and the
connect -> load-table -> disconnect flow that materializes a table from a
database connection into a CSV for the analysis pipeline.

The backend runs multiple uvicorn workers in production, so /connect and
/load-table each do their own short-lived connect/disconnect cycle rather
than sharing a live connector instance — these tests assert that shape
(connector constructed fresh per call) rather than assuming a single
long-lived connection object.
"""

from unittest.mock import MagicMock

import pandas as pd
import pytest
from app.api import connectors as connectors_api
from app.api.connectors import ConnectRequest, LoadTableRequest
from app.services.connection_store import ConnectionStore
from fastapi import HTTPException


class TestConnectValidation:
    @pytest.mark.asyncio
    async def test_unsupported_type_rejected(self):
        with pytest.raises(HTTPException) as exc:
            await connectors_api.connect_database(ConnectRequest(type="oracle", connection_string="x"))
        assert exc.value.status_code == 400
        assert "Unsupported connector" in exc.value.detail

    @pytest.mark.asyncio
    async def test_empty_connection_string_rejected(self):
        with pytest.raises(HTTPException) as exc:
            await connectors_api.connect_database(
                ConnectRequest(type="postgresql", connection_string="   ")
            )
        assert exc.value.status_code == 400
        assert "empty" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_malformed_postgresql_dsn_gives_friendly_message(self):
        """A garbage string like 'z' should never reach psycopg2's raw DSN
        parser error — it should be caught with an actionable message."""
        with pytest.raises(HTTPException) as exc:
            await connectors_api.connect_database(
                ConnectRequest(type="postgresql", connection_string="z")
            )
        assert exc.value.status_code == 400
        assert "Invalid connection string" in exc.value.detail
        assert "postgresql://" in exc.value.detail

    @pytest.mark.asyncio
    async def test_malformed_mysql_dsn_gives_friendly_message(self):
        with pytest.raises(HTTPException) as exc:
            await connectors_api.connect_database(ConnectRequest(type="mysql", connection_string="not-a-url"))
        assert exc.value.status_code == 400
        assert "Invalid connection string" in exc.value.detail
        assert "mysql://" in exc.value.detail

    @pytest.mark.asyncio
    async def test_wrong_scheme_rejected(self):
        with pytest.raises(HTTPException) as exc:
            await connectors_api.connect_database(
                ConnectRequest(type="postgresql", connection_string="mysql://user:pass@host/db")
            )
        assert exc.value.status_code == 400
        assert "Invalid connection string" in exc.value.detail


@pytest.fixture
def store(monkeypatch):
    """Fresh in-memory connection store wired into the router for each test."""
    s = ConnectionStore(ttl_seconds=600)
    s._use_redis = False  # force in-memory regardless of environment
    monkeypatch.setattr(connectors_api, "_store", s)
    return s


@pytest.fixture
def fake_connector(monkeypatch):
    """A connector double wired into CONNECTOR_MAP["postgresql"], so /connect
    and /load-table exercise the real endpoint logic without a real driver."""
    instance = MagicMock()
    instance.test_connection.return_value = True
    instance.get_schema.return_value = {
        "users": [{"name": "id", "type": "integer"}, {"name": "name", "type": "text"}]
    }
    instance.execute_query.return_value = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})

    monkeypatch.setitem(connectors_api.CONNECTOR_MAP, "postgresql", MagicMock(return_value=instance))
    return instance


async def _connect(store, fake_connector) -> str:
    result = await connectors_api.connect_database(
        ConnectRequest(type="postgresql", connection_string="postgresql://u:p@h:5432/db")
    )
    return result["connection_id"]


class TestConnectRegistersConnection:
    @pytest.mark.asyncio
    async def test_connect_returns_connection_id_and_schema(self, store, fake_connector):
        result = await connectors_api.connect_database(
            ConnectRequest(type="postgresql", connection_string="postgresql://u:p@h:5432/db")
        )
        assert result["status"] == "connected"
        assert "connection_id" in result
        assert "users" in result["schema"]

    @pytest.mark.asyncio
    async def test_connect_disconnects_before_returning(self, store, fake_connector):
        """The live connection must not be held open across requests — a
        later request can land on a different uvicorn worker process."""
        await connectors_api.connect_database(
            ConnectRequest(type="postgresql", connection_string="postgresql://u:p@h:5432/db")
        )
        fake_connector.disconnect.assert_called_once()


class TestLoadTable:
    @pytest.mark.asyncio
    async def test_load_table_success_writes_csv(self, store, fake_connector):
        connection_id = await _connect(store, fake_connector)

        result = await connectors_api.load_table(
            LoadTableRequest(connection_id=connection_id, table_name="users")
        )

        assert result["table_name"] == "users"
        assert result["row_count"] == 2
        assert result["column_count"] == 2
        loaded = pd.read_csv(result["file_path"])
        assert list(loaded["name"]) == ["Alice", "Bob"]

        query = fake_connector.execute_query.call_args[0][0]
        assert '"users"' in query
        assert "LIMIT" in query
        # /connect and /load-table each reconnect independently
        assert fake_connector.connect.call_count == 2
        assert fake_connector.disconnect.call_count == 2

    @pytest.mark.asyncio
    async def test_unknown_connection_id_404(self, store):
        with pytest.raises(HTTPException) as exc:
            await connectors_api.load_table(LoadTableRequest(connection_id="nope", table_name="users"))
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_unknown_table_rejected(self, store, fake_connector):
        connection_id = await _connect(store, fake_connector)

        with pytest.raises(HTTPException) as exc:
            await connectors_api.load_table(
                LoadTableRequest(connection_id=connection_id, table_name="not_a_real_table")
            )
        assert exc.value.status_code == 400
        assert "Unknown table" in exc.value.detail

    @pytest.mark.asyncio
    async def test_row_limit_is_clamped(self, store, fake_connector):
        connection_id = await _connect(store, fake_connector)

        await connectors_api.load_table(
            LoadTableRequest(connection_id=connection_id, table_name="users", row_limit=10_000_000)
        )

        query = fake_connector.execute_query.call_args[0][0]
        assert "LIMIT 500000" in query

    @pytest.mark.asyncio
    async def test_query_failure_gives_clean_400(self, store, fake_connector):
        connection_id = await _connect(store, fake_connector)
        fake_connector.execute_query.side_effect = RuntimeError("relation does not exist")

        with pytest.raises(HTTPException) as exc:
            await connectors_api.load_table(
                LoadTableRequest(connection_id=connection_id, table_name="users")
            )
        assert exc.value.status_code == 400
        assert "Failed to load table" in exc.value.detail


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_success(self, store, fake_connector):
        connection_id = await _connect(store, fake_connector)

        result = await connectors_api.disconnect_database(connection_id)

        assert result == {"status": "disconnected"}
        with pytest.raises(HTTPException):
            await connectors_api.load_table(
                LoadTableRequest(connection_id=connection_id, table_name="users")
            )

    @pytest.mark.asyncio
    async def test_disconnect_unknown_404(self, store):
        with pytest.raises(HTTPException) as exc:
            await connectors_api.disconnect_database("nope")
        assert exc.value.status_code == 404
