import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.auth import require_role
from app.config import settings
from app.services.audit_log import get_audit_log_store
from app.services.user_store import Role, UserRecord

router = APIRouter(prefix="/audit", tags=["audit"])
_audit = get_audit_log_store()


def _require_auth_enabled() -> None:
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="Auth is not enabled on this server.")


@router.get("/log")
async def list_audit_log(
    limit: int = Query(200, ge=1, le=1000),
    _user: UserRecord | None = Depends(require_role(Role.ADMIN)),
):
    _require_auth_enabled()
    return {"entries": _audit.list_recent(limit=limit)}


@router.get("/export")
async def export_audit_log(_user: UserRecord | None = Depends(require_role(Role.ADMIN))):
    """Every retained entry as JSON Lines, for a SIEM to ingest."""
    _require_auth_enabled()
    lines = "\n".join(json.dumps(entry) for entry in _audit.export_all())
    return PlainTextResponse(
        content=lines,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=audit-log.jsonl"},
    )
