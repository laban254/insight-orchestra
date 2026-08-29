"""
Dataset Registry — maps an opaque dataset id to a file the server owns.

Every ingestion path used to hand the browser a server filesystem path and
take it back on each request. That had three consequences:

* `/process` and `/nlq` had to accept any path under `/tmp` (where demo
  datasets, materialized DB tables and BigQuery results were written), which
  on a backend with no authentication is an arbitrary-file read.
* Those `/tmp` files vanish when the container is recreated — an image
  upgrade, or `docker compose down && up`. A saved workspace still restored
  its charts from Redis, then 404'd on the next question.
* Nothing could be cached against the dataset, because the server had no
  identity for it beyond a path the client supplied.

So datasets get an id, live under a directory on the mounted volume, and the
client never sees a path. Records are stored the same way sessions and
workspaces are: Redis-backed with an in-memory fallback.

Demo datasets additionally record how to rebuild themselves, so reopening an
old workspace regenerates the data instead of dead-ending.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from typing import TypedDict

from app.config import settings
from app.utils.file_utils import UPLOAD_DIR

logger = logging.getLogger(__name__)

# Datasets live inside the uploads volume so they survive a container
# recreate, unlike the /tmp files they replace.
DATASET_DIR = os.path.join(UPLOAD_DIR, "datasets")
os.makedirs(DATASET_DIR, exist_ok=True)

_RECORD_KEY = "dataset:{id}"
_INDEX_KEY = "datasets:index"

# Prefix marking a dataset the server knows how to rebuild from nothing.
DEMO_SOURCE_PREFIX = "demo:"


class DatasetRecord(TypedDict):
    id: str
    path: str
    name: str
    source: str  # "upload" | "demo:<dataset_id>" | "database" | "bigquery"
    created_at: float
    # Bumped on resolve_path() (sliding expiry, like ConnectionStore) so a
    # workspace someone keeps coming back to never gets reaped, while one
    # abandoned for DATASET_TTL_SECONDS does.
    last_accessed_at: float


class DatasetMissingError(Exception):
    """The dataset id is unknown, or its file is gone and unrecoverable."""


class DatasetRegistry:
    """Dataset metadata store with Redis backend and in-memory fallback."""

    def __init__(self):
        self._redis_client = None
        self._use_redis = False
        self._memory_store: dict[str, DatasetRecord] = {}
        self._lock = threading.Lock()
        self._init_redis()

    def _init_redis(self):
        if not settings.use_redis:
            logger.info("Redis disabled via USE_REDIS=false, using in-memory dataset registry")
            return
        try:
            import redis

            self._redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            self._redis_client.ping()
            self._use_redis = True
            logger.info(f"Dataset registry connected to Redis at {settings.redis_url}")
        except ImportError:
            logger.warning("redis package not installed, using in-memory dataset registry")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, using in-memory dataset registry")

    def register(self, path: str, name: str, source: str = "upload") -> str:
        dataset_id = uuid.uuid4().hex
        now = time.time()
        record: DatasetRecord = {
            "id": dataset_id,
            "path": path,
            "name": name,
            "source": source,
            "created_at": now,
            "last_accessed_at": now,
        }
        self._write(record)
        return dataset_id

    def touch(self, dataset_id: str) -> None:
        """Mark a dataset as just used, resetting its idle clock."""
        record = self.get(dataset_id)
        if record is not None:
            record["last_accessed_at"] = time.time()
            self._write(record)

    def _write(self, record: DatasetRecord) -> None:
        if self._use_redis and self._redis_client:
            try:
                payload = json.dumps(record)
                pipe = self._redis_client.pipeline()
                pipe.set(_RECORD_KEY.format(id=record["id"]), payload)
                pipe.hset(_INDEX_KEY, record["id"], payload)
                pipe.execute()
                return
            except Exception as e:
                logger.error(f"Redis dataset registry write error: {e}")

        with self._lock:
            self._memory_store[record["id"]] = record

    def get(self, dataset_id: str) -> DatasetRecord | None:
        if self._use_redis and self._redis_client:
            try:
                raw = self._redis_client.get(_RECORD_KEY.format(id=dataset_id))
                return json.loads(raw) if raw else None
            except Exception as e:
                logger.error(f"Redis dataset registry get error: {e}")
                return None

        with self._lock:
            return self._memory_store.get(dataset_id)

    def all(self) -> list[DatasetRecord]:
        """Every known record — used by the retention sweep."""
        if self._use_redis and self._redis_client:
            try:
                raw = self._redis_client.hgetall(_INDEX_KEY)
                return [json.loads(v) for v in raw.values()]
            except Exception as e:
                logger.error(f"Redis dataset registry list error: {e}")
                return []

        with self._lock:
            return list(self._memory_store.values())

    def delete(self, dataset_id: str, remove_file: bool = True) -> bool:
        record = self.get(dataset_id)
        if record is None:
            return False

        if remove_file:
            try:
                os.remove(record["path"])
            except OSError:
                pass  # already gone, or never written

        if self._use_redis and self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                pipe.delete(_RECORD_KEY.format(id=dataset_id))
                pipe.hdel(_INDEX_KEY, dataset_id)
                pipe.execute()
                return True
            except Exception as e:
                logger.error(f"Redis dataset registry delete error: {e}")
                return False

        with self._lock:
            return self._memory_store.pop(dataset_id, None) is not None

    def resolve_path(self, dataset_id: str) -> str:
        """Path for a dataset, rebuilding demo data if its file has gone.

        Raises DatasetMissingError with a message meant for the user.
        """
        record = self.get(dataset_id)
        if record is None:
            raise DatasetMissingError(
                "That dataset is no longer available. Upload it again to continue."
            )

        if os.path.isfile(record["path"]):
            self.touch(dataset_id)
            return record["path"]

        # A demo dataset is generated, not uploaded, so it can be rebuilt
        # rather than dead-ending an otherwise valid saved workspace.
        if record["source"].startswith(DEMO_SOURCE_PREFIX):
            demo_id = record["source"][len(DEMO_SOURCE_PREFIX) :]
            try:
                from app.utils.demo_data import DEMO_DATASETS, get_demo_dataset

                # get_demo_dataset() silently falls back to "sales" for an
                # unknown key, which here would rebuild a workspace named
                # "Weather Data" out of sales rows. Only regenerate a demo
                # that still exists.
                if demo_id not in DEMO_DATASETS:
                    raise KeyError(demo_id)
                df, _ = get_demo_dataset(demo_id)
                df.to_csv(record["path"], index=False)
                logger.info("Regenerated missing demo dataset %s", demo_id)
                self.touch(dataset_id)
                return record["path"]
            except Exception as e:
                logger.warning("Could not regenerate demo dataset %s: %s", demo_id, e)

        raise DatasetMissingError(
            f"The data behind '{record['name']}' is no longer on disk. "
            f"Load the dataset again to continue."
        )

    def reap_expired(self, ttl_seconds: int) -> list[str]:
        """Delete datasets idle past `ttl_seconds`; return the ids removed.

        `ttl_seconds <= 0` disables age-based reaping (the registry then
        only shrinks via explicit delete()). A workspace referencing a
        reaped dataset simply reports the data as gone on reopen — the same
        path already used for a dataset lost to any other cause.
        """
        if ttl_seconds <= 0:
            return []
        now = time.time()
        expired = [r["id"] for r in self.all() if now - r.get("last_accessed_at", 0) > ttl_seconds]
        for dataset_id in expired:
            self.delete(dataset_id)
        return expired


_registry: DatasetRegistry | None = None


def get_dataset_registry() -> DatasetRegistry:
    global _registry
    if _registry is None:
        _registry = DatasetRegistry()
    return _registry
