"""
Redis-backed cache for /nlq answers, keyed by dataset + question + the
active provider/model + the conversation so far.

Same dataset, same question, same provider/model, same prior conversation
implies the same LLM output for a low-temperature call — worth skipping the
generation + sandbox-execution round trip for. A different provider/model or
a different conversation history simply misses (a different key) rather than
needing explicit invalidation. Only successful executions are cached — a
transient failure shouldn't get "stuck" for the TTL, denying a retry a fresh
chance to succeed.

Same Redis-with-in-memory-fallback shape as session_manager.py /
workspace_store.py, so a Redis outage degrades this cache to per-process
rather than taking `/nlq` down.
"""

import hashlib
import json
import logging
import threading
from collections import OrderedDict
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# Bounded so a long-running process without Redis can't grow this
# unboundedly across many datasets/questions.
MAX_MEMORY_ENTRIES = 500


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _cache_key(
    dataset_id: str,
    question: str,
    provider: str,
    model: str,
    context: list[dict[str, Any]] | None,
) -> str:
    question_digest = _digest(question.strip().lower())
    context_digest = _digest(context or [])
    return f"nlq_cache:{dataset_id}:{provider}:{model}:{question_digest}:{context_digest}"


class QueryCache:
    def __init__(self):
        self._redis_client = None
        self._use_redis = False
        self._memory_store: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._init_redis()

    def _init_redis(self):
        if not settings.use_redis:
            logger.info("Redis disabled via USE_REDIS=false, using in-memory query cache")
            return
        try:
            import redis

            self._redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            self._redis_client.ping()
            self._use_redis = True
            logger.info(f"Query cache connected to Redis at {settings.redis_url}")
        except ImportError:
            logger.warning("redis package not installed, using in-memory query cache")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, using in-memory query cache")

    def get(
        self,
        dataset_id: str,
        question: str,
        provider: str,
        model: str,
        context: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        if not settings.query_cache_enabled:
            return None
        key = _cache_key(dataset_id, question, provider, model, context)

        if self._use_redis and self._redis_client:
            try:
                raw = self._redis_client.get(key)
                return json.loads(raw) if raw else None
            except Exception as e:
                logger.error(f"Query cache Redis get error: {e}")
                return None

        with self._lock:
            entry = self._memory_store.get(key)
            if entry is not None:
                self._memory_store.move_to_end(key)
            return entry

    def set(
        self,
        dataset_id: str,
        question: str,
        provider: str,
        model: str,
        response: dict[str, Any],
        context: list[dict[str, Any]] | None = None,
    ) -> None:
        if not settings.query_cache_enabled:
            return
        key = _cache_key(dataset_id, question, provider, model, context)

        if self._use_redis and self._redis_client:
            try:
                self._redis_client.set(
                    key, json.dumps(response), ex=settings.query_cache_ttl_seconds
                )
                return
            except Exception as e:
                logger.error(f"Query cache Redis set error: {e}")
                # Fall through to the in-memory path so a Redis hiccup at
                # write time doesn't lose the cache entry entirely.

        with self._lock:
            self._memory_store[key] = response
            self._memory_store.move_to_end(key)
            while len(self._memory_store) > MAX_MEMORY_ENTRIES:
                self._memory_store.popitem(last=False)


_query_cache: QueryCache | None = None


def get_query_cache() -> QueryCache:
    """Get the global query cache instance."""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache()
    return _query_cache
