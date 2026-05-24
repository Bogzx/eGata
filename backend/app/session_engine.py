"""Shared agent engine — one Session.step() for both text and voice.

Yields a stream of typed Events that the transport layer formats for its
wire (SSE frames for text, JSON over WS for voice). All state lives in
the `Session`; the transports are dumb pipes.

Event vocabulary (the `kind` field):

    delta             — agent text grew; `data.text` is the FULL accumulated
                        text since the start of this turn.
    tool_call         — model emitted a function call. `data = {name, arguments}`.
    tool_result       — tool dispatched. `data = {name, output, error}`.
    frontend_event    — tool surfaced a UI directive (document_opened,
                        widget_proposed, field_updated, document_delivered,
                        redirect). `data` is the event payload.
    session_snapshot  — push the current Session.snapshot() — frontend mirrors
                        this directly into its store.
    done              — turn complete. `data = {message, tool_calls}`.
    error             — fatal. `data = {detail}`.

Caller persists `session` after the iterator finishes (the engine mutates
it in place but does not call update_session — keeping persistence at the
transport edge avoids double-write storms when both transports happen to
fire on the same conversation).
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from app.agent_tools import REGISTRY as TOOLS_REGISTRY, ToolContext, dispatch, permitted_tools
from app.azure_clients import (
    get_openai_client,
    history_to_openai_messages,
    tools_for_chat_completions,
)
from app.citizens import fetch_citizen_by_id
from app.config import get_settings
from app.documents import fetch_document
from app.procedures import get_registry
from app.prompts import build_system_prompt
from app.sessions import Session, SessionState
from app.text_hygiene import strip_thinking

log = logging.getLogger("session_engine")

_MAX_TOOL_LOOP_ITERATIONS = 15


@dataclass
class Event:
    kind: str
    data: dict[str, Any]


# ---- system prompt + context preamble ----


def _doc_state_lines(
    session: Session, citizen_attrs: dict[str, Any]
) -> list[str]:
    """Render the current document state as bullet lines for the preamble.

    Uses applies_if-aware field-state computation so the model sees the
    *currently* missing required set, not the static schema.
    """
    if not session.active_document_id:
        return []
    try:
        from uuid import UUID

        doc = fetch_document(UUID(session.active_document_id))
    except Exception:
        return []
    reg = get_registry()
    proc = reg.get(doc["procedure_id"])
    title = proc.title if proc else doc["procedure_id"]
    fields = doc.get("fields") or {}
    lines = [
        f"\nDocument activ: {title} (status={doc['status']})",
        f"Câmpuri completate: {fields}",
    ]
    if proc and proc.llm_hint:
        lines.append(f"Indicații flow pentru procedură: {proc.llm_hint}")
    if proc:
        from app.procedure_state import evaluate_field_states, _is_nonempty

        states = evaluate_field_states(proc, fields, citizen_attrs)
        lines.append(f"Câmpuri obligatorii rămase: {states.missing}")
        # Explicit list of set_field calls the LLM should issue right now —
        # forces auto-fill of optional fields (email, ap_domiciliu, ...) that
        # the LLM would otherwise skip because they're not in `missing`.
        autofillable: list[tuple[str, Any]] = []
        # Merged context = profile attrs + already-completed doc fields. Lets
        # `default_from` resolve to a field the LLM just auto-filled (e.g.
        # nr_placuta defaulting to nr_domiciliu, where nr_domiciliu itself
        # was just filled from profile).
        merged_ctx: dict[str, Any] = {**citizen_attrs, **fields}
        for fld in proc.fields:
            current = fields.get(fld.name)
            if _is_nonempty(current):
                continue
            # 1) direct match: profile has a value with this exact name
            attr_value = citizen_attrs.get(fld.name)
            if attr_value not in (None, ""):
                autofillable.append((fld.name, attr_value))
                continue
            # 2) default_from: this field copies another field's value
            if fld.default_from:
                src_value = merged_ctx.get(fld.default_from)
                if src_value not in (None, ""):
                    autofillable.append((fld.name, src_value))
        if autofillable:
            lines.append(
                "APELEAZĂ ACUM aceste set_field (auto-fill obligatoriu, "
                "chiar dacă field-ul e required:false):"
            )
            for name, value in autofillable:
                lines.append(f"  • set_field(name='{name}', value='{value}')")
        if proc.acte_necesare:
            lines.append("Acte fizice necesare:")
            for a in proc.acte_necesare:
                flag = "" if a.obligatoriu else " (opțional)"
                note = f" — {a.observatie}" if a.observatie else ""
                lines.append(f"  • {a.denumire}{flag}{note}")
    return lines


def build_system_instruction(
    session: Session,
    citizen_attrs: dict[str, Any],
    *,
    simple_language: bool,
    voice_only: bool,
) -> str:
    """System prompt + per-turn state preamble + permitted-tools brief."""
    base = build_system_prompt(
        variant="conversational",
        simple_language=simple_language,
        voice_only=voice_only,
    )
    citizen_lines = [
        "\n\n---\nProfil cetățean activ:",
        f"Atribute: {citizen_attrs}",
    ]
    doc_lines = _doc_state_lines(session, citizen_attrs)
    state_lines = [
        f"\nStare sesiune: {session.state.value}",
        f"Tool-uri permise: {permitted_tools(session.state)}",
    ]
    if session.state == SessionState.REVIEWING:
        state_lines.append(
            "\n*** ÎN STAREA REVIEWING ***\n"
            "PAS 1 — CONFIRMARE (obligatoriu primul):\n"
            "  propose_widget(type='confirm', "
            "question='Verifică datele din dreapta. Sunt complete și corecte?')\n"
            "  AȘTEAPTĂ Da/Nu. NU sări la PAS 2 până nu confirmă.\n"
            "  • Dacă Nu sau cere modificare: set_field cu noua valoare, apoi repetă PAS 1.\n"
            "PAS 2 — LIVRARE (doar după Da la PAS 1):\n"
            "  propose_widget(type='choice', options=["
            "'Salvare PDF', 'Trimitere la primărie', 'Tipărire', "
            "'Descarcă PDF'], "
            "question='Cum vrei să trimitem cererea?') — O SINGURĂ DATĂ\n"
            "  AȘTEAPTĂ alegerea, apoi complete_document cu delivery-ul ales "
            "('Descarcă PDF' → delivery='download').\n"
            "NU apela propose_widget cu aceeași întrebare de două ori la rând."
        )
    return base + "\n".join(citizen_lines + doc_lines + state_lines)


def _tools_for_state(state: SessionState) -> list[dict[str, Any]]:
    """OpenAI-format tool definitions filtered to state-permitted tools."""
    names = permitted_tools(state)
    declarations = [TOOLS_REGISTRY[n].function_declaration() for n in names]
    return tools_for_chat_completions(declarations)


def _sanitize_history_for_gemini(
    history: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    """Trim trailing orphan turns so Gemini gets a valid alternating history.

    Why: `step()` persists the user turn into `session.history` BEFORE the
    model has responded (so a mid-stream crash doesn't lose what the user
    typed — see `test_history_persists_user_turn_before_model_responds`).
    If the model call then fails, the persisted history ends with role=user.
    On the NEXT turn we'd append another role=user — Gemini rejects
    consecutive same-role turns and the chat appears stuck from turn 2 on.

    The fix: when constructing Gemini `contents`, peel off trailing orphans:

      - role=user with function_response parts → dropped silently
        (agent-internal tool result the model never consumed; not user data)
      - role=model with function_call parts → dropped silently
        (agent-internal — dispatch was supposed to add a function_response
        next but the turn died first)
      - role=user with text parts → dropped from history BUT the text is
        returned to the caller so it can be prepended to the new user
        message (no data loss; the user's prior attempt rides along)
      - role=model with only text → clean end-of-history, leave it

    `session.history` itself is NOT mutated here — callers do that via the
    normal `session.history = [_content_to_dict(c) for c in contents]`
    write at end-of-step. That naturally drops the orphan on the next
    successful commit.

    Returns: (sanitized_history, leftover_user_text).
    """
    sanitized = list(history)
    orphan_text_chronological_reversed: list[str] = []

    while sanitized:
        last = sanitized[-1]
        role = last.get("role")
        parts = last.get("parts") or []

        if role == "user":
            has_function_response = any(
                isinstance(p, dict) and p.get("function_response") for p in parts
            )
            if has_function_response:
                sanitized.pop()
                continue
            for p in parts:
                if isinstance(p, dict):
                    text = p.get("text")
                    if isinstance(text, str) and text.strip():
                        orphan_text_chronological_reversed.append(text)
            sanitized.pop()
            continue

        if role == "model":
            has_function_call = any(
                isinstance(p, dict) and p.get("function_call") for p in parts
            )
            if has_function_call:
                sanitized.pop()
                continue
            break

        # Unknown role: bail conservatively.
        break

    leftover = (
        "\n".join(reversed(orphan_text_chronological_reversed))
        if orphan_text_chronological_reversed
        else None
    )
    return sanitized, leftover


# ---- the engine ----


async def step(
    session: Session,
    user_message: str,
    *,
    simple_language: bool = False,
    voice_only: bool = False,
    citizen_attrs: dict[str, Any] | None = None,
) -> AsyncIterator[Event]:
    """Drive one user→agent turn end-to-end. Mutates `session` in place."""
    settings = get_settings()
    client = get_openai_client()

    if citizen_attrs is None:
        try:
            from uuid import UUID

            citizen = fetch_citizen_by_id(UUID(session.citizen_id))
            citizen_attrs = citizen.get("attributes") or {}
        except Exception:
            citizen_attrs = {}

    prior_messages = history_to_openai_messages(session.history)
    messages: list[dict[str, Any]] = list(prior_messages) + [
        {"role": "user", "content": user_message}
    ]

    # Persist the user turn NOW so a mid-stream crash doesn't lose it.
    # The transport's finally-block update_session() will commit this even
    # if the iterator never reaches a terminal branch.
    session.history = list(messages)

    log.info(
        "step: in conv=%s citizen=%s state=%s doc=%s msg_len=%d history_turns=%d deployment=%s",
        session.id,
        session.citizen_id,
        session.state.value,
        session.active_document_id,
        len(user_message or ""),
        len(session.history),
        settings.azure_openai_chat_deployment,
    )
    turn_started = time.perf_counter()

    tool_calls_emitted: list[dict[str, Any]] = []
    ctx = ToolContext(citizen_id=session.citizen_id, citizen_attributes=citizen_attrs)

    yield Event("session_snapshot", session.snapshot())

    transcript_so_far = ""

    for iter_idx in range(_MAX_TOOL_LOOP_ITERATIONS):
        system_instruction = build_system_instruction(
            session,
            citizen_attrs,
            simple_language=simple_language,
            voice_only=voice_only,
        )
        tools = _tools_for_state(session.state)
        # Prepend a fresh system message each iteration so the model sees
        # current state. The previous iteration's system message stays in
        # `messages` only when persisted; per-call we splice one in.
        call_messages = [{"role": "system", "content": system_instruction}] + messages

        log.info(
            "azure_openai: call conv=%s iter=%d msgs=%d tools=%s",
            session.id,
            iter_idx,
            len(call_messages),
            [t["function"]["name"] for t in tools],
        )
        iter_started = time.perf_counter()
        try:
            # Don't set temperature — gpt-5 reasoning models reject anything
            # other than the default (1). Let the model decide.
            stream = await client.chat.completions.create(
                model=settings.azure_openai_chat_deployment,
                messages=call_messages,
                tools=tools or None,
                tool_choice="auto" if tools else None,
                stream=True,
            )
        except Exception as e:  # noqa: BLE001
            log.exception(
                "azure_openai: chat.completions.create failed conv=%s iter=%d",
                session.id,
                iter_idx,
            )
            # Structured error so the transport can pass `code` + `type`
            # to the frontend; see agent.py:_stream_turn for the wire
            # format.
            yield Event(
                "error",
                {
                    "code": "gemini_stream_failed",
                    "type": type(e).__name__,
                    "detail": f"Agent error: {e}",
                },
            )
            return

        accumulated_text = ""
        tool_calls_acc: dict[int, dict[str, Any]] = {}
        chunk_count = 0
        finish_reason: str | None = None
        async for chunk in stream:
            chunk_count += 1
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta
            if delta is None:
                continue
            if getattr(delta, "content", None):
                accumulated_text += delta.content
                yield Event("delta", {"text": transcript_so_far + accumulated_text})
            if getattr(delta, "tool_calls", None):
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    slot = tool_calls_acc.setdefault(
                        idx,
                        {"id": "", "name": "", "arguments": ""},
                    )
                    if tc_delta.id:
                        slot["id"] = tc_delta.id
                    fn = getattr(tc_delta, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            slot["name"] = fn.name
                        if getattr(fn, "arguments", None):
                            slot["arguments"] += fn.arguments
            if choice.finish_reason:
                finish_reason = choice.finish_reason

        log.info(
            "azure_openai: iter done conv=%s iter=%d duration_ms=%.0f chunks=%d text_len=%d tool_calls=%d finish=%r",
            session.id,
            iter_idx,
            (time.perf_counter() - iter_started) * 1000,
            chunk_count,
            len(accumulated_text),
            len(tool_calls_acc),
            finish_reason,
        )

        iter_cleaned = strip_thinking(accumulated_text)

        assistant_msg: dict[str, Any] = {"role": "assistant"}
        if iter_cleaned:
            assistant_msg["content"] = iter_cleaned
        if tool_calls_acc:
            assistant_msg["tool_calls"] = [
                {
                    "id": slot["id"] or f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": slot["name"],
                        "arguments": slot["arguments"] or "{}",
                    },
                }
                for i, slot in sorted(tool_calls_acc.items())
            ]
        if "content" not in assistant_msg and "tool_calls" not in assistant_msg:
            # Truly empty turn — give it an empty string so downstream
            # serializers don't blow up.
            assistant_msg["content"] = ""
        messages.append(assistant_msg)

        if tool_calls_acc:
            if iter_cleaned:
                transcript_so_far += iter_cleaned
                yield Event("delta", {"text": transcript_so_far})

            for i, slot in sorted(tool_calls_acc.items()):
                name = slot["name"]
                try:
                    args = json.loads(slot["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                    log.warning(
                        "step: tool args not valid json conv=%s name=%s raw=%r",
                        session.id,
                        name,
                        slot["arguments"][:200],
                    )
                tool_calls_emitted.append({"name": name, "arguments": args})
                yield Event("tool_call", {"name": name, "arguments": args})

                result = await dispatch(session, name, args, ctx)
                yield Event(
                    "tool_result",
                    {
                        "name": name,
                        "output": result.output,
                        "error": result.error,
                    },
                )
                if result.frontend_event:
                    yield Event("frontend_event", result.frontend_event)
                yield Event("session_snapshot", session.snapshot())

                tool_response_payload = {
                    "output": result.output,
                    "error": result.error,
                }
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": slot["id"] or f"call_{i}",
                        "name": name,
                        "content": json.dumps(
                            tool_response_payload, ensure_ascii=False
                        ),
                    }
                )
            continue

        # Text-only turn: model is done.
        transcript_so_far += iter_cleaned
        final_text = transcript_so_far or "Cum te pot ajuta?"
        if final_text != (transcript_so_far + accumulated_text):
            yield Event("delta", {"text": final_text})

        session.history = list(messages)
        yield Event("session_snapshot", session.snapshot())
        log.info(
            "step: out conv=%s duration_ms=%.0f final_text_len=%d tool_calls=%d state=%s",
            session.id,
            (time.perf_counter() - turn_started) * 1000,
            len(final_text),
            len(tool_calls_emitted),
            session.state.value,
        )
        yield Event(
            "done",
            {"message": final_text, "tool_calls": tool_calls_emitted},
        )
        return

    # Loop exhausted.
    log.warning(
        "step: tool-loop exhausted conv=%s after %d iters — model kept calling tools",
        session.id,
        _MAX_TOOL_LOOP_ITERATIONS,
    )
    session.history = list(messages)
    yield Event("session_snapshot", session.snapshot())
    fallback = "Am procesat câteva acțiuni. Vrei să continuăm?"
    final_text = transcript_so_far or fallback
    log.info(
        "step: out (exhausted) conv=%s duration_ms=%.0f final_text_len=%d tool_calls=%d state=%s",
        session.id,
        (time.perf_counter() - turn_started) * 1000,
        len(final_text),
        len(tool_calls_emitted),
        session.state.value,
    )
    yield Event(
        "done",
        {"message": final_text, "tool_calls": tool_calls_emitted},
    )
