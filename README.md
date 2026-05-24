# eGata

**Conversational AI agent for Romanian primărie (city-hall) procedures.**
Built for the Cluj Hackathon 2026 (Bosch Cluj, May 22–24).

> Spune-i ce ai nevoie. Îți spune ce acte îți trebuie. Le și completează cu tine.

A citizen logs in once with their digital ID (or scans the MRZ on the back of the
CI), describes what they need in plain Romanian — by voice or text — and eGata
runs a stateful agent that picks the right procedure, asks only for what's
genuinely missing, generates a signed LaTeX PDF, delivers it (save / SMS /
print), writes every milestone to a tamper-evident hash-chain ledger, and
queues proactive reminders for the next legal steps.

---

## Table of contents

- [What's in the box](#whats-in-the-box)
- [Architecture at a glance](#architecture-at-a-glance)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [Feature surface](#feature-surface)
  - [Identity & authentication](#identity--authentication)
  - [Conversational agent](#conversational-agent)
  - [Voice — browser & phone](#voice--browser--phone)
  - [Procedures, scenarios, institutions](#procedures-scenarios-institutions)
  - [Documents, PDF & delivery](#documents-pdf--delivery)
  - [Hash-chain audit ledger](#hash-chain-audit-ledger)
  - [Proactive reminders worker](#proactive-reminders-worker)
  - [Accessibility & kiosk mode](#accessibility--kiosk-mode)
  - [Demo controls](#demo-controls)
- [HTTP / WebSocket API](#http--websocket-api)
- [Demo personas](#demo-personas)
- [Tech stack](#tech-stack)
- [Environment variables](#environment-variables)
- [Running tests](#running-tests)
- [Docker compose](#docker-compose)
- [Roadmap](#roadmap)
- [Docs](#docs)

---

## What's in the box

| Capability | Status |
|---|---|
| Romanian voice + text chat with a stateful agent (6-state machine) | shipped |
| 23 primărie procedures with field schemas, LaTeX templates, conditional logic | shipped |
| 5 multi-step real-life scenarios (e.g. *cumpărare apartament*) | shipped |
| 16 external institutions catalog (ANAF, CNAS, DRPCIV, SPCLEP-MAI, …) | shipped |
| RAG over procedures + scenarios via pgvector (768-d embeddings) | shipped |
| LaTeX → `pdflatex` → Supabase Storage PDF pipeline | shipped |
| Three delivery modes: **save**, **send** (Twilio SMS), **print** | shipped |
| Hash-chain ledger (sha256) — every event signed, chain-verified on read | shipped |
| Background worker — `next_steps[]` → reminders with `applies_if` filtering | shipped |
| Azure VoiceLive browser WebSocket bridge (PCM16, streaming partials) | shipped |
| Twilio Media Streams ↔ VoiceLive phone bridge (μ-law 8 kHz) | shipped |
| Accessibility: simple-language, voice-only, large-text, kiosk modes | shipped |
| MRZ scanner via tesseract.js (camera / upload / manual) | shipped |
| ROeID + OTP login (Twilio Verify, with `MOCK_OTP=1` for demo) | shipped |
| Demo reset endpoint, MSW mocks, three pre-seeded personas | shipped |

---

## Architecture at a glance

```
                ┌──────────────────────────────────────────────────┐
                │  Next.js 15 · React 19 · Zustand · Tailwind      │
   Browser ────►│  /  ·  /login  ·  /home  ·  /req/[id]  ·  /doc   │
   (voice+text) │  ChatSurface ─ RightPane ─ Widgets ─ AuditTimeline│
                └─────┬────────────────────────────────────────────┘
                      │ HTTPS (Bearer JWT)   WebSocket (PCM16)
                      ▼
                ┌──────────────────────────────────────────────────┐
                │  FastAPI · Pydantic v2 · APScheduler             │
                │  /auth /citizens /procedures /scenarios          │
                │  /documents /agent /reminders /demo  /health     │
                │                                                   │
                │  ┌─────────────┐  ┌─────────────┐  ┌────────────┐│
                │  │ session_    │  │ agent_tools │  │ pdf.py     ││
                │  │  engine     │──│ (state-     │  │ (LaTeX +   ││
                │  │ (text+voice)│  │  gated 7-   │  │  pdflatex) ││
                │  └──────┬──────┘  │  tool surf.)│  └────────────┘│
                │         │         └─────────────┘                 │
                │  ┌──────┴──────────────────────────────────────┐ │
                │  │ ledger.py (sha256 chain, verify on read)    │ │
                │  └─────────────────────────────────────────────┘ │
                └─────┬────────────────────────────────────────┬───┘
                      │                                        │
       Azure OpenAI   │   Azure VoiceLive   Twilio    Supabase │
       (gpt-5-mini +  │   (gpt-realtime,    (Verify, │ Postgres + RLS,
        embed-3-large)│    24 kHz PCM16)    Media)   │ pgvector, Storage
```

---

## Repository layout

```
backend/
  app/                 FastAPI routers, agent engine, tools, ledger, pdf, voice bridges
  migrations/          001…008 SQL migrations (schema, RLS, ledger fn, sessions, RAG)
  procedures/          23 JSON procedure definitions (fields, templates, next_steps)
  scenarios/           5 multi-step real-life scenarios (in-scope + external steps)
  institutions/        16 external-institution definitions (ANAF, ANEVAR, …)
  templates/           LaTeX templates (.tex) + base.tex + assets/
  scripts/             apply_migrations, index_rag, export_openapi, …
  tests/               17 pytest modules (state machine, ledger, RAG, end-to-end)

frontend/
  app/                 Next.js App Router (/, /login, /home, /req, /doc, /p, /r)
  components/          ChatSurface, RightPane, widgets/, MrzScanner, KioskShell, …
  lib/                 api.ts, sseChat, voiceWs, accessibilityStore, sessionStore, …
  mocks/               MSW handlers + fixtures (offline-capable frontend)
  e2e/                 Playwright specs

contracts/openapi.yaml OpenAPI 3.1 spec exported from FastAPI
docs/superpowers/      Design specs + four implementation plans + execution roadmap
docker-compose.yml     One-command stack (backend healthcheck-gated, frontend follows)
```

See `docs/superpowers/specs/2026-05-23-egata-design.md` for the full product +
architecture spec.

---

## Quick start

### Prerequisites

- Python 3.12 (FastAPI backend)
- Node 20+ (Next.js frontend)
- A Supabase project in the EU region with `vector` + `pgcrypto` extensions
- Azure OpenAI resource (chat + embedding deployment)
- *(optional)* Azure VoiceLive resource for voice, Twilio for real SMS/phone
- `pdflatex` on PATH (TeX Live or MiKTeX) for PDF generation

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp ../.env.example .env                                # fill SUPABASE_*, AZURE_*, JWT_*
python scripts/apply_migrations.py                     # 8 migrations, seeds 3 demo citizens
python -m scripts.index_rag                            # embeds procedures + scenarios
uvicorn app.main:app --reload --port 8000
```

Verify:

```bash
curl http://localhost:8000/health        # {"status":"ok","service":"egata-backend"}
curl http://localhost:8000/healthz       # liveness — used by Railway healthcheck
```

### 2. Frontend

```bash
cd frontend
npm install --legacy-peer-deps
cp .env.local.example .env.local
# In .env.local set:
#   NEXT_PUBLIC_USE_MOCKS=0
#   NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
#   NEXT_PUBLIC_DEMO_MODE=1
npm run dev                                            # http://localhost:3000
```

### 3. Demo walk-through

1. Open `http://localhost:3000` → **Intră în cont**
2. Pick persona **Maria Ionescu** → **Login cu ROeID**
3. OTP code: `123456` (accepted while `MOCK_OTP=1`)
4. `/home`: pre-seeded documents + 2 reminders
5. **Începe o cerere nouă** → type *"vreau să-mi schimb domiciliul"*
6. Confirm match → agent fills auto-known fields, asks via inline widgets for the rest
7. Once required fields are set, the **save / send / print** delivery buttons appear
8. After delivery, the ref number (`CV-XXXX`) appears and the ledger records the event
9. Click the document on `/home` to see the full `AuditTimeline` (every hashed event)

### 4. Frontend-only dev (no backend)

Set `NEXT_PUBLIC_USE_MOCKS=1` and run `npm run dev`. MSW serves the full
contract from `frontend/mocks/handlers.ts` with the same three personas and
fixtures that match the seeded backend.

---

## Feature surface

### Identity & authentication

- **`POST /auth/login-roeid`** — mock ROeID broker (returns a challenge for the
  persona's CNP). In demo mode, the LoginButton shows a persona dropdown.
- **`POST /auth/login-mrz`** — MRZ-derived login. The frontend's `MrzScanner`
  component uses **tesseract.js** to OCR the back of the CI in three modes
  (camera, upload, manual entry) — see `frontend/components/MrzScanner.tsx`.
- **`POST /auth/otp`** — challenge + 6-digit code → JWT. Real OTP goes through
  **Twilio Verify**; `MOCK_OTP=1` accepts the static code `123456`.
- JWTs are HS256, 24 h TTL by default, issued by `app.security.mint_access_token`.
- All authenticated routes accept the JWT as `Authorization: Bearer <token>`.

### Conversational agent

The agent is a **6-state machine** (`exploring → confirming_match → filling →
reviewing → delivered`, plus `redirected`) implemented in
`backend/app/sessions.py`. Each tool declares the states it's permitted in; the
dispatcher (`backend/app/agent_tools/__init__.py`) refuses out-of-state calls
as a hard guarantee — not a soft hint to the LLM.

| Tool | Permitted in | Purpose |
|---|---|---|
| `lookup_procedure` | exploring · confirming_match · delivered · redirected | RAG search across procedures + scenarios |
| `list_procedures` | exploring · confirming_match · delivered · redirected | Surface the catalog |
| `start_procedure` | confirming_match · delivered | Open a draft document for a procedure |
| `propose_widget` | confirming_match · filling · reviewing | Render an inline UI widget (choice / confirm / date) |
| `set_field` | filling · reviewing | Validate and write a field into the active document |
| `complete_document` | reviewing | Mark the draft complete; unlocks delivery |
| `find_redirect` | exploring · confirming_match · delivered · redirected | Route out-of-scope requests (ANAF, CNAS, DRPCIV, …) |

`find_redirect` and `lookup_procedure` are intentionally **off** during
filling/reviewing — a mid-fill remark ("vreau și impozit cândva") must not
abandon the draft. The agent can still answer with text; it just can't mutate
state.

**Transports**:

- `POST /agent/chat` — non-streaming, kept for tests / programmatic callers.
- `POST /agent/chat/stream` — Server-Sent Events with frames `delta`,
  `tool_call`, `tool_result`, `frontend_event`, `session_snapshot`, `done`,
  `error`, and `conversation` (echoes the resolved `conversation_id`).
- `POST /agent/widget-result` — resolve a pending widget directly without a
  model round-trip; returns `requires_chat_followup` when the answer is a
  signal the agent must react to.

### Voice — browser & phone

Two parallel bridges, both backed by **Azure VoiceLive** (`gpt-realtime`):

1. **Browser** — `WS /agent/voice/ws` (`backend/app/agent_voice.py`).
   - Browser captures 16 kHz PCM16 via an `AudioWorklet`
     (`frontend/lib/audioWorklet.ts`).
   - Backend resamples 16 → 24 kHz, relays to Azure, plays back 24 kHz unchanged.
   - **Streaming partial transcripts** via `gpt-4o-mini-transcribe` (delta events)
     plus a parallel Azure Speech SDK WebSocket for word-by-word user bubble
     fills.
   - The `start` frame carries the Bearer JWT (browsers can't set headers on a
     WS upgrade), plus optional `simple_language` / `voice_only` preferences.
   - Tool dispatch goes through the **same** `app.agent_tools` registry as text —
     no behavioural drift between voice and chat.

2. **Phone** — `WS /voice/twilio` + `POST /voice/twilio/webhook`
   (`backend/app/twilio_bridge.py`).
   - Twilio Media Streams sends μ-law 8 kHz; the bridge transcodes to PCM16
     24 kHz for Azure (`audioop`).
   - Tool allowlist is restricted to `{lookup_procedure, find_redirect}` —
     **no document writes from a phone session** (no consent surface).

### Procedures, scenarios, institutions

Three JSON catalogs, all loaded once and cached:

- **`backend/procedures/` (23 files)** — primărie-issued procedures
  (`schimbare-domiciliu`, `preschimbare-ci`, `certificat-fiscal`,
  `declarare-cladire`, `card-parcare-dizabilitati`, `taiere-arbore-curte-privata`,
  `premiu-100-ani`, …). Each file declares:
  - `fields[]` with `applies_if` conditional expressions and `default_from`
    auto-fill rules (see `backend/app/applies_if.py`).
  - `acte_necesare[]` cross-referencing the institutions catalog (with
    `linked_procedure_id` when an "act" is itself bookable in-app).
  - LaTeX `template` name.
  - `next_steps[]` consumed by the proactive worker after delivery.
  - `llm_hint` — free-form prompt tuning per procedure, never shown in UI.

- **`backend/scenarios/` (5 files)** — multi-step life situations
  (`sc-cumparare-apartament`, `sc-vanzare-apartament`,
  `sc-autorizatie-construire`, `sc-persoana-dizabilitati`,
  `sc-certificat-fiscal`). Each scenario sequences existing in-scope procedures
  + external-institution steps into a coherent plan with a `complexitate` and a
  `termen_total`.

- **`backend/institutions/` (16 files)** — external bodies (ANAF, ANEVAR,
  AJOFM, banca, casa-pensii, CNAS, DGASPC, diriginte-șantier, DRPCIV, instanță,
  notariat, OCPI-ANCPI, ONRC, SPCLEP-MAI, spital-medic, auditor-energetic). Each
  carries a `note_ai_cannot_complete` string that bubbles to the UI when the
  agent surfaces a redirect.

**RAG (`backend/app/embeddings.py`)** — `text-embedding-3-large` reduced to
**768 dimensions** via the `dimensions` parameter, stored in `rag_entries`
(pgvector). Reindex with `python -m scripts.index_rag`.

### Documents, PDF & delivery

Full document lifecycle is auditable end-to-end:

| Step | Endpoint | Ledger event |
|---|---|---|
| Create draft | `POST /documents` | `doc_created` |
| Patch fields | `PATCH /documents/{id}/fields` | — |
| Mark complete | implicit via `complete_document` tool | `completed_draft` |
| Render PDF | `POST /documents/{id}/generate-pdf` | `pdf_generated` |
| Deliver | `POST /documents/{id}/deliver` (`save` / `send` / `print`) | `delivered` |
| Inspect chain | `GET /documents/{id}/ledger` | (read-only verify) |

**PDF pipeline** (`backend/app/pdf.py`): LaTeX template + `{{ field }}`
placeholders → safe LaTeX escaping (`\&`, `\%`, `\_`, …) → `pdflatex`
subprocess → Supabase Storage bucket `pdfs` → public URL.

A **preview PDF without persisting a draft** is available via
`GET /procedures/{id}/preview-pdf` — used by the right-pane "Vezi documentul"
button for citizens who want to see the form before starting.

**Delivery modes**:

- `save` — store in the citizen's "My documents" list.
- `send` — Twilio SMS with a link to the PDF (uses `TWILIO_PHONE_NUMBER`).
- `print` — return URL + a printable view; useful in **kiosk mode**.

### Hash-chain audit ledger

Every state-changing event is appended to the `ledger` table via the Postgres
`append_ledger()` function (migration `003_ledger_function.sql`):

```
row_hash = sha256(event_type || payload_hash || prev_hash || iso_ts)
```

- `payload_hash = sha256(canonical_json(payload))` — keys sorted, no
  whitespace, UTF-8, `ensure_ascii=False` (Romanian characters survive verbatim).
- `prev_hash` = tip of the chain for that citizen; genesis is configurable via
  `LEDGER_GENESIS_HASH`.
- `GET /documents/{id}/ledger` returns the rows **and** a `verified: bool`
  recomputed server-side — the AuditTimeline UI surfaces this badge.
- Six event types: `doc_created`, `completed_draft`, `pdf_generated`,
  `delivered`, `redirected`, `reminder_created`.

Tests cover canonical JSON stability, tamper detection, and broken-link
rejection (`backend/tests/test_ledger.py`).

### Proactive reminders worker

`backend/app/worker.py` boots an **APScheduler** background job inside the
FastAPI lifespan that polls the `pending_delivered_events` SQL view every
`REMINDERS_POLL_SECONDS` (default 5). For each new `delivered` ledger row, it:

1. Looks up the procedure's `next_steps[]`.
2. Filters by `applies_if` expressions against the combined context of
   `citizen.attributes` + `document.fields`.
3. Writes a `reminder` row per applicable step.
4. Appends a `reminder_created` ledger entry per reminder.
5. Marks the ledger id processed in `processed_events` so it never fires twice.

Reminders surface in the UI via `RemindersList` on `/home`. Each reminder is
either:

- **`in_scope_procedure`** — `POST /reminders/{id}/start` creates a fresh
  document and routes the user to `/req/[id]`.
- **`external_redirect`** — `POST /reminders/{id}/dismiss` after the user
  acknowledges (the UI shows the institution's URL + phone).

### Accessibility & kiosk mode

The frontend's `accessibilityStore` (Zustand) drives four global toggles
persisted in `localStorage`:

- **Simple language** — agent prompt switches to A2-level Romanian.
- **Voice-only** — UI compresses to a single voice waveform; text input hides.
- **Large text** — site-wide font-size bump via Tailwind variants.
- **Kiosk mode** — fullscreen shell (`KioskShell.tsx`), all interactive
  controls ≥ 3 rem tall (touchscreen-friendly), pre-set demo persona, no
  external links.

`AccessibilityToggles` exposes them as switches with ARIA roles; the
preferences ride along on every `/agent/chat/stream` call as `preferences`.

### Demo controls

- **`POST /demo/reset`** — wipes a citizen's documents, reminders, ledger
  rows, processed-events watermarks, then re-applies their seeded reminders.
  Guarded by `DEMO_RESET_TOKEN` env var; unset = always 401 (safe in prod).
- `DemoResetButton.tsx` — floating button in the bottom corner when
  `NEXT_PUBLIC_DEMO_MODE=1`.
- **MSW mocks** (`frontend/mocks/`) — full contract mirroring `/auth`,
  `/citizens`, `/procedures`, `/documents`, `/agent/chat/stream`, `/reminders`.
  Set `NEXT_PUBLIC_USE_MOCKS=1` and frontend runs without a backend.

---

## HTTP / WebSocket API

Routes mounted in `backend/app/main.py`. Run `python scripts/export_openapi.py`
to regenerate `contracts/openapi.yaml` after route changes.

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/login-roeid` | Issue OTP challenge for a persona |
| POST | `/auth/login-mrz` | Issue OTP challenge from MRZ data |
| POST | `/auth/otp` | Exchange challenge + code for JWT |
| GET | `/citizens/me` | Authenticated citizen profile |
| PATCH | `/citizens/me/attributes` | Update flexible profile attributes |
| GET | `/procedures` | List all 23 procedures |
| GET | `/procedures/{id}` | Resolved procedure (acts enriched with institution metadata) |
| GET | `/procedures/{id}/preview-pdf` | LaTeX preview rendered with citizen profile |
| POST | `/procedures/lookup` | RAG search (pgvector cosine + redirect fallback) |
| GET | `/scenarios` | List multi-step scenarios |
| GET | `/scenarios/{id}` | Resolved scenario plan (steps + institutions) |
| POST | `/documents` | Create draft |
| GET | `/documents` | List citizen's documents |
| GET | `/documents/{id}` | Fetch one document |
| PATCH | `/documents/{id}/fields` | Patch fields (validated against schema) |
| POST | `/documents/{id}/generate-pdf` | Compile LaTeX → upload PDF |
| POST | `/documents/{id}/deliver` | save / send / print + ledger write |
| GET | `/documents/{id}/ledger` | Hash-chain with `verified` flag |
| POST | `/agent/chat` | Non-streaming agent turn |
| POST | `/agent/chat/stream` | **SSE** stream (deltas + tool events + snapshot) |
| POST | `/agent/widget-result` | Resolve a pending widget without LLM round-trip |
| WS | `/agent/voice/ws` | **Browser voice bridge** (PCM16, JWT in `start` frame) |
| WS | `/voice/twilio` | **Twilio Media Streams** bridge (μ-law 8 kHz) |
| POST | `/voice/twilio/webhook` | Twilio TwiML for inbound voice |
| GET | `/reminders` | Pending reminders for the citizen |
| PATCH | `/reminders/{id}` | Update reminder status |
| POST | `/reminders/{id}/start` | Open the linked procedure as a draft |
| POST | `/reminders/{id}/dismiss` | Mark dismissed |
| POST | `/demo/reset` | Wipe + reseed a citizen's demo state |
| GET | `/health` | App-level health |
| GET | `/healthz` | Liveness probe (no Postgres dependency) |

---

## Demo personas

Seeded by `backend/migrations/002_seed_data.sql`; mirrored exactly in
`frontend/mocks/fixtures.ts`.

| Persona ID | Name | CNP | Accessibility profile |
|---|---|---|---|
| `maria-ionescu` | Maria Ionescu (40) | `2851014123456` | Standard |
| `andrei-popa` | Andrei Popa (36) | `1900512123456` | Simple-language |
| `elena-dumitru` | Elena Dumitru (63) | `2620908123456` | Voice-only + simple + large-text |

> Phone numbers in the seed are placeholders. Replace with real team-member
> numbers before the live demo for actual SMS confirmations.

---

## Tech stack

**Backend** — Python 3.12 · FastAPI 0.115 · Pydantic v2 · Supabase (Postgres
+ pgvector + Storage + RLS) · psycopg 3 · Azure OpenAI SDK · Azure VoiceLive
SDK (`azure-ai-voicelive`) · Azure Cognitive Services Speech SDK · Twilio
9.3 (Verify + Voice + Media Streams) · APScheduler · Jinja2 · PyJWT ·
`pdflatex` (TeX Live / MiKTeX) · Sentry SDK · pytest + pytest-asyncio · ruff
+ mypy.

**Frontend** — Next.js 15 (App Router, RSC) · React 19 · TypeScript 5.6 ·
Tailwind 3.4 · `tailwindcss-animate` · Zustand 5 · framer-motion 11 ·
Radix UI primitives (dialog, label, slot, toast) · `class-variance-authority` ·
lucide-react icons · tesseract.js (OCR for MRZ) · `mrz` (parser) · MSW 2.6
(service-worker mocks) · Vitest + Testing Library · Playwright + axe-core
(a11y assertions).

**Infra** — Docker (multi-stage builds for both apps) · `docker-compose`
(backend healthcheck-gated, frontend depends-on healthy) · Railway-ready
(`railway.json` + `Procfile`).

---

## Environment variables

`.env.example` at the repo root is the canonical reference. Highlights:

| Variable | Purpose |
|---|---|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL` | Database + storage |
| `AZURE_OPENAI_*` | Chat (`gpt-5-mini`) + embeddings (`text-embedding-3-large`) |
| `AZURE_VOICELIVE_*` | Realtime voice (`gpt-realtime`, `gpt-4o-mini-transcribe`) |
| `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | Parallel Speech SDK for streaming user transcript partials |
| `JWT_SIGNING_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRES_SECONDS` | Token signing (`openssl rand -hex 32`) |
| `MOCK_OTP=1` | Skip Twilio, accept `123456` |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_VERIFY_SERVICE_SID`, `TWILIO_PHONE_NUMBER` | Real SMS + voice |
| `ALLOW_ORIGINS` | CORS allow-list (comma-separated; covers `:3000/:3001/:3030` by default) |
| `LEDGER_GENESIS_HASH` | Genesis hash for the audit chain |
| `DEMO_RESET_TOKEN` | Required header for `/demo/reset` (else 401) |
| `REMINDERS_POLL_SECONDS` | Worker tick interval (default `5`) |
| `LOG_LEVEL` | `INFO` default; `DEBUG` traces every audio chunk |
| `SENTRY_DSN` | Optional — if set, FastAPI integration is wired |
| `NEXT_PUBLIC_USE_MOCKS` | `1` runs the frontend offline with MSW |
| `NEXT_PUBLIC_API_BASE_URL` | Backend base URL for the frontend |
| `NEXT_PUBLIC_DEMO_MODE` | `1` enables the persona dropdown + demo reset button |

---

## Running tests

```bash
cd backend && pytest                        # 17 test modules
cd frontend && npm test                     # Vitest unit tests
cd frontend && npm run e2e                  # Playwright + axe-core a11y
```

Backend coverage:

- `test_sessions_state_machine.py` — every legal/illegal transition
- `test_agent_tools_dispatch.py` — state-gating refusal logic
- `test_ledger.py` — canonical JSON, tamper detection, broken-link rejection
- `test_applies_if.py` — conditional field expression evaluator
- `test_pdf.py` — LaTeX escape + render security
- `test_embeddings.py` — cosine, source text, registry validation
- `test_procedure_state.py` — required/applicable field computation
- `test_reminders_selection.py` — applies_if filtering for next_steps
- `test_scenarios.py`, `test_institutions.py` — catalog integrity
- `test_security_token.py` — JWT mint/verify round-trip
- `test_sanitize_history.py` — chat history strip-thinking + PII redaction
- `test_end_to_end_mocked.py` — login → otp → me → create → patch → generate-pdf → deliver → ledger
- `test_smoke_deployed.py` — production smoke against a live URL
- `test_health.py` — health endpoint

---

## Docker compose

One-command stack (uses the same `.env.example` variables):

```bash
docker compose up --build
# backend:  http://localhost:8000  (health-gated)
# frontend: http://localhost:3000  (depends_on backend healthy)
```

Procedures, scenarios, institutions, and templates are mounted as volumes so
edits hot-reload without a rebuild.

---

## Roadmap

- **Wave 1 (shipped)** — Plans 1 (frontend) + 2 (backend) — auth, procedures,
  documents, PDF, delivery, ledger, mocks.
- **Wave 2 (shipped)** — Plans 3 (agent + Azure VoiceLive) + 4 (proactive
  worker, accessibility final pass, demo polish).
- **Checkpoint 2 (shipped)** — full agent-driven flow + reminders worker +
  a11y certification.
- **Post-hackathon** — multi-language (en/hu/de), real ROeID broker
  integration, signed PDF (eIDAS QES), per-procedure analytics dashboard.

See `docs/superpowers/plans/2026-05-23-egata-execution-roadmap.md` for the full
execution model.

---

## Docs

- `docs/superpowers/specs/2026-05-23-egata-design.md` — product + architecture spec
- `docs/superpowers/specs/2026-05-23-multi-procedure-rag-design.md` — RAG design
- `docs/superpowers/specs/2026-05-23-voice-ws-bridge-design.md` — voice bridge
- `docs/superpowers/specs/2026-05-23-chat-first-redesign-design.md` — UI redesign
- `docs/superpowers/plans/` — four implementation plans (one per wave/team)
- `backend/RUNBOOK.md` — Supabase setup, Railway deploy, demo prep checklist
- `backend/CHECKPOINT_1.md` — backend Wave 1 acceptance notes
- `PITCH_QA.md` — judge-facing Q&A for the live pitch

---

**Made with care for `primărie` queues that didn't have to be.**
