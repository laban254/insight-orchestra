import pymysql
import pandas as pd
from urllib.parse import urlparse
from .base import BaseConnector

class MySQLConnector(BaseConnector):
    def __init__(self):
        self.connection = None
        self.cursor = None

    def connect(self, connection_string: str) -> None:
        """
        Accepts connection strings like:
        mysql://user:password@host:3306/dbname
        """
        parsed = urlparse(connection_string)
        self.connection = pymysql.connect(
            host=parsed.hostname,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:],
            port=parsed.port or 3306
        )
        self.cursor = self.connection.cursor()

    def get_schema(self) -> dict:
        query = """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
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
