"""
Unit tests for the append-only audit log store (Redis LIST-backed, bounded
in-memory deque fallback).
"""

from app.services.audit_log import AuditLogStore


def make_store(max_entries=100) -> AuditLogStore:
    store = AuditLogStore(max_entries=max_entries)
    store._use_redis = False  # force in-memory regardless of environment
    return store


class TestAuditLogStore:
    def test_record_and_list_recent(self):
        store = make_store()
        store.record("login", actor_user_id="u1", actor_email="a@example.com")

        entries = store.list_recent()

        assert len(entries) == 1
        assert entries[0]["action"] == "login"
        assert entries[0]["actor_user_id"] == "u1"
        assert entries[0]["actor_email"] == "a@example.com"
        assert entries[0]["id"]
        assert entries[0]["timestamp"] > 0

    def test_newest_first(self):
        store = make_store()
        store.record("login", actor_email="first@example.com")
        store.record("login", actor_email="second@example.com")

        entries = store.list_recent()

        assert entries[0]["actor_email"] == "second@example.com"
        assert entries[1]["actor_email"] == "first@example.com"

    def test_optional_fields_default_to_none(self):
        store = make_store()
        store.record("login_failed", actor_email="nope@example.com")

        entry = store.list_recent()[0]
        assert entry["actor_user_id"] is None
        assert entry["resource"] is None
        assert entry["detail"] is None
        assert entry["ip_address"] is None

    def test_detail_and_resource_and_ip_are_recorded(self):
        store = make_store()
        store.record(
            "config_change",
            actor_user_id="u1",
            resource="dataset-1",
            detail={"provider": "openai"},
            ip_address="10.0.0.1",
        )

        entry = store.list_recent()[0]
        assert entry["resource"] == "dataset-1"
        assert entry["detail"] == {"provider": "openai"}
        assert entry["ip_address"] == "10.0.0.1"

    def test_list_recent_respects_limit(self):
        store = make_store()
        for i in range(5):
            store.record("login", actor_email=f"user{i}@example.com")

        assert len(store.list_recent(limit=2)) == 2

    def test_bounded_by_max_entries(self):
        store = make_store(max_entries=3)
        for i in range(5):
            store.record("login", actor_email=f"user{i}@example.com")

        entries = store.export_all()

        assert len(entries) == 3
        # Oldest entries were dropped, newest kept.
        assert entries[0]["actor_email"] == "user4@example.com"
        assert entries[-1]["actor_email"] == "user2@example.com"

    def test_export_all_returns_every_retained_entry(self):
        store = make_store()
        for i in range(3):
            store.record("login", actor_email=f"user{i}@example.com")

        assert len(store.export_all()) == 3
