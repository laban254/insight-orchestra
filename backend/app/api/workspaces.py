import re
import threading
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.workspace_store import get_workspace_store

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
_store = get_workspace_store()

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# updatedAt drives list ordering and eviction; rapid saves can land in the
# same millisecond, so keep the timestamp strictly monotonic.
_ts_lock = threading.Lock()
_unused_last_ts = 0


def _now_ms() -> int:
    global _unused_last_ts
    with _ts_lock:
        now = int(time.time() * 1000)
        if now <= _unused_last_ts:
            now = _unused_last_ts + 1
        _unused_last_ts = now
        return now


def _validate_id(workspace_id: str) -> str:
    if not _ID_RE.match(workspace_id):
        raise HTTPException(status_code=400, detail="Invalid workspace id.")
    return workspace_id


class WorkspaceUpsert(BaseModel):
    datasetName: str = Field(min_length=1, max_length=200)
    filePath: str = Field(default="", max_length=1000)
    createdAt: int | None = None
    state: dict


@router.get("")
async def list_workspaces():
    """List saved workspaces (metadata only), most recently updated first."""
    return {"workspaces": _store.list_metas()}


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str):
    """Fetch a full workspace record (metadata + saved state)."""
    record = _store.get(_validate_id(workspace_id))
    if record is None:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return record


@router.put("/{workspace_id}")
async def upsert_workspace(workspace_id: str, payload: WorkspaceUpsert):
    """Create or update a workspace. The saved state replaces any previous one."""
    _validate_id(workspace_id)
    now_ms = _now_ms()
    existing = _store.get(workspace_id)
    record = {
        "id": workspace_id,
        "datasetName": payload.datasetName,
        "filePath": payload.filePath,
        "createdAt": payload.createdAt or (existing or {}).get("createdAt") or now_ms,
        "updatedAt": now_ms,
        "state": payload.state,
    }
    return _store.upsert(record)


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str):
    """Delete a saved workspace."""
    _store.delete(_validate_id(workspace_id))
    return {"status": "deleted"}
