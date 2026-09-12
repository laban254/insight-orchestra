"""
API key store - long-lived credentials for headless (non-browser) callers.

The raw key is only ever shown once, at creation time. What's persisted is a
SHA-256 hash of it (like a password hash, but a plain fast hash is fine here
since the key itself already carries 256 bits of entropy — there's no
low-entropy human password to protect against brute-forcing). Lookup on each
request is by that hash, so a leaked database dump doesn't hand over usable
keys.

Same Redis-with-in-memory-fallback shape as the other stores. Keys don't
expire by default (api_key_ttl_seconds = 0); when a TTL is configured it's a
fixed expiry from creation, not sliding — an API key is a credential handed
to an external system, not a login session, so "still being used" shouldn't
silently extend its life the way a browser session's does.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import threading
import time
from typing import TypedDict

from app.config import settings

logger = logging.getLogger(__name__)

_RECORD_KEY = "apikey:{id}"
_HASH_INDEX_KEY = "apikeys:by_hash"  # key_hash -> key_id
_USER_INDEX_KEY = "apikeys:by_user:{user_id}"  # set of key_ids
_PREFIX = "iok_"


class APIKeyRecord(TypedDict):
    id: str
    user_id: str
    name: str
    display_prefix: str  # short, non-secret prefix shown in UIs after creation
    key_hash: str
    created_at: float
    expires_at: float | None
    last_used_at: float | None


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class APIKeyStore:
    """API key store with Redis backend and in-memory fallback."""

    def __init__(self):
        self._redis_client = None
        self._use_redis = False
        self._memory_records: dict[str, APIKeyRecord] = {}
        self._memory_by_hash: dict[str, str] = {}  # key_hash -> id
        self._memory_by_user: dict[str, set[str]] = {}  # user_id -> {id, ...}
        self._lock = threading.Lock()

        self._init_redis()

    def _init_redis(self):
        if not settings.use_redis:
            logger.info("Redis disabled via USE_REDIS=false, using in-memory API keys")
            return
        try:
            import redis

            self._redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            self._redis_client.ping()
            self._use_redis = True
            logger.info(f"API key store connected to Redis at {settings.redis_url}")
        except ImportError:
            logger.warning("redis package not installed, using in-memory API keys")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, using in-memory API keys")

    def create(self, user_id: str, name: str) -> tuple[APIKeyRecord, str]:
        """Create a key and return (record, raw_key). raw_key is shown to the caller once."""
        raw_key = f"{_PREFIX}{secrets.token_urlsafe(32)}"
        key_hash = _hash_key(raw_key)
        now = time.time()
        ttl = settings.api_key_ttl_seconds

        record: APIKeyRecord = {
            "id": secrets.token_hex(16),
            "user_id": user_id,
            "name": name,
            "display_prefix": raw_key[: len(_PREFIX) + 6],
            "key_hash": key_hash,
            "created_at": now,
            "expires_at": (now + ttl) if ttl > 0 else None,
            "last_used_at": None,
        }

        if self._use_redis and self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                pipe.set(_RECORD_KEY.format(id=record["id"]), json.dumps(record))
                pipe.hset(_HASH_INDEX_KEY, key_hash, record["id"])
                pipe.sadd(_USER_INDEX_KEY.format(user_id=user_id), record["id"])
                pipe.execute()
                return record, raw_key
            except Exception as e:
                logger.error(f"Redis API-key-store create error: {e}")

        with self._lock:
            self._memory_records[record["id"]] = record
            self._memory_by_hash[key_hash] = record["id"]
            self._memory_by_user.setdefault(user_id, set()).add(record["id"])
        return record, raw_key

    def get(self, key_id: str) -> APIKeyRecord | None:
        if self._use_redis and self._redis_client:
            try:
                raw = self._redis_client.get(_RECORD_KEY.format(id=key_id))
                return json.loads(raw) if raw else None
            except Exception as e:
                logger.error(f"Redis API-key-store get error: {e}")
                return None

        with self._lock:
            return self._memory_records.get(key_id)

    def resolve(self, raw_key: str) -> APIKeyRecord | None:
        """Look up a live (unexpired) key by its raw value and bump last_used_at."""
        key_hash = _hash_key(raw_key)

        if self._use_redis and self._redis_client:
            try:
                key_id = self._redis_client.hget(_HASH_INDEX_KEY, key_hash)
                if not key_id:
                    return None
            except Exception as e:
                logger.error(f"Redis API-key-store hash lookup error: {e}")
                return None
        else:
            with self._lock:
                key_id = self._memory_by_hash.get(key_hash)
            if not key_id:
                return None

        record = self.get(key_id)
        if record is None:
            return None
        if record["expires_at"] is not None and record["expires_at"] < time.time():
            return None

        record["last_used_at"] = time.time()
        self._save(record)
        return record

    def list_for_user(self, user_id: str) -> list[APIKeyRecord]:
        if self._use_redis and self._redis_client:
            try:
                ids = self._redis_client.smembers(_USER_INDEX_KEY.format(user_id=user_id))
                if not ids:
                    return []
                raws = self._redis_client.mget([_RECORD_KEY.format(id=i) for i in ids])
                return [json.loads(r) for r in raws if r]
            except Exception as e:
                logger.error(f"Redis API-key-store list error: {e}")
                return []

        with self._lock:
            ids = self._memory_by_user.get(user_id, set())
            return [self._memory_records[i] for i in ids if i in self._memory_records]

    def delete(self, key_id: str) -> bool:
        record = self.get(key_id)
        if record is None:
            return False

        if self._use_redis and self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                pipe.delete(_RECORD_KEY.format(id=key_id))
                pipe.hdel(_HASH_INDEX_KEY, record["key_hash"])
                pipe.srem(_USER_INDEX_KEY.format(user_id=record["user_id"]), key_id)
                pipe.execute()
                return True
            except Exception as e:
                logger.error(f"Redis API-key-store delete error: {e}")
                return False

        with self._lock:
            self._memory_records.pop(key_id, None)
            self._memory_by_hash.pop(record["key_hash"], None)
            self._memory_by_user.get(record["user_id"], set()).discard(key_id)
        return True

    def _save(self, record: APIKeyRecord) -> None:
        """Persist an in-place update (currently just last_used_at bumps)."""
        if self._use_redis and self._redis_client:
            try:
                self._redis_client.set(_RECORD_KEY.format(id=record["id"]), json.dumps(record))
                return
            except Exception as e:
                logger.error(f"Redis API-key-store save error: {e}")
                return

        with self._lock:
            self._memory_records[record["id"]] = record


_store: APIKeyStore | None = None


def get_api_key_store() -> APIKeyStore:
    global _store
    if _store is None:
        _store = APIKeyStore()
    return _store
