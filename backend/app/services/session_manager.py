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
import os
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Session configuration
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", 3600))  # 1 hour default
MAX_HISTORY_PER_SESSION = 10


class SessionManager:
    """
    Session manager with Redis backend and in-memory fallback.
    """
    
    def __init__(self):
        self._redis_client = None
        self._use_redis = False
        self._memory_store: Dict[str, List[Dict]] = {}
        
        # Try to initialize Redis
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection if available."""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        
        if redis_url == "redis://localhost:6379":
            # Check if Redis is explicitly disabled
            if os.getenv("USE_REDIS", "true").lower() == "false":
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
    
    def get(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get session history.
        
        Args:
            session_id: The session identifier
            
        Returns:
            List of session interactions
        """
        if self._use_redis and self._redis_client:
            try:
                data = self._redis_client.get(f"session:{session_id}")
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        
        # Fallback to memory
        return self._memory_store.get(session_id, [])
    
    def set(self, session_id: str, history: List[Dict[str, Any]]) -> None:
        """
        Set session history.
        
        Args:
            session_id: The session identifier
            history: List of interactions to store
        """
        # Limit history size
        history = history[-MAX_HISTORY_PER_SESSION:]
        
        if self._use_redis and self._redis_client:
            try:
                self._redis_client.setex(
                    f"session:{session_id}",
                    SESSION_TTL_SECONDS,
                    json.dumps(history)
                )
                return
            except Exception as e:
                logger.error(f"Redis set error: {e}")
        
        # Fallback to memory
        self._memory_store[session_id] = history
    
    def append(self, session_id: str, interaction: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Append an interaction to session history.
        
        Args:
            session_id: The session identifier
            interaction: The interaction to add
            
        Returns:
            Updated session history
        """
        history = self.get(session_id)
        history.append(interaction)
        history = history[-MAX_HISTORY_PER_SESSION:]
        self.set(session_id, history)
        return history
    
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
    
    def get_stats(self) -> Dict[str, Any]:
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
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
