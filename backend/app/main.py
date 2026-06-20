from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router
from app.config import settings

app = FastAPI()

# Explicit allowed origins (set ALLOWED_ORIGINS, comma-separated). A wildcard
# can't be combined with credentials, so only enable credentials when scoped.
_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
_wildcard = "*" in _origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=not _wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

from app.api.connectors import router as connectors_router
app.include_router(connectors_router)

from app.api.export import router as export_router
app.include_router(export_router)

from app.api.sessions import router as sessions_router
app.include_router(sessions_router)

@app.get("/health")
def health_check():
    return {"status": "ok"} 