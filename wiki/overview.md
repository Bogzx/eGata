---
type: meta
title: "CivicAI Backend Overview"
updated: 2026-05-23
status: living
---

# CivicAI Backend — Executive Summary

## What it is

A FastAPI backend for a Romanian city-hall (primărie) AI assistant. A citizen says what they need in natural Romanian; the agent finds the right procedure, fills the document with them (asking only for what it doesn't already know about them), renders a LaTeX PDF, delivers it via save / send-to-primărie / print, and writes every step to a tamper-evident hash-chain ledger.

Built for Cluj Hackathon 2026 (Bosch Cluj, May 22-24). Romanian-language only.

## The four-line architecture

```
Citizen ──► Frontend (Next.js 15)
                │ HTTPS (REST + SSE)  /  WSS (voice)
                ▼
            FastAPI (this repo)
                │
                ├── Supabase Postgres (with pgvector + RLS)  — state, ledger, embeddings
                ├── Supabase Storage                          — generated PDFs
                ├── Gemini 2.5 Flash + Live + embedding-001   — agent reasoning, voice, RAG
                ├── Twilio Verify + Programmable Voice        — OTP and phone calls
                └── APScheduler (in-process)                  — proactive reminders worker
```

See [[Frontend Map]] for the FE side and [[Deployment Railway]] for production.

## The eight routers

`backend/app/main.py` registers ten routers; the ones with real surface area are:

| Router | Module | Owns |
|---|---|---|
| `/auth` | [[auth]] | Login (ROeID-mock + MRZ) + OTP exchange for a JWT |
| `/citizens` | [[citizens]] | `GET /me`, `PATCH /me/attributes` |
| `/procedures` | [[procedures]] | List, get, `POST /lookup` (RAG) |
| `/scenarios` | [[scenarios]] | List + resolve multi-procedure plans |
| `/documents` | [[documents]] | CRUD + `generate-pdf` + `deliver` + `ledger` |
| `/agent` | [[agent]], [[agent_voice]] | Text SSE chat, voice WS bridge, widget result |
| `/reminders` | [[reminders]] | List, patch status, start, dismiss |
| `/voice/twilio` | [[twilio_bridge]] | Twilio Media Streams WS + TwiML webhook |
| `/demo` | [[demo]] | `POST /reset` for live demos |
| `/health`, `/healthz` | [[health]] | Probes |

Every route — see [[HTTP API Surface]].

## The central nervous system

All conversational behavior funnels through one object: **the [[Session Aggregate]]**. Persisted in `sessions` (Postgres jsonb), it owns:

- `state` — one of 6 values, see [[Flow Session State Machine]]
- `active_document_id` — the document currently being filled (if any)
- `pending_widgets` — UI prompts the agent has emitted but the user hasn't answered
- `history` — Gemini `Content` list, JSON-serialized
- `scenario_id`, `step_index` — multi-procedure plan pointer

A single `step()` function (`backend/app/session_engine.py`) drives one turn end-to-end. It yields **typed Events** (`delta`, `tool_call`, `tool_result`, `frontend_event`, `session_snapshot`, `done`, `error`). The text transport ([[agent]]) wraps them in SSE frames; the voice transport ([[agent_voice]]) wraps them in JSON over WS. Both paths use the **same engine, same registry, same state machine** — the only voice-specific code is audio plumbing and a `_state` recap embedded in every tool response (because Gemini Live freezes `system_instruction` at connect time — see [[State Recap]]).

## The seven tools

The agent has exactly **7 callable tools**, gated by session state. See [[agent_tools]]. The dispatcher (`agent_tools/__init__.py:dispatch`) refuses out-of-state calls and returns an error — this is a hard guarantee, not a soft hint to the LLM.

```
                    EXPLORING  CONFIRMING_MATCH  FILLING  REVIEWING  DELIVERED  REDIRECTED
lookup_procedure       ●            ●                                   ●           ●
list_procedures        ●            ●                                   ●           ●
start_procedure                     ●                                   ●
propose_widget                      ●               ●
set_field                                           ●         ●
complete_document                                             ●
find_redirect          ●            ●                                   ●           ●
```

## The ledger (the demo's "wow" moment)

Every meaningful event (doc_created, completed_draft, pdf_generated, delivered, redirected, reminder_created) is appended to a `ledger` table. The append goes through a Postgres function `append_ledger()` ([[ledger]]) that **enforces `prev_hash` integrity at the DB level** — out-of-band INSERTs that bypass the chain fail. The frontend can replay the timeline ([[Frontend Map]] → `AuditTimeline`) and a `verified` boolean shows whether the chain is intact.

## How the frontend connects

Five wire-level contracts:

1. **REST + JSON** — every CRUD route, plus `POST /agent/chat` (non-streaming, kept for tests). See [[HTTP API Surface]].
2. **SSE** — `POST /agent/chat/stream`. Frames: `conversation`, `delta`, `tool_call`, `tool_result`, `frontend_event`, `session_snapshot`, `done`, `error`. See [[SSE Frame Schema]].
3. **WebSocket (voice)** — `WSS /agent/voice/ws`. Browser sends PCM16/16k mono + JSON control frames; backend forwards to Gemini Live, returns PCM16/24k audio + transcripts + tool calls. See [[Voice WS Frame Schema]].
4. **WebSocket (phone)** — `WSS /voice/twilio`. μ-law 8k frames in Twilio JSON envelopes. See [[Twilio WS Frame Schema]].
5. **JWT bearer** — every authenticated REST call carries `Authorization: Bearer <token>`. The voice WS receives the token inside the first `start` frame because browsers can't set the WS upgrade headers ([[ADR Single Live Session Text + Voice]]).

The frontend mirrors the backend's `SessionSnapshot` into a Zustand store keyed by `seq` (monotonic) so reorderings during reconnects can be dropped. See [[Frontend Session Mirror]].

## What's not in this wiki

- Frontend internals beyond the lib/ glue. The frontend has its own design system, a11y modes (`voice_only`, `simple_language`, `large_text`), and right-pane state machine — out of scope here.
- The procedure JSON catalog and LaTeX templates — touched at the contract level only ([[Procedure JSON Schema]], [[pdf]]).
- The hackathon-specific demo script.
