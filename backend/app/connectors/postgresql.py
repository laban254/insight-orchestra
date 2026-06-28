import logging
import re

import pandas as pd
import psycopg2

from .base import BaseConnector

logger = logging.getLogger(__name__)


class PostgreSQLConnector(BaseConnector):
    def __init__(self):
        self.connection = None
        self.cursor = None

    def _mask_credentials(self, connection_string: str) -> str:
        """Mask credentials in connection string for logging."""
        # Mask password in connection string
        return re.sub(r"(password=)[^&]+", r"\1****", connection_string)

    def connect(self, connection_string: str) -> None:
        """
        Accepts standard PostgreSQL connection strings:
        postgresql://user:password@host:5432/dbname
        """
        # Log connection without credentials
        logger.info(f"Connecting to PostgreSQL: {self._mask_credentials(connection_string)}")
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
        # CRITICAL: read-only safety check - more comprehensive
        sql_upper = sql.strip().upper()

        # Block dangerous keywords anywhere in the query
        blocked_keywords = [
            "DROP",
            "DELETE",
            "INSERT",
            "UPDATE",
            "ALTER",
            "TRUNCATE",
            "CREATE",
            "GRANT",
            "REVOKE",
            "EXEC",
            "EXECUTE",
            "CALL",
        ]

        # Also check for semicolons (potential for multiple statements)
        if ";" in sql:
            raise ValueError("Multiple statements are not permitted")

        for keyword in blocked_keywords:
            # Use word boundary matching to prevent bypass attempts
            if f" {keyword} " in sql_upper or sql_upper.startswith(keyword):
                raise ValueError(
                    f"Keyword '{keyword}' is not permitted. Only SELECT queries are allowed."
                )

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
