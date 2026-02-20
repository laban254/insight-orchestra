from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router

app = FastAPI()

# Allow all origins for development; restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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