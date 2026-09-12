import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.endpoints import router as api_router
from app.auth import hash_password
from app.config import settings
from app.logging_config import RequestIDMiddleware, configure_logging
from app.rate_limit import RateLimitMiddleware
from app.services.retention import run_periodic_sweep
from app.services.user_store import Role, get_user_store

configure_logging(settings.log_level)


def _bootstrap_admin() -> None:
    """Create the first admin account from ADMIN_EMAIL/ADMIN_PASSWORD.

    Only runs when auth is enabled, both env vars are set, and no users
    exist yet — so it's a one-time bootstrap, not something that fights
    with an admin who has since changed their password or been demoted.
    An OIDC-only deployment can leave these unset entirely (the first person
    to sign in via SSO becomes admin instead — see api/auth.py).
    """
    if not settings.auth_enabled or not (settings.admin_email and settings.admin_password):
        return
    users = get_user_store()
    if users.count() > 0:
        return
    users.create(
        email=settings.admin_email,
        name="Admin",
        role=Role.ADMIN,
        password_hash=hash_password(settings.admin_password),
        auth_provider="local",
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _bootstrap_admin()

    # Reaps expired datasets and deletes orphaned upload files on a
    # schedule — nothing else in the backend ever deletes an upload on its
    # own. Runs once, in-process; with multiple uvicorn workers each one
    # runs its own sweep, which is harmless since delete() is idempotent.
    sweeper = asyncio.create_task(run_periodic_sweep(settings.retention_sweep_interval_seconds))
    try:
        yield
    finally:
        sweeper.cancel()
        try:
            await sweeper
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)


# Every deliberate error in the app (`HTTPException(status_code, detail=...)`,
# ~35 call sites) returns `{"detail": "<string>"}`, and every frontend error
# handler reads `response.data.detail` expecting a string. FastAPI's default
# 422 for a bad request body is the one exception — `detail` is a list of
# `{loc, msg, type}` objects — which would render as "[object Object]" in
# the UI. Collapse it into the same string shape as everything else instead
# of inventing a second, different envelope just for this one case.
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    def _describe(error: dict) -> str:
        field = ".".join(str(p) for p in error["loc"] if p != "body")
        return f"{field}: {error['msg']}" if field else error["msg"]

    return JSONResponse(
        status_code=422,
        content={"detail": "; ".join(_describe(e) for e in exc.errors())},
    )


# Starlette's add_middleware() prepends, so the LAST one added ends up
# outermost. Order here (innermost to outermost): rate-limit, CORS,
# request-id. Rate-limit sits inside CORS so its 429s still get CORS
# headers attached (otherwise the browser reports a generic network error
# instead of a readable 429). Request-id is outermost so the id is set,
# and every log line during this request carries it, before any of the
# other middleware or the route handler runs.
app.add_middleware(RateLimitMiddleware)

# Explicit allowed origins (set ALLOWED_ORIGINS, comma-separated). A wildcard
# can't be combined with credentials, so only enable credentials when scoped.
_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
_wildcard = "*" in _origins or not _origins  # empty list also falls back to wildcard
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=not _wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)

# Versioned API surface. /health (below) deliberately stays outside it —
# it's an infra/ops concern (the Docker healthcheck hits it directly), not
# part of the versioned contract — and so do /docs and /redoc, which FastAPI
# serves itself regardless of router prefixes.
API_PREFIX = "/api/v1"

app.include_router(api_router, prefix=API_PREFIX)

from app.api.connectors import router as connectors_router  # noqa: E402

app.include_router(connectors_router, prefix=API_PREFIX)

from app.api.export import router as export_router  # noqa: E402

app.include_router(export_router, prefix=API_PREFIX)

from app.api.sessions import router as sessions_router  # noqa: E402

app.include_router(sessions_router, prefix=API_PREFIX)

from app.api.workspaces import router as workspaces_router  # noqa: E402

app.include_router(workspaces_router, prefix=API_PREFIX)

from app.api.auth import router as auth_router  # noqa: E402

app.include_router(auth_router, prefix=API_PREFIX)

from app.api.audit import router as audit_router  # noqa: E402

app.include_router(audit_router, prefix=API_PREFIX)


@app.get("/health")
def health_check():
    return {"status": "ok"}
