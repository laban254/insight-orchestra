"""
Auth session store - opaque login-session tokens for the (optional) auth layer.

Deliberately separate from SessionManager (which tracks a chat/analysis
conversation, not an authenticated identity) and from the DB connection
store's short-lived metadata. A token here maps to nothing but a user_id;
everything else about the user lives in UserStore, looked up fresh on each
request so a role change or deactivation takes effect immediately instead of
waiting for a stale cached session to expire.

Same Redis-with-in-memory-fallback shape as the other stores.
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from typing import TypedDict

from app.config import settings

logger = logging.getLogger(__name__)

_KEY = "authsession:{token}"


class AuthSessionData(TypedDict):
    user_id: str
    created_at: float


class AuthSessionStore:
    """Opaque auth-session-token store with Redis backend and in-memory fallback."""

    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._redis_client = None
        self._use_redis = False
        self._memory_store: dict[str, tuple[AuthSessionData, float]] = {}
        self._lock = threading.Lock()

        self._init_redis()

    def _init_redis(self):
        if not settings.use_redis:
            logger.info("Redis disabled via USE_REDIS=false, using in-memory auth sessions")
            return
        try:
            import redis

            self._redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            self._redis_client.ping()
            self._use_redis = True
            logger.info(f"Auth session store connected to Redis at {settings.redis_url}")
        except ImportError:
            logger.warning("redis package not installed, using in-memory auth sessions")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, using in-memory auth sessions")

    def create(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        data: AuthSessionData = {"user_id": user_id, "created_at": time.time()}

        if self._use_redis and self._redis_client:
            try:
                self._redis_client.set(_KEY.format(token=token), json.dumps(data), ex=self._ttl)
                return token
            except Exception as e:
                logger.error(f"Redis auth-session create error: {e}")

        with self._lock:
            self._reap_locked()
            self._memory_store[token] = (data, time.monotonic())
        return token

    def get_user_id(self, token: str) -> str | None:
        """Look up the user_id for a token, refreshing its TTL (sliding expiry)."""
        if self._use_redis and self._redis_client:
            try:
                key = _KEY.format(token=token)
                raw = self._redis_client.get(key)
                if raw is None:
                    return None
                self._redis_client.expire(key, self._ttl)
                data: AuthSessionData = json.loads(raw)
                return data["user_id"]
            except Exception as e:
                logger.error(f"Redis auth-session get error: {e}")
                return None

        with self._lock:
            self._reap_locked()
            entry = self._memory_store.get(token)
            if entry is None:
                return None
            data, _ = entry
            self._memory_store[token] = (data, time.monotonic())
            return data["user_id"]

    def revoke(self, token: str) -> bool:
        if self._use_redis and self._redis_client:
            try:
                return bool(self._redis_client.delete(_KEY.format(token=token)))
            except Exception as e:
                logger.error(f"Redis auth-session delete error: {e}")
                return False

        with self._lock:
            return self._memory_store.pop(token, None) is not None

    def _reap_locked(self) -> None:
        """Evict entries idle past the TTL. Caller holds _lock. In-memory only."""
        now = time.monotonic()
        stale = [t for t, (_, ts) in self._memory_store.items() if now - ts > self._ttl]
        for t in stale:
            self._memory_store.pop(t, None)


_store: AuthSessionStore | None = None


def get_auth_session_store() -> AuthSessionStore:
    global _store
    if _store is None:
        _store = AuthSessionStore(ttl_seconds=settings.auth_session_ttl_seconds)
    return _store
