import duckdb
import pandas as pd

from .base import BaseConnector


class DuckDBConnector(BaseConnector):
    """
    DuckDB is special — it can directly query:
    - Parquet files
    - CSV files (faster than pandas)
    - JSON files
    - Remote S3 files

    This makes it a universal connector for analytical workloads.
    """

    def __init__(self):
        self.connection = None

    def connect(self, path: str = ":memory:") -> None:
        """
        path = ":memory:" for in-memory (fastest)
        path = "/path/to/file.db" for persistent
        """
        self.connection = duckdb.connect(path)

    def load_csv(self, file_path: str, table_name: str = "data") -> None:
        """Load CSV directly — no pandas needed, much faster"""
        self.connection.execute(
            f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{file_path}')"
        )

    def execute_query(self, sql: str) -> pd.DataFrame:
        return self.connection.execute(sql).df()

    def get_schema(self) -> dict:
        tables = self.connection.execute("SHOW TABLES").fetchall()
        schema = {}
        for (table,) in tables:
            cols = self.connection.execute(f"DESCRIBE {table}").fetchall()
            schema[table] = [{"name": col[0], "type": col[1]} for col in cols]
        return schema

    def test_connection(self) -> bool:
        try:
            self.connection.execute("SELECT 1")
            return True
        except Exception:
            return False

    def disconnect(self) -> None:
        if self.connection:
            self.connection.close()
