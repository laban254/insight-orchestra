import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import router as api_router
from app.config import settings
from app.services.retention import run_periodic_sweep


@asynccontextmanager
async def lifespan(_app: FastAPI):
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

app.include_router(api_router)

from app.api.connectors import router as connectors_router  # noqa: E402

app.include_router(connectors_router)

from app.api.export import router as export_router  # noqa: E402

app.include_router(export_router)

from app.api.sessions import router as sessions_router  # noqa: E402

app.include_router(sessions_router)

from app.api.workspaces import router as workspaces_router  # noqa: E402

app.include_router(workspaces_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
