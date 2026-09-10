"""
Unit tests for the Redis-backed (in-memory fallback) user account store.

Forces the in-memory path for determinism, mirroring the pattern used for
ConnectionStore/WorkspaceStore tests.
"""

import pytest
from app.services.user_store import EmailAlreadyRegisteredError, Role, UserStore


def make_store() -> UserStore:
    store = UserStore()
    store._use_redis = False  # force in-memory regardless of environment
    return store


class TestUserStore:
    def test_create_and_get_roundtrip(self):
        store = make_store()
        record = store.create(email="Admin@Example.com", name="Admin", role=Role.ADMIN)

        assert record["email"] == "admin@example.com"  # lowercased/stripped
        assert record["role"] == "admin"
        assert record["is_active"] is True
        assert record["password_hash"] is None

        fetched = store.get(record["id"])
        assert fetched == record

    def test_get_by_email_case_insensitive(self):
        store = make_store()
        record = store.create(email="user@example.com", name="U", role=Role.MEMBER)

        assert store.get_by_email("USER@EXAMPLE.COM") == record
        assert store.get_by_email(" user@example.com ") == record

    def test_get_unknown_id_returns_none(self):
        store = make_store()
        assert store.get("does-not-exist") is None

    def test_get_by_email_unknown_returns_none(self):
        store = make_store()
        assert store.get_by_email("nobody@example.com") is None

    def test_duplicate_email_rejected(self):
        store = make_store()
        store.create(email="dupe@example.com", name="First", role=Role.MEMBER)

        with pytest.raises(EmailAlreadyRegisteredError):
            store.create(email="dupe@example.com", name="Second", role=Role.VIEWER)

    def test_duplicate_email_rejected_case_insensitive(self):
        store = make_store()
        store.create(email="dupe@example.com", name="First", role=Role.MEMBER)

        with pytest.raises(EmailAlreadyRegisteredError):
            store.create(email="DUPE@example.com", name="Second", role=Role.VIEWER)

    def test_list_all(self):
        store = make_store()
        store.create(email="a@example.com", name="A", role=Role.ADMIN)
        store.create(email="b@example.com", name="B", role=Role.MEMBER)

        emails = {u["email"] for u in store.list_all()}
        assert emails == {"a@example.com", "b@example.com"}

    def test_count(self):
        store = make_store()
        assert store.count() == 0
        store.create(email="a@example.com", name="A", role=Role.ADMIN)
        assert store.count() == 1

    def test_update_merges_fields(self):
        store = make_store()
        record = store.create(email="a@example.com", name="A", role=Role.MEMBER)

        updated = store.update(record["id"], role="admin", is_active=False)

        assert updated["role"] == "admin"
        assert updated["is_active"] is False
        assert updated["email"] == "a@example.com"  # untouched fields survive

    def test_update_unknown_id_returns_none(self):
        store = make_store()
        assert store.update("nope", role="admin") is None

    def test_delete_removes_from_both_indexes(self):
        store = make_store()
        record = store.create(email="a@example.com", name="A", role=Role.MEMBER)

        assert store.delete(record["id"]) is True
        assert store.get(record["id"]) is None
        assert store.get_by_email("a@example.com") is None

    def test_delete_unknown_id_returns_false(self):
        store = make_store()
        assert store.delete("nope") is False

    def test_create_with_password_hash_and_provider(self):
        store = make_store()
        record = store.create(
            email="local@example.com",
            name="Local",
            role=Role.MEMBER,
            password_hash="$2b$...",
            auth_provider="local",
        )
        assert record["password_hash"] == "$2b$..."
        assert record["auth_provider"] == "local"

    def test_create_oidc_user_has_no_password(self):
        store = make_store()
        record = store.create(
            email="sso@example.com", name="SSO", role=Role.ADMIN, auth_provider="oidc"
        )
        assert record["password_hash"] is None
        assert record["auth_provider"] == "oidc"
