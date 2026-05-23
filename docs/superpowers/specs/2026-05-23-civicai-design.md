# CivicAI — Design Spec

- **Date:** 2026-05-23
- **Event:** Cluj Hackathon 2026 — Digital Romania / NoQueue.Done
- **Team:** 4 (Backend · Voice/AI · Frontend/Design · PM/Domain/Pitch)
- **Tagline:** *Spune-i ce ai nevoie. Îți spune ce acte îți trebuie. Le și completează cu tine.*
- **Status:** Design approved, ready for implementation plan

---

## 1. Problem & product

Interacting with a Romanian primărie is the canonical bad UX of public life. Citizens don't know which forms apply to their situation, fill them by hand with errors, return three times to fix the same paperwork, and queue for clerks who spend most of their day re-explaining identical procedures. Existing portals like ghiseul.ro handle payments but not the "what do I even need?" layer where most of the friction lives.

**CivicAI** is a conversational, multi-channel civic agent for primărie procedures. It maps a citizen's plain-language life event to the exact pre-filled documents they need — and proactively surfaces follow-up steps that the citizen would otherwise discover too late. Scope is primărie-only by design; for needs outside that scope (ANAF, CNAS, DRPCIV, etc.), the agent recognizes and elegantly redirects, with full integration on the roadmap.

## 2. Win strategy & scoring alignment

The hackathon scores 100 points across 5 criteria. Each design decision below maps to specific points:

| Criterion | Pts | How CivicAI scores |
|---|---|---|
| Social impact | 25 | Universal pain point; accessibility-first (voice-only mode, simple-language toggle); citizen-bypasses-queue at primărie. |
| UX / Usability | 25 | Next.js 15 + Tailwind + shadcn + framer-motion; three completion modes (manual, on-screen, vocal); live form preview; AA-compliant; modern aesthetic deliberately unlike existing state apps. |
| Technical feasibility | 20 | Mature components (Gemini Live, Supabase, Twilio, pgvector); declarative procedure registry; hash-chain ledger; deployed live by Hour 5. |
| Working demo | 20 | At-desk, multi-device live demo with juror poke-list; demo seed-reset; mobile-hotspot fallback. |
| Coherence with Digital Romania vision | 10 | All six judge-graded principles addressed (Citizen-centric, Single Login, Proactive, Universally Accessible, Feasible Today, Human Language). |

**Headline angle (the line we want jurors saying):** *"The civic agent that thinks ahead for you."* Proactive is the principle most teams will miss; we lead with it.

**Tracks targeted:** Grand Prize, AI Civic Agents (special), Killed the Queue Award, Most Brutal Fix.

## 3. System architecture

One Next.js app. Four surfaces. One agent core. One database. Two LLM access patterns (conversational + background).

```
Browser (Next.js 15)
  |  WebRTC audio  ──>  Gemini Live  <── function calls ──>  FastAPI
  |  HTTP state    ──>  FastAPI                              |
  |                                                          |
  +─ MRZ scan (tesseract.js + mrz, in-browser)              |
                                                              |
Twilio (phone) ── Media Streams WS ──> FastAPI ── audio bridge ──> Gemini Live
                                                              |
FastAPI ── Postgres (Supabase EU)
       ── Storage (Supabase: PDFs)
       ── LaTeX compile (pdflatex subprocess)
       ── Background worker (reads next_steps, writes reminders)
```

Two agent contexts share the same Gemini Live + Pydantic AI skeleton:
- **Conversational agent** — full tool set (lookup_procedure, set_field, generate_pdf, deliver, find_redirect, set_reminder). Runs on browser surfaces.
- **Phone agent** — RAG-only, tools disabled. Info-only mode.
- **Background agent** — fires after each delivered document. Reads procedure's `next_steps`, evaluates `applies_if` against citizen `attributes`, writes `reminders` rows.

## 4. Surfaces

All routes live in the same Next.js 15 codebase.

| Surface | Route | Form factor | Auth |
|---|---|---|---|
| Kiosk | `/?mode=kiosk` (auto-detected by viewport + touch + idle timer) | Tablet ≥10" landscape, full-screen | MRZ scan + SMS OTP |
| Citizen home | `/` | Mobile-first, responsive desktop | Mocked ROeID button + SMS OTP (demo persona chooser in dev builds only) |
| Procedure flow | `/req/[procedureId]` | Chat panel + live form preview side-by-side | Same as home |
| Document detail | `/doc/[docId]` | Status + audit timeline + PDF download | Same as home |
| Phone | Twilio inbound number | Voice-only | None (info-only) |

No clerk dashboard (out of scope per project decision).

## 5. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | **Next.js 15** (App Router) + Tailwind + shadcn/ui + **framer-motion** | shadcn AA-default; framer-motion respects `prefers-reduced-motion` |
| Backend | **FastAPI** (Python) + **Pydantic AI SDK** + **OpenAI SDK** | OpenAI SDK retained for embeddings (text-embedding-3-small) and fallback realtime if Gemini disappoints |
| DB | **Supabase** Postgres EU region + **pgvector** | RLS for citizen-scoped data |
| Storage | Supabase Storage | PDFs |
| LLM + Voice | **Gemini Live** (realtime speech-to-speech) | Primary path; OpenAI Realtime as fallback |
| Phone | **Twilio** Media Streams | EU number preferred; UK +44 fallback |
| PDF | **LaTeX templates** + `pdflatex` subprocess from FastAPI | WeasyPrint HTML→PDF as fallback if LaTeX deploy is problematic |
| ID scan | `mrz` npm package + `tesseract.js` + `getUserMedia` | All browser-side; ID image never persisted |
| Hosting | Vercel (frontend) + Railway (FastAPI) + Supabase Cloud (DB) | EU regions throughout |
| Embeddings | OpenAI `text-embedding-3-small` | Best Romanian quality at low cost |

**Stack defense for jurors (in case asked why not the sanctioned stack):** *"Gemini Live gives true realtime Romanian speech-to-speech under 400ms; sanctioned alternatives still pipeline at 800ms+. We prioritized voice quality."*

## 6. Identity & auth (ROeID mock)

The participant guide explicitly directs teams to **simulate ROeID**. We do exactly that with the simplest possible mock that still demonstrates the principle.

**Citizen-side login flow:**
- `/login` page renders a single **"Login cu ROeID"** button.
- A "Demo persona" chooser (dropdown of seeded citizens) is rendered ONLY when `NEXT_PUBLIC_DEMO_MODE=1`. Hidden in production builds.
- Click → FastAPI receives the persona ID (or the default demo citizen) → issues SMS OTP to that citizen's seeded phone (a team member's phone, for SMS to actually arrive during the demo).
- Citizen enters 6-digit code → Supabase Auth session created.

**Kiosk auth flow:**
- `/?mode=kiosk` shows two paths: "Login cu ROeID" (same as above) OR "Scanează buletinul".
- MRZ path: camera capture via `getUserMedia` → in-browser `tesseract.js` OCR + `mrz` parser → resolved CNP → SMS OTP to citizen.phone → session.
- The camera image bytes never leave the browser. Only the parsed text fields (CNP, names, DOB) are sent to FastAPI for citizen lookup.

**Phone:** No login. Inbound calls land on the phone agent in info-only mode.

**Demo seeding:** 2-3 citizens pre-loaded in Supabase with:
- Rich `attributes` JSONB (owns_vehicle, marital_status, has_children, employer, medic_familie, accessibility preferences).
- 1-2 existing `documents` (one delivered, one draft).
- 1-2 active `reminders` already on the home screen.

This ensures the citizen home has content the moment a juror logs in.

## 7. Data model (Supabase Postgres)

```sql
citizens (
  id            uuid PK,
  cnp           text UNIQUE,
  nume          text,
  prenume       text,
  data_nasterii date,
  email         text,
  phone         text,
  attributes    jsonb DEFAULT '{}',
  created_at    timestamptz
)

documents (
  id            uuid PK,
  citizen_id    uuid FK -> citizens.id,
  procedure_id  text,           -- key into procedure registry
  status        text,           -- draft | finalized   (clerk states accepted/rejected out of scope)
  fields        jsonb,          -- collected field values
  pdf_url       text NULL,      -- supabase storage key
  delivery      text NULL,      -- save | send | print  (null while draft, set at finalization)
  ref_number    text NULL,      -- short hash of id, shown to citizen at "send" confirmation
  created_at    timestamptz,
  delivered_at  timestamptz NULL
)

ledger (
  id            bigserial PK,
  citizen_id    uuid,
  document_id   uuid NULL,
  event_type    text,           -- doc_created | completed_draft | pdf_generated | delivered | redirected | reminder_created
  payload_hash  text,           -- sha256(canonical_json(payload))
  prev_hash     text,
  row_hash      text,           -- sha256(event_type || payload_hash || prev_hash || iso_ts)
  created_at    timestamptz
)

reminders (
  id              uuid PK,
  citizen_id      uuid FK,
  trigger_doc_id  uuid NULL,
  kind            text,         -- in_scope_procedure | external_redirect
  procedure_id    text NULL,
  redirect_target text NULL,    -- ANAF | CNAS | DRPCIV | ...
  title           text,
  due_date        date NULL,
  status          text,         -- pending | started | done | dismissed
  created_at      timestamptz
)

procedures_embeddings (
  procedure_id  text PK,
  embedding     vector(1536),    -- text-embedding-3-small
  source_text   text             -- title + description + synonyms + sample_queries
)
```

RLS: citizens see only their own rows. Service role bypasses for FastAPI background work.

## 8. Procedure registry

Procedures are **declarative JSON files** in `backend/procedures/*.json`. Adding a procedure = adding a JSON file + a LaTeX template + re-embedding. No code changes.

```jsonc
// backend/procedures/schimbare-domiciliu.json
{
  "id": "schimbare-domiciliu",
  "title": "Schimbare domiciliu",
  "description": "Înscrierea mențiunii de stabilire a domiciliului",
  "scope": "primarie",
  "category": "evidenta-persoanelor",
  "synonyms": ["mutare", "schimbat adresa", "domiciliu nou"],
  "sample_queries": [
    "vreau să-mi schimb domiciliul",
    "m-am mutat la altă adresă",
    "trebuie să schimb adresa pe buletin"
  ],
  "fields": [
    { "name": "nume_complet",   "label": "Nume complet",   "source": "id_scan|profile",  "required": true },
    { "name": "cnp",            "label": "CNP",            "source": "id_scan|profile",  "required": true, "redact_in_voice": true },
    { "name": "adresa_curenta", "label": "Adresă curentă", "source": "id_scan|profile",  "required": true },
    { "name": "adresa_noua",    "label": "Adresă nouă",    "source": "ask",              "required": true },
    { "name": "tip_proprietate","label": "Tip proprietate","source": "ask",
      "options": ["proprietar", "chiriaș", "găzduit"], "required": true },
    { "name": "motivul",        "label": "Motivul cererii","source": "ask",
      "suggest_default": "Schimbare loc de muncă", "required": false }
  ],
  "template": "schimbare-domiciliu.tex",
  "next_steps": [
    { "kind": "in_scope_procedure", "procedure_id": "preschimbare-ci",
      "deadline_days": 15, "title": "Preschimbare carte de identitate" },
    { "kind": "external_redirect",  "redirect_target": "DRPCIV",
      "deadline_days": 30, "title": "Actualizare certificat înmatriculare auto",
      "applies_if": "owns_vehicle == true" },
    { "kind": "external_redirect",  "redirect_target": "CNAS",
      "title": "Actualizare medic de familie" },
    { "kind": "external_redirect",  "redirect_target": "ANAF",
      "title": "Notificare schimbare domiciliu fiscal" }
  ]
}
```

**Deep-demo procedure (1):** `schimbare-domiciliu` — complete LaTeX template, complete `next_steps`, validated end-to-end.

**Known procedures (2, JSON-stubbed with title/description/sample_queries; agent can describe them and start the form but LaTeX template may be a stub):**
- `certificat-fiscal`
- `preschimbare-ci`

**Redirect targets (recognized, agent hands off):**
- `ANAF` — taxes, fiscal residence
- `CNAS` — medical record, family doctor
- `DRPCIV` — vehicle registration

**`applies_if`** is a simple expression evaluated against `citizen.attributes`. Examples: `owns_vehicle == true`, `marital_status == "căsătorit"`, `has_children == true`.

## 9. RAG (procedure lookup)

When the citizen describes a need, the agent uses **RAG over the procedure registry** rather than relying on the LLM's general knowledge:

1. `lookup_procedure(query: str)` tool is called by the agent.
2. FastAPI embeds the query with OpenAI `text-embedding-3-small`.
3. Cosine top-3 against `procedures_embeddings`.
4. Returns: `{procedure_id, title, score}` for top-3, plus a `redirect_candidate` if top score < threshold (≈0.6).
5. Agent presents the best match for citizen confirmation, or offers a redirect with explanation.

Embeddings are computed at deploy time from each procedure's `title + description + synonyms + sample_queries`. Re-embedding triggered when JSON files change.

**Fallback if pgvector unavailable:** in-memory NumPy cosine — fine at 7 procedures.

## 10. Conversation loop (the citizen's experience)

After login (the citizen profile is now loaded into the session):

1. Citizen describes need (voice or text). Gemini Live → `lookup_procedure(query)` → RAG retrieves top match. Agent confirms: *"Înțeleg că vrei să-ți schimbi domiciliul. Continuăm?"* If no match → redirect offer.

2. On confirmation, agent loads procedure JSON + citizen profile. **Auto-fills** all `source: "id_scan|profile"` fields silently. Then renders:
   ```
   Schimbare domiciliu

   Am completat din profilul tău:
    ✓ Nume complet: Maria Ionescu
    ✓ CNP: 2851...   ✓ Data naștere: 14.03.1985
    ✓ Adresă curentă: Str. Avram Iancu 5, Cluj

   Mai am nevoie de 3 lucruri.
   Cum vrei să le completăm?

   [ Manual ]   [ Pe ecran ]   [ Vocal ]
   ```

3. **Three completion modes** (see §11). Live form preview updates as fields fill.

4. Light validation per field: required, options, simple regex. **No** per-field ledger entries — batch at milestones (`doc_created`, `completed_draft`, `pdf_generated`, `delivered`).

5. **Interactive completion** — preview pane shows the form taking shape in real-time. User can tap any field to edit, switch modes mid-flow, or correct an auto-filled value.

6. When all required fields collected, agent presents the PDF preview and three buttons:
   - **Save as PDF** (download to device, ledger entry `delivery=save`)
   - **Send to primărie** (writes ledger entry `delivery=send`, sets `documents.status='delivered'`, shows confirmation screen with reference number)
   - **Print** (browser print dialog on kiosk, ledger entry `delivery=print`)

7. After delivery, **background agent** fires. Reads procedure's `next_steps`, evaluates `applies_if` against citizen `attributes`, writes `reminders` rows. Home screen shows new cards with framer-motion entry animation — *"Following your domicile change, here's what's next."*

## 11. Completion modes

The auto-fill summary screen lets the citizen choose how to fill the **remaining** fields. All three modes share form state and the live preview.

| Mode | Behavior |
|---|---|
| **Manual** | Plain text inputs render for remaining fields. No agent prompts. User submits when ready. |
| **Pe ecran** | Agent guides field-by-field with tap-buttons for `options`, text inputs with inline suggestions, no mic required. |
| **Vocal** | Agent speaks each prompt; user replies by voice; live transcript visible; tap-to-edit any field at any time. |

Mode switcher always visible in the corner. Any auto-filled field is tap-editable at any time.

## 12. Live form preview

A styled HTML mockup that closely approximates (not pixel-perfect) the LaTeX-generated PDF's layout. Renders in real-time as fields populate. Right pane on desktop/kiosk; collapsible below chat on mobile.

The actual LaTeX→PDF compile happens **once** at "Save / Send / Print" click — not on every field update. The HTML mockup is the visual stand-in throughout. At the moment of compile, the final PDF replaces the mockup in the preview pane and the delivery choice buttons activate.

Framer-motion animates: field highlights on focus, autofill reveal pulse, mode-switch transitions.

## 13. Voice pipeline (Gemini Live)

**Browser path (kiosk + mobile + desktop):**

```
Browser  ──ephemeral session request──>  FastAPI
FastAPI  ──Gemini Live session token────────────────>  returns to browser
Browser  <══WebSocket (audio + function calls)══>  Gemini Live
Browser  ──HTTP w/ short-lived JWT──>  FastAPI tool endpoints
                                       (lookup_procedure, set_field,
                                        generate_pdf, deliver, find_redirect,
                                        set_reminder)
```

- Browser holds the WebSocket directly to Gemini Live — no server hop on audio path = lowest latency.
- Function calls dispatched by the browser SDK to FastAPI HTTP endpoints with signed JWT.
- Romanian voice config in Gemini Live session params.
- Barge-in (user interruption) handled natively by Gemini Live.
- Mic-permission denied → text-input fallback in same chat panel; no flow change.

**Twilio path (phone, info-only):**

```
PSTN caller ──> Twilio ──Media Streams WS──> FastAPI bridge ──WS──> Gemini Live
                                              (G.711 ↔ PCM transcode)
```

- ~150 LOC Python bridge in FastAPI relays inbound audio bytes to Gemini Live and Gemini's audio back to Twilio.
- Function calls disabled on phone variant — pure RAG-over-procedures + general info.
- **Demo-day fallback** if the bridge misbehaves: TwiML `<Say>` plays *"Vizitați civicai.ro pentru asistență completă"* in Romanian.

## 14. PDF generation + delivery

**Primary path: LaTeX**
- One `.tex` template per procedure in `backend/templates/`.
- Jinja2-style placeholders for fields (Python string substitution; LaTeX-safe escaping for special chars: `&`, `%`, `$`, etc.).
- `pdflatex` subprocess invoked from FastAPI (Railway Dockerfile based on `texlive/texlive:latest`).
- Output → Supabase Storage; URL returned to browser.

**Fallback path: WeasyPrint**
- If `pdflatex` deploy is problematic, switch the renderer to WeasyPrint (HTML+CSS→PDF, pure Python).
- Each procedure's template becomes an HTML+CSS file styled to match the official form.
- Less faithful to "real Cluj form" look but reliable.

**Delivery actions (chosen by citizen after preview):**
- **Save**: PDF download via browser; `delivery='save'`; ledger entry.
- **Send**: PDF stored, `documents.status='delivered'`, `delivery='send'`, ledger entry, reference number displayed (and SMS-confirmed to citizen.phone).
- **Print**: Browser print dialog (kiosk has a real printer attached for demo); `delivery='print'`; ledger entry.

## 15. Ledger (simulated distributed ledger)

The participant guide explicitly requires data integrity via blockchain or simulated ledger.

**Hash-chain implementation:**
- Genesis row written at first deploy: `prev_hash = "0x00...00"`.
- Each new entry: `payload_hash = sha256(canonical_json(payload))`, `row_hash = sha256(event_type || payload_hash || prev_hash || iso_ts)`, `prev_hash` = previous row's `row_hash`.
- Postgres function `append_ledger(...)` refuses insert if `prev_hash` doesn't match the actual last row's `row_hash` — guarantees append-only at the DB level.
- Periodic verifier (background worker) walks chain end-to-end; mismatched hashes set the doc's audit timeline status to ⚠️ instead of ✓.

**Events recorded:**
- `doc_created` (procedure session begun)
- `completed_draft` (all required fields collected)
- `pdf_generated` (template compiled to PDF)
- `delivered` (save / send / print chosen)
- `redirected` (agent referred citizen to external institution)
- `reminder_created` (background agent wrote a proactive nudge)

**Citizen-visible UI:** `/doc/[docId]` shows an "Istoric integritate" timeline — vertical list of events with timestamps and a green ✓ at the end ("Chain verified") or red ⚠️ if the verifier detected tampering.

## 16. Proactive layer

The headline differentiator. Hits the "Proactive" judge-graded principle that most teams will miss.

**After delivery, the background agent:**
1. Reads the just-delivered procedure's `next_steps` array.
2. For each step, evaluates `applies_if` (if present) against citizen `attributes`.
3. Filters in only applicable steps.
4. Creates `reminders` rows:
   - `kind = "in_scope_procedure"` → primărie procedure the agent can handle next; renders as *"Start now"* card.
   - `kind = "external_redirect"` → out-of-scope; renders as *"You'll also need to talk to {target}"* card with contact info, a deadline if any, and a roadmap note about future integration.

**Pre-seeded reminders for demo:** 2-3 active reminders on the demo citizen so the home screen is rich from first login (e.g., *"Cartea de identitate expiră în 23 de zile — vrei să programezi preschimbarea?"*).

**Home screen layout:**
```
Bună ziua, Maria.

Următoarele acțiuni recomandate:           [3 active]
┌──────────────────────────────────────────────┐
│ ⚠ Cartea de identitate expiră în 23 de zile │
│   [ Programează preschimbarea ]              │
└──────────────────────────────────────────────┘
┌──────────────────────────────────────────────┐
│ ↪ După schimbarea domiciliului trebuie să-ți│
│   actualizezi certificatul auto la DRPCIV   │
│   (termen: 30 zile)        [ Vezi cum ]     │
└──────────────────────────────────────────────┘

Documente recente
- Cerere schimbare domiciliu (trimisă acum 2 ore) ✓
- Adeverință venit (în lucru — completare 60%)

[ + Start o cerere nouă ]
```

## 17. Accessibility

WCAG AA is mandatory per the participant guide; we go further by leveraging voice as a first-class accessibility surface.

**Baseline AA:**
- shadcn/ui components used as-is (AA-default).
- Tailwind config audited for 4.5:1 contrast on all text.
- Full keyboard navigation; focus rings visible.
- ARIA labels on all icon-only buttons; semantic landmarks (`<nav>`, `<main>`, `<section>`).
- `prefers-reduced-motion` respected by framer-motion (animations disabled when set).
- CI runs Lighthouse + axe-core; PR-blocking on AA violations.

**Voice-only mode** (`attributes.accessibility.voice_only`):
- Toggle in settings, persists per citizen.
- Every screen narrates state changes audibly (*"Câmpul «adresă nouă» a fost completat cu Str. Plopilor 15"*).
- Mic stays hot throughout; submission confirmed audibly.
- Agent narrates option lists before pausing for input.

**Simple-language toggle** ("Explică-mi mai simplu", `attributes.accessibility.simple_language`):
- Toggle injects a system-prompt directive into the agent context (both conversational and phone variants): *"Răspunde la nivelul unui copil de clasa a 6-a, fără jargon administrativ."*
- Static UI strings have `.standard` / `.simple` variants in the i18n file; the active variant is selected by the toggle.

**Kiosk accessibility shortcut:** A prominent "Pentru persoane cu nevoi speciale" corner button immediately surfaces voice-only + simple-language + large-text in one tap.

## 18. Build order (phased timeline)

Total budget ~36h. Claude-Code-driven, realistic human-attention time ~26-30h.

| Phase | What | Hours | Blocks |
|---|---|---|---|
| 0 | Setup: repos, Supabase EU, Railway/Vercel/Twilio dev accounts, Gemini + OpenAI keys, Cluj forms downloaded, pgvector verified | 1.5 | All |
| 1 | Foundation deployed: Next.js skeleton on Vercel, FastAPI on Railway, Supabase schema + RLS + tables, 2-3 seeded citizens with rich `attributes`. Both reachable from public URLs. | 4 | All |
| 2 | Identity + Profile: Supabase Auth, ROeID mock login button, demo persona chooser, MRZ scanner in-browser, SMS OTP via Twilio Verify, kiosk-mode detection, profile page. | 3 | Agent |
| 3 | Procedure registry + RAG: 7 procedure JSON files (1 deep + 6 known), embed via OpenAI `text-embedding-3-small`, pgvector retrieval, `lookup_procedure` endpoint. | 3 | Agent |
| 4 | Agent — text-first: Pydantic AI agent with tools, Romanian system prompt, three completion modes, live HTML form preview. **End-to-end test by typing before adding voice.** | 6 | Voice, PDF |
| 5 | Voice — Gemini Live (browser): ephemeral-token endpoint, browser WS to Gemini Live with Romanian voice config, function-call dispatch, barge-in, mic-denied fallback. | 4 | Polish |
| 6 | PDF + delivery + ledger: LaTeX template for schimbare-domiciliu, `pdflatex` subprocess in FastAPI, three delivery actions, hash-chain writes at milestones, per-doc audit timeline UI. | 4 | Proactive |
| 7 | Proactive layer: background worker, `next_steps` evaluation with `applies_if`, `reminders` rows, home-screen cards with framer-motion, "Start now" → starts next procedure. | 3 | — |
| 8 | Phone — Twilio bridge to Gemini Live: ~150 LOC FastAPI WS bridge, info-only, redirect-on-out-of-scope. **Cut to static TwiML `<Say>` if running short.** | 3 | — |
| 9 | Accessibility passes: voice-only toggle, simple-language toggle + Gemini prompt directive, axe-core fixes, `prefers-reduced-motion`, large-text mode. | 2 | — |
| 10 | Polish + demo prep: framer-motion transitions, demo seed-reset button, dry runs from 3 devices, juror script with poke-prompts. | 3 | — |

**Cut order if behind:** phone bridge → 2 of 6 known-procedure JSONs → voice-only mode → simple-language toggle → reduce delivery options to 1.

**Never cut:** proactive layer, ledger. Both are load-bearing for scoring.

## 19. Team allocation

In Claude-Code-driven mode, each member owns a domain — sets requirements, reviews PRs, tests, makes product calls. Claude Code does the typing.

| Member | Domain |
|---|---|
| **Backend** | FastAPI + Supabase + Railway. Owns schema, ledger, RAG plumbing, Twilio bridge, deploys. |
| **Voice/AI** | Gemini Live + Pydantic AI agent + Romanian prompts. Owns tool definitions, system prompts, voice config, embedding pipeline. |
| **Frontend/Design** | Next.js 15 + Tailwind + shadcn + framer-motion. Owns all citizen surfaces, kiosk mode, live form preview, completion-mode UX, accessibility audit, Vercel deploys. |
| **PM/Domain/Pitch** | Real Cluj form acquisition (primariaclujnapoca.ro), procedure JSON authoring, LaTeX templates, demo data design, demo script + juror poke-list, accessibility QA. |

Backend + Voice partition the FastAPI codebase by file. Frontend + PM partition the Next.js codebase. Reviews via PRs into a shared branch.

## 20. Risks + mitigations

| # | Risk | Mitigation |
|---|---|---|
| 1 | Gemini Live Romanian voice quality unknown | Test in Hour 0 with 5 sample queries. If poor → swap to OpenAI Realtime, same WS pattern. |
| 2 | Twilio + Gemini Live bridge fragile | Phone is most disposable surface. TwiML fallback playing static Romanian message. |
| 3 | MRZ scan unreliable | "Enter CNP manually" fallback always visible. Pre-test in venue lighting. |
| 4 | `pdflatex` install on Railway | Custom Dockerfile from `texlive/texlive:latest`, built + pushed Hour 1. Fallback: WeasyPrint. |
| 5 | Gemini Live tool-call timeout (>2s) | Aggressive caching, precomputed embeddings, warm session at login. Tool endpoints ack optimistically; long work runs in background. |
| 6 | pgvector not enabled in Supabase EU | Verify Hour 0. Fallback: NumPy cosine in-memory (fine at 7 procedures). |
| 7 | Demo data burned by previous juror | "Reset demo" dev-panel button re-seeds citizen + clears ledger + restores reminders. ~10s reset between jurors. |
| 8 | Venue WiFi congestion | Mobile-hotspot backup + smoke-test on cellular. |
| 9 | Stack-defense ("why not Claude/ElevenLabs?") | One-liner: *"Gemini Live gives true realtime Romanian speech-to-speech under 400ms; sanctioned alternatives still pipeline at 800ms+."* Bring side-by-side audio sample. |
| 10 | Time blow-up on phone or PDF | Use cut order above. Never cut proactive or ledger. |

## 21. Demo plan (at-desk, multi-rotation)

Format: jurors rotate to our desk, ~10-15 min per visit. We demo with multiple devices live: tablet (kiosk), laptop (citizen mobile/desktop), phone (Twilio call).

**Walkthrough script (~5 min target):**
1. *"Iată ce vede cetățeanul când deschide aplicația acasă."* — citizen home with 2 proactive reminders + recent docs.
2. *"Acum imaginați-vă că este la primărie."* — switch to tablet in kiosk mode.
3. ID scan → SMS OTP → in. *"Vreau să-mi schimb domiciliul."* (spoken in Romanian).
4. RAG match confirmation → auto-fill from profile → choose "Vocal" mode.
5. Agent collects remaining fields via voice. Live form preview fills on screen.
6. Save / Send / Print choice (we click Send).
7. **Proactive nudge appears** on the citizen's mobile: *"După schimbarea domiciliului, trebuie să-ți actualizezi auto la DRPCIV (termen 30 zile)."*
8. Open doc detail → show audit timeline with ledger ✓.
9. Pick up the phone, dial Twilio number → agent answers in Romanian → ask *"De ce acte am nevoie pentru o adeverință de venit?"* — agent describes them.
10. *"Și pentru cei care nu pot vedea sau citi ușor:"* — toggle voice-only + simple-language → re-start a flow to show accessibility.

**Juror poke-list** (anticipated questions + prepared answers):
- *"Și pentru ANAF?"* → demonstrate redirect (*"ANAF nu e în scope-ul nostru — vă ducem la ghiseul.ro. Pe roadmap avem integrarea."*)
- *"Cum știți că documentul nu poate fi falsificat?"* → open audit timeline, explain hash chain.
- *"Poate să fie folosit de bunica mea?"* → demo voice-only + simple-language modes.
- *"Câte primării ar putea folosi asta mâine?"* → answer with Cluj-Napoca real forms anchor.
- *"De ce nu ați folosit Claude / ElevenLabs?"* → stack-defense one-liner above.

**Reset button** in dev panel restores demo state between juror rotations.

## 22. Open decisions

These are intentionally left to settle in-flight:

- **PDF renderer:** LaTeX (primary) vs WeasyPrint (fallback). Decision deadline: end of Phase 1. Test `pdflatex` in Railway Dockerfile; if it builds clean, stay LaTeX.
- **Voice provider final pick:** Gemini Live (primary) vs OpenAI Realtime (fallback). Decision deadline: end of Phase 5 Hour 1. Test 5 Romanian queries first; pick whichever sounds better.
- **Phone bridge included or replaced with static TwiML:** Decision deadline: Hour 30. If foundation/agent/PDF are wobbly, cut bridge to static message.
- **Number of "known" procedures actually shipped:** Target 6 stubs but acceptable to land 4. PM owns the cut decision.

## 23. Out of scope / roadmap

Explicitly **not** in the hackathon scope; mentioned in the pitch as roadmap:
- ANAF, CNAS, DRPCIV, ONRC, SPCEP integrations (redirect-only today).
- Real ROeID API integration (mocked today).
- Outbound SMS reminders (push-only today; reminders surface on home screen).
- Clerk-facing dashboard (not in this hackathon).
- Real e-signature for legally-binding submissions (uses simulated "send" today).
- National rollout / multi-primărie tenancy.
- Multi-language UI beyond Romanian (RO-only today; EN as roadmap).

---

## Appendix A — Agent system prompt (Romanian, draft)

```
Ești CivicAI, asistentul digital al primăriei. Vorbește simplu, prietenos, în română.
Scopul tău: să ajuți cetățeanul să completeze documente pentru primărie.

Reguli stricte:
1. Răspunzi DOAR pentru proceduri de primărie. Pentru altceva (ANAF, CNAS, DRPCIV),
   recunoaște și redirecționează: "Asta nu e treaba primăriei — vă rog vizitați ..."
2. Folosește profilul cetățeanului pentru auto-completare. Nu repeta informații
   pe care le ai deja.
3. Înainte de a completa un câmp, sugerează un răspuns implicit dacă există.
4. Nu menționa CNP-uri vocal. Spune doar "...CNP-ul tău" sau "..."ultimele 4 cifre".
5. La final, oferă cele trei opțiuni: Salvare PDF / Trimitere la primărie / Tipărire.
6. După livrare, descrie pașii următori cu termen și instituția responsabilă.

Stil: cald, fără jargon, propoziții scurte. Dacă utilizatorul a activat
modul „simplu", vorbește ca pentru un copil de clasa a 6-a.
```

## Appendix B — Useful repo layout

```
/
├── frontend/                 # Next.js 15 (Vercel)
│   ├── app/
│   │   ├── page.tsx          # Citizen home
│   │   ├── login/
│   │   ├── req/[id]/         # Procedure flow
│   │   └── doc/[id]/         # Document detail + audit timeline
│   ├── components/
│   │   ├── KioskShell.tsx
│   │   ├── FormPreview.tsx
│   │   ├── ChatPanel.tsx
│   │   ├── ProactiveCard.tsx
│   │   └── accessibility/
│   └── lib/
│       ├── gemini-live.ts    # WebSocket client + token fetch
│       ├── mrz.ts            # tesseract + mrz parser
│       └── api.ts            # FastAPI client
│
├── backend/                  # FastAPI (Railway)
│   ├── app/
│   │   ├── main.py
│   │   ├── auth.py           # ROeID mock + OTP
│   │   ├── agent.py          # Pydantic AI agent + tools
│   │   ├── procedures.py     # Registry loader + RAG
│   │   ├── pdf.py            # LaTeX compile
│   │   ├── ledger.py         # Hash chain
│   │   ├── reminders.py      # Background proactive worker
│   │   └── twilio_bridge.py  # Phone WS bridge
│   ├── procedures/           # *.json procedure registry
│   ├── templates/            # *.tex LaTeX templates
│   └── Dockerfile            # texlive base
│
└── docs/
    └── superpowers/specs/
        └── 2026-05-23-civicai-design.md  # this file
```
