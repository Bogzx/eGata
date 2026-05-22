"""FastAPI app entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent import router as agent_router
from app.auth import router as auth_router
from app.citizens import router as citizens_router
from app.config import get_settings
from app.documents import router as documents_router
from app.procedures import router as procedures_router

settings = get_settings()

app = FastAPI(
    title="CivicAI",
    description="Civic AI agent for Romanian primărie procedures",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allow_origins.split(",")] or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(citizens_router)
app.include_router(procedures_router)
app.include_router(documents_router)
app.include_router(agent_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "civicai-backend"}
