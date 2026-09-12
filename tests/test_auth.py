"""
Unit tests for app/auth.py: password hashing and the get_current_user /
require_user / require_role FastAPI dependencies.

Route handlers elsewhere in the app call these via Depends(), which this
suite doesn't exercise (matches the existing convention of calling route
functions directly rather than through TestClient — see tests/api/). Here
they're called directly as plain async functions, passing explicit
`authorization`/`io_session`/`user` arguments instead of letting FastAPI
resolve the dependency chain.
"""

import pytest
from app import auth as auth_module
from app.auth import (
    get_current_user,
    hash_password,
    require_role,
    require_user,
    verify_password,
)
from app.services.user_store import Role
from fastapi import HTTPException


def make_user(role="member", is_active=True, user_id="u1"):
    return {
        "id": user_id,
        "email": "user@example.com",
        "name": "User",
        "role": role,
        "password_hash": None,
        "auth_provider": "local",
        "created_at": 0.0,
        "is_active": is_active,
    }


class TestPasswordHashing:
    def test_roundtrip(self):
        hashed = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct horse battery staple")
        assert verify_password("wrong password", hashed) is False

    def test_hash_is_not_the_plaintext(self):
        hashed = hash_password("secret")
        assert hashed != "secret"

    def test_malformed_hash_returns_false_not_raise(self):
        assert verify_password("secret", "not-a-real-bcrypt-hash") is False


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_auth_disabled_always_returns_none(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "auth_enabled", False)
        user = await get_current_user(authorization="Bearer whatever", io_session="whatever")
        assert user is None

    @pytest.mark.asyncio
    async def test_auth_enabled_no_credentials_returns_none(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "auth_enabled", True)
        user = await get_current_user(authorization=None, io_session=None)
        assert user is None

    @pytest.mark.asyncio
    async def test_resolves_from_bearer_api_key(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "auth_enabled", True)
        record = make_user()

        fake_key_store = type(
            "S",
            (),
            {"resolve": lambda self, raw: {"user_id": record["id"]} if raw == "sk" else None},
        )()
        fake_user_store = type(
            "S", (), {"get": lambda self, uid: record if uid == record["id"] else None}
        )()
        monkeypatch.setattr(auth_module, "get_api_key_store", lambda: fake_key_store)
        monkeypatch.setattr(auth_module, "get_user_store", lambda: fake_user_store)

        user = await get_current_user(authorization="Bearer sk", io_session=None)
        assert user == record

    @pytest.mark.asyncio
    async def test_resolves_from_session_cookie(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "auth_enabled", True)
        record = make_user()

        fake_session_store = type(
            "S", (), {"get_user_id": lambda self, tok: record["id"] if tok == "tok" else None}
        )()
        fake_user_store = type(
            "S", (), {"get": lambda self, uid: record if uid == record["id"] else None}
        )()
        monkeypatch.setattr(auth_module, "get_auth_session_store", lambda: fake_session_store)
        monkeypatch.setattr(auth_module, "get_user_store", lambda: fake_user_store)

        user = await get_current_user(authorization=None, io_session="tok")
        assert user == record

    @pytest.mark.asyncio
    async def test_inactive_user_returns_none(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "auth_enabled", True)
        record = make_user(is_active=False)

        fake_session_store = type("S", (), {"get_user_id": lambda self, tok: record["id"]})()
        fake_user_store = type("S", (), {"get": lambda self, uid: record})()
        monkeypatch.setattr(auth_module, "get_auth_session_store", lambda: fake_session_store)
        monkeypatch.setattr(auth_module, "get_user_store", lambda: fake_user_store)

        user = await get_current_user(authorization=None, io_session="tok")
        assert user is None


class TestRequireUser:
    @pytest.mark.asyncio
    async def test_auth_disabled_is_a_noop(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "auth_enabled", False)
        assert await require_user(user=None) is None

    @pytest.mark.asyncio
    async def test_auth_enabled_no_user_raises_401(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "auth_enabled", True)
        with pytest.raises(HTTPException) as exc:
            await require_user(user=None)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_auth_enabled_with_user_passes_through(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "auth_enabled", True)
        record = make_user()
        assert await require_user(user=record) == record


class TestRequireRole:
    @pytest.mark.asyncio
    async def test_auth_disabled_is_a_noop(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "auth_enabled", False)
        dep = require_role(Role.ADMIN)
        assert await dep(user=None) is None

    @pytest.mark.asyncio
    async def test_no_user_raises_401(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "auth_enabled", True)
        dep = require_role(Role.MEMBER)
        with pytest.raises(HTTPException) as exc:
            await dep(user=None)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_matching_role_passes(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "auth_enabled", True)
        dep = require_role(Role.MEMBER)
        record = make_user(role="member")
        assert await dep(user=record) == record

    @pytest.mark.asyncio
    async def test_wrong_role_raises_403(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "auth_enabled", True)
        dep = require_role(Role.MEMBER)
        record = make_user(role="viewer")
        with pytest.raises(HTTPException) as exc:
            await dep(user=record)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_bypasses_any_role_requirement(self, monkeypatch):
        monkeypatch.setattr(auth_module.settings, "auth_enabled", True)
        dep = require_role(Role.VIEWER)
        record = make_user(role="admin")
        assert await dep(user=record) == record
