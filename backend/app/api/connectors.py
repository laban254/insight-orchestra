import os
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.connectors import DuckDBConnector, MySQLConnector, PostgreSQLConnector, SQLiteConnector
from app.services.connection_store import get_connection_store
from app.services.dataset_registry import DATASET_DIR, get_dataset_registry
from app.utils.file_utils import UPLOAD_DIR

router = APIRouter(prefix="/connectors", tags=["connectors"])

_store = get_connection_store()
_datasets = get_dataset_registry()

CONNECTOR_MAP = {
    "postgresql": PostgreSQLConnector,
    "mysql": MySQLConnector,
    "sqlite": SQLiteConnector,
    "duckdb": DuckDBConnector,
}

# Expected connection string shape per type, used both for validation and
# for the example shown back to the user when their string doesn't match.
_URL_SCHEMES = {
    "postgresql": (("postgresql", "postgres"), "postgresql://user:password@host:5432/dbname"),
    "mysql": (("mysql",), "mysql://user:password@host:3306/dbname"),
}


# File-backed databases the user can drop into the mounted uploads directory.
_DB_FILE_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".duckdb", ".ddb")


class ConnectRequest(BaseModel):
    type: str  # "postgresql", "mysql", "sqlite", "duckdb"
    connection_string: str  # Standard connection string


@router.get("/local-files")
async def list_local_database_files():
    """SQLite/DuckDB files the backend can actually reach.

    The backend runs in a container, so a path from the user's own machine
    means nothing to it — the old UI placeholder ("/path/to/database.db")
    could never resolve. The uploads directory is bind-mounted, so it is the
    one place a user can put a database file and have it be openable.
    """
    try:
        names = sorted(f for f in os.listdir(UPLOAD_DIR) if f.lower().endswith(_DB_FILE_SUFFIXES))
    except OSError:
        names = []
    return {
        "host_directory": "./backend/uploads",
        "files": [{"name": name, "path": os.path.join(UPLOAD_DIR, name)} for name in names],
    }


def _validate_connection_string(db_type: str, connection_string: str) -> None:
    """Reject obviously malformed strings before they reach the driver.

    Drivers like psycopg2 raise low-level DSN-parser errors (e.g. `invalid
    dsn: missing "=" after "z"`) for garbage input, which aren't actionable
    for a user typing into a form. Catch that case here with a clear message
    instead.
    """
    if not connection_string.strip():
        raise HTTPException(400, "Connection string cannot be empty.")

    if db_type in _URL_SCHEMES:
        schemes, example = _URL_SCHEMES[db_type]
        parsed = urlparse(connection_string)
        if parsed.scheme not in schemes or not parsed.hostname:
            raise HTTPException(400, f"Invalid connection string. Expected format: {example}")


@router.post("/connect")
async def connect_database(req: ConnectRequest):
    if req.type not in CONNECTOR_MAP:
        raise HTTPException(400, f"Unsupported connector: {req.type}")

    _validate_connection_string(req.type, req.connection_string)

    connector = CONNECTOR_MAP[req.type]()  # type: ignore[abstract]
    try:
        connector.connect(req.connection_string)
    except ValueError as e:
        # Connectors raise ValueError with a message written for the user.
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(400, f"Failed to connect: {str(e)}") from e

    try:
        if not connector.test_connection():
            raise HTTPException(500, "Connection failed. Check your credentials.")
        schema = connector.get_schema()
    finally:
        # Don't hold the connection open across requests: with multiple
        # uvicorn workers, a later request may land on a different process
        # that can't see it anyway. Reconnect fresh in /load-table instead.
        connector.disconnect()

    connection_id = _store.register(req.type, req.connection_string, schema)
    return {"status": "connected", "connection_id": connection_id, "schema": schema}


@router.get("/schema")
async def get_schema():
    """Returns active connection schema for the agent context"""
    # This is a placeholder; active sessions would store this internally.
    return {"status": "not_implemented"}


class LoadTableRequest(BaseModel):
    connection_id: str
    table_name: str
    row_limit: int = 50_000


def _quote_identifier(db_type: str, name: str) -> str:
    """Quote a table name for safe interpolation into a SQL identifier position.

    `table_name` is checked against the connection's own schema before this
    is called, so it's a known-real table name, not arbitrary user input —
    this quoting is defense in depth against identifiers containing quote
    characters, not the primary safety check.
    """
    if db_type == "mysql":
        return "`" + name.replace("`", "``") + "`"
    return '"' + name.replace('"', '""') + '"'


@router.post("/load-table")
async def load_table(req: LoadTableRequest):
    """Materialize a table from a DB connection into a CSV so it can flow
    through the same analysis pipeline (/process, /nlq) as an uploaded file."""
    meta = _store.get(req.connection_id)
    if meta is None:
        raise HTTPException(
            404, "Connection not found or expired. Please reconnect to the database."
        )

    if req.table_name not in meta["schema"]:
        raise HTTPException(400, f"Unknown table: {req.table_name}")

    row_limit = max(1, min(req.row_limit, 500_000))
    quoted = _quote_identifier(meta["db_type"], req.table_name)

    connector = CONNECTOR_MAP[meta["db_type"]]()  # type: ignore[abstract]
    try:
        connector.connect(meta["connection_string"])
        df = connector.execute_query(f"SELECT * FROM {quoted} LIMIT {row_limit}")
    except Exception as e:
        raise HTTPException(400, f"Failed to load table: {str(e)}") from e
    finally:
        connector.disconnect()

    # Written into the managed dataset directory (on the mounted volume)
    # rather than /tmp, which does not survive a container recreate.
    file_path = os.path.join(DATASET_DIR, f"dbtable_{uuid.uuid4().hex}.csv")
    df.to_csv(file_path, index=False)
    dataset_id = _datasets.register(file_path, name=req.table_name, source="database")

    return {
        "dataset_id": dataset_id,
        "table_name": req.table_name,
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": list(df.columns),
    }


@router.delete("/{connection_id}")
async def disconnect_database(connection_id: str):
    if not _store.remove(connection_id):
        raise HTTPException(404, "Connection not found or already expired.")
    return {"status": "disconnected"}
