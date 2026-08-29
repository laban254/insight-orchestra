from unittest.mock import MagicMock, patch

import pytest
from app.connectors.duckdb import DuckDBConnector
from app.connectors.mysql import MySQLConnector
from app.connectors.postgresql import PostgreSQLConnector
from app.connectors.sqlite import SQLiteConnector


def test_sqlite_connector(tmp_path):
    # The connector opens existing databases read-only, so the fixture data
    # is written with a plain sqlite3 connection first.
    import sqlite3

    db_path = tmp_path / "fixture.db"
    seed = sqlite3.connect(db_path)
    seed.execute("CREATE TABLE test_table (id INTEGER, name TEXT)")
    seed.execute("INSERT INTO test_table VALUES (1, 'Insight'), (2, 'Orchestra')")
    seed.commit()
    seed.close()

    connector = SQLiteConnector()
    connector.connect(str(db_path))

    assert connector.test_connection() is True

    # Test schema
    schema = connector.get_schema()
    assert "test_table" in schema
    assert len(schema["test_table"]) == 2

    # Test query
    df = connector.execute_query("SELECT * FROM test_table")
    assert len(df) == 2
    assert list(df.columns) == ["id", "name"]

    connector.disconnect()


def test_duckdb_connector(tmp_path):
    import duckdb

    db_path = tmp_path / "fixture.duckdb"
    seed = duckdb.connect(str(db_path))
    seed.execute("CREATE TABLE users (id INTEGER, name VARCHAR)")
    seed.execute("INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob')")
    seed.close()

    connector = DuckDBConnector()
    connector.connect(str(db_path))

    assert connector.test_connection() is True

    schema = connector.get_schema()
    assert "users" in schema

    df = connector.execute_query("SELECT * FROM users")
    assert len(df) == 2

    connector.disconnect()


@patch("psycopg2.connect")
def test_postgresql_connector(mock_connect):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    connector = PostgreSQLConnector()
    connector.connect("postgresql://user:pass@localhost:5432/db")

    mock_cursor.execute.side_effect = None
    assert connector.test_connection() is True

    # Test read-only enforcement
    with pytest.raises(ValueError):
        connector.execute_query("DROP TABLE users;")

    connector.disconnect()
    mock_cursor.close.assert_called_once()
    mock_conn.close.assert_called_once()


@patch("pymysql.connect")
def test_mysql_connector(mock_connect):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    connector = MySQLConnector()
    connector.connect("mysql://user:pass@localhost:3306/db")
    mock_connect.assert_called_with(
        host="localhost", user="user", password="pass", database="db", port=3306
    )

    mock_cursor.execute.side_effect = None
    assert connector.test_connection() is True

    with pytest.raises(ValueError):
        connector.execute_query("UPDATE users SET name='test';")

    connector.disconnect()


class TestFileBackedConnectorGuards:
    """SQLite and DuckDB create a missing database file rather than failing,
    so a mistyped path used to 'connect' successfully, report zero tables,
    and leave an empty database behind."""

    def test_sqlite_missing_file_errors_and_creates_nothing(self, tmp_path):
        target = tmp_path / "typo.db"
        with pytest.raises(ValueError, match="No database file"):
            SQLiteConnector().connect(str(target))
        assert not target.exists()

    def test_sqlite_memory_is_rejected_as_always_empty(self):
        with pytest.raises(ValueError, match="always empty"):
            SQLiteConnector().connect(":memory:")

    def test_sqlite_opens_existing_database_read_only(self, tmp_path):
        import sqlite3

        path = tmp_path / "real.db"
        seed = sqlite3.connect(path)
        seed.execute("CREATE TABLE widgets (id INTEGER)")
        seed.commit()
        seed.close()

        connector = SQLiteConnector()
        connector.connect(str(path))
        try:
            assert "widgets" in connector.get_schema()
            with pytest.raises(sqlite3.OperationalError):
                connector.connection.execute("INSERT INTO widgets VALUES (2)")
        finally:
            connector.disconnect()

    def test_duckdb_missing_file_errors_and_creates_nothing(self, tmp_path):
        target = tmp_path / "typo.duckdb"
        with pytest.raises(ValueError, match="No database file"):
            DuckDBConnector().connect(str(target))
        assert not target.exists()

    def test_duckdb_memory_is_rejected_as_always_empty(self):
        with pytest.raises(ValueError, match="always empty"):
            DuckDBConnector().connect(":memory:")


class TestReadOnlyEnforcement:
    """The word-boundary keyword check is defense in depth, not the primary
    control: connect() also puts the session itself into read-only mode, so
    the database rejects a write regardless of what query-text filtering
    does or doesn't catch."""

    @patch("psycopg2.connect")
    def test_postgres_session_is_set_read_only(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        PostgreSQLConnector().connect("postgresql://user:pass@localhost:5432/db")

        mock_conn.set_session.assert_called_once_with(readonly=True)

    @patch("psycopg2.connect")
    def test_postgres_catches_keyword_bypass_via_non_space_whitespace(self, mock_connect):
        """The old check only matched a literal ' KEYWORD ' substring or a
        leading match, so a tab or newline in place of a space slipped
        past it even though SQL treats them identically."""
        mock_connect.return_value = MagicMock()
        connector = PostgreSQLConnector()
        connector.connect("postgresql://user:pass@localhost:5432/db")

        with pytest.raises(ValueError, match="DROP"):
            connector.execute_query("SELECT 1\tDROP\tTABLE\tusers")

    @patch("psycopg2.connect")
    def test_postgres_column_name_is_not_a_false_positive(self, mock_connect):
        mock_connect.return_value = MagicMock()
        connector = PostgreSQLConnector()
        connector.connect("postgresql://user:pass@localhost:5432/db")

        # Must not raise: "updated_at" contains "UPDATE" but is one word.
        connector.execute_query("SELECT id, updated_at FROM events")

    @patch("pymysql.connect")
    def test_mysql_session_is_set_read_only(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        MySQLConnector().connect("mysql://user:pass@localhost:3306/db")

        mock_cursor.execute.assert_any_call("SET SESSION TRANSACTION READ ONLY")

    @patch("pymysql.connect")
    def test_mysql_catches_keyword_bypass_via_non_space_whitespace(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = MagicMock()
        connector = MySQLConnector()
        connector.connect("mysql://user:pass@localhost:3306/db")

        with pytest.raises(ValueError, match="DELETE"):
            connector.execute_query("SELECT 1\nDELETE\nFROM\nusers")

    @patch("pymysql.connect")
    def test_mysql_column_name_is_not_a_false_positive(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = MagicMock()
        connector = MySQLConnector()
        connector.connect("mysql://user:pass@localhost:3306/db")

        connector.execute_query("SELECT id, created_at FROM events")

    @patch("pymysql.connect")
    def test_mysql_percent_encoded_credentials_are_decoded(self, mock_connect):
        """urlparse does not decode userinfo, so a password containing '@',
        ':' or '/' — correctly percent-encoded when the URL was built —
        would otherwise reach pymysql still escaped and fail to
        authenticate."""
        mock_connect.return_value = MagicMock()

        MySQLConnector().connect("mysql://user:p%40ss%2Fw%3Aord@localhost:3306/db")

        mock_connect.assert_called_with(
            host="localhost",
            user="user",
            password="p@ss/w:ord",
            database="db",
            port=3306,
        )
