"""
Audit log - append-only record of security-relevant actions.

Unlike the other stores, this is written far more than it's read, and never
updated in place — entries are immutable once written (an audit trail that
can be edited after the fact isn't one). Redis backend uses a LIST (LPUSH +
LTRIM) so appends and the retention cap are both O(1); the in-memory
fallback uses a bounded deque with the same newest-first ordering.

Bounded by audit_log_max_entries rather than kept forever, since this is an
operational safety net (who did what, for incident review), not a
compliance-grade immutable ledger — a deployment that needs the latter
should ship entries to real SIEM storage via the export endpoint instead of
relying on this store as the system of record.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import deque
from typing import Any, TypedDict

from app.config import settings

logger = logging.getLogger(__name__)

_LIST_KEY = "auditlog:entries"


class AuditEntry(TypedDict):
    id: str
    timestamp: float
    actor_user_id: str | None
    actor_email: str | None
    action: str
    resource: str | None
    detail: dict[str, Any] | None
    ip_address: str | None


class AuditLogStore:
    """Append-only audit log with Redis backend and in-memory fallback."""

    def __init__(self, max_entries: int):
        self._max_entries = max_entries
        self._redis_client = None
        self._use_redis = False
        self._memory_entries: deque[AuditEntry] = deque(maxlen=max_entries)
        self._lock = threading.Lock()

        self._init_redis()

    def _init_redis(self):
        if not settings.use_redis:
            logger.info("Redis disabled via USE_REDIS=false, using in-memory audit log")
            return
        try:
            import redis

            self._redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            self._redis_client.ping()
            self._use_redis = True
            logger.info(f"Audit log connected to Redis at {settings.redis_url}")
        except ImportError:
            logger.warning("redis package not installed, using in-memory audit log")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, using in-memory audit log")

    def record(
        self,
        action: str,
        actor_user_id: str | None = None,
        actor_email: str | None = None,
        resource: str | None = None,
        detail: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        entry: AuditEntry = {
            "id": uuid.uuid4().hex,
            "timestamp": time.time(),
            "actor_user_id": actor_user_id,
            "actor_email": actor_email,
            "action": action,
            "resource": resource,
            "detail": detail,
            "ip_address": ip_address,
        }

        if self._use_redis and self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                pipe.lpush(_LIST_KEY, json.dumps(entry))
                pipe.ltrim(_LIST_KEY, 0, self._max_entries - 1)
                pipe.execute()
                return
            except Exception as e:
                logger.error(f"Redis audit-log write error: {e}")
                # Fall through: even with Redis configured, a security-relevant
                # action should not be silently dropped just because Redis is
                # briefly unreachable — keep it in memory for this process.

        with self._lock:
            self._memory_entries.appendleft(entry)

    def list_recent(self, limit: int = 200) -> list[AuditEntry]:
        """Newest first."""
        if self._use_redis and self._redis_client:
            try:
                raws = self._redis_client.lrange(_LIST_KEY, 0, limit - 1)
                return [json.loads(r) for r in raws]
            except Exception as e:
                logger.error(f"Redis audit-log read error: {e}")
                return []

        with self._lock:
            return list(self._memory_entries)[:limit]

    def export_all(self) -> list[AuditEntry]:
        """Every retained entry, newest first — for SIEM export."""
        if self._use_redis and self._redis_client:
            try:
                raws = self._redis_client.lrange(_LIST_KEY, 0, -1)
                return [json.loads(r) for r in raws]
            except Exception as e:
                logger.error(f"Redis audit-log export error: {e}")
                return []

        with self._lock:
            return list(self._memory_entries)


_store: AuditLogStore | None = None


def get_audit_log_store() -> AuditLogStore:
    global _store
    if _store is None:
        _store = AuditLogStore(max_entries=settings.audit_log_max_entries)
    return _store
