"""
Minimal OIDC client for SSO login (Authorization Code flow). SAML is not
supported — see PLAN.md for why OIDC-only was chosen.

Deliberately not authlib's Starlette integration
(`authlib.integrations.starlette_client.OAuth`) — that stores the CSRF
state in `request.session`, which needs Starlette's SessionMiddleware (and
the itsdangerous dependency it pulls in) just for a value that only needs
to survive a few minutes. This uses the same short-lived-nonce shape as
everywhere else in the app instead: an in-memory store with a TTL. A
backend restart mid-login just means the user's callback fails and they
retry — an acceptable edge case for a value this short-lived, and
consistent with the single-worker assumption documented in the Dockerfile.

The discovery document and JWKS are cached for the life of the process:
real providers rotate signing keys rarely and expect clients to cache this
metadata rather than fetching it on every login.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from urllib.parse import urlencode

import requests
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import JoseError

from app.config import settings

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 10


class OIDCNotConfiguredError(Exception):
    pass


class OIDCError(Exception):
    """The provider rejected the login, or the response couldn't be trusted."""


class _NonceStore:
    """CSRF state tokens for an in-flight login, expiring after a few minutes."""

    def __init__(self, ttl_seconds: int = 600):
        self._ttl = ttl_seconds
        self._entries: dict[str, float] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        token = uuid.uuid4().hex
        with self._lock:
            self._sweep_locked()
            self._entries[token] = time.monotonic()
        return token

    def consume(self, token: str) -> bool:
        """True if `token` was live (single-use: removed either way)."""
        with self._lock:
            self._sweep_locked()
            ts = self._entries.pop(token, None)
        return ts is not None and (time.monotonic() - ts) <= self._ttl

    def _sweep_locked(self) -> None:
        now = time.monotonic()
        stale = [t for t, ts in self._entries.items() if now - ts > self._ttl]
        for t in stale:
            self._entries.pop(t, None)


_state_store = _NonceStore()


def _require_configured() -> None:
    if not (settings.oidc_issuer and settings.oidc_client_id and settings.oidc_client_secret):
        raise OIDCNotConfiguredError(
            "OIDC is not configured (set OIDC_ISSUER / OIDC_CLIENT_ID / "
            "OIDC_CLIENT_SECRET / OIDC_REDIRECT_URI)."
        )


class _Discovery:
    """Process-lifetime cache of the provider's discovery doc + JWKS."""

    def __init__(self):
        self._metadata: dict | None = None
        self._jwks: dict | None = None
        self._lock = threading.Lock()

    def metadata(self) -> dict:
        with self._lock:
            if self._metadata is None:
                url = settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"
                resp = requests.get(url, timeout=_HTTP_TIMEOUT)
                resp.raise_for_status()
                self._metadata = resp.json()
            return self._metadata

    def jwks(self) -> dict:
        with self._lock:
            if self._jwks is None:
                resp = requests.get(self.metadata()["jwks_uri"], timeout=_HTTP_TIMEOUT)
                resp.raise_for_status()
                self._jwks = resp.json()
            return self._jwks


_discovery = _Discovery()


def create_login_state() -> str:
    return _state_store.create()


def authorization_url(state: str) -> str:
    _require_configured()
    meta = _discovery.metadata()
    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scope": "openid email profile",
        "state": state,
    }
    return f"{meta['authorization_endpoint']}?{urlencode(params)}"


def handle_callback(code: str, state: str) -> dict:
    """Validate state, exchange the code, verify the id_token.

    Returns {"email", "name", "sub"} from the verified token claims.
    """
    _require_configured()
    if not _state_store.consume(state):
        raise OIDCError("This login attempt has expired or was already used. Please try again.")

    meta = _discovery.metadata()
    resp = requests.post(
        meta["token_endpoint"],
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.oidc_redirect_uri,
            "client_id": settings.oidc_client_id,
            "client_secret": settings.oidc_client_secret,
        },
        timeout=_HTTP_TIMEOUT,
    )
    if resp.status_code != 200:
        logger.warning(f"OIDC token exchange failed: {resp.status_code} {resp.text[:300]}")
        raise OIDCError("The identity provider rejected the login.")

    token_response = resp.json()
    id_token = token_response.get("id_token")
    if not id_token:
        raise OIDCError("The identity provider did not return an id_token.")

    try:
        key_set = JsonWebKey.import_key_set(_discovery.jwks())
        claims = jwt.decode(
            id_token,
            key_set,
            claims_options={
                "iss": {"values": [meta.get("issuer", settings.oidc_issuer)]},
                "aud": {"values": [settings.oidc_client_id]},
            },
        )
        claims.validate()
    except JoseError as e:
        raise OIDCError(f"Could not verify the identity token: {e}") from e

    email = claims.get("email")
    if not email:
        raise OIDCError("The identity provider did not return an email claim.")

    return {"email": email, "name": claims.get("name") or email, "sub": claims.get("sub")}
