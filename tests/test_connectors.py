import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from app.connectors.sqlite import SQLiteConnector
from app.connectors.duckdb import DuckDBConnector
from app.connectors.postgresql import PostgreSQLConnector
from app.connectors.mysql import MySQLConnector

def test_sqlite_connector():
    connector = SQLiteConnector()
    connector.connect(":memory:")
    
    assert connector.test_connection() is True
    
    # Create a table
    connector.cursor.execute("CREATE TABLE test_table (id INTEGER, name TEXT)")
    connector.cursor.execute("INSERT INTO test_table VALUES (1, 'Insight'), (2, 'Orchestra')")
    
    # Test schema
    schema = connector.get_schema()
    assert "test_table" in schema
    assert len(schema["test_table"]) == 2
    
    # Test query
    df = connector.execute_query("SELECT * FROM test_table")
    assert len(df) == 2
    assert list(df.columns) == ["id", "name"]
    
    connector.disconnect()

def test_duckdb_connector():
    connector = DuckDBConnector()
    connector.connect(":memory:")
    
    assert connector.test_connection() is True
    
    connector.connection.execute("CREATE TABLE users (id INTEGER, name VARCHAR)")
    connector.connection.execute("INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob')")
    
    schema = connector.get_schema()
    assert "users" in schema
    
    df = connector.execute_query("SELECT * FROM users")
    assert len(df) == 2
    
    connector.disconnect()

@patch('psycopg2.connect')
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

@patch('pymysql.connect')
def test_mysql_connector(mock_connect):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    connector = MySQLConnector()
    connector.connect("mysql://user:pass@localhost:3306/db")
    mock_connect.assert_called_with(host='localhost', user='user', password='pass', database='db', port=3306)
    
    mock_cursor.execute.side_effect = None
    assert connector.test_connection() is True
    
    with pytest.raises(ValueError):
        connector.execute_query("UPDATE users SET name='test';")
        
    connector.disconnect()
