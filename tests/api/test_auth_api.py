"""
Tests for /auth: login/logout/me, self-service API keys, and admin user
management. Follows the existing convention (see test_workspaces.py) of
calling route functions directly rather than through a TestClient, with
fresh in-memory stores wired in per test.
"""

import pytest
from app.api import auth as auth_api
from app.auth import SESSION_COOKIE_NAME, hash_password
from app.services.api_keys import APIKeyStore
from app.services.audit_log import AuditLogStore
from app.services.auth_session import AuthSessionStore
from app.services.user_store import Role, UserStore
from fastapi import HTTPException, Response


class FakeClient:
    def __init__(self, host):
        self.host = host


class FakeRequest:
    def __init__(self, cookies=None, client_host="203.0.113.5"):
        self.cookies = cookies or {}
        self.client = FakeClient(client_host) if client_host else None


@pytest.fixture(autouse=True)
def stores(monkeypatch):
    """Fresh in-memory stores wired into the router, and auth switched on
    by default — most of these routes 404 outright when it's off."""
    users = UserStore()
    users._use_redis = False
    sessions = AuthSessionStore(ttl_seconds=3600)
    sessions._use_redis = False
    api_keys = APIKeyStore()
    api_keys._use_redis = False
    audit = AuditLogStore(max_entries=1000)
    audit._use_redis = False

    monkeypatch.setattr(auth_api, "_users", users)
    monkeypatch.setattr(auth_api, "_sessions", sessions)
    monkeypatch.setattr(auth_api, "_api_keys", api_keys)
    monkeypatch.setattr(auth_api, "_audit", audit)
    monkeypatch.setattr(auth_api.settings, "auth_enabled", True)

    return {"users": users, "sessions": sessions, "api_keys": api_keys, "audit": audit}


def make_local_user(stores, email="person@example.com", password="hunter22", role=Role.MEMBER):
    return stores["users"].create(
        email=email, name="Person", role=role, password_hash=hash_password(password)
    )


class TestLogin:
    @pytest.mark.asyncio
    async def test_wrong_password_records_login_failed_and_401s(self, stores):
        make_local_user(stores, password="correct-password")

        with pytest.raises(HTTPException) as exc:
            await auth_api.login(
                auth_api.LoginRequest(email="person@example.com", password="wrong"),
                FakeRequest(),
                Response(),
            )
        assert exc.value.status_code == 401
        entries = stores["audit"].list_recent()
        assert entries[0]["action"] == "login_failed"

    @pytest.mark.asyncio
    async def test_unknown_email_401s(self, stores):
        with pytest.raises(HTTPException) as exc:
            await auth_api.login(
                auth_api.LoginRequest(email="nobody@example.com", password="whatever"),
                FakeRequest(),
                Response(),
            )
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_oidc_only_account_cannot_password_login(self, stores):
        stores["users"].create(
            email="sso@example.com", name="SSO", role=Role.MEMBER, auth_provider="oidc"
        )
        with pytest.raises(HTTPException) as exc:
            await auth_api.login(
                auth_api.LoginRequest(email="sso@example.com", password="anything"),
                FakeRequest(),
                Response(),
            )
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_successful_login_sets_cookie_and_returns_user(self, stores):
        make_local_user(stores, password="correct-password")
        response = Response()

        result = await auth_api.login(
            auth_api.LoginRequest(email="person@example.com", password="correct-password"),
            FakeRequest(),
            response,
        )

        assert result["user"]["email"] == "person@example.com"
        assert "password_hash" not in result["user"]
        assert SESSION_COOKIE_NAME in response.headers.get("set-cookie", "")
        assert stores["audit"].list_recent()[0]["action"] == "login"

    @pytest.mark.asyncio
    async def test_inactive_account_cannot_login(self, stores):
        user = make_local_user(stores, password="correct-password")
        stores["users"].update(user["id"], is_active=False)

        with pytest.raises(HTTPException) as exc:
            await auth_api.login(
                auth_api.LoginRequest(email="person@example.com", password="correct-password"),
                FakeRequest(),
                Response(),
            )
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_disabled_when_auth_off(self, monkeypatch, stores):
        monkeypatch.setattr(auth_api.settings, "auth_enabled", False)
        with pytest.raises(HTTPException) as exc:
            await auth_api.login(
                auth_api.LoginRequest(email="anyone@example.com", password="x"),
                FakeRequest(),
                Response(),
            )
        assert exc.value.status_code == 404


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_revokes_session_and_clears_cookie(self, stores):
        user = make_local_user(stores)
        token = stores["sessions"].create(user["id"])
        response = Response()

        result = await auth_api.logout(
            FakeRequest(cookies={SESSION_COOKIE_NAME: token}), response, user=user
        )

        assert result == {"status": "logged_out"}
        assert stores["sessions"].get_user_id(token) is None


class TestMe:
    @pytest.mark.asyncio
    async def test_me_reports_auth_enabled_and_user(self, stores):
        user = make_local_user(stores)
        result = await auth_api.me(user=user)
        assert result["auth_enabled"] is True
        assert result["user"]["email"] == "person@example.com"

    @pytest.mark.asyncio
    async def test_me_with_no_user_returns_null_user(self, stores):
        result = await auth_api.me(user=None)
        assert result["user"] is None


class TestAPIKeys:
    @pytest.mark.asyncio
    async def test_create_list_delete_roundtrip(self, stores):
        user = make_local_user(stores)

        created = await auth_api.create_api_key(
            auth_api.APIKeyCreateRequest(name="CI key"), user=user
        )
        assert created["key"].startswith("iok_")
        assert created["name"] == "CI key"

        listed = await auth_api.list_api_keys(user=user)
        assert len(listed["api_keys"]) == 1
        assert "key" not in listed["api_keys"][0]  # raw key never listed back

        result = await auth_api.delete_api_key(created["id"], user=user)
        assert result == {"status": "deleted"}
        assert await auth_api.list_api_keys(user=user) == {"api_keys": []}

    @pytest.mark.asyncio
    async def test_cannot_delete_another_users_key(self, stores):
        owner = make_local_user(stores, email="owner@example.com")
        other = make_local_user(stores, email="other@example.com")
        created = await auth_api.create_api_key(
            auth_api.APIKeyCreateRequest(name="Owner's key"), user=owner
        )

        with pytest.raises(HTTPException) as exc:
            await auth_api.delete_api_key(created["id"], user=other)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_admin_can_delete_any_users_key(self, stores):
        owner = make_local_user(stores, email="owner@example.com")
        admin = make_local_user(stores, email="admin@example.com", role=Role.ADMIN)
        created = await auth_api.create_api_key(
            auth_api.APIKeyCreateRequest(name="Owner's key"), user=owner
        )

        result = await auth_api.delete_api_key(created["id"], user=admin)
        assert result == {"status": "deleted"}

    @pytest.mark.asyncio
    async def test_api_keys_disabled_when_auth_off(self, monkeypatch, stores):
        monkeypatch.setattr(auth_api.settings, "auth_enabled", False)
        with pytest.raises(HTTPException) as exc:
            await auth_api.list_api_keys(user=None)
        assert exc.value.status_code == 404


class TestUserManagement:
    @pytest.mark.asyncio
    async def test_admin_can_create_and_list_users(self, stores):
        admin = make_local_user(stores, email="admin@example.com", role=Role.ADMIN)

        created = await auth_api.create_user(
            auth_api.UserCreateRequest(
                email="new@example.com", name="New", password="longenough", role=Role.VIEWER
            ),
            user=admin,
        )
        assert created["role"] == "viewer"
        assert "password_hash" not in created

        listed = await auth_api.list_users(_user=admin)
        emails = {u["email"] for u in listed["users"]}
        assert {"admin@example.com", "new@example.com"} == emails

    @pytest.mark.asyncio
    async def test_duplicate_email_conflicts(self, stores):
        admin = make_local_user(stores, email="admin@example.com", role=Role.ADMIN)
        await auth_api.create_user(
            auth_api.UserCreateRequest(email="dupe@example.com", name="A", password="longenough"),
            user=admin,
        )
        with pytest.raises(HTTPException) as exc:
            await auth_api.create_user(
                auth_api.UserCreateRequest(
                    email="dupe@example.com", name="B", password="longenough"
                ),
                user=admin,
            )
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_update_user_role(self, stores):
        admin = make_local_user(stores, email="admin@example.com", role=Role.ADMIN)
        member = make_local_user(stores, email="member@example.com", role=Role.MEMBER)

        updated = await auth_api.update_user(
            member["id"], auth_api.UserUpdateRequest(role=Role.ADMIN), user=admin
        )
        assert updated["role"] == "admin"

    @pytest.mark.asyncio
    async def test_update_with_no_fields_400s(self, stores):
        admin = make_local_user(stores, email="admin@example.com", role=Role.ADMIN)
        member = make_local_user(stores, email="member@example.com", role=Role.MEMBER)

        with pytest.raises(HTTPException) as exc:
            await auth_api.update_user(member["id"], auth_api.UserUpdateRequest(), user=admin)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_admin_cannot_delete_own_account(self, stores):
        admin = make_local_user(stores, email="admin@example.com", role=Role.ADMIN)
        with pytest.raises(HTTPException) as exc:
            await auth_api.delete_user(admin["id"], user=admin)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_admin_can_delete_other_user(self, stores):
        admin = make_local_user(stores, email="admin@example.com", role=Role.ADMIN)
        member = make_local_user(stores, email="member@example.com", role=Role.MEMBER)

        result = await auth_api.delete_user(member["id"], user=admin)
        assert result == {"status": "deleted"}
        assert stores["users"].get(member["id"]) is None

    @pytest.mark.asyncio
    async def test_user_management_disabled_when_auth_off(self, monkeypatch, stores):
        monkeypatch.setattr(auth_api.settings, "auth_enabled", False)
        with pytest.raises(HTTPException) as exc:
            await auth_api.list_users(_user=None)
        assert exc.value.status_code == 404
