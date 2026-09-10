"""
Unit tests for the minimal OIDC client: CSRF state handling, and the
Authorization Code + id_token verification flow with a real (test-generated)
signed JWT rather than a mocked verifier — the signature/claims check is the
actual security boundary, so it's worth exercising for real.
"""

import time
from unittest.mock import MagicMock

import pytest
from app.services import oidc as oidc_module
from app.services.oidc import (
    OIDCError,
    OIDCNotConfiguredError,
    authorization_url,
    create_login_state,
    handle_callback,
)
from authlib.jose import JsonWebKey
from authlib.jose import jwt as jose_jwt


def configure(
    monkeypatch,
    issuer="https://idp.example.com",
    client_id="client-123",
    client_secret="shh",
    redirect_uri="https://app.example.com/callback",
):
    monkeypatch.setattr(oidc_module.settings, "oidc_issuer", issuer)
    monkeypatch.setattr(oidc_module.settings, "oidc_client_id", client_id)
    monkeypatch.setattr(oidc_module.settings, "oidc_client_secret", client_secret)
    monkeypatch.setattr(oidc_module.settings, "oidc_redirect_uri", redirect_uri)


def make_signed_id_token(issuer: str, client_id: str, extra_claims: dict | None = None):
    """A real RS256-signed id_token plus the matching JWKS document, so
    handle_callback exercises actual signature verification."""
    key = JsonWebKey.generate_key("RSA", 2048, options={"kid": "test-key"}, is_private=True)
    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": client_id,
        "sub": "user-123",
        "email": "person@example.com",
        "name": "Person",
        "iat": now,
        "exp": now + 300,
    }
    if extra_claims:
        payload.update(extra_claims)
    header = {"alg": "RS256", "kid": "test-key"}
    id_token = jose_jwt.encode(header, payload, key).decode("utf-8")
    public_jwk = key.as_dict(is_private=False)
    return id_token, {"keys": [public_jwk]}


class TestNotConfigured:
    def test_authorization_url_raises_when_unconfigured(self, monkeypatch):
        monkeypatch.setattr(oidc_module.settings, "oidc_issuer", "")
        monkeypatch.setattr(oidc_module.settings, "oidc_client_id", "")
        monkeypatch.setattr(oidc_module.settings, "oidc_client_secret", "")
        with pytest.raises(OIDCNotConfiguredError):
            authorization_url("state123")

    def test_handle_callback_raises_when_unconfigured(self, monkeypatch):
        monkeypatch.setattr(oidc_module.settings, "oidc_issuer", "")
        monkeypatch.setattr(oidc_module.settings, "oidc_client_id", "")
        monkeypatch.setattr(oidc_module.settings, "oidc_client_secret", "")
        with pytest.raises(OIDCNotConfiguredError):
            handle_callback("code", "state")


class TestLoginState:
    def test_state_tokens_are_unique(self):
        assert create_login_state() != create_login_state()

    def test_consume_is_single_use(self):
        store = oidc_module._NonceStore(ttl_seconds=60)
        token = store.create()
        assert store.consume(token) is True
        assert store.consume(token) is False

    def test_consume_unknown_token_fails(self):
        store = oidc_module._NonceStore(ttl_seconds=60)
        assert store.consume("nope") is False

    def test_expired_token_fails(self):
        store = oidc_module._NonceStore(ttl_seconds=0.05)
        token = store.create()
        time.sleep(0.1)
        assert store.consume(token) is False


class TestAuthorizationUrl:
    def test_builds_expected_params(self, monkeypatch):
        configure(monkeypatch)
        monkeypatch.setattr(
            oidc_module._discovery,
            "metadata",
            lambda: {"authorization_endpoint": "https://idp.example.com/authorize"},
        )
        url = authorization_url("state-abc")
        assert url.startswith("https://idp.example.com/authorize?")
        assert "client_id=client-123" in url
        assert "state=state-abc" in url
        assert "scope=openid" in url


class TestHandleCallback:
    def test_rejects_unknown_state(self, monkeypatch):
        configure(monkeypatch)
        with pytest.raises(OIDCError, match="expired"):
            handle_callback("code123", "never-issued-state")

    def test_happy_path_returns_claims(self, monkeypatch):
        configure(monkeypatch)
        state = create_login_state()
        id_token, jwks = make_signed_id_token(
            oidc_module.settings.oidc_issuer, oidc_module.settings.oidc_client_id
        )

        monkeypatch.setattr(
            oidc_module._discovery,
            "metadata",
            lambda: {
                "issuer": oidc_module.settings.oidc_issuer,
                "token_endpoint": "https://idp.example.com/token",
            },
        )
        monkeypatch.setattr(oidc_module._discovery, "jwks", lambda: jwks)

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = {"id_token": id_token}
        monkeypatch.setattr(oidc_module.requests, "post", lambda *a, **k: fake_response)

        claims = handle_callback("code123", state)

        assert claims == {"email": "person@example.com", "name": "Person", "sub": "user-123"}

    def test_token_endpoint_error_raises_oidc_error(self, monkeypatch):
        configure(monkeypatch)
        state = create_login_state()
        monkeypatch.setattr(
            oidc_module._discovery,
            "metadata",
            lambda: {"token_endpoint": "https://idp.example.com/token"},
        )
        fake_response = MagicMock(status_code=400, text="invalid_grant")
        monkeypatch.setattr(oidc_module.requests, "post", lambda *a, **k: fake_response)

        with pytest.raises(OIDCError):
            handle_callback("bad-code", state)

    def test_wrong_audience_rejected(self, monkeypatch):
        configure(monkeypatch)
        state = create_login_state()
        id_token, jwks = make_signed_id_token(
            oidc_module.settings.oidc_issuer, "someone-elses-client-id"
        )

        monkeypatch.setattr(
            oidc_module._discovery,
            "metadata",
            lambda: {
                "issuer": oidc_module.settings.oidc_issuer,
                "token_endpoint": "https://idp.example.com/token",
            },
        )
        monkeypatch.setattr(oidc_module._discovery, "jwks", lambda: jwks)

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = {"id_token": id_token}
        monkeypatch.setattr(oidc_module.requests, "post", lambda *a, **k: fake_response)

        with pytest.raises(OIDCError):
            handle_callback("code123", state)

    def test_missing_email_claim_rejected(self, monkeypatch):
        configure(monkeypatch)
        state = create_login_state()
        key = JsonWebKey.generate_key("RSA", 2048, options={"kid": "test-key"}, is_private=True)
        now = int(time.time())
        payload = {
            "iss": oidc_module.settings.oidc_issuer,
            "aud": oidc_module.settings.oidc_client_id,
            "sub": "user-123",
            "iat": now,
            "exp": now + 300,
        }
        id_token = jose_jwt.encode({"alg": "RS256", "kid": "test-key"}, payload, key).decode(
            "utf-8"
        )
        jwks = {"keys": [key.as_dict(is_private=False)]}

        monkeypatch.setattr(
            oidc_module._discovery,
            "metadata",
            lambda: {
                "issuer": oidc_module.settings.oidc_issuer,
                "token_endpoint": "https://idp.example.com/token",
            },
        )
        monkeypatch.setattr(oidc_module._discovery, "jwks", lambda: jwks)

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = {"id_token": id_token}
        monkeypatch.setattr(oidc_module.requests, "post", lambda *a, **k: fake_response)

        with pytest.raises(OIDCError, match="email"):
            handle_callback("code123", state)
