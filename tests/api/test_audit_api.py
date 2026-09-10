"""Tests for /audit: admin-only recent-entries listing and JSON Lines export."""

import json

import pytest
from app.api import audit as audit_api
from app.services.audit_log import AuditLogStore
from app.services.user_store import Role
from fastapi import HTTPException


@pytest.fixture
def store(monkeypatch):
    s = AuditLogStore(max_entries=1000)
    s._use_redis = False
    monkeypatch.setattr(audit_api, "_audit", s)
    monkeypatch.setattr(audit_api.settings, "auth_enabled", True)
    return s


def make_admin(user_id="admin-1"):
    return {
        "id": user_id,
        "email": "admin@example.com",
        "name": "Admin",
        "role": Role.ADMIN.value,
        "password_hash": None,
        "auth_provider": "local",
        "created_at": 0.0,
        "is_active": True,
    }


class TestAuditLogEndpoints:
    @pytest.mark.asyncio
    async def test_list_recent_returns_entries(self, store):
        store.record("login", actor_email="a@example.com")
        result = await audit_api.list_audit_log(limit=200, _user=make_admin())
        assert len(result["entries"]) == 1
        assert result["entries"][0]["action"] == "login"

    @pytest.mark.asyncio
    async def test_export_returns_json_lines(self, store):
        store.record("login", actor_email="a@example.com")
        store.record("logout", actor_email="a@example.com")

        response = await audit_api.export_audit_log(_user=make_admin())
        lines = response.body.decode("utf-8").strip().split("\n")

        assert len(lines) == 2
        assert json.loads(lines[0])["action"] == "logout"  # newest first

    @pytest.mark.asyncio
    async def test_disabled_when_auth_off(self, store, monkeypatch):
        monkeypatch.setattr(audit_api.settings, "auth_enabled", False)
        with pytest.raises(HTTPException) as exc:
            await audit_api.list_audit_log(limit=200, _user=None)
        assert exc.value.status_code == 404
