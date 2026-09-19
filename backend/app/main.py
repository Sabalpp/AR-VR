from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.websocket import router as ws_router
from app.config import settings

app = FastAPI(
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    title="Reach Physical Therapy API",
    version="1.0.0",
    description="Fictional hackathon demo; measurements are observational, not clinical assessment.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.public_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)
app.include_router(ws_router)


@app.get("/health")
def health():
    return {"status": "ok", "presage_enabled": False}


@app.get("/api/v1/time")
def server_time():
    from app.models import now

    return {"server_time": now().isoformat()}
