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
import time
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
    """Rehydrate persisted session.history into Gemini Content objects.

    Validation errors are logged WITH the underlying exception (the previous
    version dropped the error silently, which made history-corruption bugs
    invisible — a dropped model turn between two user turns silently broke
    role alternation and Gemini rejected the whole conversation).
    """
    out: list[genai_types.Content] = []
    for entry in history:
        try:
            out.append(genai_types.Content.model_validate(entry))
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "history rehydrate failed; entry dropped: %s — entry=%r",
                exc,
                entry,
            )
    return out


def _content_to_dict(c: genai_types.Content) -> dict[str, Any]:
    return c.model_dump(mode="json", exclude_none=True)


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
    client = _client()

    if citizen_attrs is None:
        try:
            from uuid import UUID

            citizen = fetch_citizen_by_id(UUID(session.citizen_id))
            citizen_attrs = citizen.get("attributes") or {}
        except Exception:
            citizen_attrs = {}

    # Strip trailing orphan turns from a previously-failed step before
    # sending to Gemini. Without this, a turn that died after persisting the
    # user message (see early-save below) leaves history ending in role=user;
    # the next call would create user→user, which Gemini rejects — the
    # chat would appear broken from message 2 onward. The leftover_text is
    # the orphan user's typed message, merged into the current turn so the
    # user's prior attempt isn't silently lost.
    sanitized_history, leftover_text = _sanitize_history_for_gemini(session.history)
    if len(sanitized_history) != len(session.history):
        log.warning(
            "session_engine: trimmed %d orphan turn(s) from prior failed step "
            "(leftover_user_text=%s)",
            len(session.history) - len(sanitized_history),
            "yes" if leftover_text else "no",
        )

    effective_message = (
        f"{leftover_text}\n\n{user_message}" if leftover_text else user_message
    )

    contents = _history_to_contents(sanitized_history) + [
        genai_types.Content(
            role="user", parts=[genai_types.Part.from_text(text=effective_message)]
        )
    ]

    # Persist the user turn into session.history NOW so a mid-stream crash
    # (Gemini timeout, client disconnect, tool exception) doesn't lose it.
    # The transport's finally-block update_session() will commit this even
    # if the iterator never reaches a terminal branch. Note: we write the
    # SANITIZED prefix here, not the raw session.history — that's how the
    # orphan from a previous failed step gets cleaned up on disk.
    session.history = [_content_to_dict(c) for c in contents]

    log.info(
        "step: in conv=%s citizen=%s state=%s doc=%s msg_len=%d history_turns=%d model=%s",
        session.id,
        session.citizen_id,
        session.state.value,
        session.active_document_id,
        len(user_message or ""),
        len(session.history),
        settings.gemini_model,
    )
    turn_started = time.perf_counter()

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

        log.info(
            "gemini: call conv=%s iter=%d history_len=%d contents_len=%d tools=%s",
            session.id,
            _,
            len(session.history),
            len(contents),
            [t["name"] for t in _function_declarations_for_state(session.state)],
        )
        iter_started = time.perf_counter()
        try:
            stream = await client.aio.models.generate_content_stream(
                model=settings.gemini_model,
                contents=contents,
                config=config,
            )
        except Exception as e:  # noqa: BLE001
            log.exception(
                "gemini: generate_content_stream failed conv=%s iter=%d",
                session.id,
                _,
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

        chunk_count = 0
        part_count = 0
        last_finish_reason = None
        last_safety = None
        async for chunk in stream:
            chunk_count += 1
            candidate = chunk.candidates[0] if chunk.candidates else None
            if candidate is None:
                log.warning("gemini: chunk has no candidates conv=%s", session.id)
                continue
            last_finish_reason = getattr(candidate, "finish_reason", None)
            last_safety = getattr(candidate, "safety_ratings", None)
            content = candidate.content
            if content is None:
                log.warning(
                    "gemini: candidate has no content conv=%s finish=%r",
                    session.id,
                    last_finish_reason,
                )
                continue
            parts = content.parts or []
            if not parts:
                log.warning(
                    "gemini: content has no parts conv=%s role=%r finish=%r safety=%r",
                    session.id,
                    getattr(content, "role", None),
                    last_finish_reason,
                    last_safety,
                )
            for p in parts:
                part_count += 1
                text = getattr(p, "text", None)
                fc = getattr(p, "function_call", None)
                thought_flag = getattr(p, "thought", None)
                # Per-part log is per-token-stream — quite chatty. Keep at
                # DEBUG so prod stays readable, set LOG_LEVEL=DEBUG to inspect.
                log.debug(
                    "gemini: part conv=%s text=%r fc=%r thought=%r",
                    session.id,
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
        log.info(
            "gemini: iter done conv=%s iter=%d duration_ms=%.0f chunks=%d parts=%d text_len=%d fc=%d finish=%r",
            session.id,
            _,
            (time.perf_counter() - iter_started) * 1000,
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

    # Loop exhausted — preserve whatever the model emitted last instead of
    # silently swallowing it with a canned fallback (P1-#23).
    log.warning(
        "step: tool-loop exhausted conv=%s after %d iters — model kept calling tools",
        session.id,
        _MAX_TOOL_LOOP_ITERATIONS,
    )
    session.history = [_content_to_dict(c) for c in contents]
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
