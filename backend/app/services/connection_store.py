"""
Connection Store - persistence for database connection metadata.

The backend runs with multiple uvicorn worker processes (see
backend/Dockerfile: --workers 2), so a live DB connector (an open socket +
cursor) held in one worker's memory is invisible to the others — a request
routed to a different worker would see it as "not connected." Rather than
holding connections open across requests, each connect/load-table call is a
short-lived connect -> use -> disconnect cycle. What's persisted between
requests is just the metadata needed to reconnect (type, connection string,
cached schema), stored the same way session history and workspaces are:
Redis-backed with an in-memory fallback (see SessionManager, WorkspaceStore).

Connection strings contain plaintext credentials, so entries carry a TTL
(unlike workspaces, which persist indefinitely) to bound how long they sit
in Redis after a user stops using them.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, TypedDict

from app.config import settings

logger = logging.getLogger(__name__)

_KEY = "dbconn:{id}"


class ConnectionMeta(TypedDict):
    db_type: str
    connection_string: str
    schema: dict[str, Any]


class ConnectionStore:
    """DB connection metadata store with Redis backend and in-memory fallback."""

    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._redis_client = None
        self._use_redis = False
        self._memory_store: dict[str, tuple[ConnectionMeta, float]] = {}
        self._lock = threading.Lock()

        self._init_redis()

    def _init_redis(self):
        if not settings.use_redis:
            logger.info("Redis disabled via USE_REDIS=false, using in-memory connection store")
            return

        try:
            import redis

            self._redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            self._redis_client.ping()
            self._use_redis = True
            logger.info(f"Connection store connected to Redis at {settings.redis_url}")
        except ImportError:
            logger.warning("redis package not installed, using in-memory connection store")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, using in-memory connection store")

    def register(self, db_type: str, connection_string: str, schema: dict[str, Any]) -> str:
        import uuid

        connection_id = uuid.uuid4().hex
        meta: ConnectionMeta = {
            "db_type": db_type,
            "connection_string": connection_string,
            "schema": schema,
        }

        if self._use_redis and self._redis_client:
            try:
                self._redis_client.set(
                    _KEY.format(id=connection_id), json.dumps(meta), ex=self._ttl
                )
                return connection_id
            except Exception as e:
                logger.error(f"Redis connection-store set error: {e}")

        with self._lock:
            self._reap_locked()
            self._memory_store[connection_id] = (meta, time.monotonic())
        return connection_id

    def get(self, connection_id: str) -> ConnectionMeta | None:
        """Look up connection metadata, refreshing its TTL (sliding expiry)."""
        if self._use_redis and self._redis_client:
            try:
                key = _KEY.format(id=connection_id)
                raw = self._redis_client.get(key)
                if raw is None:
                    return None
                self._redis_client.expire(key, self._ttl)
                return json.loads(raw)
            except Exception as e:
                logger.error(f"Redis connection-store get error: {e}")
                return None

        with self._lock:
            self._reap_locked()
            entry = self._memory_store.get(connection_id)
            if entry is None:
                return None
            meta, _ = entry
            self._memory_store[connection_id] = (meta, time.monotonic())
            return meta

    def remove(self, connection_id: str) -> bool:
        if self._use_redis and self._redis_client:
            try:
                return bool(self._redis_client.delete(_KEY.format(id=connection_id)))
            except Exception as e:
                logger.error(f"Redis connection-store delete error: {e}")
                return False

        with self._lock:
            return self._memory_store.pop(connection_id, None) is not None

    def _reap_locked(self) -> None:
        """Evict entries idle past the TTL. Caller holds _lock. In-memory only."""
        now = time.monotonic()
        stale_ids = [cid for cid, (_, ts) in self._memory_store.items() if now - ts > self._ttl]
        for cid in stale_ids:
            self._memory_store.pop(cid, None)


_store: ConnectionStore | None = None


def get_connection_store() -> ConnectionStore:
    global _store
    if _store is None:
        _store = ConnectionStore(ttl_seconds=settings.db_connection_ttl_seconds)
    return _store
