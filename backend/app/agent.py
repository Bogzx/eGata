"""Conversational agent — Gemini with function-calling, seven CivicAI tools.

Two endpoints:
- ``POST /agent/chat`` — non-streaming, returns the final agent message in one
  JSON response. Kept for backwards-compat / programmatic callers / tests.
- ``POST /agent/chat/stream`` — Server-Sent Events. Emits one ``delta`` frame
  per accumulated text chunk, one ``tool_call`` + ``tool_result`` pair per
  function-call the model issues, and a final ``done`` frame. The frontend
  uses this to surface tokens live.

Both endpoints share ``_run_agent_turn`` for the tool-loop logic, so behaviour
cannot drift between them.
"""
from __future__ import annotations

import json
import logging
import secrets
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types as genai_types

from app.citizens import fetch_citizen_by_id
from app.config import get_settings
from app.documents import fetch_document
from app.models import AgentChatRequest, AgentChatResponse, ChatToolCall
from app.procedures import get_registry
from app.prompts import build_system_prompt
from app.security import current_citizen_id
from app.text_hygiene import strip_thinking
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
    {
        "name": "propose_widget",
        "description": (
            "Cere cetățeanului un răspuns structurat via un widget interactiv în chat: "
            "type='choice' cu options pentru selecție rapidă, type='confirm' pentru da/nu, "
            "type='date' pentru o dată calendaristică. Pentru choice, target_field este "
            "câmpul din formular pe care valoarea aleasă îl va completa."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "type": {"type": "STRING", "enum": ["choice", "confirm", "date"]},
                "question": {"type": "STRING"},
                "options": {"type": "ARRAY", "items": {"type": "STRING"}},
                "target_field": {"type": "STRING"},
            },
            "required": ["type", "question"],
        },
    },
]


# ---- Conversation store (in-memory; hackathon scope) ----
#
# Process-local dict — fine for single-worker dev/demo. Multi-worker deploys
# would need Redis or sticky sessions. Bounded by ``_MAX_CONVERSATIONS`` to
# avoid unbounded growth during a long demo run.

_MAX_CONVERSATIONS = 256
_conversations: dict[str, list[genai_types.Content]] = {}


def _remember(conv_id: str, contents: list[genai_types.Content]) -> None:
    if len(_conversations) > _MAX_CONVERSATIONS and conv_id not in _conversations:
        # Evict the oldest entry (insertion order).
        oldest = next(iter(_conversations))
        _conversations.pop(oldest, None)
    _conversations[conv_id] = contents


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
        "\n\n---\nProfil cetățean activ:",
        f"Nume: {citizen['prenume']} {citizen['nume']}",
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
        lines.append(f"\nDocument activ: {title} (status={doc['status']})")
        lines.append(f"Câmpuri completate: {doc.get('fields') or {}}")
        if proc:
            filled = doc.get("fields") or {}
            missing = [f.name for f in proc.fields if f.required and not filled.get(f.name)]
            lines.append(f"Câmpuri obligatorii rămase: {missing}")
            if proc.acte_necesare:
                lines.append("Acte fizice necesare:")
                for a in proc.acte_necesare:
                    flag = "" if a.obligatoriu else " (opțional)"
                    note = f" — {a.observatie}" if a.observatie else ""
                    lines.append(f"  • {a.denumire}{flag}{note}")
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


def _build_config(
    citizen_id: UUID,
    document_id: UUID | None,
    *,
    simple_language: bool,
    voice_only: bool,
) -> genai_types.GenerateContentConfig:
    system_prompt = build_system_prompt(
        variant="conversational",
        simple_language=simple_language,
        voice_only=voice_only,
    )
    preamble = _build_context_preamble(citizen_id, document_id)
    full_prompt = system_prompt + preamble
    return genai_types.GenerateContentConfig(
        system_instruction=full_prompt,
        tools=[genai_types.Tool(function_declarations=_FUNCTION_DECLS)],
        temperature=0.7,
    )


# ---- Non-streaming endpoint (legacy / fallback) ----


@router.post("/chat", response_model=AgentChatResponse)
async def chat(
    req: AgentChatRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> AgentChatResponse:
    settings = get_settings()
    conv_id = req.conversation_id or f"conv_{secrets.token_urlsafe(8)}"
    history = _conversations.setdefault(conv_id, [])

    prefs = req.preferences
    config = _build_config(
        citizen_id,
        req.document_id,
        simple_language=bool(prefs and prefs.simple_language),
        voice_only=bool(prefs and prefs.voice_only),
    )

    contents: list[genai_types.Content] = list(history) + [
        genai_types.Content(
            role="user", parts=[genai_types.Part.from_text(text=req.message)]
        )
    ]

    ctx = ToolContext(
        citizen_id=str(citizen_id),
        document_id=str(req.document_id) if req.document_id else None,
    )

    tool_calls_emitted: list[ChatToolCall] = []
    client = _client()

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

        text_parts = [p.text for p in parts if getattr(p, "text", None)]
        raw = "".join(text_parts).strip()
        cleaned = strip_thinking(raw) or "Cum te pot ajuta?"
        if cleaned != raw and raw:
            contents.append(
                genai_types.Content(
                    role="model", parts=[genai_types.Part.from_text(text=cleaned)]
                )
            )
        else:
            contents.append(candidate.content)
        _remember(conv_id, contents)
        return AgentChatResponse(
            conversation_id=conv_id,
            message=cleaned,
            tool_calls=tool_calls_emitted,
        )

    _remember(conv_id, contents)
    return AgentChatResponse(
        conversation_id=conv_id,
        message="Am procesat câteva acțiuni. Vrei să continuăm?",
        tool_calls=tool_calls_emitted,
    )


# ---- Streaming endpoint (SSE) ----


def _sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


async def _stream_agent_turn(
    req: AgentChatRequest,
    citizen_id: UUID,
) -> AsyncIterator[bytes]:
    settings = get_settings()
    conv_id = req.conversation_id or f"conv_{secrets.token_urlsafe(8)}"
    history = _conversations.setdefault(conv_id, [])

    prefs = req.preferences
    config = _build_config(
        citizen_id,
        req.document_id,
        simple_language=bool(prefs and prefs.simple_language),
        voice_only=bool(prefs and prefs.voice_only),
    )

    contents: list[genai_types.Content] = list(history) + [
        genai_types.Content(
            role="user", parts=[genai_types.Part.from_text(text=req.message)]
        )
    ]

    ctx = ToolContext(
        citizen_id=str(citizen_id),
        document_id=str(req.document_id) if req.document_id else None,
    )

    tool_calls_emitted: list[ChatToolCall] = []
    client = _client()

    # Tell the client which conversation this is up front so it can persist it
    # even if the connection drops mid-stream.
    yield _sse("conversation", {"conversation_id": conv_id})

    for _ in range(5):
        accumulated_text = ""
        accumulated_function_calls: list[Any] = []
        accumulated_parts: list[genai_types.Part] = []

        try:
            stream = await client.aio.models.generate_content_stream(
                model=settings.gemini_model,
                contents=contents,
                config=config,
            )
        except Exception as e:  # noqa: BLE001
            log.exception("Gemini generate_content_stream failed")
            yield _sse("error", {"detail": f"Agent error: {e}"})
            return

        async for chunk in stream:
            candidate = chunk.candidates[0] if chunk.candidates else None
            if candidate is None or candidate.content is None:
                continue
            for p in candidate.content.parts or []:
                text = getattr(p, "text", None)
                fc = getattr(p, "function_call", None)
                if text:
                    accumulated_text += text
                    accumulated_parts.append(p)
                    yield _sse("delta", {"text": accumulated_text})
                if fc:
                    accumulated_function_calls.append(fc)
                    accumulated_parts.append(p)

        if accumulated_parts:
            contents.append(
                genai_types.Content(role="model", parts=accumulated_parts)
            )

        if accumulated_function_calls:
            tool_response_parts: list[genai_types.Part] = []
            for fc in accumulated_function_calls:
                args = dict(fc.args) if fc.args else {}
                tool_calls_emitted.append(ChatToolCall(name=fc.name, arguments=args))
                yield _sse("tool_call", {"name": fc.name, "arguments": args})
                result = await _execute_tool(fc.name, args, ctx)
                yield _sse("tool_result", {"name": fc.name, "output": result})
                tool_response_parts.append(
                    genai_types.Part.from_function_response(
                        name=fc.name, response={"output": result}
                    )
                )
            contents.append(
                genai_types.Content(role="user", parts=tool_response_parts)
            )
            continue

        cleaned = strip_thinking(accumulated_text) or "Cum te pot ajuta?"
        if cleaned != accumulated_text and accumulated_text and contents:
            # Replace the just-appended model turn with the cleaned text so
            # the agent doesn't see its own thinking-leak on the next turn.
            contents[-1] = genai_types.Content(
                role="model", parts=[genai_types.Part.from_text(text=cleaned)]
            )
            yield _sse("delta", {"text": cleaned})
        _remember(conv_id, contents)
        yield _sse(
            "done",
            {
                "conversation_id": conv_id,
                "message": cleaned,
                "tool_calls": [tc.model_dump() for tc in tool_calls_emitted],
            },
        )
        return

    _remember(conv_id, contents)
    yield _sse(
        "done",
        {
            "conversation_id": conv_id,
            "message": "Am procesat câteva acțiuni. Vrei să continuăm?",
            "tool_calls": [tc.model_dump() for tc in tool_calls_emitted],
        },
    )


@router.post("/chat/stream")
async def chat_stream(
    req: AgentChatRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> StreamingResponse:
    """SSE stream — see module docstring for the frame schema."""
    return StreamingResponse(
        _stream_agent_turn(req, citizen_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
