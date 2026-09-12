"""
User Store - accounts for the (now optional) auth layer.

Same Redis-with-in-memory-fallback shape as WorkspaceStore/ConnectionStore.
Users persist indefinitely (like workspaces, unlike the TTL'd connection
store) — there's no natural expiry for an account. Two indexes: one by id
(the record itself) and one by email (login looks up by email, and email
must stay unique).
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from enum import StrEnum
from typing import Any, TypedDict, cast

from app.config import settings

logger = logging.getLogger(__name__)

_RECORD_KEY = "user:{id}"
_EMAIL_INDEX_KEY = "users:by_email"  # email -> user_id
_ID_INDEX_KEY = "users:index"  # user_id -> 1 (membership set, as a hash for redis+memory parity)


class Role(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class UserRecord(TypedDict):
    id: str
    email: str
    name: str
    role: str  # a Role value
    password_hash: str | None  # None for SSO-only accounts
    auth_provider: str  # "local" | "oidc"
    created_at: float
    is_active: bool


class EmailAlreadyRegisteredError(Exception):
    pass


class UserStore:
    """User account store with Redis backend and in-memory fallback."""

    def __init__(self):
        self._redis_client = None
        self._use_redis = False
        self._memory_records: dict[str, UserRecord] = {}
        self._memory_by_email: dict[str, str] = {}  # email -> user_id
        self._lock = threading.Lock()

        self._init_redis()

    def _init_redis(self):
        if not settings.use_redis:
            logger.info("Redis disabled via USE_REDIS=false, using in-memory users")
            return
        try:
            import redis

            self._redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            self._redis_client.ping()
            self._use_redis = True
            logger.info(f"User store connected to Redis at {settings.redis_url}")
        except ImportError:
            logger.warning("redis package not installed, using in-memory users")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, using in-memory users")

    def create(
        self,
        email: str,
        name: str,
        role: Role,
        password_hash: str | None = None,
        auth_provider: str = "local",
    ) -> UserRecord:
        email = email.strip().lower()
        if self.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError(f"'{email}' is already registered.")

        record: UserRecord = {
            "id": uuid.uuid4().hex,
            "email": email,
            "name": name,
            "role": role.value if isinstance(role, Role) else role,
            "password_hash": password_hash,
            "auth_provider": auth_provider,
            "created_at": time.time(),
            "is_active": True,
        }

        if self._use_redis and self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                pipe.set(_RECORD_KEY.format(id=record["id"]), json.dumps(record))
                pipe.hset(_ID_INDEX_KEY, record["id"], 1)
                pipe.hset(_EMAIL_INDEX_KEY, email, record["id"])
                pipe.execute()
                return record
            except Exception as e:
                logger.error(f"Redis user-store create error: {e}")

        with self._lock:
            self._memory_records[record["id"]] = record
            self._memory_by_email[email] = record["id"]
        return record

    def get(self, user_id: str) -> UserRecord | None:
        if self._use_redis and self._redis_client:
            try:
                raw = self._redis_client.get(_RECORD_KEY.format(id=user_id))
                return json.loads(raw) if raw else None
            except Exception as e:
                logger.error(f"Redis user-store get error: {e}")
                return None

        with self._lock:
            return self._memory_records.get(user_id)

    def get_by_email(self, email: str) -> UserRecord | None:
        email = email.strip().lower()
        if self._use_redis and self._redis_client:
            try:
                user_id = self._redis_client.hget(_EMAIL_INDEX_KEY, email)
                return self.get(user_id) if user_id else None
            except Exception as e:
                logger.error(f"Redis user-store email lookup error: {e}")
                return None

        with self._lock:
            user_id = self._memory_by_email.get(email)
            return self._memory_records.get(user_id) if user_id else None

    def list_all(self) -> list[UserRecord]:
        if self._use_redis and self._redis_client:
            try:
                ids = list(self._redis_client.hkeys(_ID_INDEX_KEY))
                if not ids:
                    return []
                raws = self._redis_client.mget([_RECORD_KEY.format(id=i) for i in ids])
                return [json.loads(r) for r in raws if r]
            except Exception as e:
                logger.error(f"Redis user-store list error: {e}")
                return []

        with self._lock:
            return list(self._memory_records.values())

    def count(self) -> int:
        if self._use_redis and self._redis_client:
            try:
                return int(self._redis_client.hlen(_ID_INDEX_KEY))
            except Exception as e:
                logger.error(f"Redis user-store count error: {e}")
                return 0

        with self._lock:
            return len(self._memory_records)

    def update(self, user_id: str, **fields: Any) -> UserRecord | None:
        """Merge `fields` into the record (role, is_active, name, password_hash)."""
        if self._use_redis and self._redis_client:
            try:
                raw = self._redis_client.get(_RECORD_KEY.format(id=user_id))
                if raw is None:
                    return None
                redis_record = cast(UserRecord, json.loads(raw))
                redis_record.update(fields)  # type: ignore[typeddict-item]
                self._redis_client.set(_RECORD_KEY.format(id=user_id), json.dumps(redis_record))
                return redis_record
            except Exception as e:
                logger.error(f"Redis user-store update error: {e}")
                return None

        with self._lock:
            record = self._memory_records.get(user_id)
            if record is None:
                return None
            record.update(fields)  # type: ignore[typeddict-item]
            return record

    def delete(self, user_id: str) -> bool:
        record = self.get(user_id)
        if record is None:
            return False

        if self._use_redis and self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                pipe.delete(_RECORD_KEY.format(id=user_id))
                pipe.hdel(_ID_INDEX_KEY, user_id)
                pipe.hdel(_EMAIL_INDEX_KEY, record["email"])
                pipe.execute()
                return True
            except Exception as e:
                logger.error(f"Redis user-store delete error: {e}")
                return False

        with self._lock:
            self._memory_records.pop(user_id, None)
            self._memory_by_email.pop(record["email"], None)
        return True


_store: UserStore | None = None


def get_user_store() -> UserStore:
    global _store
    if _store is None:
        _store = UserStore()
    return _store
