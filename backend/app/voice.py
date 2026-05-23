"""Voice session + tool-JWT signing/verification.

Two responsibilities:
- Issue short-lived JWTs the browser uses when Gemini Live emits a function-call
  that hits our HTTP tool-dispatch endpoints.
- POST /voice/session: bootstrap a Gemini Live browser session — returns the
  API key (TLS-protected), model/voice config, system prompt with context
  preamble, and the tool JWT + tool registry names.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.citizens import fetch_citizen_by_id
from app.config import get_settings
from app.documents import fetch_document
from app.procedures import get_registry
from app.prompts import build_system_prompt
from app.security import current_citizen_id

_bearer = HTTPBearer(auto_error=False)


@dataclass
class JwtClaims:
    citizen_id: str
    document_id: str | None
    aud: str
    iss: str
    exp: int
    jti: str


def issue_tool_jwt(
    citizen_id: str,
    document_id: str | None,
    ttl_seconds: int = 600,
) -> str:
    settings = get_settings()
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": citizen_id,
        "doc": document_id,
        "aud": settings.jwt_audience,
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": uuid.uuid4().hex,
    }
    return pyjwt.encode(payload, settings.jwt_signing_secret, algorithm="HS256")


def verify_tool_jwt(token: str) -> JwtClaims:
    settings = get_settings()
    decoded = pyjwt.decode(
        token,
        settings.jwt_signing_secret,
        algorithms=["HS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )
    return JwtClaims(
        citizen_id=decoded["sub"],
        document_id=decoded.get("doc"),
        aud=decoded["aud"],
        iss=decoded["iss"],
        exp=decoded["exp"],
        jti=decoded["jti"],
    )


def require_tool_jwt(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> JwtClaims:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing tool JWT")
    try:
        return verify_tool_jwt(creds.credentials)
    except pyjwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid tool JWT: {e}")


# ---- /voice/session endpoint ----

router = APIRouter(prefix="/voice", tags=["voice"])


class VoicePreferences(BaseModel):
    simple_language: bool = False
    voice_only: bool = False


class VoiceSessionRequest(BaseModel):
    document_id: str | None = None
    preferences: VoicePreferences = VoicePreferences()


class VoiceSessionResponse(BaseModel):
    session_id: str
    gemini_api_key: str
    gemini_model: str
    gemini_voice: str
    system_prompt: str
    tool_jwt: str
    tool_base_url: str
    tool_names: list[str]
    citizen_context: dict[str, Any]
    document_context: dict[str, Any] | None


@router.post("/session", response_model=VoiceSessionResponse)
def create_voice_session(
    req: VoiceSessionRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> VoiceSessionResponse:
    settings = get_settings()
    # Lazy import to avoid circular dependency at module load
    from app.tools import REGISTRY

    citizen = fetch_citizen_by_id(citizen_id)

    document_context: dict[str, Any] | None = None
    if req.document_id:
        try:
            doc = fetch_document(UUID(req.document_id))
        except Exception:
            raise HTTPException(status_code=404, detail="Document not found")
        if str(doc["citizen_id"]) != str(citizen_id):
            raise HTTPException(status_code=403, detail="Not your document")
        reg = get_registry()
        proc = reg.get(doc["procedure_id"])
        document_context = {
            "id": str(doc["id"]),
            "procedure_id": doc["procedure_id"],
            "procedure_title": proc.title if proc else doc["procedure_id"],
            "fields": doc.get("fields") or {},
            "required_fields": [
                f.model_dump() for f in (proc.fields if proc else []) if f.required
            ],
            "all_fields": [f.model_dump() for f in (proc.fields if proc else [])],
        }

    system_prompt = build_system_prompt(
        variant="conversational",
        simple_language=req.preferences.simple_language,
        voice_only=req.preferences.voice_only,
    )

    preamble_parts = [
        "\n\n---\nProfil cetățean activ:",
        f"Nume: {citizen['prenume']} {citizen['nume']}",
        f"Atribute: {citizen.get('attributes') or {}}",
    ]
    if document_context:
        missing = [
            f["name"] for f in document_context["required_fields"]
            if f["name"] not in (document_context["fields"] or {})
        ]
        preamble_parts.append(
            f"\nDocument activ: {document_context['procedure_title']}"
        )
        preamble_parts.append(f"Câmpuri completate: {document_context['fields']}")
        preamble_parts.append(f"Câmpuri obligatorii rămase: {missing}")

    full_prompt = system_prompt + "\n".join(preamble_parts)

    tool_jwt = issue_tool_jwt(
        citizen_id=str(citizen_id),
        document_id=req.document_id,
        ttl_seconds=1800,
    )

    return VoiceSessionResponse(
        session_id=uuid.uuid4().hex,
        gemini_api_key=settings.gemini_api_key,
        gemini_model=settings.gemini_voice_model,
        gemini_voice=settings.gemini_voice_name,
        system_prompt=full_prompt,
        tool_jwt=tool_jwt,
        tool_base_url=f"{settings.public_base_url}/tools",
        tool_names=list(REGISTRY.keys()),
        citizen_context={
            "id": str(citizen["id"]),
            "nume": citizen["nume"],
            "prenume": citizen["prenume"],
            "attributes": citizen.get("attributes") or {},
        },
        document_context=document_context,
    )
