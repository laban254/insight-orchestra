from abc import ABC, abstractmethod

import pandas as pd


class BaseConnector(ABC):
    @abstractmethod
    def connect(self, connection_string: str) -> None:
        """Establish connection to the database"""
        pass

    @abstractmethod
    def get_schema(self) -> dict:
        """Return table names + column names + types"""
        pass

    @abstractmethod
    def execute_query(self, sql: str) -> pd.DataFrame:
        """Execute SQL and return DataFrame"""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Health check — returns True if connected"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass
