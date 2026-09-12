import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from app.auth import (
    SESSION_COOKIE_NAME,
    get_current_user,
    hash_password,
    require_role,
    require_user,
    verify_password,
)
from app.config import settings
from app.services import oidc
from app.services.api_keys import APIKeyRecord, get_api_key_store
from app.services.audit_log import get_audit_log_store
from app.services.auth_session import get_auth_session_store
from app.services.user_store import EmailAlreadyRegisteredError, Role, UserRecord, get_user_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_users = get_user_store()
_sessions = get_auth_session_store()
_api_keys = get_api_key_store()
_audit = get_audit_log_store()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _require_auth_enabled() -> None:
    """Identity-management routes have no meaning with auth off — 404 rather
    than silently letting an unauthenticated caller provision accounts that
    no login path will ever check."""
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="Auth is not enabled on this server.")


def _public_user(user: UserRecord) -> dict:
    """UserRecord without password_hash — every response that echoes a user goes through this."""
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "auth_provider": user["auth_provider"],
        "created_at": user["created_at"],
        "is_active": user["is_active"],
    }


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=settings.auth_session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.allowed_origins != "*",
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
async def login(req: LoginRequest, request: Request, response: Response):
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="Auth is not enabled on this server.")

    user = _users.get_by_email(req.email)
    if (
        user is None
        or user["password_hash"] is None
        or not user["is_active"]
        or not verify_password(req.password, user["password_hash"])
    ):
        _audit.record("login_failed", actor_email=req.email.lower(), ip_address=_client_ip(request))
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = _sessions.create(user["id"])
    _set_session_cookie(response, token)
    _audit.record(
        "login",
        actor_user_id=user["id"],
        actor_email=user["email"],
        ip_address=_client_ip(request),
    )
    return {"user": _public_user(user)}


@router.post("/logout")
async def logout(
    request: Request, response: Response, user: UserRecord | None = Depends(require_user)
):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        _sessions.revoke(token)
    response.delete_cookie(SESSION_COOKIE_NAME)
    if user is not None:
        _audit.record("logout", actor_user_id=user["id"], actor_email=user["email"])
    return {"status": "logged_out"}


@router.get("/me")
async def me(user: UserRecord | None = Depends(get_current_user)):
    """Whether auth is on, and who (if anyone) the caller is authenticated as.

    Never requires auth — the frontend calls this before it knows whether a
    login is needed, so an unauthenticated caller must get a clean
    `{auth_enabled, user: null}` rather than a 401.
    """
    return {
        "auth_enabled": settings.auth_enabled,
        "oidc_configured": bool(settings.oidc_issuer and settings.oidc_client_id),
        "user": _public_user(user) if user is not None else None,
    }


# --- OIDC SSO -----------------------------------------------------------


@router.get("/oidc/login")
async def oidc_login():
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="Auth is not enabled on this server.")
    try:
        state = oidc.create_login_state()
        url = oidc.authorization_url(state)
    except oidc.OIDCNotConfiguredError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return RedirectResponse(url)


@router.get("/oidc/callback")
async def oidc_callback(code: str, state: str, request: Request, response: Response):
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="Auth is not enabled on this server.")
    try:
        claims = oidc.handle_callback(code, state)
    except (oidc.OIDCNotConfiguredError, oidc.OIDCError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    email = claims["email"]
    user = _users.get_by_email(email)
    if user is None:
        # First user ever becomes admin (there's no one else to have granted
        # them a role); everyone after that starts as member and an admin
        # can promote them from there.
        role = Role.ADMIN if _users.count() == 0 else Role.MEMBER
        user = _users.create(email=email, name=claims["name"], role=role, auth_provider="oidc")

    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="This account has been deactivated.")

    token = _sessions.create(user["id"])
    _set_session_cookie(response, token)
    _audit.record(
        "login",
        actor_user_id=user["id"],
        actor_email=user["email"],
        detail={"provider": "oidc"},
        ip_address=_client_ip(request),
    )

    frontend_redirect = settings.allowed_origins.split(",")[0].strip() or "/"
    return RedirectResponse(frontend_redirect)


# --- API keys (self-service) --------------------------------------------


class APIKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


def _public_api_key(record: APIKeyRecord) -> dict:
    return {
        "id": record["id"],
        "name": record["name"],
        "display_prefix": record["display_prefix"],
        "created_at": record["created_at"],
        "expires_at": record["expires_at"],
        "last_used_at": record["last_used_at"],
    }


@router.post("/api-keys")
async def create_api_key(req: APIKeyCreateRequest, user: UserRecord | None = Depends(require_user)):
    _require_auth_enabled()
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    record, raw_key = _api_keys.create(user["id"], req.name)
    _audit.record(
        "api_key_create", actor_user_id=user["id"], actor_email=user["email"], resource=record["id"]
    )
    # raw_key is only ever returned here — the caller must save it now.
    return {**_public_api_key(record), "key": raw_key}


@router.get("/api-keys")
async def list_api_keys(user: UserRecord | None = Depends(require_user)):
    _require_auth_enabled()
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return {"api_keys": [_public_api_key(r) for r in _api_keys.list_for_user(user["id"])]}


@router.delete("/api-keys/{key_id}")
async def delete_api_key(key_id: str, user: UserRecord | None = Depends(require_user)):
    _require_auth_enabled()
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    record = _api_keys.get(key_id)
    if record is None or (record["user_id"] != user["id"] and user["role"] != Role.ADMIN.value):
        raise HTTPException(status_code=404, detail="API key not found.")
    _api_keys.delete(key_id)
    _audit.record(
        "api_key_delete", actor_user_id=user["id"], actor_email=user["email"], resource=key_id
    )
    return {"status": "deleted"}


# --- User management (admin only) ---------------------------------------


class UserCreateRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    role: Role = Role.MEMBER


class UserUpdateRequest(BaseModel):
    name: str | None = None
    role: Role | None = None
    is_active: bool | None = None


@router.get("/users")
async def list_users(_user: UserRecord | None = Depends(require_role(Role.ADMIN))):
    _require_auth_enabled()
    return {"users": [_public_user(u) for u in _users.list_all()]}


@router.post("/users")
async def create_user(
    req: UserCreateRequest, user: UserRecord | None = Depends(require_role(Role.ADMIN))
):
    _require_auth_enabled()
    try:
        record = _users.create(
            email=req.email,
            name=req.name,
            role=req.role,
            password_hash=hash_password(req.password),
            auth_provider="local",
        )
    except EmailAlreadyRegisteredError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if user is not None:
        _audit.record(
            "user_create",
            actor_user_id=user["id"],
            actor_email=user["email"],
            resource=record["id"],
            detail={"email": record["email"], "role": record["role"]},
        )
    return _public_user(record)


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    req: UserUpdateRequest,
    user: UserRecord | None = Depends(require_role(Role.ADMIN)),
):
    _require_auth_enabled()
    fields = {
        k: (v.value if isinstance(v, Role) else v)
        for k, v in req.model_dump(exclude_unset=True).items()
    }
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")
    updated = _users.update(user_id, **fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user is not None:
        _audit.record(
            "user_update",
            actor_user_id=user["id"],
            actor_email=user["email"],
            resource=user_id,
            detail=fields,
        )
    return _public_user(updated)


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, user: UserRecord | None = Depends(require_role(Role.ADMIN))):
    _require_auth_enabled()
    if user is not None and user_id == user["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")
    if not _users.delete(user_id):
        raise HTTPException(status_code=404, detail="User not found.")
    if user is not None:
        _audit.record(
            "user_delete", actor_user_id=user["id"], actor_email=user["email"], resource=user_id
        )
    return {"status": "deleted"}
