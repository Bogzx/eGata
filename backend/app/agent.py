"""Mock /agent/chat endpoint for Wave 1.

Plan 3 will replace the body with a real Pydantic AI + Gemini Live agent.
The endpoint contract (request/response shapes) must stay identical.
"""
from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends

from app.models import AgentChatRequest, AgentChatResponse, ChatToolCall
from app.security import current_citizen_id

router = APIRouter(prefix="/agent", tags=["agent"])

REDIRECT_REPLIES: dict[str, str] = {
    "anaf": (
        "Asta nu e treaba primăriei — ANAF se ocupă de taxele și impozitele pe venit. "
        "Te rog vizitează anaf.ro sau ghiseul.ro pentru plăți online."
    ),
    "cnas": (
        "Pentru CNAS (medic de familie, card de sănătate) nu putem completa noi cererea. "
        "Te rog contactează CNAS direct sau medicul tău de familie."
    ),
    "drpciv": (
        "Pentru DRPCIV (înmatriculări auto, talon) trebuie să mergi la serviciul DRPCIV. "
        "Pe roadmap-ul nostru avem integrarea directă."
    ),
}

KEYWORD_TO_PROCEDURE: list[tuple[tuple[str, ...], str, str]] = [
    (
        ("domiciliu", "mutare", "schimbat adresa"),
        "schimbare-domiciliu",
        "Înțeleg că vrei să-ți schimbi domiciliul. Continuăm?",
    ),
    (
        ("adeverință venit", "adeverinta venit", "dovada venit", "venit pentru banc"),
        "adeverinta-venit",
        "Am înțeles, vrei o adeverință de venit. Pentru ce scop o folosești?",
    ),
    (
        ("certificat fiscal", "atestare fiscală", "lipsa datorii"),
        "certificat-fiscal",
        "Vrei un certificat fiscal. Pentru ce ai nevoie de el?",
    ),
    (
        ("certificat de naștere", "duplicat naștere", "copie certificat nastere"),
        "certificat-nastere-copie",
        "Vrei o copie a certificatului de naștere. Pot să te ajut cu cererea.",
    ),
    (
        ("căsătorie", "casatorie", "vreau să mă căsătoresc"),
        "inregistrare-casatorie",
        "Felicitări! Te ajut cu declarația pentru oficierea căsătoriei.",
    ),
    (
        ("ajutor social", "venit minim"),
        "ajutor-social",
        "Te ajut să faci cererea pentru ajutor social.",
    ),
    (
        ("buletin", "carte de identitate", "ci nouă", "expiră buletinul"),
        "preschimbare-ci",
        "Te ajut cu cererea pentru preschimbarea cărții de identitate.",
    ),
]

DEFAULT_REPLY = (
    "Salut! Sunt CivicAI, asistentul digital al primăriei. "
    "Spune-mi cu ce te pot ajuta — de exemplu: «vreau să-mi schimb domiciliul» sau "
    "«am nevoie de o adeverință de venit»."
)


def _match_redirect(message: str) -> str | None:
    msg = message.lower()
    for key, reply in REDIRECT_REPLIES.items():
        if key in msg:
            return reply
    return None


def _match_procedure(message: str) -> tuple[str, str] | None:
    msg = message.lower()
    for keywords, procedure_id, reply in KEYWORD_TO_PROCEDURE:
        for kw in keywords:
            if kw in msg:
                return procedure_id, reply
    return None


@router.post("/chat", response_model=AgentChatResponse)
def chat(
    req: AgentChatRequest,
    _citizen_id: UUID = Depends(current_citizen_id),
) -> AgentChatResponse:
    conversation_id = req.conversation_id or f"conv_{secrets.token_urlsafe(8)}"

    redirect = _match_redirect(req.message)
    if redirect is not None:
        return AgentChatResponse(
            conversation_id=conversation_id,
            message=redirect,
            tool_calls=[],
        )

    match = _match_procedure(req.message)
    if match is not None:
        procedure_id, reply = match
        return AgentChatResponse(
            conversation_id=conversation_id,
            message=reply,
            tool_calls=[
                ChatToolCall(name="lookup_procedure", arguments={"query": req.message}),
                ChatToolCall(
                    name="suggest_procedure",
                    arguments={"procedure_id": procedure_id},
                ),
            ],
        )

    return AgentChatResponse(
        conversation_id=conversation_id,
        message=DEFAULT_REPLY,
        tool_calls=[],
    )
