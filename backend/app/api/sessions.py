from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import secrets
from datetime import datetime, timedelta

router = APIRouter(prefix="/sessions", tags=["sessions"])

# In-memory store for shared sessions (in a real app, use Redis or Postgres)
SHARED_SESSIONS = {}

class ShareRequest(BaseModel):
    session_id: str
    session_data: dict # Data payload to store

@router.post("/share")
async def create_share_link(req: ShareRequest):
    token = secrets.token_urlsafe(16)
    expires_at = datetime.now() + timedelta(hours=72)
    
    SHARED_SESSIONS[token] = {
        "data": req.session_data,
        "expires_at": expires_at
    }
    
    return {"token": token, "expires_at": expires_at.isoformat()}

@router.get("/shared/{token}")
async def get_shared_session(token: str):
    session = SHARED_SESSIONS.get(token)
    if not session:
        raise HTTPException(status_code=404, detail="Shared session not found or expired")
        
    if datetime.now() > session["expires_at"]:
        del SHARED_SESSIONS[token]
        raise HTTPException(status_code=404, detail="Shared session has expired")
        
    return session["data"]
