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

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types as genai_types

from app.agent_tools import REGISTRY as TOOLS_REGISTRY, ToolContext, dispatch, permitted_tools
from app.citizens import fetch_citizen_by_id
from app.config import get_settings
from app.documents import fetch_document
from app.procedures import get_registry
from app.prompts import build_system_prompt
from app.sessions import Session, SessionState
from app.text_hygiene import strip_thinking

log = logging.getLogger("session_engine")

_MAX_TOOL_LOOP_ITERATIONS = 5

_genai_client: genai.Client | None = None


def _client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(api_key=get_settings().gemini_api_key)
    return _genai_client


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
    if proc:
        from app.procedure_state import evaluate_field_states

        states = evaluate_field_states(proc, fields, citizen_attrs)
        lines.append(f"Câmpuri obligatorii rămase: {states.missing}")
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
    return base + "\n".join(citizen_lines + doc_lines + state_lines)


def _function_declarations_for_state(state: SessionState) -> list[dict[str, Any]]:
    """The Gemini function_declarations list, filtered by state-permitted tools."""
    names = permitted_tools(state)
    return [TOOLS_REGISTRY[n].function_declaration() for n in names]


def _build_gemini_config(
    session: Session,
    citizen_attrs: dict[str, Any],
    *,
    simple_language: bool,
    voice_only: bool,
) -> genai_types.GenerateContentConfig:
    return genai_types.GenerateContentConfig(
        system_instruction=build_system_instruction(
            session,
            citizen_attrs,
            simple_language=simple_language,
            voice_only=voice_only,
        ),
        tools=[
            genai_types.Tool(
                function_declarations=_function_declarations_for_state(session.state)
            )
        ],
        temperature=0.7,
        # Gemini 2.5 Flash defaults to "auto" thinking, which on some turns
        # produces only thought=True parts that the SDK filters out, leaving
        # us with an empty response (finish_reason=STOP, parts=[]). Disable
        # it: we want direct tool calls + text, not chain-of-thought.
        thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
    )


def _history_to_contents(
    history: list[dict[str, Any]],
) -> list[genai_types.Content]:
    """Rehydrate persisted session.history into Gemini Content objects."""
    out: list[genai_types.Content] = []
    for entry in history:
        try:
            out.append(genai_types.Content.model_validate(entry))
        except Exception:
            log.warning("could not rehydrate history entry: %r", entry)
    return out


def _content_to_dict(c: genai_types.Content) -> dict[str, Any]:
    return c.model_dump(mode="json", exclude_none=True)


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
    client = _client()

    if citizen_attrs is None:
        try:
            from uuid import UUID

            citizen = fetch_citizen_by_id(UUID(session.citizen_id))
            citizen_attrs = citizen.get("attributes") or {}
        except Exception:
            citizen_attrs = {}

    contents = _history_to_contents(session.history) + [
        genai_types.Content(
            role="user", parts=[genai_types.Part.from_text(text=user_message)]
        )
    ]

    # Persist the user turn into session.history NOW so a mid-stream crash
    # (Gemini timeout, client disconnect, tool exception) doesn't lose it.
    # The transport's finally-block update_session() will commit this even
    # if the iterator never reaches a terminal branch.
    session.history = [_content_to_dict(c) for c in contents]

    tool_calls_emitted: list[dict[str, Any]] = []
    ctx = ToolContext(citizen_id=session.citizen_id, citizen_attributes=citizen_attrs)

    # Initial snapshot so the client sees state at turn start.
    yield Event("session_snapshot", session.snapshot())

    # Cumulative cleaned text across all tool-loop iterations. Each delta is
    # emitted as `transcript_so_far + this_iter_text` so the user's bubble
    # never loses iteration-1's preamble when iteration-2 starts after a
    # tool call.
    transcript_so_far = ""

    for _ in range(_MAX_TOOL_LOOP_ITERATIONS):
        accumulated_text = ""
        accumulated_function_calls: list[Any] = []
        accumulated_parts: list[genai_types.Part] = []

        config = _build_gemini_config(
            session,
            citizen_attrs,
            simple_language=simple_language,
            voice_only=voice_only,
        )

        try:
            stream = await client.aio.models.generate_content_stream(
                model=settings.gemini_model,
                contents=contents,
                config=config,
            )
        except Exception as e:  # noqa: BLE001
            log.exception("Gemini generate_content_stream failed")
            yield Event("error", {"detail": f"Agent error: {e}"})
            return

        chunk_count = 0
        part_count = 0
        last_finish_reason = None
        last_safety = None
        log.warning(
            "iter start: history_len=%d contents_len=%d",
            len(session.history),
            len(contents),
        )
        async for chunk in stream:
            chunk_count += 1
            candidate = chunk.candidates[0] if chunk.candidates else None
            if candidate is None:
                log.warning("chunk: no candidates")
                continue
            last_finish_reason = getattr(candidate, "finish_reason", None)
            last_safety = getattr(candidate, "safety_ratings", None)
            content = candidate.content
            if content is None:
                log.warning(
                    "chunk: candidate has no content (finish=%r)",
                    last_finish_reason,
                )
                continue
            parts = content.parts or []
            if not parts:
                log.warning(
                    "chunk: content has no parts (role=%r finish=%r safety=%r)",
                    getattr(content, "role", None),
                    last_finish_reason,
                    last_safety,
                )
            for p in parts:
                part_count += 1
                text = getattr(p, "text", None)
                fc = getattr(p, "function_call", None)
                thought_flag = getattr(p, "thought", None)
                log.warning(
                    "iter part: text=%r fc=%r thought=%r",
                    (text[:80] + "...") if text and len(text) > 80 else text,
                    fc.name if fc else None,
                    thought_flag,
                )
                if text:
                    accumulated_text += text
                    accumulated_parts.append(p)
                    yield Event(
                        "delta", {"text": transcript_so_far + accumulated_text}
                    )
                if fc:
                    accumulated_function_calls.append(fc)
                    accumulated_parts.append(p)
        log.warning(
            "iter done: chunks=%d parts=%d text_len=%d fc_count=%d finish=%r",
            chunk_count,
            part_count,
            len(accumulated_text),
            len(accumulated_function_calls),
            last_finish_reason,
        )

        # Clean this iteration's text for history hygiene + transcript.
        iter_cleaned = strip_thinking(accumulated_text)
        if (
            iter_cleaned != accumulated_text
            and accumulated_text
            and accumulated_parts
        ):
            # Replace text parts with the cleaned single-part version so
            # chain-of-thought never re-enters the Gemini history.
            cleaned_parts: list[genai_types.Part] = []
            text_replaced = False
            for p in accumulated_parts:
                if getattr(p, "text", None):
                    if not text_replaced and iter_cleaned:
                        cleaned_parts.append(
                            genai_types.Part.from_text(text=iter_cleaned)
                        )
                        text_replaced = True
                else:
                    cleaned_parts.append(p)
            accumulated_parts = cleaned_parts

        if accumulated_parts:
            contents.append(
                genai_types.Content(role="model", parts=accumulated_parts)
            )

        if accumulated_function_calls:
            # Carry the iter's user-visible text into the running transcript
            # before the tool runs (so the next iter's deltas stack on top).
            if iter_cleaned:
                transcript_so_far += iter_cleaned
                # Re-emit cumulative delta now that this iter's text is sealed
                # into the running transcript (handles case where streaming
                # leaked partial thinking that got scrubbed).
                yield Event("delta", {"text": transcript_so_far})

            tool_response_parts: list[genai_types.Part] = []
            for fc in accumulated_function_calls:
                args = dict(fc.args) if fc.args else {}
                tool_calls_emitted.append({"name": fc.name, "arguments": args})
                yield Event("tool_call", {"name": fc.name, "arguments": args})

                result = await dispatch(session, fc.name, args, ctx)
                yield Event(
                    "tool_result",
                    {
                        "name": fc.name,
                        "output": result.output,
                        "error": result.error,
                    },
                )
                if result.frontend_event:
                    yield Event("frontend_event", result.frontend_event)
                # Snapshot after every state mutation
                yield Event("session_snapshot", session.snapshot())

                tool_response_parts.append(
                    genai_types.Part.from_function_response(
                        name=fc.name,
                        response={
                            "output": result.output,
                            "error": result.error,
                        },
                    )
                )
            contents.append(genai_types.Content(role="user", parts=tool_response_parts))
            continue

        # Text-only turn: model is done.
        transcript_so_far += iter_cleaned
        final_text = transcript_so_far or "Cum te pot ajuta?"
        if final_text != (transcript_so_far + accumulated_text):
            # Cleaning changed something; correct the bubble's final text.
            yield Event("delta", {"text": final_text})

        # Persist history into the session (caller commits to DB)
        session.history = [_content_to_dict(c) for c in contents]
        yield Event("session_snapshot", session.snapshot())
        yield Event(
            "done",
            {"message": final_text, "tool_calls": tool_calls_emitted},
        )
        return

    # Loop exhausted — preserve whatever the model emitted last instead of
    # silently swallowing it with a canned fallback (P1-#23).
    session.history = [_content_to_dict(c) for c in contents]
    yield Event("session_snapshot", session.snapshot())
    fallback = "Am procesat câteva acțiuni. Vrei să continuăm?"
    final_text = transcript_so_far or fallback
    yield Event(
        "done",
        {"message": final_text, "tool_calls": tool_calls_emitted},
    )
