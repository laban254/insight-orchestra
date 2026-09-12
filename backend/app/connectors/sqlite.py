import os
import sqlite3

import pandas as pd

from .base import BaseConnector


class SQLiteConnector(BaseConnector):
    def __init__(self):
        self.connection = None
        self.cursor = None

    def connect(self, connection_string: str) -> None:
        """Open an existing SQLite database read-only.

        `sqlite3.connect(path)` *creates* the file when it doesn't exist, so
        a mistyped path used to connect successfully, report zero tables,
        and leave an empty database behind. The URI form with mode=ro fails
        instead — and, since nothing here should ever write, rules out
        modifying the user's database at all.
        """
        path = connection_string.strip()
        if path == ":memory:":
            raise ValueError(
                "An in-memory SQLite database is always empty. Point at a database file instead."
            )
        if not os.path.isfile(path):
            raise ValueError(
                f"No database file at {path}. Copy it into the uploads "
                f"directory (mounted at ./backend/uploads) and use the path "
                f"shown there."
            )
        self.connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
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
