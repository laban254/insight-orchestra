import sqlite3

import pandas as pd

from .base import BaseConnector


class SQLiteConnector(BaseConnector):
    def __init__(self):
        self.connection = None
        self.cursor = None

    def connect(self, connection_string: str) -> None:
        self.connection = sqlite3.connect(connection_string)
        self.cursor = self.connection.cursor()

    def get_schema(self) -> dict:
        query = "SELECT name FROM sqlite_master WHERE type='table';"
        self.cursor.execute(query)
        tables = self.cursor.fetchall()

        schema = {}
        for (table,) in tables:
            self.cursor.execute(f"PRAGMA table_info({table});")
            cols = self.cursor.fetchall()
            schema[table] = [{"name": col[1], "type": col[2]} for col in cols]

        return schema

    def execute_query(self, sql: str) -> pd.DataFrame:
        sql_upper = sql.strip().upper()
        if any(
            sql_upper.startswith(kw)
            for kw in ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE"]
        ):
            raise ValueError("Only SELECT queries are permitted")
        return pd.read_sql_query(sql, self.connection)

    def test_connection(self) -> bool:
        try:
            self.cursor.execute("SELECT 1")
            return True
        except Exception:
            return False

    def disconnect(self) -> None:
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
