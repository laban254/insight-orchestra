import json
import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)

SHARE_TTL_SECONDS = 72 * 3600  # 72h

# Redis-backed share store (durable across restarts) with in-memory fallback.
_memory_store: dict = {}
_redis = None
if settings.use_redis:
    try:
        import redis

        _redis = redis.from_url(settings.redis_url, decode_responses=True)
        _redis.ping()
        logger.info("Share store using Redis")
    except Exception as e:
        logger.warning(f"Share store: Redis unavailable ({e}); using in-memory")
        _redis = None


class ShareRequest(BaseModel):
    session_id: str
    session_data: dict


@router.post("/share")
async def create_share_link(req: ShareRequest):
    token = secrets.token_urlsafe(16)
    expires_at = datetime.now() + timedelta(seconds=SHARE_TTL_SECONDS)

    if _redis:
        try:
            _redis.set(f"shared:{token}", json.dumps(req.session_data), ex=SHARE_TTL_SECONDS)
            return {"token": token, "expires_at": expires_at.isoformat()}
        except Exception as e:
            logger.error(f"Share store redis set error: {e}")

    _memory_store[token] = {"data": req.session_data, "expires_at": expires_at}
    return {"token": token, "expires_at": expires_at.isoformat()}


@router.get("/shared/{token}")
async def get_shared_session(token: str):
    if _redis:
        try:
            raw = _redis.get(f"shared:{token}")
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.error(f"Share store redis get error: {e}")

    item = _memory_store.get(token)
    if not item:
        raise HTTPException(status_code=404, detail="Shared session not found or expired")
    if datetime.now() > item["expires_at"]:
        del _memory_store[token]
        raise HTTPException(status_code=404, detail="Shared session has expired")
    return item["data"]
