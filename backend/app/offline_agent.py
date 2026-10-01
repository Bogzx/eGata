"""Deterministic offline agent — the chat without an LLM.

Active when AGENT_BACKEND resolves to `offline` (the default when no
AZURE_OPENAI_API_KEY is set), so `docker compose up` gives a stranger a chat
that walks the whole flow: find the procedure, confirm it, fill the missing
fields, review, deliver, with the same ledger rows and PDF as the LLM path.

It is a script, not a model, and says so in its first reply. What it shares
with the LLM agent is everything below the conversation: every state change
goes through `app.agent_tools.dispatch`, so the state machine, the
state-gating, field validation, the review gate before delivery and the
ledger writes are the ones the LLM path uses. It emits the same Event
vocabulary as `session_engine.step` and keeps `session.history` in the same
OpenAI message shape, so a conversation can move between backends.

Understands: a free-text request (keyword search over the procedure catalogue
via lookup_procedure, then find_redirect for ANAF / CNAS / DRPCIV), "da" /
"nu", a procedure title, typed answers to the question it asked, an option
typed instead of clicked, "<câmp>: <valoare>" corrections during review, a
delivery choice, "ce proceduri sunt?" and "renunț" to start over.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

from app.agent_tools import ToolContext, ToolResult, dispatch
from app.agent_tools.lookup_procedure import MATCH_THRESHOLD
from app.documents import fetch_document
from app.procedure_state import evaluate_field_states, find_field
from app.procedures import get_registry
from app.session_engine import Event
from app.sessions import (
    Session,
    SessionState,
    clear_review_confirmed,
    is_review_confirmed,
    mark_review_confirmed,
    transition,
)

log = logging.getLogger("offline_agent")

OFFLINE_NOTICE = (
    "(Mod offline: sunt un asistent scriptat, fără model AI — caut după cuvinte "
    "cheie și completez formularul pas cu pas.)"
)

# The exact prompts the LLM path uses (session_engine / propose_widget), so the
# frontend treats both backends' widgets the same.
REVIEW_QUESTION = "Verifică datele din dreapta. Sunt complete și corecte?"
DELIVERY_QUESTION = "Cum vrei să primești cererea completată?"
# "send" texts the citizen their reference (Twilio). Nothing here files the
# form with the primărie, so no option may say it does.
DELIVERY_OPTIONS = ["Salvare PDF", "Confirmare pe SMS", "Tipărire", "Descarcă PDF"]
_DELIVERY_BY_KEYWORD = [
    ("descarc", "download"),
    ("salv", "save"),
    ("trimit", "send"),
    ("sms", "send"),
    ("tipar", "print"),
    ("print", "print"),
]

# Two lookup scores closer than this are offered as a choice instead of
# guessing (e.g. "certificat de urbanism" matches both cerere- and prelungire-).
_AMBIGUITY_MARGIN = 0.05
_OTHER = "Altceva"

_YES = {"da", "ok", "okay", "sigur", "confirm", "confirmat", "corect", "exact", "yes",
        "incepe", "incepem", "hai", "bine", "desigur", "gata", "continua", "continuam"}
_NO = {"nu", "no", "gresit", "incorect", "altceva", "nu e", "nu este"}
_GREETINGS = {"buna", "ziua", "salut", "salutare", "hello", "hi", "hey", "neata",
              "seara", "dimineata", "servus", "noroc", "alo", "multumesc", "mersi"}
_RESET = ("renunt", "anuleaza", "anulez", "de la capat", "alta cerere", "o alta cerere", "reset")
_CATALOG = ("ce proceduri", "ce cereri", "ce poti face", "ce stii", "lista", "catalog",
            "ce servicii", "ajutor", "help")


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9: ]+", " ", text)).strip()


def _words(text: str) -> set[str]:
    return set(_fold(text).replace(":", " ").split())


def _is_yes(text: str) -> bool:
    words = _words(text)
    return bool(words) and len(words) <= 4 and bool(words & _YES) and not (words & {"nu"})


def _is_no(text: str) -> bool:
    folded = _fold(text)
    return folded in _NO or folded.startswith("nu ")


def _is_greeting(text: str) -> bool:
    words = _words(text)
    return not words or words <= _GREETINGS


def _delivery_for(text: str) -> str | None:
    folded = _fold(text)
    for keyword, delivery in _DELIVERY_BY_KEYWORD:
        if keyword in folded:
            return delivery
    return None


class _Turn:
    """One user turn: runs tools through the dispatcher and collects events."""

    def __init__(self, session: Session, ctx: ToolContext, user_message: str) -> None:
        self.session = session
        self.ctx = ctx
        self.messages: list[dict[str, Any]] = list(session.history) + [
            {"role": "user", "content": user_message}
        ]
        self.events: list[Event] = []
        self.text_parts: list[str] = []
        self.tool_calls: list[dict[str, Any]] = []

    async def call(self, name: str, /, **args: Any) -> ToolResult:
        call_id = f"offline_{uuid4().hex[:10]}"
        self.messages.append(
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
                    }
                ],
            }
        )
        self.tool_calls.append({"name": name, "arguments": args})
        self.events.append(Event("tool_call", {"name": name, "arguments": args}))
        result = await dispatch(self.session, name, args, self.ctx)
        self.events.append(
            Event("tool_result", {"name": name, "output": result.output, "error": result.error})
        )
        if result.frontend_event:
            self.events.append(Event("frontend_event", result.frontend_event))
        self.events.append(Event("session_snapshot", self.session.snapshot()))
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": json.dumps(
                    {"output": result.output, "error": result.error}, ensure_ascii=False
                ),
            }
        )
        return result

    def say(self, text: str) -> None:
        self.text_parts.append(text)

    @property
    def text(self) -> str:
        return "\n\n".join(p for p in self.text_parts if p)


# ---- conversation memory (read back from the OpenAI-shaped history) ----


def _last_lookup(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Output of the most recent lookup_procedure call, if any."""
    for msg in reversed(history):
        if msg.get("role") == "tool" and msg.get("name") == "lookup_procedure":
            try:
                return json.loads(msg.get("content") or "{}").get("output") or None
            except json.JSONDecodeError:
                return None
    return None


def _has_spoken(history: list[dict[str, Any]]) -> bool:
    return any(m.get("role") == "assistant" and m.get("content") for m in history)


# ---- document helpers ----


def _active_doc(session: Session) -> tuple[dict[str, Any], Any] | None:
    if not session.active_document_id:
        return None
    try:
        doc = fetch_document(UUID(session.active_document_id))
    except Exception:  # noqa: BLE001
        return None
    proc = get_registry().get(doc["procedure_id"])
    if proc is None:
        return None
    return doc, proc


def _missing_fields(session: Session, ctx: ToolContext) -> tuple[Any, list[Any]]:
    loaded = _active_doc(session)
    if loaded is None:
        return None, []
    doc, proc = loaded
    states = evaluate_field_states(proc, doc.get("fields") or {}, ctx.citizen_attributes)
    return proc, [find_field(proc, name) for name in states.missing]


def _pending_for(session: Session, field_name: str) -> bool:
    return any(w.target_field == field_name for w in session.pending_widgets)


def _drop_pending(session: Session, *, field: str | None = None, question: str | None = None) -> None:
    session.pending_widgets = [
        w
        for w in session.pending_widgets
        if not ((field and w.target_field == field) or (question and w.question == question))
    ]


# ---- steps of the script ----


async def _greet(turn: _Turn) -> None:
    turn.say(
        "Bună ziua! Spune-mi pe scurt ce ai nevoie de la primărie — de exemplu "
        "„vreau să-mi schimb domiciliul”, „am pierdut buletinul”, „vreau să tai un "
        "copac din curte” sau „ce proceduri sunt?”."
    )


async def _catalog(turn: _Turn) -> None:
    result = await turn.call("list_procedures")
    lines = []
    for cat in result.output.get("categories", []):
        titles = ", ".join(p["title"] for p in cat.get("procedures", []))
        lines.append(f"• {cat['label']}: {titles}")
    turn.say("Pot să te ajut cu aceste cereri:\n" + "\n".join(lines))
    turn.say("Scrie-mi pe care o vrei, cu cuvintele tale.")


async def _search(turn: _Turn, query: str) -> None:
    session = turn.session
    if session.state in {SessionState.DELIVERED, SessionState.REDIRECTED}:
        # A new request after a finished one starts from scratch; the state
        # machine does not allow redirected -> confirming_match directly.
        transition(session, SessionState.EXPLORING)
    result = await turn.call("lookup_procedure", query=query)
    matches = result.output.get("matches") or []
    plan = result.output.get("scenario_plan")
    found = bool(plan) or bool(matches and matches[0]["score"] >= MATCH_THRESHOLD)

    if not found:
        if session.state == SessionState.CONFIRMING_MATCH:
            transition(session, SessionState.EXPLORING)
        redirect = await turn.call("find_redirect", query=query)
        target = redirect.output.get("target")
        if target:
            turn.say(
                f"{redirect.output.get('explanation', '')} "
                f"Detalii: {redirect.output.get('url', '')}, tel. {redirect.output.get('phone', '')}."
            )
        else:
            turn.say(
                "Nu am găsit o procedură a primăriei potrivită. Încearcă să descrii "
                "altfel (de exemplu „certificat fiscal”, „parcare”, „construiesc o "
                "casă”) sau scrie „ce proceduri sunt?”."
            )
        return

    if plan:
        steps = plan.get("in_scope_steps") or []
        external = plan.get("external_steps") or []
        lines = [f"Pentru „{plan['title']}” pașii sunt:"]
        lines += [f"{s['ordine']}. {s['procedure_title']} (la primărie)" for s in steps]
        lines += [f"• {e['institutie_nume']} — {e.get('scope') or ''}".rstrip(" —") for e in external]
        turn.say("\n".join(lines))
        if steps:
            await turn.call(
                "propose_widget",
                type="choice",
                question="Cu ce cerere de la primărie începem?",
                options=[s["procedure_title"] for s in steps] + [_OTHER],
            )
        return

    top = matches[0]
    close = [m for m in matches if top["score"] - m["score"] <= _AMBIGUITY_MARGIN]
    if len(close) > 1:
        turn.say("Am găsit mai multe cereri care se potrivesc:")
        await turn.call(
            "propose_widget",
            type="choice",
            question="Pe care o vrei?",
            options=[m["title"] for m in close] + [_OTHER],
        )
        return

    acte = [a.get("denumire") for a in top.get("acte_necesare") or [] if a.get("denumire")]
    text = f"Cred că ai nevoie de: {top['title']}. {top.get('description') or ''}".strip()
    if acte:
        text += "\nActe necesare: " + "; ".join(acte[:6]) + ("; …" if len(acte) > 6 else "")
    turn.say(text)
    await turn.call(
        "propose_widget", type="confirm", question=f"Completăm cererea „{top['title']}”?"
    )


async def _start(turn: _Turn, procedure_id: str) -> None:
    result = await turn.call("start_procedure", procedure_id=procedure_id)
    if result.error:
        turn.say(f"Nu am putut deschide cererea: {result.error}")
        return
    prefilled = result.output.get("prefilled_from_profile") or []
    turn.say(
        f"Am deschis „{result.output.get('title')}”."
        + (f" Am completat din profilul tău {len(prefilled)} câmpuri." if prefilled else "")
    )
    await _ask_next(turn)


async def _ask_next(turn: _Turn) -> None:
    """Ask for whatever is still missing, or move on to review."""
    session = turn.session
    if session.state == SessionState.REVIEWING:
        await _propose_review(turn)
        return
    proc, missing = _missing_fields(session, turn.ctx)
    if proc is None:
        return
    asked_text = False
    for fld in missing:
        if fld.options:
            if not _pending_for(session, fld.name):
                await turn.call(
                    "propose_widget",
                    type="choice",
                    question=fld.label,
                    options=list(fld.options),
                    target_field=fld.name,
                )
        elif not asked_text:
            hint = f" ({fld.observatie})" if fld.observatie else ""
            turn.say(f"{fld.label}?{hint}")
            asked_text = True
    if not asked_text and missing:
        turn.say("Alege una dintre variantele de mai jos.")


async def _fill(turn: _Turn, message: str) -> None:
    session = turn.session
    proc, missing = _missing_fields(session, turn.ctx)
    if proc is None:
        turn.say("Nu mai găsesc documentul deschis. Spune-mi din nou ce ai nevoie.")
        transition(session, SessionState.EXPLORING)
        return

    # An option typed instead of clicked ("proprietar") answers that widget.
    target = None
    folded = _fold(message)
    for fld in missing:
        if fld.options and any(_fold(o) == folded for o in fld.options):
            target = fld
            break
    if target is None:
        target = next((f for f in missing if not f.options), None)
    if target is None:
        # Only choices are left and the text matched none of them. Typing
        # hid them in the browser, so ask them again.
        await _ask_next(turn)
        return

    result = await turn.call("set_field", name=target.name, value=message.strip())
    if result.error:
        turn.say(f"Nu am putut completa „{target.label}”: {result.error}")
        turn.say(f"{target.label}?")
        return
    _drop_pending(session, field=target.name)
    await _ask_next(turn)


async def _propose_review(turn: _Turn) -> None:
    session = turn.session
    if any(w.question == REVIEW_QUESTION for w in session.pending_widgets):
        turn.say("Verifică datele din dreapta și confirmă.")
        return
    turn.say("Am toate datele necesare.")
    await turn.call("propose_widget", type="confirm", question=REVIEW_QUESTION)


async def _review(turn: _Turn, message: str) -> None:
    session = turn.session
    delivery = _delivery_for(message)

    if not is_review_confirmed(session):
        if _is_yes(message):
            # Typed instead of clicked: same effect as the widget's Da.
            _drop_pending(session, question=REVIEW_QUESTION)
            mark_review_confirmed(session)
        elif ":" in message and await _correct(turn, message):
            return
        elif _is_no(message):
            _drop_pending(session, question=REVIEW_QUESTION)
            turn.say(
                "Poți corecta un câmp cu creionul din dreapta, sau scrie-mi "
                "„<câmp>: <valoare nouă>” (de exemplu „Adresă nouă: Str. Lungă 3”)."
            )
            return
        else:
            await _propose_review(turn)
            return

    if delivery is None:
        if not any(w.question == DELIVERY_QUESTION for w in session.pending_widgets):
            turn.say("Datele sunt confirmate. Cum vrei să primești cererea completată?")
            await turn.call(
                "propose_widget", type="choice", question=DELIVERY_QUESTION, options=DELIVERY_OPTIONS
            )
        else:
            turn.say("Alege cum vrei să primești cererea.")
        return

    _drop_pending(session, question=DELIVERY_QUESTION)
    result = await turn.call("complete_document", delivery=delivery)
    if result.error or result.output.get("refused"):
        turn.say(f"Nu am putut finaliza: {result.error or result.output.get('reason')}")
        return
    ref = result.output.get("ref_number")
    turn.say(
        f"Gata! Cererea e completată, cu referința {ref}. PDF-ul e disponibil în "
        "dreapta și în „Documentele mele”; fiecare pas e înregistrat în jurnalul de audit."
    )
    if delivery == "send":
        turn.say(
            "Ți-am trimis referința pe SMS."
            if result.output.get("sms_sent")
            else "SMS-ul nu e configurat pe acest server, așa că nu a plecat niciun mesaj."
        )
    turn.say("eGata nu depune cererea pentru tine: semnează PDF-ul și depune-l la ghișeul primăriei.")
    turn.say("Te mai pot ajuta cu altceva?")


async def _correct(turn: _Turn, message: str) -> bool:
    """`<câmp>: <valoare>` during review. True if it named a real field."""
    loaded = _active_doc(turn.session)
    if loaded is None:
        return False
    _, proc = loaded
    label, _, value = message.partition(":")
    wanted = _fold(label)
    fld = next(
        (f for f in proc.fields if _fold(f.label) == wanted or _fold(f.name) == wanted), None
    )
    if fld is None or not value.strip():
        return False
    result = await turn.call("set_field", name=fld.name, value=value.strip())
    if result.error:
        turn.say(f"Nu am putut modifica „{fld.label}”: {result.error}")
        return True
    turn.say(f"Am modificat „{fld.label}”.")
    clear_review_confirmed(turn.session)
    await _ask_next(turn)
    return True


async def _confirming(turn: _Turn, message: str) -> None:
    session = turn.session
    lookup = _last_lookup(turn.messages) or {}
    matches = lookup.get("matches") or []
    plan = lookup.get("scenario_plan") or {}
    candidates = [(m["procedure_id"], m["title"]) for m in matches]
    candidates += [(s["procedure_id"], s["procedure_title"]) for s in plan.get("in_scope_steps") or []]
    session.pending_widgets = []

    folded = _fold(message)
    chosen = next((pid for pid, title in candidates if _fold(title) == folded), None)
    if chosen is None and _is_yes(message) and matches:
        chosen = matches[0]["procedure_id"]
    if chosen:
        await _start(turn, chosen)
        return
    if _is_no(message) or folded == _fold(_OTHER):
        transition(session, SessionState.EXPLORING)
        turn.say("Bine. Descrie-mi mai exact ce ai nevoie.")
        return
    await _search(turn, message)


async def _reset(turn: _Turn) -> None:
    session = turn.session
    if session.state != SessionState.EXPLORING:
        transition(session, SessionState.EXPLORING)
    session.pending_widgets = []
    session.active_document_id = None
    turn.events.append(Event("session_snapshot", session.snapshot()))
    turn.say("Am renunțat la cererea în lucru (ciorna rămâne în „Documentele mele”). Cu ce te ajut?")


# ---- entry point ----


async def step(
    session: Session,
    user_message: str,
    *,
    simple_language: bool = False,  # noqa: ARG001 — the script is already plain
    voice_only: bool = False,  # noqa: ARG001
    citizen_attrs: dict[str, Any] | None = None,
) -> AsyncIterator[Event]:
    """Offline counterpart of `session_engine.step` (same events, same history)."""
    ctx = ToolContext(citizen_id=session.citizen_id, citizen_attributes=citizen_attrs or {})
    first_turn = not _has_spoken(session.history)
    turn = _Turn(session, ctx, user_message)
    session.history = list(turn.messages)
    yield Event("session_snapshot", session.snapshot())

    message = (user_message or "").strip()
    folded = _fold(message)
    state = session.state
    log.info("offline: conv=%s state=%s msg_len=%d", session.id, state.value, len(message))

    try:
        wants_reset = any(folded == r or folded.startswith(r + " ") for r in _RESET)
        if folded and wants_reset and state != SessionState.EXPLORING:
            await _reset(turn)
        elif state == SessionState.FILLING:
            await _fill(turn, message)
        elif state == SessionState.REVIEWING:
            await _review(turn, message)
        elif state == SessionState.CONFIRMING_MATCH:
            await _confirming(turn, message)
        elif _is_greeting(message):
            await _greet(turn)
        elif any(k in folded for k in _CATALOG):
            await _catalog(turn)
        else:
            await _search(turn, message)
    except Exception as e:  # noqa: BLE001
        log.exception("offline agent failed conv=%s", session.id)
        yield Event("error", {"code": "offline_agent_error", "type": type(e).__name__, "detail": str(e)})
        session.history = list(turn.messages)
        return

    text = turn.text or "Cum te pot ajuta?"
    if first_turn:
        text = f"{OFFLINE_NOTICE}\n\n{text}"

    for ev in turn.events:
        yield ev
    yield Event("delta", {"text": text})
    turn.messages.append({"role": "assistant", "content": text})
    session.history = list(turn.messages)
    yield Event("session_snapshot", session.snapshot())
    yield Event("done", {"message": text, "tool_calls": turn.tool_calls})
