---
type: meta
title: "Hot Cache"
updated: 2026-05-23
---

# Recent Context

## Last Updated

2026-05-23. Built the full backend architecture wiki from a clean repo. Mode B (Repository).

## Key Recent Facts

- **CivicAI** is a Romanian primărie (city hall) assistant built for Cluj Hackathon 2026. Backend is FastAPI + Supabase Postgres + Gemini + Twilio. Frontend is Next.js 15.
- The backend's central nervous system is a **6-state Session machine** (EXPLORING → CONFIRMING_MATCH → FILLING → REVIEWING → DELIVERED, plus REDIRECTED). Tools are state-gated: an out-of-state call returns an error result instead of trusting the LLM.
- A single **shared agent engine** (`app/session_engine.py:step`) drives both text (SSE) and voice (Gemini Live WS) — the transports are dumb pipes.
- Every state mutation writes to the **hash-chain ledger** (`app/ledger.py`) via a Postgres function that enforces `prev_hash` integrity at the DB level.
- The Frontend mirrors a backend-pushed `SessionSnapshot` into a Zustand store. Frontend events (`document_opened`, `widget_proposed`, `field_updated`, `document_delivered`, `redirect`, `lookup_returned`) drive UI changes.

## Recent Changes

- Created: 28 module pages, 7 agent-tool pages, 9 flow pages, 8 contract pages, 9 ADRs, 8 dependency pages, 6 frontend pages, 3 deployment pages.
- Updated: [[index]], [[overview]], [[hot]], [[log]] — initial population.

## Active Threads

- Whole vault is fresh — nothing flagged for follow-up yet.
- Suggested first queries: "what tools does the agent have?", "explain the ledger", "what happens after `complete_document`?", "how does the voice WS authenticate?", "what does the frontend persist locally?"

## Hot pointers

- Single source of truth for HTTP routes: [[HTTP API Surface]].
- Single source of truth for tool catalog: [[agent_tools]].
- Backend→frontend wire vocabulary: [[Frontend Event Schema]] + [[Session Snapshot Schema]].
