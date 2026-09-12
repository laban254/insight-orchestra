"""
Unit tests for the Redis-backed (in-memory fallback) DB connection store.

Forces the in-memory path for determinism, mirroring the pattern used for
WorkspaceStore/SessionManager tests.
"""

import time

from app.services.connection_store import ConnectionStore


def make_store(ttl_seconds=60) -> ConnectionStore:
    store = ConnectionStore(ttl_seconds=ttl_seconds)
    store._use_redis = False  # force in-memory regardless of environment
    return store


class TestConnectionStore:
    def test_register_and_get_roundtrip(self):
        store = make_store()
        schema = {"users": [{"name": "id", "type": "integer"}]}

        connection_id = store.register("postgresql", "postgresql://u:p@h/db", schema)
        meta = store.get(connection_id)

        assert meta is not None
        assert meta["db_type"] == "postgresql"
        assert meta["connection_string"] == "postgresql://u:p@h/db"
        assert meta["schema"] == schema

    def test_get_unknown_id_returns_none(self):
        store = make_store()
        assert store.get("does-not-exist") is None

    def test_remove_drops_entry(self):
        store = make_store()
        connection_id = store.register("sqlite", ":memory:", {})

        removed = store.remove(connection_id)

        assert removed is True
        assert store.get(connection_id) is None

    def test_remove_unknown_id_returns_false(self):
        store = make_store()
        removed = store.remove("does-not-exist")
        assert removed is False

    def test_stale_entry_is_reaped(self):
        store = make_store(ttl_seconds=0.05)
        connection_id = store.register("duckdb", ":memory:", {})

        time.sleep(0.1)

        assert store.get(connection_id) is None

    def test_get_refreshes_ttl_to_prevent_reap(self):
        store = make_store(ttl_seconds=0.15)
        connection_id = store.register("mysql", "mysql://u:p@h/db", {})

        time.sleep(0.08)
        assert store.get(connection_id) is not None  # refreshes expiry
        time.sleep(0.08)
        assert store.get(connection_id) is not None  # still alive: <0.15s since refresh
