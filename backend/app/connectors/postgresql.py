import psycopg2
import pandas as pd
from .base import BaseConnector

class PostgreSQLConnector(BaseConnector):

    def __init__(self):
        self.connection = None
        self.cursor = None

    def connect(self, connection_string: str) -> None:
        """
        Accepts standard PostgreSQL connection strings:
        postgresql://user:password@host:5432/dbname
        """
        self.connection = psycopg2.connect(connection_string)
        self.cursor = self.connection.cursor()

    def get_schema(self) -> dict:
        """
        Returns schema as dict:
        { "users": ["id", "name", "email"], "orders": [...] }
        """
        query = """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
        """
        self.cursor.execute(query)
        rows = self.cursor.fetchall()

        schema = {}
        for table, column, dtype in rows:
            if table not in schema:
                schema[table] = []
            schema[table].append({"name": column, "type": dtype})

        return schema

    def execute_query(self, sql: str) -> pd.DataFrame:
        # CRITICAL: read-only safety check
        sql_upper = sql.strip().upper()
        if any(sql_upper.startswith(kw) for kw in ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE"]):
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
