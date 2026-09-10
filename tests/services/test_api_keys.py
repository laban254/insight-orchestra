"""
Unit tests for the API key store: hashed lookup, self-service listing,
deletion, and expiry.
"""

import time

from app.services import api_keys as api_keys_module
from app.services.api_keys import APIKeyStore


def make_store() -> APIKeyStore:
    store = APIKeyStore()
    store._use_redis = False  # force in-memory regardless of environment
    return store


class TestAPIKeyStore:
    def test_create_returns_record_and_raw_key_once(self):
        store = make_store()
        record, raw_key = store.create("user-1", "CI key")

        assert raw_key.startswith("iok_")
        assert record["name"] == "CI key"
        assert record["user_id"] == "user-1"
        # The raw key is never persisted — only its hash and a short prefix.
        assert "key" not in record
        assert record["display_prefix"] == raw_key[: len(record["display_prefix"])]

    def test_resolve_finds_key_by_raw_value(self):
        store = make_store()
        record, raw_key = store.create("user-1", "CI key")

        resolved = store.resolve(raw_key)

        assert resolved is not None
        assert resolved["id"] == record["id"]
        assert resolved["last_used_at"] is not None  # bumped on resolve

    def test_resolve_unknown_key_returns_none(self):
        store = make_store()
        assert store.resolve("iok_not-a-real-key") is None

    def test_resolve_expired_key_returns_none(self, monkeypatch):
        monkeypatch.setattr(api_keys_module.settings, "api_key_ttl_seconds", 1)
        store = make_store()
        _, raw_key = store.create("user-1", "Short-lived")

        time.sleep(1.2)

        assert store.resolve(raw_key) is None

    def test_no_expiry_by_default(self, monkeypatch):
        monkeypatch.setattr(api_keys_module.settings, "api_key_ttl_seconds", 0)
        store = make_store()
        record, _ = store.create("user-1", "Forever")
        assert record["expires_at"] is None

    def test_list_for_user_scoped_to_owner(self):
        store = make_store()
        store.create("user-1", "Key A")
        store.create("user-1", "Key B")
        store.create("user-2", "Other user's key")

        keys = store.list_for_user("user-1")

        assert {k["name"] for k in keys} == {"Key A", "Key B"}

    def test_delete_removes_key(self):
        store = make_store()
        record, raw_key = store.create("user-1", "CI key")

        assert store.delete(record["id"]) is True
        assert store.get(record["id"]) is None
        assert store.resolve(raw_key) is None

    def test_delete_unknown_id_returns_false(self):
        store = make_store()
        assert store.delete("does-not-exist") is False
