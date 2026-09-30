# eGata

**Conversational AI agent for Romanian primărie (city-hall) procedures.**
Built for the Cluj Hackathon 2026 (Bosch Cluj, May 22–24).

> Spune-i ce ai nevoie. Îți spune ce acte îți trebuie. Le și completează cu tine.

A citizen logs in once with their digital ID (or scans the MRZ on the back of the
CI), describes what they need in plain Romanian — by voice or text — and eGata
runs a stateful agent that picks the right procedure, asks only for what's
genuinely missing, renders the form to PDF with LaTeX, delivers it (save /
SMS / print), writes every milestone — including the SHA-256 of the PDF — to
a tamper-evident hash-chain ledger you can verify yourself, and queues
proactive reminders for the next legal steps.

> The PDF is not digitally signed. "Signed" anywhere in this project means
> a short-lived *signed download link*. See [What's demo-only](#whats-demo-only).

---

## Table of contents

- [What's in the box](#whats-in-the-box)
- [What's demo-only](#whats-demo-only)
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

This is a three-day hackathon build. The table below is triaged honestly:

- **shipped** — works, tested, runs offline from `docker compose up`.
- **partial** — works, with a caveat named in the row.
- **demo-only** — real code, but standing in for something that would have to
  exist before anyone could use this for real. See
  [What's demo-only](#whats-demo-only).

| Capability | Status | |
|---|---|---|
| 23 primărie procedures — field schemas, LaTeX templates, conditional logic | shipped | |
| 5 multi-step real-life scenarios (e.g. *cumpărare apartament*) | shipped | |
| 17 external institutions catalog (ANAF, CNAS, DRPCIV, SPCLEP-MAI, …) | shipped | |
| LaTeX → `pdflatex` → PDF pipeline, all 23 templates rendered in CI | shipped | |
| Hash-chain ledger (sha256), append-only, per-document chains that bind the PDF's hash; verifiable off-server with `scripts/verify_ledger.py` | shipped | tamper-evident, not tamper-proof — see below |
| Background worker — `next_steps[]` → reminders with `applies_if` filtering | shipped | |
| Accessibility: simple-language, voice-only, large-text, kiosk modes | shipped | |
| Stateful agent, 6-state machine with state-gated tool dispatch | shipped | |
| Romanian text chat — **offline agent** | shipped | no key needed; a deterministic script (keyword search, then field by field), not an LLM — it says so |
| Romanian text chat — LLM agent (Azure OpenAI) | partial | needs a paid Azure OpenAI key |
| Procedure search via pgvector (768-d) | shipped | local lexical index built automatically; the Azure embedding index needs a paid deployment |
| Azure VoiceLive browser WebSocket bridge (PCM16, streaming partials) | partial | needs a separate Azure VoiceLive resource |
| Twilio Media Streams ↔ VoiceLive phone bridge (μ-law 8 kHz) | partial | needs Twilio + a public tunnel; not exercised by tests |
| Delivery mode **send** (Twilio SMS) | partial | needs Twilio credentials; `save`/`print` work offline |
| MRZ scanner via tesseract.js (camera / upload / manual) | partial | parses the MRZ, then looks the CNP up in the seed table |
| ROeID login | demo-only | there is no ROeID integration; it maps a persona name to a seeded citizen |
| OTP login with `MOCK_OTP=1` | demo-only | accepts the literal `123456`; off by default in code |
| `POST /demo/reset`, three pre-seeded personas | demo-only | |
| MSW frontend mocks | partial | cover the REST surface, **not** `/agent/chat/stream` |
| Row-level security policies | demo-only | defined, but the backend connects as owner and bypasses them |

---

## What's demo-only

Naming these plainly, because each one looks finished from the outside and is
not. None of them is hidden — they are all one grep away — but a reader
shouldn't have to grep.

**There is no ROeID integration.** `POST /auth/login-roeid` takes a persona
name (`maria-ionescu`, `andrei-popa`, `elena-dumitru`), looks up a hardcoded
CNP in `backend/app/auth.py`, and finds the matching seeded citizen. A real
integration would be an OAuth flow against the ROeID broker. The MRZ path
(`POST /auth/login-mrz`) does genuinely parse the machine-readable zone
client-side, but then it, too, only matches against the three seeded rows.

**`MOCK_OTP=1` is an authentication bypass.** It skips Twilio and accepts the
literal code `123456` for any challenge. It is **off by default in code** —
`docker compose` turns it on explicitly for the demo stack, and a deployment
that forgets the variable fails closed rather than open.

**There is no citizen registry.** Everything runs against three citizens
seeded by `migrations/002_seed_data.sql`. There is no sign-up, no identity
proofing, no way to add a fourth person short of writing SQL.

**Nothing is submitted anywhere.** "Delivery" means the PDF is stored and a
reference number of the form `CV-XXXX` is generated from the document UUID.
No primărie receives anything; the number is not a real registration number.

**Row-level security is decorative.** `migrations/004_rls_policies.sql`
defines per-citizen policies keyed on Supabase's `auth.uid()`, which is NULL
for a backend connection. The backend's role (`egata_app`, or the owner on
older setups) passes them through: `migrations/014` gives `egata_app` an
explicit allow-all policy. Authorization is application-level
(`_require_owner` in `backend/app/documents.py`, the conversation checks in
`backend/app/agent.py`). The policies would start mattering the day a client
talked to the database directly, which nothing does. What the database
itself *does* enforce for `egata_app` is the ledger: SELECT only, appends
only through `append_ledger()`.

**The PDF is not digitally signed.** No key signs it; there is no PAdES /
eIDAS signature and no seal a third party could validate. What exists: the
PDF is served through short-lived HMAC-signed (local) or Supabase-signed
*links*, and the ledger records the SHA-256 of the exact bytes stored, so a
PDF swapped in storage afterwards no longer matches its ledger row. A
qualified signature is on the roadmap and needs a trust-service provider.

**The ledger is tamper-evident, not tamper-proof.** What holds:

- Rows are hash-chained, and each is **Ed25519-signed** with a key kept
  outside the database. Someone who can write to Postgres but does not hold
  the key cannot produce a rewritten chain that verifies against the
  published public key.
- The backend's own role cannot INSERT into, change or truncate the ledger,
  or drop its triggers. It appends only through `append_ledger()`.
- A citizen can verify everything independently (`verify_ledger.py`, or the
  documents drawer in the browser) and keep a **signed receipt** of the
  current head (`--save-receipt`). If a later export no longer contains that
  head, the receipt proves the rewrite, and the operator cannot deny having
  signed it.

What doesn't hold:

- Whoever holds the **signing key** (the operator) can still rebuild and
  re-sign history. Only citizens holding earlier receipts would notice.
- Cutting rows off the end of a chain is invisible without a receipt.
- There is no external anchor. Periodically timestamping chain heads with an
  RFC 3161 TSA, or publishing them somewhere the operator doesn't control, is
  the recommended next step.
- The database owner or a superuser can still bypass everything at the SQL
  level. The point is that the application and its credential cannot. That
  includes `ledger_legacy_watermark` (`migrations/016`): an owner who raises
  it gets the backend to sign rows up to the new mark at its next start.
  Once an upgraded deployment has signed its history, nothing below the
  mark is unsigned, so this only matters for rows the owner appends.

**The reminders worker runs in-process, but is replica-safe.** `APScheduler`
runs inside each FastAPI process. Each tick takes a Postgres advisory lock,
so with several replicas only one works through the pending events and the
others skip that tick. Conversation turns are serialized the same way, with
a per-conversation advisory lock held for the turn. The review gate ("the
citizen confirmed the form") lives on the session row. Nothing that has to
be consistent across replicas is kept in process memory any more.
`DISTRIBUTED_LOCKS=0` falls back to in-process locks (unit tests).

---

## Architecture at a glance

```
                ┌──────────────────────────────────────────────────┐
                │  Next.js 15 · React 19 · Zustand · Tailwind      │
   Browser ────►│  /  ·  /login  ·  /home  ·  /req/[id]  ·  /doc   │
   (voice+text) │  ChatSurface ─ RightPane ─ Widgets ─ DocsDrawer   │
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
       Azure OpenAI   │   Azure VoiceLive   Twilio    Postgres │
       (gpt-5-mini +  │   (gpt-realtime,    (Verify, │ + pgvector
        embed-3-large)│    24 kHz PCM16)    Media)   │ (local or Supabase)
                      │                              │ PDFs: volume or
                      │                              │ private bucket
```

---

## Repository layout

```
backend/
  app/                 FastAPI routers, agent engine, tools, ledger, pdf, voice bridges
  migrations/          001…011 SQL migrations (schema, RLS, ledger fn, sessions, RAG)
  procedures/          23 JSON procedure definitions (fields, templates, next_steps)
  scenarios/           5 multi-step real-life scenarios (in-scope + external steps)
  institutions/        17 external-institution definitions (ANAF, ANEVAR, …)
  templates/           LaTeX templates (.tex) + base.tex + assets/
  scripts/             bootstrap_local_db, index_rag, export_openapi, …
  tests/               22 pytest modules (state machine, ledger, storage, PDF, end-to-end)

frontend/
  app/                 Next.js App Router (/, /login, /home, /req, /doc, /p, /r)
  components/          ChatSurface, RightPane, widgets/, MrzScanner, KioskShell, …
  lib/                 api.ts, sseChat, voiceWs, accessibilityStore, sessionStore, …
  mocks/               MSW handlers + fixtures (offline-capable frontend)
  e2e/                 Playwright specs

contracts/openapi.yaml OpenAPI 3.1 spec exported from FastAPI
docs/superpowers/      Design specs + four implementation plans + execution roadmap
docs/archive/          Superseded docs from the Gemini-era architecture
.github/workflows/     CI: pytest · ledger-vs-Postgres · vitest + tsc · pdflatex
docker-compose.yml     Full stack: Postgres+pgvector, migrate, backend, frontend
```

See `docs/superpowers/specs/2026-05-23-egata-design.md` for the full product +
architecture spec.

---

## Quick start

### The short version

```bash
git clone https://github.com/Bogzx/eGata && cd eGata
docker compose up --build
```

Open <http://localhost:3000>. Nothing else to configure: compose brings up
Postgres+pgvector, applies the migrations, seeds three citizens, and stores
PDFs on a local volume. No Supabase project, no cloud database, no API key.

**What works with zero configuration:** login (persona → OTP `123456`) ·
profile · the 23-procedure catalogue · **text chat with the offline agent** ·
creating and filling a document · real `pdflatex` rendering · save/print
delivery · the audit ledger and its timeline · reminders.

The offline agent (`backend/app/offline_agent.py`) is a deterministic script,
not an LLM, and its first reply says so: it finds the procedure by keyword
search over a local index the `migrate` step builds, confirms it, asks for
the missing fields one at a time, and walks review and delivery through the
same tools, state machine, PDF and ledger as the LLM agent. Try *"vreau să-mi
schimb domiciliul"*, *"am pierdut buletinul"* or *"ce proceduri sunt?"*.

**What needs a key:** the LLM agent (free-form conversation, paraphrases the
keyword search misses) and voice. See [Turning the LLM on](#turning-the-llm-on).

### Turning the LLM on

```bash
cp .env.example .env
# fill AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY
docker compose up -d --build
docker compose run --rm migrate python -m scripts.index_rag   # ~28 embedding calls
```

With a key set, `AGENT_BACKEND=auto` (the default) switches the chat to the
LLM and search to the Azure index; `AGENT_BACKEND=offline` keeps the script.
Every vector records the model that built it and search only reads the
current model's rows (`migrations/012`), so the local and Azure indexes live
side by side. Re-index after changing `AZURE_OPENAI_EMBED_DEPLOYMENT` — two
Azure deployments are not told apart.

### Running it without Docker

Prerequisites: Python 3.12, Node 20+, `pdflatex` on PATH (TeX Live or
MiKTeX), and a Postgres 14+ with the `vector` and `pgcrypto` extensions —
either a local one (`docker compose up -d db` gives you one on `:5432`) or a
Supabase project.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp ../.env.example .env                                # set SUPABASE_DB_URL at minimum
python -m scripts.bootstrap_local_db                   # migrations + seed + offline index; safe to re-run
python -m scripts.index_rag                            # Azure index — only if you have a key
uvicorn app.main:app --reload --port 8000
```

Verify:

```bash
curl http://localhost:8000/health        # {"status":"ok","service":"egata-backend"}
curl http://localhost:8000/healthz       # dependency report (Postgres, keys, agent backend); always 200
```

Frontend:

```bash
cd frontend
npm install --legacy-peer-deps
cp .env.local.example .env.local
npm run dev                                            # http://localhost:3000
```

### Demo walk-through

1. Open `http://localhost:3000` → **Intră în cont**
2. Pick persona **Maria Ionescu** → **Login cu ROeID**
3. OTP code: `123456` (accepted while `MOCK_OTP=1`)
4. `/home`: pre-seeded documents + 2 reminders
5. **Începe o cerere nouă** → type *"vreau să-mi schimb domiciliul"*
6. Confirm match → agent fills auto-known fields, asks via inline widgets for the rest
7. Once required fields are set, the **save / send / print** delivery buttons appear
8. After delivery, the ref number (`CV-XXXX`) appears and the ledger records the event
9. Open **Documentele mele** and click the document: its audit history, re-verified
   in your browser (WebCrypto), with the PDF's SHA-256 and the head hash to keep

### Frontend-only dev (no backend)

Set `NEXT_PUBLIC_USE_MOCKS=1` and run `npm run dev`. MSW serves the REST
surface from `frontend/mocks/handlers.ts` — `/auth`, `/citizens`,
`/procedures`, `/documents`, `/reminders` — with the same three personas as
the seeded backend.

It does **not** cover `/agent/chat/stream`, `/agent/widget-result` or
`/scenarios/*`. Those fall through (`onUnhandledRequest: "warn"`) to the real
backend carrying a mock JWT it rejects, so **the chat does not work in mocks
mode**. Use this for component and layout work, not for the agent flow. Same
caveat is in `frontend/.env.local.example`.

---

## Feature surface

### Identity & authentication

- **`POST /auth/login-roeid`** — **mock** ROeID broker. Takes a persona name,
  maps it to a hardcoded CNP, finds the seeded citizen, issues a challenge.
  There is no ROeID integration; see [What's demo-only](#whats-demo-only).
- **`POST /auth/login-mrz`** — MRZ-derived login. The frontend's `MrzScanner`
  component uses **tesseract.js** to OCR the back of the CI in three modes
  (camera, upload, manual entry) — see `frontend/components/MrzScanner.tsx`.
- **`POST /auth/otp`** — challenge + 6-digit code → JWT. Real OTP goes through
  **Twilio Verify**; `MOCK_OTP=1` accepts the static code `123456` for anyone,
  which is why it defaults to off.
- JWTs are HS256, 24 h TTL by default, issued by `app.security.mint_access_token`.
- All authenticated routes accept the JWT as `Authorization: Bearer <token>`.
- The profile keeps the address as one string (`current_address`);
  `app/address.py` splits it into `strada`, `numar`, `bloc`, `scara`, `etaj`,
  `apartament`, `localitate`, `judet`, `sector`, `cod_postal` at seed time
  (`bootstrap_local_db`) and at every login, storing the parts with the
  string they came from. Autofill then fills those fields instead of asking.
  It's conservative: a part is taken only when labelled or in street
  position, and the county only from `jud.` or a county seat. Explicit
  attributes win, and an edited address is re-parsed.
- A `conversation_id` or `document_id` sent to `/agent/chat*`,
  `/agent/widget-result` or the voice socket must belong to the caller
  (403 / close 4403 otherwise); ownership is checked before any work starts.

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

**Backends** (`AGENT_BACKEND`): the Azure OpenAI LLM, or the offline
scripted agent (`app/offline_agent.py`). Both drive the tools above through
the same dispatcher; `/healthz` reports which one is active.

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
   - Only Twilio can open it: the webhook verifies `X-Twilio-Signature`
     (and without `TWILIO_AUTH_TOKEN` never reveals the stream URL), and the
     TwiML carries a 2-minute HMAC token bound to the CallSid that the socket
     checks in the `start` frame before starting a (billed) VoiceLive session.

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

- **`backend/institutions/` (17 files)** — external bodies (ANAF, ANEVAR,
  AJOFM, banca, casa-pensii, CNAS, DGASPC, diriginte-șantier, DRPCIV, instanță,
  notariat, OCPI-ANCPI, ONRC, SPCLEP-MAI, spital-medic, auditor-energetic,
  stare-civilă). Each
  carries a `note_ai_cannot_complete` string that bubbles to the UI when the
  agent surfaces a redirect.

**RAG (`backend/app/embeddings.py`)** — two embedders into one 768-d
pgvector column (`rag_entries`): `text-embedding-3-large` reduced via the
`dimensions` parameter, or the offline lexical embedder
(`app/local_embeddings.py`: hashed diacritic-folded words, stems and
trigrams). `EMBEDDINGS_BACKEND` picks one; the local index is rebuilt by
`scripts.bootstrap_local_db`, the Azure one by `python -m scripts.index_rag`.

### Documents, PDF & delivery

Full document lifecycle is auditable end-to-end:

| Step | Endpoint | Ledger event |
|---|---|---|
| Create draft | `POST /documents` (or the agent's `start_procedure`, which also prefills profile fields) | `doc_created` |
| Patch fields | `PATCH /documents/{id}/fields` — validated against the schema (unknown field, bad option, non-scalar or >2000 chars → 422) | — |
| Draft complete | when the last required field (with `applies_if`) is filled, via PATCH or `set_field` | `completed_draft` |
| Render PDF | `POST /documents/{id}/generate-pdf` | `pdf_generated` (with `pdf_sha256`, `fields_sha256`) |
| Deliver | `POST /documents/{id}/deliver` (`save` / `send` / `print`) — needs every required field and a PDF rendered from the current fields, else 422 / 409 | `delivered` |
| Inspect chain | `GET /documents/{id}/ledger` | (read-only verify) |

A finalized document is frozen: PATCH, generate-pdf and deliver return 409,
and the agent's `set_field` refuses it.

**PDF pipeline** (`backend/app/pdf.py`): LaTeX template + `{{ field }}`
placeholders → every value sanitized and escaped → `pdflatex` subprocess →
object storage → **short-lived signed URL** (the link is signed; the PDF is not).

Field values come from citizens and from the model, so they are treated as
hostile. All ten TeX specials are escaped, so `\input`, `\write18` or `^^`
escapes cannot be formed; whitespace is collapsed (a blank line inside
`\underline{}` used to abort three templates); control characters,
pictographs and letters the preamble cannot set (CJK, Cyrillic, …) are
folded to a base letter or `?` rather than failing the render. `pdflatex`
runs with `-no-shell-escape` and kpathsea `openin_any=p` / `openout_any=p`,
so even a template bug could neither run a program nor read outside its
build directory. A failed render returns a PII-free error; the TeX log,
which echoes field values, stays in the server log.

The completed forms carry full name, CNP and home address, so the bucket is
private and links expire after 15 minutes. Two storage backends, same
contract (`backend/app/storage.py`):

- `local` (compose default) — a Docker volume, served by `GET /files/pdf`
  behind an HMAC over the object path and an expiry. No Supabase needed.
- `supabase` — a **private** bucket, links via `create_signed_url`.

Nothing persists a URL. `documents.pdf_url` holds the storage object path and
a fresh signature is minted per response, so a link's lifetime is decided when
it is handed out rather than baked into a row that outlives it. Ledger
payloads record the object path, never a credential-bearing link.

Every template is rendered through real `pdflatex` in CI, with values full of
LaTeX metacharacters and injection attempts (`backend/tests/test_template_rendering.py`), and
`backend/tests/test_template_field_parity.py` asserts each procedure's field
schema matches its template's placeholders in both directions.

A **preview PDF without persisting a draft** is available via
`GET /procedures/{id}/preview-pdf` — used by the right-pane "Vezi documentul"
button for citizens who want to see the form before starting.

**Delivery modes**:

- `save` — store in the citizen's "My documents" list.
- `send` — Twilio SMS with a link to the PDF (uses `TWILIO_PHONE_NUMBER`).
- `print` — return URL + a printable view; useful in **kiosk mode**.

### Hash-chain audit ledger

Every state-changing event is appended to the `ledger` table via the Postgres
`append_ledger()` function (migrations `003` + `009`):

```
row_hash = sha256(event_type || payload_hash || prev_hash || ts_iso)
```

- `payload_hash = sha256(canonical_json(payload))` — keys sorted, no
  whitespace, UTF-8, `ensure_ascii=False` (Romanian characters survive verbatim).
- `prev_hash` = tip of the chain for **that (citizen, document) pair**, which
  is the same slice `GET /documents/{id}/ledger` reads back and verifies.
  Events with no document (reminders) form one per-citizen chain. Every chain
  starts at the all-zero genesis hash (a protocol constant; it used to be a
  setting that, if changed, broke every verification).
- `pdf_generated` carries `pdf_sha256` (the stored bytes) and `fields_sha256`
  (the values rendered), binding the ledger to the document's content.
- Nothing hash-shaped crosses the wire. The function receives the canonical
  JSON and derives prev_hash, both hashes and the timestamp itself, so a
  caller cannot store a hash that disagrees with its payload.
- Append-only: `UPDATE`/`DELETE`/`TRUNCATE` are rejected by triggers, and the
  backend's role `egata_app` has only SELECT on `ledger`. Appends go through
  `append_ledger()`, which is `SECURITY DEFINER` with a pinned `search_path`,
  and whose EXECUTE is revoked from PUBLIC (on Supabase, that also closes it
  to the `anon` REST role). `POST /demo/reset` appends a `demo_reset` marker
  rather than deleting.
- **Signatures** (`migrations/014`, `backend/app/ledger_signing.py`). In the
  same transaction as each append, the backend signs
  `canonical_json({v, type: "egata-ledger-head", key_id, citizen_id,
  document_id, row_id, row_hash})` with Ed25519. `row_hash` commits to every
  earlier row, so each signature attests the whole chain up to that row.
  Signatures live in the append-only `ledger_signatures` table. The private
  key comes from `LEDGER_SIGNING_KEY` (PEM or base64 seed) or
  `LEDGER_SIGNING_KEY_FILE`, never from the database. In dev it is generated
  on first start with a loud warning. Public keys, including retired ones
  listed in `LEDGER_RETIRED_PUBLIC_KEYS`, are served unauthenticated at
  `GET /.well-known/egata-ledger-keys.json` and embedded in every ledger
  response. Rows from before signing existed are signed at the next backend
  start (`ledger_signatures.signed_at` shows when), but only up to the
  watermark `migrations/016` recorded: a later row without a signature was
  not appended by the backend, stays unverifiable, and is reported as an
  ERROR at every start. (Before 016, a restart signed whatever unsigned rows
  it found, including one appended with just the database password.)
- `GET /documents/{id}/ledger` returns the rows — with each `payload` and
  `hashed_at`, the exact timestamp string inside `row_hash` — **and** a
  `verified: bool` recomputed server-side. The documents drawer does not rely
  on that flag: `frontend/lib/ledgerVerify.ts` re-derives every hash and checks
  every Ed25519 signature in the browser (WebCrypto). It shows the result, the
  signing key, the PDF fingerprint and the head hash. The server flag is only
  a fallback when WebCrypto is unavailable.
- Don't take the server's word for it:

  ```bash
  python backend/scripts/verify_ledger.py --api http://localhost:8000 \
      --token "$JWT" --document <id> --pdf cerere.pdf \
      --public-key <base64 key you got independently> --save-receipt receipt.json
  # later: … --receipt receipt.json   → fails with "HISTORY REWRITTEN" if the
  #                                      signed head is gone
  # or offline: python backend/scripts/verify_ledger.py saved-ledger.json --pdf cerere.pdf
  ```

  Standard library only — Ed25519 included — and no `app` imports: a second
  implementation of the format. Without `--public-key` / `--keys-file` it uses
  the key embedded in the export and says so, which only proves the export is
  self-consistent. Exit 0 when every hash and signature checks out and the PDF
  matches.
- Seven event types: `doc_created`, `completed_draft`, `pdf_generated`,
  `delivered`, `redirected`, `reminder_created`, `demo_reset`.

Scope note: this is tamper-**evident**, not tamper-proof — see
[What's demo-only](#whats-demo-only).

Tests: canonical JSON stability, tamper detection and broken-link rejection
(`test_ledger.py`); two interleaved documents each verifying on their own
(`test_ledger_chain_scope.py`); the verifier script against honest, edited,
truncated and PDF-swapped exports (`test_verify_ledger.py`); and the same
against a real Postgres in CI, which is the only way to check that the
timestamp string the database hashes and the one Python rehashes are
byte-identical (`test_ledger_postgres.py`, `test_api_postgres.py`).

### Proactive reminders worker

`backend/app/worker.py` boots an **APScheduler** background job inside the
FastAPI lifespan that polls the `pending_delivered_events` SQL view every
`REMINDERS_POLL_SECONDS` (default 5), under a cluster-wide advisory lock so
one replica does each tick. For each new `delivered` ledger row, it:

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

- **`POST /demo/reset`** — deletes a citizen's documents and reminders,
  appends a `demo_reset` marker to the (append-only) ledger, then re-applies
  their seeded reminders. Guarded by `DEMO_RESET_TOKEN`; unset = always 401,
  so a production deploy is safe by default.
- `DemoResetButton.tsx` — floating button in the bottom corner when
  `NEXT_PUBLIC_DEMO_MODE=1`.
- **MSW mocks** (`frontend/mocks/`) — `/auth`, `/citizens`, `/procedures`,
  `/documents`, `/reminders`. **Not** `/agent/chat/stream`, so the chat does
  not work under `NEXT_PUBLIC_USE_MOCKS=1`.

---

## HTTP / WebSocket API

Routes mounted in `backend/app/main.py`. Run `python -m scripts.export_openapi`
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
| POST | `/documents/{id}/generate-pdf` | Compile LaTeX → store → return a signed URL |
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
| GET | `/files/pdf/{citizen}/{file}` | Signed PDF download (local storage backend only) |
| POST | `/demo/reset` | Clear documents/reminders, mark the ledger, reseed |
| GET | `/health` | App-level health |
| GET | `/healthz` | Dependency report (Postgres, keys, active agent/embeddings backend); always 200 |

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

`.env.example` at the repo root is the single canonical reference — there is
no second one under `backend/`. Every variable has a working default in
`docker-compose.yml`, so a `.env` is optional. Highlights:

| Variable | Purpose |
|---|---|
| `SUPABASE_DB_URL` | Postgres connection string. The only database variable that is ever required |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Only for `STORAGE_BACKEND=supabase` |
| `STORAGE_BACKEND` | `local` (volume + signed `/files/pdf` links), `supabase` (private bucket), or `auto` |
| `PDF_STORAGE_DIR` | Where the local backend keeps PDFs |
| `PUBLIC_BASE_URL` | Browser-reachable backend URL; local signed PDF links are built from it |
| `AGENT_BACKEND` | `auto` (LLM if an Azure key is set, else offline) · `offline` · `azure` |
| `EMBEDDINGS_BACKEND` | `auto` · `local` (offline lexical index) · `azure` |
| `AZURE_OPENAI_*` | LLM chat (`gpt-5-mini`) + embeddings (`text-embedding-3-large`) |
| `AZURE_VOICELIVE_*` | Realtime voice (`gpt-realtime`, `gpt-4o-mini-transcribe`) |
| `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | Parallel Speech SDK for streaming user transcript partials |
| `JWT_SIGNING_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRES_SECONDS` | Token signing (`openssl rand -hex 32`) |
| `MOCK_OTP` | `1` skips Twilio and accepts `123456` — an auth bypass. **Defaults to `0`** |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_VERIFY_SERVICE_SID`, `TWILIO_PHONE_NUMBER` | Real SMS + voice |
| `ALLOW_ORIGINS` | CORS allow-list (comma-separated; covers `:3000/:3001/:3030` by default) |
| `DEMO_RESET_TOKEN` | Required header for `/demo/reset` (else 401) |
| `REMINDERS_POLL_SECONDS` | Worker tick interval (default `5`) |
| `LOG_LEVEL` | `INFO` default; `DEBUG` traces every audio chunk |
| `APP_DB_PASSWORD` | Login for `egata_app`, the least-privilege backend role (set by `scripts.bootstrap_local_db`) |
| `LEDGER_SIGNING_KEY`, `LEDGER_SIGNING_KEY_FILE` | Ed25519 key that signs ledger rows (PEM or base64 seed; file generated in dev) |
| `LEDGER_RETIRED_PUBLIC_KEYS` | Comma-separated base64 public keys of rotated-out signing keys |
| `DISTRIBUTED_LOCKS` | `1` (default): Postgres advisory locks serialize conversation turns and the reminders worker across replicas; `0`: in-process only |
| `LOG_REDACT_PII` | `1` (default) masks CNPs, e-mails and phone numbers in every log line; `0` for local debugging |
| `SENTRY_DSN` | Optional — if set, FastAPI integration is wired |
| `NEXT_PUBLIC_USE_MOCKS` | `1` runs the frontend offline with MSW |
| `NEXT_PUBLIC_API_BASE_URL` | Backend base URL for the frontend |
| `NEXT_PUBLIC_DEMO_MODE` | `1` enables the persona dropdown + demo reset button |

---

## Running tests

```bash
cd backend  && pytest                       # offline: no database, no pdflatex, no keys
cd frontend && npm run test                 # Vitest
cd frontend && npx tsc --noEmit             # typecheck
cd frontend && npm run e2e                  # Playwright — needs a running stack (see below)
```

Three kinds of backend test are opt-in and skip by default, because they need
something the machine may not have. CI runs all of them:

```bash
RUN_PDF_TESTS=1 pytest tests/test_template_rendering.py    # needs pdflatex

# needs Postgres+pgvector with migrations applied:
#   docker compose up -d db && SUPABASE_DB_URL=... python -m scripts.bootstrap_local_db
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/egata
pytest tests/test_ledger_postgres.py tests/test_api_postgres.py tests/test_offline_agent_postgres.py
```

`.github/workflows/ci.yml` runs five jobs on every PR: backend ruff + strict
mypy + pytest (`app/` is mypy-clean; `python -m scripts.mypy_baseline` fails on
any finding not in `mypy-baseline.txt`, which only holds old test/script code
and should only ever shrink);
the ledger, document-API and offline-agent suites against a
`pgvector/pgvector:pg16` service; frontend `tsc --noEmit` + vitest; all 23
templates through real `pdflatex`; and Playwright against the full
`docker compose up` stack with no keys (the offline agent answers the chat).
Locally: `E2E_BASE_URL=http://localhost:3000 API_BASE=http://127.0.0.1:8000 npm run e2e`
with the compose stack up.

Backend coverage:

- `test_sessions_state_machine.py` — every legal/illegal transition
- `test_agent_tools_dispatch.py` — state-gating refusal logic
- `test_ledger.py` — canonical JSON, tamper detection, broken-link rejection
- `test_ledger_chain_scope.py` — two interleaved documents, each chain
  verifying on its own; caller-supplied hashes refused
- `test_ledger_postgres.py` — the same against a real Postgres, plus the
  append-only trigger (opt-in)
- `test_api_postgres.py` — the document lifecycle through the real routes,
  SQL, ledger function and storage: schema validation, delivery
  preconditions, frozen finalized documents, cross-citizen access, and the
  result checked with `scripts/verify_ledger.py` (opt-in)
- `test_offline_agent_postgres.py` — whole offline-agent conversations the
  way the frontend drives them, from request to a verified ledger (opt-in)
- `test_verify_ledger.py` — the standalone verifier against honest, edited,
  truncated and PDF-swapped exports
- `test_conversation_ownership.py` — foreign conversation / document ids
  refused on every agent endpoint
- `test_document_guards.py`, `test_log_redaction.py`, `test_offline_mode.py`
  — PATCH validation and frozen documents; PII masking in logs; backend
  selection, local-search quality on the real catalogue, the agent's parsing
- `test_storage_privacy.py` — private bucket, bounded TTL, no public URLs
- `test_local_storage.py` — signed-link tampering, expiry, cross-document
  reuse and path traversal all refused
- `test_template_field_parity.py` — all 23 procedures: field set ↔ placeholder
  set, in both directions
- `test_template_rendering.py` — all 23 templates through real `pdflatex`
  with LaTeX-hostile and injection input; absolute `\input` refused (opt-in)
- `test_config_defaults.py` — settings fail closed
- `test_prompt_tool_references.py` — every tool a system prompt names exists
- `test_applies_if.py` — conditional field expression evaluator
- `test_pdf.py` — LaTeX escaping, sanitizing of hostile input, sandboxed
  and PII-free pdflatex failures
- `test_embeddings.py` — cosine, source text, registry validation
- `test_procedure_state.py` — required/applicable field computation
- `test_reminders_selection.py` — applies_if filtering for next_steps
- `test_scenarios.py`, `test_institutions.py` — catalog integrity
- `test_security_token.py` — JWT mint/verify round-trip
- `test_end_to_end_mocked.py` — login → otp → me → create → patch →
  generate-pdf → deliver → ledger
- `test_smoke_deployed.py` — production smoke against a live URL (opt-in)
- `test_health.py` — health endpoint

---

## Docker compose

```bash
docker compose up --build
# frontend: http://localhost:3000
# backend:  http://localhost:8000   (health-gated)
# db:       localhost:5432          (postgres/postgres, database `egata`)
```

Four services:

| Service | What it does |
|---|---|
| `db` | `pgvector/pgvector:pg16` on a named volume; healthchecked |
| `migrate` | one-shot — applies `migrations/*.sql`, seeds three citizens, builds the offline search index, prints what does and doesn't work without keys. Idempotent |
| `backend` | waits for `migrate` to succeed; connects as `egata_app`; PDFs on the `egata-pdfs` volume, the ledger signing key on `egata-keys` |
| `frontend` | waits for backend health |

Procedures, scenarios, institutions and templates are bind-mounted, so editing
a JSON schema or a `.tex` only needs a backend restart, not a rebuild.

Everything has a default, so no `.env` is required. Copy `.env.example` to
`.env` to change ports, plug in Azure keys (the chat then switches from the
offline agent to the LLM), or switch `STORAGE_BACKEND` to `supabase`.

Reset the whole thing: `docker compose down -v` (drops the database, PDFs
and the dev signing key).

### Upgrading an existing database

`migrations/014` (ledger signatures + the `egata_app` role) is additive.
Nothing has to change for an existing deployment to keep working.

- **Compose:** `docker compose up --build`. `migrate` applies 014 and gives
  `egata_app` a login from `APP_DB_PASSWORD`. The backend reconnects as
  `egata_app`, generates a signing key into the `egata-keys` volume and signs
  the existing history on first start (the rows `migrations/016` marked as
  predating signatures, and no others).
- **A backend connecting as the owner** (e.g. a Supabase project using the
  `postgres` user) keeps working unchanged: owners bypass the new grants and
  policies. It signs the existing history at its next start and logs
  `INSECURE CONFIG: the backend connects to Postgres as …`. To finish the
  upgrade:
  1. `APP_DB_PASSWORD=<strong password> SUPABASE_DB_URL=<owner url> python -m scripts.bootstrap_local_db`
     (sets the login; re-run to rotate it).
  2. Point the backend's `SUPABASE_DB_URL` at `egata_app` (on Supabase's
     pooler the user is `egata_app.<project-ref>`). Keep the owner URL for
     migrations and `scripts.index_rag` only.
  3. Set `LEDGER_SIGNING_KEY` from your secret store and restart. The startup
     log names the key id, which is what `/.well-known/egata-ledger-keys.json`
     publishes.
- **If `CREATE ROLE` is not allowed** (some managed Postgres plans), 014 logs
  a notice, skips the role, and everything runs as before as the owner.
  Signatures still apply.
- **Key rotation:** add the old *public* key (from the well-known endpoint)
  to `LEDGER_RETIRED_PUBLIC_KEYS`, set the new `LEDGER_SIGNING_KEY`, restart.
  Old rows keep verifying.

---

## Roadmap

- **Wave 1 (shipped)** — Plans 1 (frontend) + 2 (backend) — auth, procedures,
  documents, PDF, delivery, ledger, mocks.
- **Wave 2 (shipped)** — Plans 3 (agent + Azure VoiceLive) + 4 (proactive
  worker, accessibility final pass, demo polish).
- **Checkpoint 2 (shipped)** — full agent-driven flow + reminders worker +
  a11y certification.
- **Post-hackathon (not started)** — multi-language (en/hu/de), real ROeID
  broker integration, signed PDF (eIDAS QES), per-procedure analytics
  dashboard, a staff panel for adding procedures without editing JSON and
  writing LaTeX.

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
- `docs/archive/` — AUDIT_CHAT, AUDIT_TOOLS, PITCH_QA, frontend-spec.
  All four describe the superseded Gemini architecture and disagree with
  this README on counts and endpoints; each carries a header saying so.

---

## License

MIT — see [LICENSE](LICENSE).

---

**Made with care for `primărie` queues that didn't have to be.**
