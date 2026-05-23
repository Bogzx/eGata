---
type: meta
title: "Index"
updated: 2026-05-23
---

# Master Catalog

The whole wiki, organized by section. Each entry is a single line so this file stays scannable.

## Overview & meta

- [[overview]] — executive summary of the whole backend
- [[hot]] — recent-context cache (~500 words)
- [[log]] — append-only operation log
- [[Conventions]] — frontmatter, wikilink, naming rules
- [[Glossary]] — CivicAI-specific vocabulary

## Modules (backend/app/*)

- [[main]] — FastAPI app entrypoint, router registration, CORS, lifespan
- [[config]] — Pydantic Settings, all environment variables
- [[db]] — Supabase client + psycopg connection factory
- [[models]] — Pydantic v2 request/response shapes (single source of truth)
- [[security]] — JWT mint / decode / `current_citizen_id` dependency
- [[auth]] — `/auth/login-roeid`, `/auth/login-mrz`, `/auth/otp`
- [[citizens]] — `/citizens/me`, attribute patching
- [[procedures]] — Procedure registry + `/procedures/lookup` (RAG)
- [[scenarios]] — Multi-procedure scenario plan builder
- [[institutions]] — External institution catalog loader
- [[documents]] — Document CRUD + PDF generation + delivery
- [[ledger]] — Hash-chain ledger writer + verifier
- [[pdf]] — LaTeX template render + `pdflatex` subprocess
- [[storage]] — Supabase Storage uploader (PDFs bucket)
- [[embeddings]] — Gemini text-embedding-004 + pgvector search
- [[procedure_state]] — `applies_if`-aware field state evaluator
- [[applies_if]] — Tiny boolean expression parser/evaluator
- [[sessions]] — Session aggregate + state machine + per-conv lock
- [[session_engine]] — Shared Gemini text loop (`step`)
- [[agent]] — `/agent/chat` SSE + `/agent/widget-result`
- [[agent_voice]] — `/agent/voice/ws` Browser↔Gemini Live bridge
- [[twilio_bridge]] — `/voice/twilio` phone-call media-stream bridge
- [[agent_tools]] — State-gated tool registry + dispatcher
- [[reminders]] — Reminders writer + endpoints + worker plumbing
- [[worker]] — APScheduler proactive reminders worker
- [[demo]] — `/demo/reset` for live-demo reset
- [[health]] — `/health` and `/healthz` checks
- [[prompts]] — Romanian system prompts (text + phone + a11y directives)
- [[text_hygiene]] — Chain-of-thought stripping helper

## Agent tools (backend/app/agent_tools/*)

- [[lookup_procedure]] — RAG search over procedures + scenarios
- [[list_procedures]] — Catalog browse (categories or drill-in)
- [[start_procedure]] — Open a new document, jump to FILLING
- [[set_field]] — Validate + write a document field, may flip FILLING ↔ REVIEWING
- [[propose_widget]] — Emit structured UI widget (choice/confirm/date)
- [[complete_document]] — Render PDF, deliver, transition to DELIVERED
- [[find_redirect]] — Detect out-of-primărie scope, transition to REDIRECTED

## Flows

- [[Flow Login + OTP]] — login-roeid/mrz → otp → JWT
- [[Flow Procedure Lookup]] — query → embed → pgvector → matches
- [[Flow Agent Text Turn]] — POST `/agent/chat/stream` SSE frames lifecycle
- [[Flow Voice Browser Turn]] — `/agent/voice/ws` Gemini Live bridge
- [[Flow Phone Call Twilio]] — Twilio webhook → media stream → Gemini Live
- [[Flow Document Lifecycle]] — create → patch → complete → ledger
- [[Flow Reminders Worker]] — delivered ledger row → applies_if → reminder rows
- [[Flow Session State Machine]] — EXPLORING → ... → DELIVERED transitions
- [[Flow Widget Round-Trip]] — propose_widget → widget_submission → set_field

## Contracts

- [[HTTP API Surface]] — every REST route grouped by router
- [[SSE Frame Schema]] — `/agent/chat/stream` event vocabulary
- [[Voice WS Frame Schema]] — `/agent/voice/ws` browser ↔ backend frames
- [[Twilio WS Frame Schema]] — Twilio Media Streams envelopes
- [[Frontend Event Schema]] — `frontend_event` payload types
- [[Session Snapshot Schema]] — what `session_snapshot` carries
- [[Procedure JSON Schema]] — `backend/procedures/*.json` shape
- [[Scenario JSON Schema]] — `backend/scenarios/*.json` shape

## Decisions

- [[ADR State Machine Over Free-Form Agent]] — why a 6-state session
- [[ADR Hash-Chain Ledger]] — tamper-evident audit log instead of plain table
- [[ADR Shared Engine For Text + Voice]] — one `step()` two transports
- [[ADR State-Gated Tool Surface]] — refuse calls instead of trusting LLM
- [[ADR Single Live Session Text + Voice]] — share Gemini Live WS even text-only
- [[ADR Applies If As First-Class Field]] — conditional required vs hard branch
- [[ADR Mock OTP Flag]] — `MOCK_OTP=1` for hackathon ergonomics
- [[ADR Service Role Key + RLS Bypass]] — backend uses service role; RLS is defense in depth
- [[ADR Phone Tool Allowlist]] — RAG-only on phone; no document writes

## Dependencies

- [[Dep Supabase]] — Postgres (EU), pgvector, Storage, RLS
- [[Dep Gemini]] — text generation (2.5 Flash) + embeddings + Live voice
- [[Dep Twilio]] — Verify OTP + Programmable Voice (Media Streams)
- [[Dep FastAPI Stack]] — FastAPI + uvicorn + Pydantic v2 + JOSE
- [[Dep APScheduler]] — Background reminders worker
- [[Dep pdflatex]] — System binary, must be on PATH in container
- [[Dep Sentry]] — Optional error reporting
- [[Database Schema]] — every Postgres table, view, function

## Components

- [[Pydantic Models]] — shared request/response shapes
- [[JWT Auth]] — HS256 bearer, 24h default, `sub=citizen_id`
- [[Session Aggregate]] — in-memory + Postgres-persisted conversation state
- [[Tool Registry]] — import side-effect populated REGISTRY
- [[PendingWidget]] — server-side widget tracking
- [[FrontendEvent]] — structured UI directives
- [[State Recap]] — voice-only `_state` injection trick

## Frontend integration

- [[Frontend Map]] — Next.js layout + how it talks to the backend
- [[Frontend Lib]] — `lib/api.ts`, `lib/sseChat.ts`, `lib/voiceWs.ts`, `lib/sessionStore.ts`
- [[Frontend Auth Flow]] — login → OTP → localStorage JWT
- [[Frontend Voice Bridge]] — `useVoiceAgentBridge` ↔ `/agent/voice/ws`
- [[Frontend Session Mirror]] — `SessionSnapshot` → Zustand store → React pages
- [[Frontend MSW Mocks]] — `NEXT_PUBLIC_USE_MOCKS=1` mode for solo FE work

## Deployment

- [[Deployment Railway]] — railway.json + Dockerfile + healthcheck
- [[Dockerfile]] — Python 3.12 slim + texlive
- [[Migrations]] — `apply_migrations.py` + the 8 SQL files
- [[Demo Reset Flow]] — `POST /demo/reset` for live demos
