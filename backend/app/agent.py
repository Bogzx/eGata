"""Conversational agent — Gemini with function-calling, six CivicAI tools.

Endpoint signature ``POST /agent/chat`` is preserved from Plan 2 so the frontend
ChatPanel does not need to change. Internally we use the ``google-genai`` SDK
directly (same library as embeddings + voice) instead of pydantic-ai.
"""
from __future__ import annotations

import logging
import secrets
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from google import genai
from google.genai import types as genai_types

from app.citizens import fetch_citizen_by_id
from app.config import get_settings
from app.documents import fetch_document
from app.models import AgentChatRequest, AgentChatResponse, ChatToolCall
from app.procedures import get_registry
from app.prompts import build_system_prompt
from app.security import current_citizen_id
from app.tools import REGISTRY, ToolContext

log = logging.getLogger("civicai.agent")

router = APIRouter(prefix="/agent", tags=["agent"])


# ---- Function declarations sent to Gemini ----

_FUNCTION_DECLS: list[dict[str, Any]] = [
    {
        "name": "lookup_procedure",
        "description": "Caută procedura potrivită din registrul primăriei pe baza unei descrieri în limba română.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Descrierea în limbaj natural."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "set_field",
        "description": "Setează o valoare pe un câmp al documentului activ.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "Numele câmpului din schema procedurii."},
                "value": {"type": "STRING", "description": "Valoarea nouă a câmpului."},
            },
            "required": ["name", "value"],
        },
    },
    {
        "name": "generate_pdf",
        "description": "Generează PDF-ul documentului activ.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "deliver",
        "description": "Finalizează documentul. delivery ∈ {save, send, print}.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "delivery": {
                    "type": "STRING",
                    "enum": ["save", "send", "print"],
                },
            },
            "required": ["delivery"],
        },
    },
    {
        "name": "find_redirect",
        "description": "Decide dacă cererea este în afara primăriei (ANAF/CNAS/DRPCIV).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING"},
                "target": {"type": "STRING", "description": "Optional: ANAF/CNAS/DRPCIV."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "set_reminder",
        "description": "Creează un memento (folosit doar la cerere explicită).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "kind": {
                    "type": "STRING",
                    "enum": ["in_scope_procedure", "external_redirect"],
                },
                "title": {"type": "STRING"},
                "procedure_id": {"type": "STRING"},
                "redirect_target": {"type": "STRING"},
                "deadline_days": {"type": "INTEGER"},
            },
            "required": ["kind", "title"],
        },
    },
]


# ---- Conversation store (in-memory; hackathon scope) ----

_conversations: dict[str, list[genai_types.Content]] = {}


# ---- Gemini client (lazy singleton) ----

_genai_client: genai.Client | None = None


def _client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(api_key=get_settings().gemini_api_key)
    return _genai_client


def _build_context_preamble(citizen_id: UUID, document_id: UUID | None) -> str:
    citizen = fetch_citizen_by_id(citizen_id)
    lines = [
        f"Profil cetățean: {citizen['prenume']} {citizen['nume']}",
        f"Atribute: {citizen.get('attributes') or {}}",
    ]
    if document_id:
        try:
            doc = fetch_document(document_id)
        except HTTPException:
            return "\n".join(lines)
        if str(doc["citizen_id"]) != str(citizen_id):
            return "\n".join(lines)
        reg = get_registry()
        proc = reg.get(doc["procedure_id"])
        title = proc.title if proc else doc["procedure_id"]
        lines.append(f"Document activ: {title} (status={doc['status']})")
        lines.append(f"Câmpuri completate: {doc.get('fields') or {}}")
        if proc:
            filled = doc.get("fields") or {}
            missing = [f.name for f in proc.fields if f.required and not filled.get(f.name)]
            lines.append(f"Câmpuri obligatorii rămase: {missing}")
    return "\n".join(lines)


async def _execute_tool(
    name: str, args: dict[str, Any], ctx: ToolContext
) -> dict[str, Any]:
    tool = REGISTRY.get(name)
    if tool is None:
        return {"error": f"unknown tool {name}"}
    try:
        result = await tool(ctx, **(args or {}))
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:  # noqa: BLE001
        log.exception("Tool %s failed", name)
        return {"error": f"{type(e).__name__}: {e}"}
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if isinstance(result, dict):
        return result
    return {"value": result}


@router.post("/chat", response_model=AgentChatResponse)
async def chat(
    req: AgentChatRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> AgentChatResponse:
    settings = get_settings()
    conv_id = req.conversation_id or f"conv_{secrets.token_urlsafe(8)}"
    history = _conversations.setdefault(conv_id, [])

    prefs = req.preferences
    system_prompt = build_system_prompt(
        variant="conversational",
        simple_language=bool(prefs and prefs.simple_language),
        voice_only=bool(prefs and prefs.voice_only),
    )
    preamble = _build_context_preamble(citizen_id, req.document_id)
    user_text = f"{preamble}\n\n---\n\n{req.message}"

    contents: list[genai_types.Content] = list(history) + [
        genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=user_text)])
    ]

    config = genai_types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=[genai_types.Tool(function_declarations=_FUNCTION_DECLS)],
        temperature=0.7,
    )

    ctx = ToolContext(
        citizen_id=str(citizen_id),
        document_id=str(req.document_id) if req.document_id else None,
    )

    tool_calls_emitted: list[ChatToolCall] = []
    client = _client()

    # Tool-loop: at most 5 iterations to keep response time bounded.
    for _ in range(5):
        try:
            resp = client.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=config,
            )
        except Exception as e:  # noqa: BLE001
            log.exception("Gemini generate_content failed")
            raise HTTPException(status_code=502, detail=f"Agent error: {e}")

        candidate = resp.candidates[0] if resp.candidates else None
        if candidate is None or candidate.content is None:
            break
        parts = candidate.content.parts or []

        function_calls = [p.function_call for p in parts if getattr(p, "function_call", None)]
        if function_calls:
            # Add the model turn (with tool calls) to history
            contents.append(candidate.content)
            tool_response_parts: list[genai_types.Part] = []
            for fc in function_calls:
                args = dict(fc.args) if fc.args else {}
                tool_calls_emitted.append(ChatToolCall(name=fc.name, arguments=args))
                result = await _execute_tool(fc.name, args, ctx)
                tool_response_parts.append(
                    genai_types.Part.from_function_response(
                        name=fc.name, response={"output": result}
                    )
                )
            contents.append(
                genai_types.Content(role="user", parts=tool_response_parts)
            )
            continue

        # No tool calls — extract text and finish
        text_parts = [p.text for p in parts if getattr(p, "text", None)]
        message = "".join(text_parts).strip() or "Cum te pot ajuta?"
        contents.append(candidate.content)
        _conversations[conv_id] = contents
        return AgentChatResponse(
            conversation_id=conv_id,
            message=message,
            tool_calls=tool_calls_emitted,
        )

    # Fell through the iteration cap
    _conversations[conv_id] = contents
    return AgentChatResponse(
        conversation_id=conv_id,
        message="Am procesat câteva acțiuni. Vrei să continuăm?",
        tool_calls=tool_calls_emitted,
    )
