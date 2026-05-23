# CivicAI Execution Roadmap

> **Purpose:** Coordinate 4 implementation plans across 2 parallel waves. This document is the **source of truth for shared contracts** (API, hooks, repo structure, conventions). Each plan references this roadmap; deviations require updating this file first.

**Spec:** `docs/superpowers/specs/2026-05-23-civicai-design.md`

---

## 1. Wave structure

```
┌─────────────────────────────────────────────────────────┐
│ WAVE 1 (parallel)                                       │
│  Plan 1: Frontend Foundation  ────┐                     │
│  Plan 2: Backend Foundation   ────┤                     │
│                                    ▼                    │
│                       ◇ Checkpoint 1: integration       │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ WAVE 2 (parallel)                                       │
│  Plan 3: Agent Intelligence + Voice  ────┐              │
│  Plan 4: Proactive + Polish + A11y   ────┤              │
│                                          ▼              │
│                            ◇ Checkpoint 2: demo-ready   │
└─────────────────────────────────────────────────────────┘
```

**Wave 1** produces a deployed app where the citizen can: log in (ROeID mock + OTP or MRZ), browse home, start a procedure, fill it (by typing — chat is mocked), generate a PDF, deliver it (save/send/print), and see the audit timeline. The agent in Wave 1 returns **canned responses**; voice is a stub.

**Wave 2** replaces the mock agent with real Pydantic AI + Gemini Live, adds the Twilio phone bridge, adds the proactive reminders layer with framer-motion polish, wires the accessibility toggles, and ships the demo-ready production deploy.

---

## 2. Repository structure

```
ClujHackathon/
├── frontend/                        # Next.js 15 (Plan 1 scaffolds; Plans 3 & 4 extend)
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                 # Citizen home (Plan 1)
│   │   ├── login/
│   │   │   ├── page.tsx             # ROeID button + persona chooser (Plan 1)
│   │   │   └── otp/page.tsx         # OTP entry (Plan 1)
│   │   ├── req/[id]/page.tsx        # Procedure flow (Plan 1; Plan 3 wires real voice)
│   │   └── doc/[id]/page.tsx        # Document detail + audit timeline (Plan 1)
│   ├── components/
│   │   ├── KioskShell.tsx           # Plan 1
│   │   ├── LoginButton.tsx          # Plan 1
│   │   ├── MrzScanner.tsx           # Plan 1
│   │   ├── OtpInput.tsx             # Plan 1
│   │   ├── ChatPanel.tsx            # Plan 1; Plan 3 wires real chat
│   │   ├── FormPreview.tsx          # Plan 1 (HTML mockup)
│   │   ├── CompletionModeSelector.tsx  # Plan 1
│   │   ├── ManualFillForm.tsx       # Plan 1
│   │   ├── GuidedFillFlow.tsx       # Plan 1
│   │   ├── VocalFillFlow.tsx        # Plan 1 (stub); Plan 3 wires voice
│   │   ├── ReminderCard.tsx         # Plan 1 shell; Plan 4 animates + wires actions
│   │   ├── AuditTimeline.tsx        # Plan 1
│   │   ├── DocumentList.tsx         # Plan 1
│   │   └── AccessibilityToggles.tsx # Plan 1 (UI toggles); Plan 4 wires behavior
│   ├── lib/
│   │   ├── api.ts                   # FastAPI HTTP client (Plan 1)
│   │   ├── mrz.ts                   # tesseract+mrz wrapper (Plan 1)
│   │   ├── types.ts                 # Shared types matching OpenAPI (Plan 1)
│   │   ├── useVoiceAgent.ts         # Plan 1 stub; Plan 3 implements real
│   │   ├── kioskMode.ts             # ?mode=kiosk detection (Plan 1)
│   │   └── i18n.ts                  # RO strings + simple-language variants (Plan 1)
│   ├── mocks/                       # MSW mock handlers (Plan 1; deleted at Checkpoint 1)
│   │   └── handlers.ts
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   ├── package.json
│   └── tsconfig.json
│
├── backend/                         # FastAPI (Plan 2 scaffolds; Plans 3 & 4 extend)
│   ├── app/
│   │   ├── main.py                  # Plan 2
│   │   ├── config.py                # Plan 2 (settings/env vars)
│   │   ├── db.py                    # Plan 2 (Supabase client)
│   │   ├── auth.py                  # Plan 2 (ROeID mock + OTP)
│   │   ├── citizens.py              # Plan 2 (profile endpoint)
│   │   ├── procedures.py            # Plan 2 (registry loader + RAG)
│   │   ├── documents.py             # Plan 2 (CRUD)
│   │   ├── ledger.py                # Plan 2 (hash chain wrapper)
│   │   ├── pdf.py                   # Plan 2 (LaTeX compile)
│   │   ├── agent.py                 # Plan 2 (mock chat) → Plan 3 (Pydantic AI agent)
│   │   ├── voice.py                 # Plan 3 (voice session + ephemeral token)
│   │   ├── twilio_bridge.py         # Plan 3 (phone bridge)
│   │   ├── reminders.py             # Plan 4 (background worker + endpoints)
│   │   ├── demo.py                  # Plan 4 (seed reset)
│   │   └── tools/                   # Plan 3 (agent tool implementations)
│   │       ├── lookup_procedure.py
│   │       ├── set_field.py
│   │       ├── generate_pdf.py
│   │       ├── deliver.py
│   │       ├── find_redirect.py
│   │       └── set_reminder.py
│   ├── procedures/                  # Plan 2 (JSON registry)
│   │   ├── schimbare-domiciliu.json
│   │   ├── certificat-fiscal.json
│   │   └── preschimbare-ci.json
│   ├── templates/                   # Plan 2 (LaTeX); Plan 4 polish
│   │   ├── base.tex
│   │   └── schimbare-domiciliu.tex
│   ├── migrations/                  # Plan 2 (Supabase SQL)
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_seed_data.sql
│   │   └── 003_ledger_function.sql
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
│
├── contracts/
│   └── openapi.yaml                 # Auto-generated by FastAPI (Plan 2); consumed by Plan 1
│
└── docs/
    └── superpowers/
        ├── specs/
        │   └── 2026-05-23-civicai-design.md
        └── plans/
            ├── 2026-05-23-civicai-execution-roadmap.md  (this file)
            ├── 2026-05-23-civicai-plan-1-frontend-foundation.md
            ├── 2026-05-23-civicai-plan-2-backend-foundation.md
            ├── 2026-05-23-civicai-plan-3-agent-voice.md
            └── 2026-05-23-civicai-plan-4-proactive-polish.md
```

**Convention:** Plan N is the **sole writer** of files marked `(Plan N)`. Plans that **extend** a file (e.g., Plan 3 extending `agent.py`) replace its body while keeping the function/endpoint signatures stable.

---

## 3. API contract (shared by Plan 1 ↔ Plan 2)

**Authoritative source:** `contracts/openapi.yaml` (auto-generated from FastAPI in Plan 2 Task A).

All endpoints below MUST exist by end of Wave 1. Plan 3 adds `/voice/*` endpoints. Plan 4 adds `/reminders/*` and `/demo/*`.

### Authentication

```http
POST /auth/login-roeid
Content-Type: application/json
{
  "persona_id": "maria-ionescu"     // optional; default demo citizen if omitted
}
→ 200 OK
{
  "challenge_id": "ch_abc123",
  "phone_hint": "***1234"            // last 4 digits of seeded phone
}

POST /auth/login-mrz
Content-Type: application/json
{
  "cnp": "2851014123456",
  "nume": "Ionescu",
  "prenume": "Maria"
}
→ 200 OK
{
  "challenge_id": "ch_xyz789",
  "phone_hint": "***1234"
}

POST /auth/otp
Content-Type: application/json
{
  "challenge_id": "ch_abc123",
  "code": "123456"
}
→ 200 OK
{
  "access_token": "eyJ...",
  "citizen_id": "uuid"
}
```

### Citizen profile

```http
GET /citizens/me
Authorization: Bearer <access_token>
→ 200 OK
{
  "id": "uuid",
  "cnp": "2851014123456",
  "nume": "Ionescu",
  "prenume": "Maria",
  "data_nasterii": "1985-03-14",
  "email": "maria@example.com",
  "phone": "+40712345678",
  "attributes": {
    "owns_vehicle": true,
    "marital_status": "necăsătorit",
    "has_children": false,
    "employer": "SC Acme SRL",
    "medic_familie": "Dr. Popescu, Cluj",
    "preferred_language": "ro",
    "accessibility": { "voice_only": false, "simple_language": false },
    "current_address": "Str. Avram Iancu 5, Cluj-Napoca"
  }
}
```

### Procedures

```http
POST /procedures/lookup
Authorization: Bearer <token>
{
  "query": "vreau să-mi schimb domiciliul"
}
→ 200 OK
{
  "matches": [
    { "procedure_id": "schimbare-domiciliu", "title": "Schimbare domiciliu", "score": 0.92 },
    { "procedure_id": "preschimbare-ci", "title": "Preschimbare CI", "score": 0.41 }
  ],
  "redirect_candidate": null
}

// When no good match:
{
  "matches": [],
  "redirect_candidate": "ANAF"
}

GET /procedures
→ 200 OK [Procedure, ...]

GET /procedures/{procedure_id}
→ 200 OK Procedure
```

### Documents

```http
POST /documents
Authorization: Bearer <token>
{ "procedure_id": "schimbare-domiciliu" }
→ 201 Created Document (status="draft")

GET /documents/{id}
→ 200 OK Document

GET /documents
→ 200 OK Document[]   // all docs for current citizen

PATCH /documents/{id}/fields
{ "fields": { "adresa_noua": "Str. Plopilor 15, Cluj-Napoca" } }
→ 200 OK Document

POST /documents/{id}/generate-pdf
→ 200 OK { "pdf_url": "https://supabase.../doc-abc.pdf" }

POST /documents/{id}/deliver
{ "delivery": "send" }
→ 200 OK Document (status="finalized", delivery="send", ref_number="CV-A4B7")

GET /documents/{id}/ledger
→ 200 OK
{
  "entries": [
    { "id": 1, "event_type": "doc_created", "payload_hash": "0x...", "prev_hash": "0x...", "row_hash": "0x...", "created_at": "..." },
    ...
  ],
  "verified": true
}
```

### Agent chat

```http
POST /agent/chat
Authorization: Bearer <token>
{
  "conversation_id": "conv_abc",    // optional; null = new conversation
  "document_id": "doc_uuid",        // optional
  "message": "Vreau să-mi schimb domiciliul",
  "preferences": { "simple_language": false }
}
→ 200 OK
{
  "conversation_id": "conv_abc",
  "message": "Înțeleg că vrei să-ți schimbi domiciliul. Continuăm?",
  "tool_calls": [
    { "name": "lookup_procedure", "arguments": { "query": "schimbare domiciliu" } }
  ]
}
```

**Wave 1:** `/agent/chat` returns hard-coded canned responses keyed off keyword matches. Sufficient for Plan 1 to integrate UI flow.
**Wave 2:** Plan 3 replaces the mock with a real Pydantic AI agent that calls Gemini Live.

### TypeScript types (Plan 1 imports from `frontend/lib/types.ts`)

```typescript
export type Citizen = {
  id: string;
  cnp: string;
  nume: string;
  prenume: string;
  data_nasterii: string;       // ISO date
  email: string;
  phone: string;
  attributes: CitizenAttributes;
};

export type CitizenAttributes = {
  owns_vehicle?: boolean;
  marital_status?: "necăsătorit" | "căsătorit" | "divorțat" | "văduv";
  has_children?: boolean;
  employer?: string;
  medic_familie?: string;
  preferred_language?: "ro" | "en";
  current_address?: string;
  accessibility?: {
    voice_only?: boolean;
    simple_language?: boolean;
    large_text?: boolean;
  };
};

export type Procedure = {
  id: string;
  title: string;
  description: string;
  scope: "primarie" | "external";
  category: string;
  synonyms: string[];
  sample_queries: string[];
  fields: ProcedureField[];
  template: string;
  next_steps: NextStep[];
};

export type ProcedureField = {
  name: string;
  label: string;
  source: string;              // "ask" | "id_scan" | "profile" | "id_scan|profile" | ...
  required: boolean;
  options?: string[];
  suggest_default?: string;
  redact_in_voice?: boolean;
};

export type NextStep = {
  kind: "in_scope_procedure" | "external_redirect";
  procedure_id?: string;
  redirect_target?: string;    // "ANAF" | "CNAS" | "DRPCIV" | ...
  deadline_days?: number;
  title: string;
  applies_if?: string;         // simple expression: "owns_vehicle == true"
};

export type Document = {
  id: string;
  citizen_id: string;
  procedure_id: string;
  status: "draft" | "finalized";
  fields: Record<string, unknown>;
  pdf_url?: string;
  delivery?: "save" | "send" | "print";
  ref_number?: string;
  created_at: string;
  delivered_at?: string;
};

export type LedgerEntry = {
  id: number;
  event_type:
    | "doc_created"
    | "completed_draft"
    | "pdf_generated"
    | "delivered"
    | "redirected"
    | "reminder_created";
  payload_hash: string;
  prev_hash: string;
  row_hash: string;
  created_at: string;
};

export type Reminder = {
  id: string;
  citizen_id: string;
  trigger_doc_id?: string;
  kind: "in_scope_procedure" | "external_redirect";
  procedure_id?: string;
  redirect_target?: string;
  title: string;
  due_date?: string;
  status: "pending" | "started" | "done" | "dismissed";
  created_at: string;
};

export type ChatToolCall = {
  name: string;
  arguments: Record<string, unknown>;
};

export type VoicePreferences = {
  simple_language?: boolean;
  voice_only?: boolean;
};
```

---

## 4. Hook contract (shared by Plan 3 ↔ Plan 4)

### `useVoiceAgent` (file: `frontend/lib/useVoiceAgent.ts`)

**Plan 1 ships a STUB.** Plan 3 implements the real version. Plan 4 consumes the hook for voice-only mode behavior.

```typescript
import { VoicePreferences } from "./types";

export type VoiceAgentState = "idle" | "connecting" | "listening" | "speaking" | "error";

export type ToolCallHandler = (
  name: string,
  args: Record<string, unknown>
) => Promise<Record<string, unknown>>;

export type VoiceAgentHook = {
  state: VoiceAgentState;
  start: (opts: {
    documentId?: string;
    preferences?: VoicePreferences;
    onAgentMessage?: (text: string) => void;
    onTranscript?: (text: string) => void;
  }) => Promise<void>;
  stop: () => void;
  sendText: (text: string) => Promise<void>;
  registerToolHandler: (handler: ToolCallHandler) => void;
  lastTranscript: string;
  lastAgentMessage: string;
};

export function useVoiceAgent(): VoiceAgentHook;
```

**Plan 1 stub returns:**
```typescript
{
  state: "idle",
  start: async () => { throw new Error("Voice not yet implemented"); },
  stop: () => {},
  sendText: async () => {},
  registerToolHandler: () => {},
  lastTranscript: "",
  lastAgentMessage: ""
}
```

### Voice session preferences

`POST /voice/session` (Plan 3) accepts:
```json
{
  "document_id": "doc_uuid",
  "preferences": {
    "simple_language": true,
    "voice_only": true
  }
}
```

Plan 3's voice session creator passes `simple_language` to the Gemini Live system prompt. Plan 4's accessibility toggles set this flag.

---

## 5. Checkpoint criteria

### Checkpoint 1 (end of Wave 1)

**Frontend (Plan 1) requirements:**
- [ ] Deployed to Vercel at a public URL.
- [ ] `/login` → ROeID button click → backend OTP challenge → OTP entry → session.
- [ ] `/` (citizen home) renders with real citizen profile from `GET /citizens/me`.
- [ ] `/?mode=kiosk` renders kiosk shell with MRZ scanner camera UI.
- [ ] MRZ scanner successfully parses a test buletin via `tesseract.js` + `mrz`.
- [ ] `/req/[id]` renders chat panel + form preview side-by-side; can type to mock agent and see canned responses.
- [ ] Form preview updates as fields fill (driven by `PATCH /documents/{id}/fields`).
- [ ] Save/Send/Print buttons trigger `POST /documents/{id}/deliver` and show confirmation.
- [ ] `/doc/[id]` shows document with ledger audit timeline from `GET /documents/{id}/ledger`.
- [ ] Lighthouse accessibility score ≥ 95.

**Backend (Plan 2) requirements:**
- [ ] Deployed to Railway at a public URL.
- [ ] Supabase Postgres EU with all tables, RLS enabled, 3 seeded citizens.
- [ ] `/auth/login-roeid`, `/auth/login-mrz`, `/auth/otp` all work.
- [ ] `/citizens/me` returns full profile.
- [ ] `/procedures/lookup` returns RAG matches for 5 sample Romanian queries.
- [ ] 7 procedure JSON files loaded; embeddings populated in pgvector.
- [ ] Document CRUD endpoints work.
- [ ] `/documents/{id}/generate-pdf` produces a real PDF for `schimbare-domiciliu` via LaTeX.
- [ ] `/documents/{id}/deliver` updates status + writes ledger entry.
- [ ] `/documents/{id}/ledger` returns chain with `verified: true`.
- [ ] `/agent/chat` returns canned responses sufficient for Plan 1's UI flow.

**Integration verification:**
- [ ] Full demo flow (login → start procedure → fill via typing → generate PDF → deliver → see in audit timeline) runs end-to-end against the deployed backend.
- [ ] MSW mocks deleted from frontend; only real backend calls remain.

### Checkpoint 2 (end of Wave 2)

**Plan 3 (Agent + Voice):**
- [ ] `/agent/chat` powered by Pydantic AI + Claude tool calls (no canned responses).
- [ ] `/voice/session` returns a working Gemini Live ephemeral token.
- [ ] `useVoiceAgent` hook drives a real WebSocket session to Gemini Live in Romanian.
- [ ] Function calls from Gemini Live dispatched to FastAPI tools.
- [ ] Voice flow for `schimbare-domiciliu` works end-to-end (citizen speaks Romanian; agent responds; form fills).
- [ ] Twilio inbound number connects to phone bridge; agent answers a procedural question in Romanian.
- [ ] TwiML fallback configured if bridge fails.

**Plan 4 (Proactive + Polish + A11y):**
- [ ] Background worker fires after `/documents/{id}/deliver`; reads `next_steps`, writes `reminders`.
- [ ] Reminder cards appear on citizen home with framer-motion entry animation.
- [ ] "Start now" on in-scope reminder creates a new document and routes to `/req/[id]`.
- [ ] External-redirect cards show contact info + roadmap note.
- [ ] Voice-only mode toggle: full procedure completable without screen touch.
- [ ] Simple-language toggle: voice session created with `simple_language: true`; agent tone changes.
- [ ] Large-text mode: Tailwind class applied across app.
- [ ] axe-core CI passes on all pages; Lighthouse a11y ≥ 100.
- [ ] `POST /demo/reset` re-seeds the citizen; dev panel exposes the button.
- [ ] Framer-motion transitions on page changes, field highlights, mode switches.
- [ ] Production environment hardened: env vars verified, Sentry installed, EU regions confirmed.

---

## 6. Plan-by-plan scope

### Plan 1 — Frontend Foundation (Wave 1)
**IN:** Next.js 15 scaffold; Tailwind + shadcn + framer-motion (light usage); all page routes; MRZ scanner; all UI components; AA baseline; types from contract; API client with MSW mocks; Vercel deploy.
**OUT:** Real voice (Plan 3 stub-replaces `useVoiceAgent`); real agent chat (Plan 2 mocks `/agent/chat`); proactive reminder behaviors (Plan 4); framer-motion polish beyond basic transitions (Plan 4); accessibility behavior wiring (Plan 4).

### Plan 2 — Backend Foundation (Wave 1)
**IN:** FastAPI + Pydantic AI scaffold (no Gemini Live yet); Supabase schema + RLS + seed; identity endpoints; citizen profile; procedure registry + RAG; document CRUD; ledger module; LaTeX PDF; delivery; mock agent chat; Railway deploy.
**OUT:** Real Pydantic AI agent with Gemini Live (Plan 3); voice session + Twilio bridge (Plan 3); reminders worker + endpoints (Plan 4); demo reset endpoint (Plan 4).

### Plan 3 — Agent Intelligence + Voice (Wave 2)
**IN:** Pydantic AI agent with Romanian system prompt; agent tools; Gemini Live integration; voice session endpoint; `useVoiceAgent` real implementation; function-call dispatch; barge-in; Twilio bridge to Gemini Live; phone agent (RAG-only); TwiML fallback. Wires the three completion modes to real agent.
**OUT:** Proactive worker (Plan 4); accessibility behaviors (Plan 4); framer-motion polish (Plan 4); demo reset (Plan 4).

### Plan 4 — Proactive + Polish + Accessibility (Wave 2)
**IN:** Background worker; `next_steps` evaluator (`applies_if` expression parser); `reminders` CRUD endpoints; reminder cards UI with framer-motion; "Start now" action; external redirect cards; voice-only mode behavior (consumes `useVoiceAgent`); simple-language toggle wiring (sets preference passed to `/voice/session`); large-text mode; framer-motion polish across app (page transitions, field highlights); demo seed-reset endpoint + dev panel button; accessibility audit (axe-core CI, Lighthouse pass); production deploy hardening (env vars, Sentry, EU region verification); dry-run smoke tests.
**OUT:** Anything involving Gemini Live or the agent loop directly (Plan 3).

---

## 7. Conventions

**Branching:**
- Wave 1: `wave1/plan-1-frontend`, `wave1/plan-2-backend`. Merge to `main` at Checkpoint 1.
- Wave 2: `wave2/plan-3-agent-voice`, `wave2/plan-4-proactive-polish`. Merge to `main` at Checkpoint 2.

**Commit style:** `feat(plan-N): subject` / `fix(plan-N): subject` / `chore(plan-N): subject`. Frequent small commits.

**Testing discipline:**
- Backend: TDD for ledger, RAG, agent tools, applies_if evaluator. Pytest. Run before each commit.
- Frontend: snapshot/component tests via Vitest + Testing Library for critical components (FormPreview, ChatPanel, MrzScanner). E2E via Playwright for login + procedure flow at the end of each plan.
- Demo dry-run mandatory at end of Wave 2.

**Environment variables (centralized at root `.env.example`):**
```
# Supabase
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Auth / OTP
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_VERIFY_SERVICE_SID=
TWILIO_PHONE_NUMBER=

# LLM / Voice
GEMINI_API_KEY=
OPENAI_API_KEY=                   # embeddings + fallback realtime

# Deployment
NEXT_PUBLIC_API_BASE_URL=
NEXT_PUBLIC_DEMO_MODE=1           # exposes demo persona chooser in dev
JWT_SIGNING_SECRET=
SENTRY_DSN=                       # Plan 4
```

**Code style:**
- Frontend: TypeScript strict mode. ESLint + Prettier with `next/core-web-vitals`.
- Backend: Python 3.12. Ruff + mypy strict. Pydantic v2 models for all request/response shapes.

---

## 8. Execution model (how plans will be run)

Each plan is **independently executable by a fresh agent session** using `superpowers:executing-plans` or `superpowers:subagent-driven-development`. The plan documents are self-contained: they reference the spec and this roadmap, but a coder picking up Plan N can execute it without reading the others end-to-end.

**Wave 1 dispatch:**
1. Start `wave1/plan-1-frontend` branch → execute Plan 1.
2. Start `wave1/plan-2-backend` branch → execute Plan 2.
3. Merge both into `main` at Checkpoint 1.
4. Run integration verification.

**Wave 2 dispatch:**
1. Start `wave2/plan-3-agent-voice` branch off `main` → execute Plan 3.
2. Start `wave2/plan-4-proactive-polish` branch off `main` → execute Plan 4.
3. Merge both into `main` at Checkpoint 2.
4. Demo dry-run.

---

## 9. Cross-plan integration notes (post-write reconciliation)

After the four plans were drafted in parallel, the following conventions are the canonical resolutions for cross-plan touchpoints. When a plan's local code conflicts with these, **the integration notes win**. The executing agent should apply these conventions silently.

### 9.1 Backend module exports (Plan 2 owes Plans 3 + 4)

Plan 2's modules MUST expose the following callable functions for in-process use by Plans 3 and 4, in addition to the HTTP endpoints:

**`backend/app/documents.py`** — export:
```python
def create_draft_document(citizen_id: UUID | str, procedure_id: str) -> dict:
    """Create a new draft document. Writes ledger entry. Returns the inserted row."""

def set_document_fields(document_id: UUID | str, fields: dict) -> dict:
    """Merge fields into document.fields. Writes ledger entry if all required fields now present."""

def get_document(document_id: UUID | str) -> dict:
    """Read a document by id."""
```
The HTTP endpoints (`POST /documents`, `PATCH /documents/{id}/fields`, `GET /documents/{id}`) are thin wrappers around these functions.

**`backend/app/db.py`** — the DB wrapper exposes:
```python
class DB:
    client: Any   # Supabase Python client; use as db.client.table("citizens").select(...).eq(...).execute()
    # ... existing pg connection accessors used by ledger.py

def get_db() -> DB:
    """FastAPI dependency injection."""
```

**`backend/app/ledger.py`** — canonical signature:
```python
def append_ledger(
    citizen_id: UUID | str,
    event_type: LedgerEventType | str,         # accept BOTH enum and string for ergonomic call sites
    payload: dict,
    document_id: UUID | str | None = None,
) -> dict:
    """Append a ledger row. Validates prev_hash. Raises on chain integrity violation."""
```
Plan 4 callers using `append_ledger(..., event_type="reminder_created", ...)` MUST drop any extra `db=` kwarg from their call sites — the function manages its own DB connection internally. The `event_type` accepts a string for hackathon ergonomics; internally it normalizes to the enum.

### 9.2 API contract additions

Two endpoints were not in roadmap §3 originally but are required:

```http
GET /reminders
Authorization: Bearer <token>
→ 200 OK
{
  "reminders": [Reminder, ...]
}
```
Plan 4 implements this; Plan 1 mocked it via MSW for Wave 1 development. Shape matches the `Reminder` type already in §3.

```http
PATCH /citizens/me/attributes
Authorization: Bearer <token>
{
  "attributes": { "accessibility": { "voice_only": true } }   // shallow merge into attributes JSONB
}
→ 200 OK Citizen
```
Plan 4 implements this; used by accessibility-toggle wiring.

### 9.3 Frontend route addition

Plan 1 added a route not in roadmap §2 — accepted:

`/req/new` — RAG search UI ("describe what you need"). Calls `POST /procedures/lookup`, shows matches, and routes to `/req/[id]` after the citizen confirms a match or to an out-of-scope redirect screen.

### 9.4 `useVoiceAgent` voice-only behavior

Plan 4's voice-only mode requires the hook to **keep the mic continuously hot between agent turns** when `voice_only: true` is passed in `preferences`. Plan 3's `useVoiceAgent` MUST implement this internally — no new public methods on the hook are needed. The Gemini Live session, once `start()`-ed with `voice_only: true`, stays in continuous-listening mode regardless of agent speech turns.

### 9.5 `set_reminder` invocation paths

Two callers, same target table:

- **Plan 3's agent tool** (`backend/app/tools/set_reminder.py`): used when the LLM agent decides to set a reminder mid-conversation. Invoked via Pydantic AI tool dispatch.
- **Plan 4's background worker** (`backend/app/reminders.py`): used after each `delivered` event to evaluate `next_steps` and write reminders. Invoked by **direct Python import** of the tool function — `from app.tools.set_reminder import set_reminder` — with a synthetic `ToolContext`. NOT via HTTP.

Both paths write to the same `reminders` table and emit `reminder_created` ledger entries through `append_ledger`.

### 9.6 Demo CNPs

Plan 4 used placeholder CNPs (`2851014123456`, `1900215987654`, `2750822111222`). At execution time, the values in Plan 2's `002_seed_data.sql` are canonical. Plan 4's queries and Python re-seed function must adjust to whatever CNPs Plan 2 actually inserts.

### 9.7 OTP and SMS mocking

A single env flag `MOCK_OTP=1` (Plan 2's choice) governs both:
- OTP code returned to test clients (deterministic code, no Twilio call).
- Delivery-confirmation SMS suppression (no Twilio call on Send).

For demo day, set `MOCK_OTP=0` (or unset) to enable real SMS so jurors see actual codes arrive on a team-member phone.

### 9.8 Background worker choice

Plan 4 chose **APScheduler** with a 5-second-poll job over a watermark in `processed_events`. Rationale: `delivered` events can come from agent tool calls (Plan 3 territory), which may not run inside an HTTP request context that FastAPI BackgroundTasks could attach to. The poll-based scheduler is reliable across all event sources. Accepted.

### 9.9 `/demo/reset` implementation

The endpoint re-seeds a citizen by mirroring `002_seed_data.sql` in Python (no `psql` invocation at runtime). This Python re-seeder lives in `backend/app/demo.py` and is brittle if the SQL diverges. **Convention:** when the SQL seed changes, Plan 4's `_seed_for_citizen` Python helper MUST be updated in the same commit.

### 9.10 Gemini Live ephemeral tokens

Plan 3 noted that Google's `google-genai` SDK ephemeral-token support has been inconsistent. **Decision for hackathon:** ship with the main `GEMINI_API_KEY` delivered to the browser over HTTPS as a short-lived signed envelope; the real authorization for side-effecting tool calls is the FastAPI-issued JWT. Mark `TODO: swap to true ephemeral tokens when SDK GA` in `backend/app/voice.py`. Accept the risk for the hackathon.
