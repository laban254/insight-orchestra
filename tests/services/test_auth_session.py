"""
Unit tests for the opaque-token auth session store (Redis-backed, in-memory
fallback). Same shape as test_connection_store.py.
"""

import time

from app.services.auth_session import AuthSessionStore


def make_store(ttl_seconds=60) -> AuthSessionStore:
    store = AuthSessionStore(ttl_seconds=ttl_seconds)
    store._use_redis = False  # force in-memory regardless of environment
    return store


class TestAuthSessionStore:
    def test_create_and_get_roundtrip(self):
        store = make_store()
        token = store.create("user-1")

        assert isinstance(token, str) and len(token) > 20
        assert store.get_user_id(token) == "user-1"

    def test_tokens_are_unique_per_call(self):
        store = make_store()
        t1 = store.create("user-1")
        t2 = store.create("user-1")
        assert t1 != t2

    def test_unknown_token_returns_none(self):
        store = make_store()
        assert store.get_user_id("does-not-exist") is None

    def test_revoke_drops_session(self):
        store = make_store()
        token = store.create("user-1")

        assert store.revoke(token) is True
        assert store.get_user_id(token) is None

    def test_revoke_unknown_token_returns_false(self):
        store = make_store()
        assert store.revoke("does-not-exist") is False

    def test_stale_session_is_reaped(self):
        store = make_store(ttl_seconds=0.05)
        token = store.create("user-1")

        time.sleep(0.1)

        assert store.get_user_id(token) is None

    def test_get_refreshes_ttl_to_prevent_reap(self):
        store = make_store(ttl_seconds=0.15)
        token = store.create("user-1")

        time.sleep(0.08)
        assert store.get_user_id(token) is not None  # refreshes expiry
        time.sleep(0.08)
        assert store.get_user_id(token) is not None  # still alive: <0.15s since refresh
