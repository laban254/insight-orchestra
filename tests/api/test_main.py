"""
App-level tests: route versioning and the standardized error envelope.
"""

import pytest
from app.auth import SESSION_COOKIE_NAME, hash_password
from app.config import settings
from app.main import app
from app.services.auth_session import get_auth_session_store
from app.services.user_store import Role, get_user_store
from starlette.testclient import TestClient

client = TestClient(app)


class TestRouteVersioning:
    def test_health_is_unversioned(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_versioned_route_is_reachable(self):
        resp = client.get("/api/v1/demo/list")
        assert resp.status_code == 200
        assert "datasets" in resp.json()

    def test_unversioned_path_is_gone(self):
        resp = client.get("/demo/list")
        assert resp.status_code == 404

    def test_docs_stays_unversioned(self):
        resp = client.get("/docs")
        assert resp.status_code == 200


class TestDatasetRowsPagination:
    """The `limit`/`offset` bounds on GET /datasets/{id}/rows are enforced
    by FastAPI's Query() validation, which only runs over real HTTP — a
    direct function call (as in tests/api/test_endpoints.py) bypasses it."""

    def test_limit_over_the_cap_is_rejected(self):
        resp = client.get("/api/v1/datasets/does-not-matter/rows", params={"limit": 5000})
        assert resp.status_code == 422
        assert isinstance(resp.json()["detail"], str)

    def test_negative_offset_is_rejected(self):
        resp = client.get("/api/v1/datasets/does-not-matter/rows", params={"offset": -1})
        assert resp.status_code == 422

    def test_unknown_dataset_is_404_not_422(self):
        resp = client.get("/api/v1/datasets/does-not-exist/rows")
        assert resp.status_code == 404


class TestErrorEnvelope:
    def test_validation_error_detail_is_a_string_not_a_list(self):
        """FastAPI's default 422 shape is `detail: [{loc, msg, type}, ...]`,
        which every frontend error handler (expecting `detail: string`)
        would render as "[object Object]". The custom handler must collapse
        it to the same string shape as every other error response."""
        resp = client.post("/api/v1/nlq", json={})  # missing required fields
        assert resp.status_code == 422
        assert isinstance(resp.json()["detail"], str)
        assert "dataset_id" in resp.json()["detail"]
        assert "question" in resp.json()["detail"]

    def test_http_exception_detail_is_still_a_string(self):
        resp = client.get("/api/v1/datasets/does-not-exist")
        assert resp.status_code == 404
        assert isinstance(resp.json()["detail"], str)

    def test_response_carries_a_request_id_header(self):
        resp = client.get("/health")
        assert resp.headers["X-Request-ID"]


class TestAuthGatingIntegration:
    """End-to-end (real TestClient, real FastAPI dependency injection —
    unlike the direct function calls in tests/api/test_endpoints.py) checks
    that AUTH_ENABLED actually gates the app when turned on, and doesn't
    touch anything when it's off (the default, exercised implicitly by
    every other test in this file running with no AUTH_ENABLED set)."""

    @pytest.fixture
    def auth_on(self, monkeypatch):
        monkeypatch.setattr(settings, "auth_enabled", True)
        users = get_user_store()
        sessions = get_auth_session_store()
        created_user_ids = []
        created_tokens = []

        def make_session(role: Role) -> str:
            user = users.create(
                email=f"{role.value}-{len(created_user_ids)}@example.com",
                name=role.value,
                role=role,
                password_hash=hash_password("irrelevant"),
            )
            created_user_ids.append(user["id"])
            token = sessions.create(user["id"])
            created_tokens.append(token)
            return token

        yield make_session

        for uid in created_user_ids:
            users.delete(uid)
        for token in created_tokens:
            sessions.revoke(token)

    def test_config_requires_auth_when_enabled(self, auth_on):
        resp = client.get("/api/v1/config")
        assert resp.status_code == 401

    def test_config_forbidden_for_non_admin(self, auth_on):
        token = auth_on(Role.MEMBER)
        resp = client.get("/api/v1/config", cookies={SESSION_COOKIE_NAME: token})
        assert resp.status_code == 403

    def test_config_reachable_for_admin(self, auth_on):
        token = auth_on(Role.ADMIN)
        resp = client.get("/api/v1/config", cookies={SESSION_COOKIE_NAME: token})
        assert resp.status_code == 200

    def test_demo_list_requires_any_authenticated_role(self, auth_on):
        resp = client.get("/api/v1/demo/list")
        assert resp.status_code == 401

        token = auth_on(Role.VIEWER)
        resp = client.get("/api/v1/demo/list", cookies={SESSION_COOKIE_NAME: token})
        assert resp.status_code == 200

    def test_shared_session_link_stays_public_even_with_auth_on(self, auth_on):
        """Deliberately ungated (see api/sessions.py) — reaches the real
        handler (404 for an unknown token) rather than being blocked by auth
        (which would be 401)."""
        resp = client.get("/api/v1/sessions/shared/does-not-exist")
        assert resp.status_code == 404

    def test_auth_me_is_reachable_unauthenticated(self, auth_on):
        """The frontend calls /auth/me before it knows whether login is
        needed — it must return 200 with user:null, never 401, or the login
        flow can't bootstrap."""
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"auth_enabled": True, "oidc_configured": False, "user": None}

    def test_auth_me_reports_the_signed_in_user(self, auth_on):
        token = auth_on(Role.ADMIN)
        resp = client.get("/api/v1/auth/me", cookies={SESSION_COOKIE_NAME: token})
        assert resp.status_code == 200
        assert resp.json()["user"]["role"] == "admin"
