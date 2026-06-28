"""
Session Manager - Redis-backed session storage for production.

This module provides:
- Redis-based session storage (persists across restarts)
- Fallback to in-memory storage if Redis unavailable
- TTL-based session expiration
- Horizontal scaling support
"""

import json
import logging
import threading
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = settings.session_ttl_seconds
MAX_HISTORY_PER_SESSION = 10


class SessionManager:
    """
    Session manager with Redis backend and in-memory fallback.
    """

    def __init__(self):
        self._redis_client = None
        self._use_redis = False
        self._memory_store: dict[str, list[dict]] = {}
        self._lock = threading.Lock()  # guards _memory_store read-modify-write

        # Try to initialize Redis
        self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection if available."""
        redis_url = settings.redis_url

        if not settings.use_redis:
            logger.info("Redis disabled via USE_REDIS=false, using in-memory sessions")
            return

        try:
            import redis

            self._redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self._redis_client.ping()
            self._use_redis = True
            logger.info(f"Connected to Redis at {redis_url}")
        except ImportError:
            logger.warning("redis package not installed, using in-memory sessions")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, using in-memory sessions")

    def get(self, session_id: str) -> list[dict[str, Any]]:
        """
        Get session history.

        Args:
            session_id: The session identifier

        Returns:
            List of session interactions
        """
        if self._use_redis and self._redis_client:
            try:
                items = self._redis_client.lrange(f"session:{session_id}", 0, -1)
                return [json.loads(item) for item in items]
            except Exception as e:
                logger.error(f"Redis get error: {e}")

        return list(self._memory_store.get(session_id, []))

    def set(self, session_id: str, history: list[dict[str, Any]]) -> None:
        """
        Set session history.

        Args:
            session_id: The session identifier
            history: List of interactions to store
        """
        history = history[-MAX_HISTORY_PER_SESSION:]

        if self._use_redis and self._redis_client:
            try:
                key = f"session:{session_id}"
                pipe = self._redis_client.pipeline()
                pipe.delete(key)
                for item in history:
                    pipe.rpush(key, json.dumps(item))
                pipe.expire(key, SESSION_TTL_SECONDS)
                pipe.execute()
                return
            except Exception as e:
                logger.error(f"Redis set error: {e}")

        with self._lock:
            self._memory_store[session_id] = list(history)

    def append(self, session_id: str, interaction: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Append an interaction to session history (atomic in both backends).
        """
        if self._use_redis and self._redis_client:
            try:
                key = f"session:{session_id}"
                pipe = self._redis_client.pipeline()
                pipe.rpush(key, json.dumps(interaction))
                pipe.ltrim(key, -MAX_HISTORY_PER_SESSION, -1)
                pipe.expire(key, SESSION_TTL_SECONDS)
                pipe.execute()
                return self.get(session_id)
            except Exception as e:
                logger.error(f"Redis append error: {e}")

        # In-memory: lock protects the read-modify-write
        with self._lock:
            history = self._memory_store.get(session_id, [])
            history = list(history)  # copy before mutating
            history.append(interaction)
            history = history[-MAX_HISTORY_PER_SESSION:]
            self._memory_store[session_id] = history
            return list(history)

    def delete(self, session_id: str) -> None:
        """
        Delete a session.

        Args:
            session_id: The session identifier
        """
        if self._use_redis and self._redis_client:
            try:
                self._redis_client.delete(f"session:{session_id}")
                return
            except Exception as e:
                logger.error(f"Redis delete error: {e}")

        # Fallback to memory
        self._memory_store.pop(session_id, None)

    def clear_all(self) -> None:
        """Clear all sessions (for testing)."""
        if self._use_redis and self._redis_client:
            try:
                keys = self._redis_client.keys("session:*")
                if keys:
                    self._redis_client.delete(*keys)
                return
            except Exception as e:
                logger.error(f"Redis clear error: {e}")

        # Fallback to memory
        self._memory_store.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        if self._use_redis and self._redis_client:
            try:
                keys = self._redis_client.keys("session:*")
                return {
                    "backend": "redis",
                    "session_count": len(keys),
                    "ttl_seconds": SESSION_TTL_SECONDS,
                }
            except Exception as e:
                logger.error(f"Redis stats error: {e}")

        return {
            "backend": "memory",
            "session_count": len(self._memory_store),
            "ttl_seconds": SESSION_TTL_SECONDS,
        }


# Global session manager instance
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
