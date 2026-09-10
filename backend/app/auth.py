"""
Auth & RBAC dependencies.

AUTH_ENABLED=False (the default) makes every dependency here a no-op, so an
operator who never configures auth gets the exact previous behaviour: no
login, no gating, nothing to break. Once enabled, `get_current_user` resolves
an identity from either a Bearer API key or the session cookie, and
`require_role(...)` / `require_user` gate an endpoint on top of that.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine

import bcrypt
from fastapi import Cookie, Depends, Header, HTTPException, status

from app.config import settings
from app.services.api_keys import get_api_key_store
from app.services.auth_session import get_auth_session_store
from app.services.user_store import Role, UserRecord, get_user_store

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "io_session"


def hash_password(password: str) -> str:
    return str(bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bool(bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8")))
    except ValueError:
        # Malformed hash (shouldn't happen for accounts created via hash_password) —
        # treat as a failed check rather than a 500.
        return False


def _resolve_from_api_key(authorization: str | None) -> UserRecord | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    raw_key = authorization[len("bearer ") :].strip()
    record = get_api_key_store().resolve(raw_key)
    if record is None:
        return None
    return get_user_store().get(record["user_id"])


def _resolve_from_session(session_token: str | None) -> UserRecord | None:
    if not session_token:
        return None
    user_id = get_auth_session_store().get_user_id(session_token)
    if user_id is None:
        return None
    return get_user_store().get(user_id)


async def get_current_user(
    authorization: str | None = Header(default=None),
    io_session: str | None = Cookie(default=None),
) -> UserRecord | None:
    """Resolve the caller's identity, or None if unauthenticated/unresolved/disabled.

    Never raises, so it's safe to depend on from endpoints that want to know
    *who* the caller is (e.g. to attribute an audit log entry) without
    forcing every caller to be someone — including every caller, always,
    when AUTH_ENABLED=False.
    """
    if not settings.auth_enabled:
        return None

    user = _resolve_from_api_key(authorization)
    if user is None:
        user = _resolve_from_session(io_session)
    if user is not None and not user.get("is_active", True):
        return None
    return user


async def require_user(user: UserRecord | None = Depends(get_current_user)) -> UserRecord | None:
    """Require a resolved identity, but only once auth is actually enabled.

    A no-op when AUTH_ENABLED=False (returns None, same as get_current_user)
    so existing no-auth deployments are unaffected. Once enabled, an
    unresolved identity is a 401.
    """
    if not settings.auth_enabled:
        return None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    return user


def require_role(*roles: Role) -> Callable[..., Coroutine[None, None, UserRecord | None]]:
    """Dependency factory: require the caller to hold one of `roles`.

    A no-op when AUTH_ENABLED=False, same rationale as require_user. Admin
    implicitly satisfies any role requirement — it's the superset role, not
    one more role to list at every call site.
    """
    allowed = {r.value for r in roles}

    async def _dep(user: UserRecord | None = Depends(get_current_user)) -> UserRecord | None:
        if not settings.auth_enabled:
            return None
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
            )
        if user["role"] == Role.ADMIN.value or user["role"] in allowed:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    return _dep
