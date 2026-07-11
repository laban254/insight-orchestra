"""
Workspace Store - server-side persistence for saved analysis workspaces.

Mirrors the SessionManager pattern: Redis-backed with an in-memory fallback,
so saved workspaces survive restarts and are shared across browsers/devices.
Unlike sessions, workspaces have no TTL — persistence is the point — but the
store keeps at most MAX_WORKSPACES records, evicting the least recently
updated ones.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

MAX_WORKSPACES = 25

_RECORD_KEY = "workspace:{id}"
_INDEX_KEY = "workspaces:index"


class WorkspaceStore:
    """Workspace store with Redis backend and in-memory fallback."""

    def __init__(self):
        self._redis_client = None
        self._use_redis = False
        self._memory_store: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()  # guards _memory_store read-modify-write

        self._init_redis()

    def _init_redis(self):
        if not settings.use_redis:
            logger.info("Redis disabled via USE_REDIS=false, using in-memory workspaces")
            return

        try:
            import redis

            self._redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            self._redis_client.ping()
            self._use_redis = True
            logger.info(f"Workspace store connected to Redis at {settings.redis_url}")
        except ImportError:
            logger.warning("redis package not installed, using in-memory workspaces")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, using in-memory workspaces")

    @staticmethod
    def _meta(record: dict[str, Any]) -> dict[str, Any]:
        return {
            k: record.get(k) for k in ("id", "datasetName", "filePath", "createdAt", "updatedAt")
        }

    def list_metas(self) -> list[dict[str, Any]]:
        """All workspace metas, most recently updated first."""
        if self._use_redis and self._redis_client:
            try:
                raw = self._redis_client.hgetall(_INDEX_KEY)
                metas = [json.loads(v) for v in raw.values()]
                return sorted(metas, key=lambda m: m.get("updatedAt", 0), reverse=True)
            except Exception as e:
                logger.error(f"Redis workspace list error: {e}")

        with self._lock:
            metas = [self._meta(r) for r in self._memory_store.values()]
        return sorted(metas, key=lambda m: m.get("updatedAt", 0), reverse=True)

    def get(self, workspace_id: str) -> dict[str, Any] | None:
        """Full workspace record (meta + state), or None."""
        if self._use_redis and self._redis_client:
            try:
                raw = self._redis_client.get(_RECORD_KEY.format(id=workspace_id))
                return json.loads(raw) if raw else None
            except Exception as e:
                logger.error(f"Redis workspace get error: {e}")
                raise

        with self._lock:
            record = self._memory_store.get(workspace_id)
            return json.loads(json.dumps(record)) if record else None

    def upsert(self, record: dict[str, Any]) -> dict[str, Any]:
        """Store a full workspace record; evict the oldest beyond MAX_WORKSPACES."""
        meta = self._meta(record)

        if self._use_redis and self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                pipe.set(_RECORD_KEY.format(id=record["id"]), json.dumps(record))
                pipe.hset(_INDEX_KEY, record["id"], json.dumps(meta))
                pipe.execute()
                self._evict_redis()
                return meta
            except Exception as e:
                logger.error(f"Redis workspace upsert error: {e}")
                raise

        with self._lock:
            self._memory_store[record["id"]] = json.loads(json.dumps(record))
            victims = self._eviction_victims([self._meta(r) for r in self._memory_store.values()])
            for victim_id in victims:
                self._memory_store.pop(victim_id, None)
        return meta

    def delete(self, workspace_id: str) -> None:
        if self._use_redis and self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                pipe.delete(_RECORD_KEY.format(id=workspace_id))
                pipe.hdel(_INDEX_KEY, workspace_id)
                pipe.execute()
                return
            except Exception as e:
                logger.error(f"Redis workspace delete error: {e}")

        with self._lock:
            self._memory_store.pop(workspace_id, None)

    def clear_all(self) -> None:
        """Remove every workspace (for testing)."""
        if self._use_redis and self._redis_client:
            try:
                ids = list(self._redis_client.hkeys(_INDEX_KEY))
                pipe = self._redis_client.pipeline()
                for wid in ids:
                    pipe.delete(_RECORD_KEY.format(id=wid))
                pipe.delete(_INDEX_KEY)
                pipe.execute()
                return
            except Exception as e:
                logger.error(f"Redis workspace clear error: {e}")

        with self._lock:
            self._memory_store.clear()

    @staticmethod
    def _eviction_victims(metas: list[dict[str, Any]]) -> list[str]:
        """IDs of the least recently updated workspaces beyond the cap."""
        if len(metas) <= MAX_WORKSPACES:
            return []
        metas = sorted(metas, key=lambda m: m.get("updatedAt", 0), reverse=True)
        return [m["id"] for m in metas[MAX_WORKSPACES:]]

    def _evict_redis(self) -> None:
        raw = self._redis_client.hgetall(_INDEX_KEY)
        victims = self._eviction_victims([json.loads(v) for v in raw.values()])
        if not victims:
            return
        pipe = self._redis_client.pipeline()
        for wid in victims:
            pipe.delete(_RECORD_KEY.format(id=wid))
            pipe.hdel(_INDEX_KEY, wid)
        pipe.execute()


# Global instance
_workspace_store: WorkspaceStore | None = None


def get_workspace_store() -> WorkspaceStore:
    """Get the global workspace store instance."""
    global _workspace_store
    if _workspace_store is None:
        _workspace_store = WorkspaceStore()
    return _workspace_store
