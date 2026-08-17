> **Archived — describes a superseded architecture.**
>
> This document was written when eGata ran on a Gemini backend with a
> different set of HTTP endpoints. The agent now runs on Azure OpenAI through
> an in-process, state-gated tool dispatcher (`backend/app/session_engine.py`,
> `backend/app/agent_tools/`), and several endpoints referenced below no
> longer exist. Counts and status claims here also disagree with the current
> README. Kept for history; do not use it as a description of the system.

# eGata — Tool-Calling & Document Auto-Completion Audit

Audit date: 2026-05-23 (demo eve). Scope: the tool-calling subsystem + the
"user says a thing, doc opens, fields fill live, PDF delivered" flow.
Voice transport (WS bridge) is out of scope for this audit — but the
text-vs-voice split is squarely in scope.

---

## 1. Current architecture (as the code actually reads)

```
                  ┌──────────────────────────────────────────────┐
                  │  Browser (Next.js, zustand sessionStore)    │
                  │                                              │
                  │   Composer / ChatStream / RightPane          │
                  │           │              ▲                   │
                  │           │              │ rightPane.kind    │
                  │           ▼              │ swap              │
                  │   sendText / onWidget    │                   │
                  │           │     │        │                   │
                  └───────────┼─────┼────────┼───────────────────┘
                              │     │        │
            ┌──── text? ──────┘     │        │
            │                       │        │ applyToolResult()
            │  voice WS?            │        │ (refetch doc, transition)
            │       │               │        │
            │       │               │        ▲
            │       ▼               ▼        │
            │ POST /agent/voice/ws  POST /tools/{name}        ← path 1
            │ (Live, in-proc REGISTRY)  (legacy, JWT)         ← path 2
            │
            ▼
   POST /agent/chat/stream  ──► Gemini text  ─┐
   (SSE: delta, tool_call,                    │
    tool_result, done)                        │  REGISTRY[name](ctx, **args)
                                              ▼
                              ┌─────────── REGISTRY (in-proc) ────────────┐
                              │ lookup_procedure  set_field    deliver    │
                              │ propose_widget    generate_pdf set_remind │
                              │ find_redirect                              │
                              └────────────┬───────────────────────────────┘
                                           │
                                           ▼
        documents (Supabase) + reminders + ledger + storage(PDF)
                                           ▲
                                           │
                  /documents/{id}/fields, /generate-pdf, /deliver  ← path 3
                  (REST, called directly by ReviewPane/DeliveryPane/store)
```

How a turn actually flows today (text path):

1. User clicks "Începe" in MatchesPane / PlanPane (frontend) OR types into Composer.
2. `sessionStore.startProcedure(id)` is the ONLY way a `Document` row is born.
   It calls `POST /documents`, sets `activeDocId`, navigates to `/r/<id>`,
   transitions `rightPane` to `guide`. **The agent itself cannot create a
   document** — there is no `start_procedure` tool.
3. `sendText` POSTs to `/agent/chat/stream`. The store carries `activeDocId`
   and `conversationId` in the body. SSE frames flow back: `delta`, `tool_call`,
   `tool_result`, `done`.
4. Per tool call, store calls `applyToolResult(name, args, result)` which
   refetches the document and computes the rightPane state via
   `computeInitialRightPaneFrom(doc, procedure)`.
5. `propose_widget` returns a widget spec attached to the agent's final message
   bubble. The user clicks/picks. The picked value is sent back into the
   agent as **plain text** (`"Da"`, `"proprietar"`, `"2026-04-27"`). The agent
   must remember which widget it just proposed and call `set_field` itself.
6. When all required fields are filled, store flips rightPane to `review`.
   The user clicks "Generează PDF" in ReviewPane, which calls the REST
   endpoint `/documents/{id}/generate-pdf` directly — **the agent is bypassed**.
7. PdfPane → DeliveryPane → user clicks save/send/print → REST
   `/documents/{id}/deliver`. Agent bypassed again.
8. Background APScheduler worker reads the `delivered` ledger row, evaluates
   each procedure's `next_steps` against citizen.attributes via the
   `applies_if` mini-DSL, writes reminders. Agent never sees this.

Two parallel "voice" implementations exist:

* **Legacy** (`useVoiceAgent.ts` + `gemini-live.ts` + `/voice/session` + `/tools/*`):
  browser opens a direct WSS to Gemini Live, gets API key from the
  `/voice/session` POST, dispatches tool calls back over HTTPS to `/tools/{name}`
  signed with a tool JWT. The system prompt context preamble (citizen + doc
  state) is rendered once at session start.
* **New** (`useVoiceAgentBridge.ts` + `/agent/voice/ws` in `agent_voice.py`):
  browser opens a WS to our backend; backend opens Live to Gemini; tools
  dispatched in-process against `REGISTRY`. **The bridge does NOT call
  `_build_context_preamble`** — see `agent_voice.py:214-218` vs `agent.py:229-235`.
  It hits `build_system_prompt(...)` only. So in voice-bridge mode the
  agent has no per-turn doc state.

Three callable surfaces for "complete this document":

| Path | Where | Auth | Caller |
|---|---|---|---|
| In-process tools, agent loop | `app.tools.REGISTRY` | citizen JWT | `/agent/chat/stream`, `/agent/voice/ws` |
| HTTP `/tools/{name}` | `app.tool_dispatch` | tool JWT | legacy browser-direct Gemini Live |
| REST `/documents/{id}/...` | `app.documents` | citizen JWT | ReviewPane, DeliveryPane, store, e2e test |

The PDF + deliver logic exists in **TWO** places: `documents.generate_pdf`
(REST) and `tools.generate_pdf` (agent). They are almost-but-not-quite
identical — see §2 P0-3.

---

## 2. What's badly designed

### P0 — Architectural debt that will hurt the demo

#### P0-1. Agent cannot start a procedure. The whole "auto-open" flow is fake.

`backend/app/tools/lookup_procedure.py:32-70` returns matches but never
creates a document.
`frontend/lib/sessionStore.ts:303-326` (`applyToolResult` for
`lookup_procedure`) only sets `rightPane: { kind: "matches" }` or
`{ kind: "plan", scenarioId }`. **The user must then click "Începe"** in
`MatchesPane.tsx:93-96` or `PlanPane.tsx:90-95` to actually call
`startProcedure(procedureId)`.

What the user feels: they say "vreau să schimb domiciliul", the agent
replies "OK, am găsit procedura", but **nothing opens on the right**.
They have to click a card. The demo script says "user speaks → doc opens" —
this is one click of click-the-button-yourself away from being a lie.

Worse: in voice-only mode (`voiceOnly`), `ChatSurface.tsx:280` hides the
right pane entirely. There is no path to start a procedure by voice at all,
because the agent has no tool for it. **The voice-only happy path is broken
end-to-end.**

#### P0-2. `propose_widget` round-trip loses the field name; agent must guess.

`frontend/components/chat/widgets/ChoiceWidget.tsx:29-30` calls
`onSubmit(opt)` with just the option string. `ChatStream.tsx:97` forwards
the raw value. `ChatSurface.tsx:270-272`:
```ts
function onWidgetSubmit(_spec: WidgetSpec, value: string) {
  void onSendText(value);
}
```
The `WidgetSpec` (which knows `targetField`) is **discarded** — sent as
`_spec`, unused. The agent receives the bare value as a user message and has
to remember it had just proposed a choice widget for `tip_proprietate` so
it can now `set_field("tip_proprietate", "proprietar")`. With 6 fields and
3 widget types, Gemini will sometimes confuse which field the value belongs
to, especially after a barge-in or partial transcription. Already brittle
in text; in voice it will fail.

What the user feels: clicks "proprietar" → agent says "Bine, am notat
proprietar." → right pane shows nothing changed → confused user asks
"dar ce am notat?" → agent calls `set_field` on the wrong field → demo dies.

#### P0-3. Three code paths for the same operation. Subtle behavior drift.

* `tools/generate_pdf.py:40` does `missing = [...required...]` and **raises**
  before render.
* `documents.py:222-247` (`POST /documents/{id}/generate-pdf`) does NOT
  check required fields — it renders whatever's in `fields` and ships it.
  ReviewPane is the only place that gates by "all required filled" — purely
  client-side trust.
* `documents.patch_fields` (`PATCH /documents/{id}/fields`) silently writes
  arbitrary keys (no field-name validation against schema), while
  `tools.set_field` validates the field name AND the option list
  (`set_field.py:27-33`). ReviewPane calls patch_fields directly when the
  user manually edits a value, so the agent's validation is bypassed.

What the user feels: editing in ReviewPane silently accepts garbage. PDF
generation succeeds with empty required fields if the user clicks Review
→ Generează PDF directly via REST. Demo failure mode: agent fills 4/5
fields, user clicks Generează PDF, PDF appears with blank lines, looks broken.

#### P0-4. Voice bridge ships without doc/citizen context preamble.

`backend/app/agent_voice.py:214-218`:
```python
system_prompt = build_system_prompt(
    variant="conversational",
    simple_language=self.start_payload.simple_language,
    voice_only=self.start_payload.voice_only,
)
```
No `_build_context_preamble(citizen_id, document_id)` call. Compare
`agent.py:229-238` which DOES include preamble — the text agent gets
"Câmpuri completate: {...}, Câmpuri obligatorii rămase: [...]" every turn
but the voice agent gets only the static system prompt.

What the user feels in voice mode: agent re-asks "care e numele tău
complet?" even though `nume_complet` is already filled by id-scan default;
agent forgets which fields are still missing; says "este totul gata?" when
two fields are blank; tries to call `generate_pdf` prematurely.

#### P0-5. `ToolContext.document_id` is fixed at session start, never refreshed.

`agent_voice.py:206-209` builds `ToolContext` once with
`start_payload.document_id`. If the user starts the WS without a doc, then
clicks "Începe" mid-conversation, the new doc id never propagates to the
voice tool context. `set_field` will fail with `"document_id required"`
or write to the wrong doc.

`agent.py` is better — `ctx` is rebuilt per `chat_stream` request from
`req.document_id` (line 367-369), so each turn picks up the latest. But the
conversation history was created without doc context, so the model still
has stale history.

What the user feels: starts a procedure mid-voice → next utterance "adresa
nouă este Strada X" → `set_field` fails because voice ctx still has
`document_id=None`.

#### P0-6. Document lifecycle has three different "completed" notions.

* `documents.allRequiredFilled` (frontend, `rightPaneState.ts:7-15`) — used
  for `review` transition.
* `_all_required_present` (backend `documents.py:157-162`) — used by
  `patch_fields` to emit `completed_draft` ledger event.
* `tools/generate_pdf.py:40` — used by agent to refuse render.

All three agree on the predicate, but `applies_if`-style conditional fields
are not considered ANYWHERE. There's an `applies_if` evaluator
(`applies_if.py`) but it's only consumed by **reminders** post-deliver
(`reminders.py:103`). If a procedure had a field like
`"applies_if": "tip_proprietate == 'găzduit'"` for the `anexa_2_signer`
field, no part of the document fill loop would respect it.

Right now, only `next_steps` use `applies_if`. But the registry HAS no
conditional fields. So this is latent debt — it's not blowing up the demo
yet, but it's a footgun the moment we add a procedure with conditional
fields. Marked P0 because the team mentioned "test_applies_if.py" as a
thing to interrogate — answer is: the conditional logic exists, but it's
walled off from the agent loop.

### P1 — Debt that will hurt week 1 post-demo

#### P1-1. `_conversations` is process-local, unbounded by procedure boundary.

`agent.py:147` `_conversations: dict[str, list[Content]] = {}`. Single
worker fine. Multi-worker prod = lost sessions. `_MAX_CONVERSATIONS = 256`
evicts oldest, which is FIFO not LRU — a user mid-flow during a Monday
spike loses their context. Also: history is in Gemini's `Content` type,
not portable. The frontend's localStorage holds the rendered messages
(`sessionStore.ts:23` LS_MSG_KEY) — but those are display-strings, not the
agent's content history. **If the backend restarts, the agent's memory is
gone and the user is mid-flow.** Frontend localStorage isn't enough to
recover.

#### P1-2. Switching procedures resets `conversationId`.

`sessionStore.ts:151`: `startProcedure` does `conversationId: null`. A
scenario plan with 3 procedures = 3 cold-start conversations. The whole
point of `scenario_plan` is multi-procedure flow; this throws away that
context. The agent doesn't know that the citizen just finished
`schimbare-domiciliu` and is now in `preschimbare-ci`.

#### P1-3. Tool surface has redundant / missing tools.

* **Redundant**: `find_redirect` largely duplicates `lookup_procedure`'s
  out-of-scope detection (`procedures.py:25-29, 48-54` has the same hint
  table). Two tools, one decision.
* **Redundant**: `set_reminder` is callable by the agent but the system
  prompt §9 says "use ONLY on explicit citizen request" — and Plan 4's
  background worker creates reminders automatically post-deliver. The
  agent path is basically dead code.
* **Missing**: `start_procedure(procedure_id)` — the agent should be able
  to instantiate a doc.
* **Missing**: `submit_widget_value(widget_id, value)` — would let the
  frontend round-trip the widget through the agent as a structured event
  instead of a free-text user message.
* **Missing**: `get_doc_state()` or implicit per-turn snapshot — the agent
  has it as preamble, but only on a turn the user spoke. After a manual
  ReviewPane edit, the agent doesn't know until the next user turn.

7 tools, but the right shape is closer to **4 well-designed + 1 fast-path
mutation**:
1. `lookup_procedure` (could also auto-start when confidence > X)
2. `set_field` (validates schema)
3. `propose_widget` (asks structured question)
4. `complete_document` (renders PDF + delivers, single step)
5. `find_redirect` (small, kept)

`set_reminder` should be implicit (post-deliver, server-side).

#### P1-4. Tool dispatch duality is a liability.

`/tools/{name}` (HTTP) and in-process REGISTRY both call the same Python
functions, so logic doesn't diverge. BUT:

* Auth differs: HTTP path uses a separate tool-JWT minted by `/voice/session`
  (TTL 1800s, separate signing). If the citizen's main JWT is revoked, the
  tool JWT keeps working until expiry.
* Error handling differs: HTTP path returns 400 on `ValueError`, agent path
  embeds error in tool_result.
* Audit-log differs: HTTP path doesn't log to ledger the way the agent path
  could (and currently neither does).
* Once `useVoiceAgentBridge` is the default (NEXT_PUBLIC_VOICE_BRIDGE=1),
  the HTTP `/tools/*` endpoints are **dead code** kept alive only by the
  legacy `useVoiceAgent` hook.

If you ship voice-bridge for the demo, delete `tool_dispatch.py` and
`useVoiceAgent.ts` in week 1. Otherwise it's a hazard.

#### P1-5. PDF generation is split: ReviewPane uses REST, agent uses tool.

`ReviewPane.tsx:35-39` calls `api.generatePdf(doc.id)` directly. Agent
calls `tools.generate_pdf` via function call. Both end up in different
code paths — REST path skips the required-fields gate, tool path
enforces it. ReviewPane *also* checks `allRequiredFilled` on the frontend
to enable the button, but a sufficiently determined user (or a test, or a
voice user via "Generează PDF chiar dacă lipsesc câmpuri") can bypass.

#### P1-6. Conversation history persisted as raw `Content` objects.

`agent.py:147` stores Gemini `genai_types.Content`. They are not
JSON-serializable in the obvious way. If we ever want Redis-backed
multi-worker, we need a serializer. Currently fine for single-worker
hackathon scope but a Week-1 problem.

#### P1-7. `applies_if` exists but is invisible to the agent.

The DSL parses `owns_vehicle == true`. It's used post-deliver for
reminders. The agent's system prompt and the field schema don't mention
conditional fields at all. If we ever need "ask birth date only if
`marital_status == minor`" — currently impossible. The infra is built but
unwired.

### P2 — Cosmetic / nice-to-have

* `_FUNCTION_DECLS` in `agent.py` and `_BROWSER_FUNCTION_DECLS` in
  `agent_voice.py` are near-duplicates with minor Romanian-description
  differences. One should be the canonical source.
* `TOOL_SCHEMAS` in `frontend/lib/useVoiceAgent.ts:66-156` is a third
  copy of the same schema. Three sources of truth for one tool surface.
* `propose_widget` returns a `widget_id` UUID server-side
  (`propose_widget.py:53`) that the frontend never uses — frontend
  generates its own with `Math.random()` (`sessionStore.ts:466`,
  `ChatSurface.tsx:39`). The backend round-trip is purely ceremonial.
* `_FUNCTION_DECLS` use uppercase JSON-Schema types (`"OBJECT"`, `"STRING"`)
  while frontend uses lowercase. Both work for Gemini but inconsistency
  is a smell.
* `find_redirect` keyword list (`tools/find_redirect.py:30-49`) duplicates
  `REDIRECT_HINTS` in `procedures.py:25-29`.
* The text agent's "5-iteration" loop limit (`agent.py:277`, `agent.py:378`)
  is silent — if hit, returns "Am procesat câteva acțiuni. Vrei să
  continuăm?" with no diagnostic. Demo problem if the model loops on a
  bad widget.
* `strip_thinking` runs after delta accumulation — partial thinking blocks
  stream to the user mid-flight, then get scrubbed on done. Visible flicker.
* `applyToolResult` for `set_field` (sessionStore.ts:287-300) fetches the
  document a SECOND time after the agent's `set_field` already returned
  the updated doc. Wasted round-trip.

---

## 3. Restructure options

### Option A — Minimum (4-6h before demo, ~tonight)

**Goal**: make the happy path "I speak → doc opens → fields fill → PDF
delivered" actually work end-to-end without re-architecting.

Changes:

1. **Add `start_procedure(procedure_id)` tool** that calls
   `documents.insert_document(citizen_id, procedure_id)` and returns the
   new doc id + initial fields auto-filled from citizen profile. ~30 lines.
2. **Update `sessionStore.applyToolResult` for `start_procedure`**: navigate
   to `/r/<id>`, set `activeDocId`, set rightPane to `guide`. ~10 lines.
3. **Wire context preamble into `agent_voice.py`**. Copy the 30-line
   `_build_context_preamble` from `agent.py` and prepend to system prompt.
   Also: rebuild context preamble per-turn (currently once at session start
   only). For voice this is harder — Gemini Live system instructions are
   set at connect time. **Workaround**: when the agent's
   `_dispatch_tool` runs `set_field`/`start_procedure`, append a synthetic
   tool result note like `{state: {fields: {...}, missing: [...]}}` so the
   model sees it without re-setting system prompt.
4. **Fix widget round-trip**: in `ChatSurface.onWidgetSubmit`, replace
   `onSendText(value)` with a synthetic structured agent input — either
   call a new tool `submit_widget_value(target_field, value)` directly via
   the store, or prepend `"[widget=tip_proprietate] proprietar"` to the
   user message so the agent has the field hint without guessing. Demo-safe
   path: prepend hint string. ~5 lines in ChatSurface.
5. **Block `POST /documents/{id}/generate-pdf` if required fields missing**
   — add the same check `tools/generate_pdf.py:40` has. 3 lines in
   `documents.py:222`. Prevents the silent-bad-PDF demo failure.
6. **Auto-transition rightPane to `delivery` after PDF generated**, so the
   agent's `generate_pdf` tool result triggers the navigation. Currently
   ReviewPane has to drive it manually.

Risk: low. Each change is local and additive. The two highest-value items
(start_procedure tool + widget hint) take ~1h. The voice preamble fix is
~2h because of the Live SDK quirks.

Cost of NOT doing it: in voice mode, demo fails. In text mode, demo
requires the user to click "Începe" — explainable but ugly.

### Option B — Medium (1-2 day focused sprint, post-demo Sunday/Monday)

**Goal**: make the agent the single authority over the doc lifecycle.

Changes on top of Option A:

1. **Collapse tool surface to 5 tools**:
   - `lookup_procedure(query)` — RAG, returns matches (no plan); on
     confidence ≥ 0.75 auto-creates doc as a side-effect via internal call
     to `start_procedure`. Returns `{matches, opened_doc_id?}`.
   - `set_field(name, value)` — unchanged; tightened validation.
   - `propose_widget(type, question, options?, target_field?)` — unchanged
     but `target_field` becomes REQUIRED and the response includes a
     `widget_id` the frontend round-trips back as a structured event, not
     a free-text user message.
   - `complete_document(delivery)` — single tool replacing
     `generate_pdf` + `deliver`. Renders PDF, finalizes, returns
     `{pdf_url, ref_number}`. Pre-condition checked server-side: all
     required fields present, applies_if respected.
   - `find_redirect(query, target?)` — unchanged.
   - Remove `set_reminder` from agent surface; keep as internal
     post-deliver helper.

2. **Single source of truth for tool schemas**: generate
   `_FUNCTION_DECLS` for Python and `TOOL_SCHEMAS` for TS from a single
   JSON file (or a Pydantic model exported via `model_json_schema()`).

3. **Delete `/tools/*` HTTP path** + `useVoiceAgent.ts` + `voice.py` (the
   `/voice/session` endpoint). Voice bridge becomes the only voice path.

4. **Make widget submit a structured frame**: frontend posts
   `{type: "widget_result", widget_id, value, target_field}` directly to
   `/agent/chat/stream` (or to the WS); backend turns it into a synthetic
   tool result the agent sees, not a user message. Agent doesn't have to
   guess.

5. **Persist conversations to Postgres**, keyed by
   `(citizen_id, conversation_id)`. Cross-procedure continuity in
   scenarios: `conversation_id` survives `startProcedure`.

6. **Per-turn context refresh in voice bridge**: after each agent
   tool-call, send a `Content(role="user", parts=[Part.from_text(
   "[STATE] fields={...}, missing=[...]")])` with `turn_complete=False`
   so the model sees current state without re-doing system prompt.

7. **Conditional fields (`applies_if`) wired into doc-fill loop**: a field
   with `applies_if` becomes "required iff condition true". The system
   preamble computes "missing required" with applies_if applied. Then
   procedures can express "ask anexa_2_signer only if tip_proprietate ==
   'găzduit'" naturally.

Risk: medium. Each piece is a clean refactor. Total work ~12-16h focused.
Worth doing the week of the demo aftermath because it unblocks shipping
new procedures without per-procedure UI work.

### Option C — Big (rebuild-from-scratch ambition; 1-week project)

**Goal**: the agent owns a state machine; the UI is a reactive view of it.
The current code is a chat agent that occasionally writes to a doc. Flip it.

Core idea: **introduce a `Session` aggregate** with explicit states
(`exploring`, `confirming`, `filling`, `reviewing`, `delivered`), each
state owning a set of permitted tools. The agent calls a `transition(...)`
tool to move states; the frontend rightPane is a pure function of
(state, doc). No rightPane local state. No frontend-only transitions
(currently `ReviewPane`/`DeliveryPane` move themselves).

```
Session:
  citizen_id
  conversation_id        ← stable across procedures within a scenario
  scenario_id?           ← if a scenario plan is being executed
  step_index?            ← position within scenario
  active_document_id?    ← current doc, None when exploring
  state: {exploring, confirming_match, filling, reviewing, delivered}
  pending_widgets: [{widget_id, target_field}]  ← so frontend submits
                                                  structured event
```

Tool surface becomes state-machine actions:
- `transition_to(state, **payload)` — single tool, dispatched by state.
- `set_field(name, value)` — only valid in `filling`.
- `propose_widget(...)` — only valid in `filling` and `confirming_match`.

Frontend:
- `applyToolResult` deleted. `sessionStore` syncs to a WebSocket-pushed
  `session` snapshot on every server change. Right pane becomes pure
  view of state.
- All "Generează PDF" / "Trimite" buttons disappear from frontend (or
  become hints that emit a structured `intent` event to the agent). User
  drives via chat; agent owns the transitions.

Validation:
- Field schemas become Pydantic models per procedure (replacing the
  current JSON `fields` list). `set_field` validates against the
  Pydantic model and returns `{ok: true, applies_if_changes: {...}}` so
  conditional fields can re-evaluate.
- `applies_if` first-class for fields, not just next_steps.

Persistence:
- `Session` is a Postgres row, not in-memory.
- Conversation history JSON-serialized per turn, keyed by session.
- Multi-worker safe out of the box.

Voice/text symmetric:
- `/session/stream` is a single SSE+WS endpoint that handles both. Voice
  delta streams in; text deltas stream in; tool calls dispatch identically.
- The "voice bridge" and "text streaming" become two thin transports
  feeding the same `Session.step()` engine.

Risk: high. This is a rewrite of the agent loop, frontend store, and
tools. ~5 working days. Worth it if eGata is going to be a real product
because the current shape will rot fast as you add procedures.

What you gain: every procedure is just a JSON schema + a `.tex` template.
No frontend changes per procedure. The agent's behavior is predictable
because permitted tools are gated by state. Conditional fields and
multi-procedure scenarios work natively.

---

## 4. Recommendation

**For the 2026-05-24 demo: Option A only.** The five items in §3 Option A
are ~6h total, each is local and reversible, and each prevents a specific
demo-failure mode I traced in the audit. Specifically:

1. `start_procedure` tool: fixes P0-1 (voice-only demo broken).
2. Widget hint string in user message: mitigates P0-2 (widget round-trip
   misroutes value).
3. Voice bridge preamble: fixes P0-4 (voice agent doesn't know doc state).
4. PDF generation server-side validation: prevents P0-3 demo embarrassment.
5. Doc-context refresh on `set_field` in voice: partial fix for P0-5.

Do NOT attempt Options B or C tonight. They are correct, but the demo is
in 24h and every line moved is a risk. **The current architecture is
shippable as a demo with these 5 fixes; the demo script just needs to
include a click on "Începe" or, post-fix, can omit it.**

**Honest demo-eve risk assessment for Option A:**

* Voice preamble fix has the highest blast radius — the voice bridge is a
  day old, and prepending context to the Live system instruction may
  conflict with the seeded conversation history (`agent_voice.py:257-264`).
  Test it twice.
* The widget-hint-prepend is a string-level hack. The agent might leak the
  `[widget=...]` hint into its spoken response. Add a hygiene scrub in
  `strip_thinking` or a regex in the system prompt.
* `start_procedure` tool requires the agent to know which procedure id to
  call. Today the model only sees titles in `lookup_procedure` results.
  Make sure the `LookupResult.matches` include `procedure_id` (already
  does — `lookup_procedure.py:62`) AND the system prompt §2 explicitly says
  "after confirming with the citizen, call `start_procedure(matches[0].procedure_id)`".

**Post-demo: do Option B in the first week.** Tool surface collapse +
single schema source + widget structured round-trip + `/tools/*` deletion
= a much smaller, cleaner codebase that's still recognizable, in ~2 days
of focused work. Option C is for if/when eGata becomes a product.

---

## 5. Open questions

These must be answered before you can start ANY restructure path:

1. **Is the voice bridge (`NEXT_PUBLIC_VOICE_BRIDGE=1`) the default at
   demo, or is the legacy direct-Gemini path the default?** If legacy,
   the P0-4 fix (voice preamble) becomes "fix /voice/session preamble
   instead" (which already exists at `voice.py:160-183` — actually
   already correct). If bridge, the P0-4 fix matters and is in
   `agent_voice.py`. Two completely different fix locations.

2. **Is `voice_only` mode part of the demo?** If yes, P0-1 is hard-blocking
   (the right pane is hidden, so the user can't click "Începe", so a
   `start_procedure` tool is the ONLY way). If no, the click-to-start
   workaround is acceptable and P0-1 drops from P0 to P1.

3. **Does the demo flow include `propose_widget`?** If the script avoids
   widgets and uses plain text for everything, P0-2 doesn't fire. If the
   script wants to show the choice/confirm/date widgets, the hint-prepend
   fix is mandatory.

4. **Is the scenario plan demo'd?** If yes, P1-2 (cross-procedure
   `conversationId` reset) shows: the agent will say "hello, how can I
   help" after every procedure. If you're demoing scenarios, this is a
   visible issue and might escalate to P0.

5. **Are we OK with the agent calling `start_procedure` without explicit
   user confirmation?** Option A as written has the agent confirm via a
   prompt rule ("Confirmă cu cetățeanul înainte de a continua" — already
   in CONVERSATIONAL_SYSTEM rule 2). If the design wants the user to
   always click, then `start_procedure` becomes "agent emits a
   `propose_widget(confirm)` and on Da, the FRONTEND calls
   `startProcedure` via the existing path". That keeps the agent
   surface clean but requires the widget round-trip fix to be solid.

6. **What's the source of truth for the field schema?** Currently it's
   `backend/procedures/*.json` consumed by Python + (separately) the
   frontend. For Option B's "single schema source" plan, decide: are we
   generating TS types from Pydantic, or both from JSON? This affects
   refactor scope significantly.

7. **Is `set_reminder` reachable in the demo?** If no one types "adu-mi
   aminte", it can be safely removed from the surface NOW (1 line in
   `_FUNCTION_DECLS`) to reduce surface area, with no demo risk. If yes,
   we keep it.

The answers to #1, #2, #5 determine whether Option A is "5 fixes" or
"3 fixes". Get them from the team before starting.
