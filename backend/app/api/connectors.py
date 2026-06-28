from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.connectors import DuckDBConnector, MySQLConnector, PostgreSQLConnector, SQLiteConnector

router = APIRouter(prefix="/connectors", tags=["connectors"])

CONNECTOR_MAP = {
    "postgresql": PostgreSQLConnector,
    "mysql": MySQLConnector,
    "sqlite": SQLiteConnector,
    "duckdb": DuckDBConnector,
}


class ConnectRequest(BaseModel):
    type: str  # "postgresql", "mysql", "sqlite", "duckdb"
    connection_string: str  # Standard connection string


@router.post("/connect")
async def connect_database(req: ConnectRequest):
    if req.type not in CONNECTOR_MAP:
        raise HTTPException(400, f"Unsupported connector: {req.type}")

    connector = CONNECTOR_MAP[req.type]()
    try:
        connector.connect(req.connection_string)
    except Exception as e:
        raise HTTPException(400, f"Failed to connect: {str(e)}") from e

    if not connector.test_connection():
        raise HTTPException(500, "Connection failed. Check your credentials.")

    schema = connector.get_schema()
    return {"status": "connected", "schema": schema}


@router.get("/schema")
async def get_schema():
    """Returns active connection schema for the agent context"""
    # This is a placeholder; active sessions would store this internally.
    return {"status": "not_implemented"}
