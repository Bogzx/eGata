# CivicAI Chat-First Redesign — Design

**Status:** Draft for implementation
**Date:** 2026-05-23
**Owners:** Bogdan + team
**Supersedes the UI of:** `app/home`, `app/req/new`, `app/req/[id]`, `app/doc/[id]`

---

## 1. Goal

Make CivicAI feel like opening a single, conversational AI surface — not a multi-page government portal. The user lands on a full-bleed chat ("Cu ce te pot ajuta?"). When the AI engages, the screen splits to a 40 / 60 chat-plus-right-pane layout. The right pane swaps between a Quick Guide, the live-filling form, a review checklist, a PDF preview, and a delivery picker — all driven by the agent's tool calls. Voice lives inside the same composer (a mic button), the same chat thread, the same tool dispatch.

This replaces the current multi-route flow (`/home` → `/req/new` → `/req/[id]` → `/doc/[id]`) with one continuous shell.

## 2. Constraints

- Frontend: Next.js 15.5.18 (App Router), React 19, TypeScript strict + `noUncheckedIndexedAccess`, Tailwind, shadcn primitives, framer-motion, MSW 2.6+, Zustand.
- Backend: FastAPI 0.115.4, Python 3.12, `google-genai`, Pydantic v2, Supabase, PyJWT, `websockets`, `audioop`, apscheduler.
- Existing voice infrastructure (Gemini Live 2.5 native audio, JWT-gated `/tools/{name}` dispatch, AudioWorklets) is reused as-is.
- Six existing tools (`lookup_procedure`, `set_field`, `generate_pdf`, `deliver`, `find_redirect`, `set_reminder`) are reused as-is. One new tool, `propose_widget`, is added.
- Login flow (`/login`, `/login/otp`, MRZ scan at kiosk) is untouched.
- Hackathon scope: localStorage chat persistence is acceptable; server-side `conversations` table is out of scope.
- Romanian-first UI copy. English is not in scope here.

## 3. User-facing model

### 3.1 Idle state (no doc active)

Full-bleed chat. Top-left: `📂 Documentele mele`. Top-right: `👤 <prenume> ▾` (accessibility toggles, sign out, "Conversație nouă"). Center: a one-line greeting, a composer (textarea + mic + send), and 3–4 suggestion chips synthesised from `api.listProcedures()` filtered by the citizen's attributes (e.g., `owns_vehicle === false` hides car-registration chips).

If `api.listReminders()` returns one or more pending reminders, an additional first chip appears: `🔔 Ai X amintiri active` — clicking it opens the `DocumentsDrawer` scrolled to the Reminders section (see 3.5).

### 3.2 Engaged state (doc active)

The layout becomes a 40 / 60 grid:

- **Left 40% — Chat pane.** The thread of user + agent turns, plus inline widgets posted by the agent. Composer always pinned to the bottom with the mic button.
- **Right 60% — Right pane.** A finite state machine driven by tool-call results. Its substates:
  - `welcome` (only when idle — hidden in engaged mode)
  - `guide` — title, numbered steps, `acte_necesare` list, "Continuă" / "Nu"
  - `filling` — the existing `<FormPreview>` with the active field highlighted
  - `review` — checklist of filled fields with pencil-edit per row
  - `pdf` — embedded PDF preview (iframe of the storage URL)
  - `delivery` — three big buttons: Save / Send / Print
  - `done` — confirmation card with `ref_number`

### 3.3 Routing

The shell never unmounts during a session. URLs reflect state via `history.pushState`:

- `/` → idle
- `/r/<doc-id>` → engaged with that doc

`popstate` triggers `loadDocument(id)` or `reset()`. Refreshing `/r/<id>` hydrates from the API.

### 3.4 Voice

Mic button in the composer. Tap → opens a Gemini Live session bound to the active doc, with the JWT issued by `POST /voice/session`. The user's spoken transcript appends as a `{role: "user", via: "voice"}` chat message; the agent's spoken response appends as `{role: "agent"}`, and the audio plays through the player worklet. Tool calls flow over the same `/tools/{name}` dispatch as the text path. If `accessibility.voice_only` is true, mic auto-starts on mount and the right pane is hidden.

### 3.5 Documents drawer

The `📂 Documentele mele` button opens a 360–400 px slide-over from the left. The chat dims behind it. Two stacked sections, top to bottom:

1. **Pentru tine acum** — pending reminders (`api.listReminders()` filtered by `status === "pending"`). Each row reuses the existing `<ReminderCard>` component with `Începe` / `Renunță` actions wired to `api.startReminder()` / `api.dismissReminder()`. Hidden if no reminders.
2. **Documentele mele** — all docs from `api.listDocuments()`, sorted newest first. Each item is a card; clicking one loads that doc (closes the drawer, sets `activeDocId`, restores chat from localStorage if present, pushes `/r/<id>`).

Esc or click-outside dismisses. Only one document is active at a time; switching auto-saves the current one (it's already on Supabase).

### 3.6 Inline widgets

When the agent needs a structured answer, it calls `propose_widget(type, question, options, target_field)`. The frontend renders the matching component from `widgets/index.ts`. Three widget types initially:

- `choice` — button group (2+ options)
- `confirm` — Yes/No card
- `date` — native date picker wrapper

Clicking a widget option sends the chosen value back through the same channel (text → `/agent/chat`, voice → `session.sendText(...)`). The agent then typically calls `set_field` with that value.

## 4. Architecture

### 4.1 File layout

```
frontend/
├── app/
│   ├── page.tsx                          # NEW — <ChatSurface activeDocId={null} />
│   ├── r/[id]/page.tsx                   # NEW — <ChatSurface activeDocId={params.id} />
│   ├── home/page.tsx                     # REPLACED — useEffect redirect to /
│   ├── req/new/page.tsx                  # REPLACED — redirect to /
│   ├── req/[id]/page.tsx                 # REPLACED — redirect to /r/[id]
│   └── doc/[id]/page.tsx                 # REPLACED — redirect to /r/[id]
├── components/
│   ├── chat/
│   │   ├── ChatSurface.tsx
│   │   ├── TopBar.tsx
│   │   ├── DocumentsDrawer.tsx
│   │   ├── ProfileMenu.tsx
│   │   ├── ChatPane.tsx
│   │   ├── ChatStream.tsx
│   │   ├── Composer.tsx
│   │   ├── RightPane.tsx
│   │   └── widgets/
│   │       ├── ChoiceWidget.tsx
│   │       ├── ConfirmWidget.tsx
│   │       ├── DateWidget.tsx
│   │       └── index.ts                  # Registry
│   └── right-pane/
│       ├── WelcomePane.tsx
│       ├── GuidePane.tsx
│       ├── FillingPane.tsx               # wraps existing FormPreview
│       ├── ReviewPane.tsx
│       ├── PdfPane.tsx
│       └── DeliveryPane.tsx
├── lib/
│   ├── sessionStore.ts                   # Zustand
│   ├── rightPaneState.ts                 # pure transitions + computeInitialRightPaneFrom
│   └── widgetTools.ts                    # types and renderable-tool list

backend/
└── app/
    └── tools/
        └── propose_widget.py             # NEW
```

**Retired (deleted) components**: `ChatPanel.tsx`, `VocalFillFlow.tsx`, `GuidedFillFlow.tsx`, `CompletionModeSelector.tsx`, `KioskShell.tsx`. Their useful logic is absorbed into the new `chat/*` components or replaced by CSS variants on `ChatSurface`.

**Reused without changes**: `lib/api.ts`, `lib/audioWorklet.ts`, `lib/gemini-live.ts`, `lib/useVoiceAgent.ts` (small refactor to expose hooks to the store), `lib/accessibilityStore.ts`, `lib/session.ts`, `lib/i18n.ts`, `components/FormPreview.tsx`, `components/ManualFillForm.tsx` (used inside the field-edit modal triggered from `ReviewPane`), `components/MrzScanner.tsx`, `components/OtpInput.tsx`.

### 4.2 Session store (`lib/sessionStore.ts`)

```ts
type RightPaneState =
  | { kind: "welcome" }
  | { kind: "guide"; procedureId: string }
  | { kind: "filling"; activeField?: string }
  | { kind: "review" }
  | { kind: "pdf"; url: string }
  | { kind: "delivery" }
  | { kind: "done"; refNumber: string };

type Message =
  | { id: string; role: "user"; text: string; via: "text" | "voice" }
  | { id: string; role: "agent"; text: string; widgets?: WidgetSpec[] }
  | { id: string; role: "system"; text: string };

type WidgetSpec =
  | { type: "choice"; question: string; options: string[]; targetField: string; widgetId: string }
  | { type: "confirm"; question: string; onConfirmTool?: string; widgetId: string }
  | { type: "date"; question: string; targetField: string; widgetId: string };

type VoiceStatus = "idle" | "connecting" | "listening" | "speaking" | "error";

interface SessionState {
  citizen: Citizen | null;
  activeDocId: string | null;
  document: Document | null;
  procedure: Procedure | null;
  conversationId: string | null;
  messages: Message[];
  rightPane: RightPaneState;
  voiceStatus: VoiceStatus;
  drawerOpen: boolean;
  profileMenuOpen: boolean;
  sending: boolean;

  hydrateCitizen(): Promise<void>;
  startProcedure(procedureId: string): Promise<void>;
  loadDocument(docId: string): Promise<void>;
  sendText(text: string): Promise<void>;
  startVoice(): Promise<void>;
  stopVoice(): void;
  applyToolResult(toolName: string, args: Record<string, unknown>, result: unknown): void;
  transitionRightPane(next: RightPaneState): void;
  openDrawer(): void;
  closeDrawer(): void;
  reset(): void;
}
```

### 4.3 Right-pane state machine (`lib/rightPaneState.ts`)

| From → To | Trigger |
|---|---|
| `welcome` → `guide` | `startProcedure(id)` completes (doc created, procedure loaded). |
| `guide` → `filling` | User confirms guide (clicks Continuă, or agent's reply after a "da" sets state). |
| `filling` → `filling` (activeField change) | `set_field` tool result includes `field_name`. |
| `filling` → `review` | All required fields filled — checked after every `set_field` against `procedure.fields` + `document.fields`. |
| `review` → `pdf` | `generate_pdf` tool result includes `pdf_url`. |
| `pdf` → `delivery` | User clicks "Continuă spre trimitere" in `PdfPane`. |
| `delivery` → `done` | `deliver` tool result includes `ref_number`. |
| Any → `welcome` | `reset()`. |
| Any → resumed substate | `loadDocument(id)` calls `computeInitialRightPaneFrom(document)`. |

```ts
function computeInitialRightPaneFrom(doc: Document, procedure: Procedure): RightPaneState {
  if (doc.status === "finalized" && doc.ref_number) return { kind: "done", refNumber: doc.ref_number };
  if (doc.pdf_url) return { kind: "pdf", url: doc.pdf_url };
  const allFilled = procedure.fields.filter(f => f.required && !isFilled(doc.fields[f.name])).length === 0;
  if (allFilled) return { kind: "review" };
  const anyFilled = Object.keys(doc.fields).some(k => isFilled(doc.fields[k]));
  return anyFilled ? { kind: "filling" } : { kind: "guide", procedureId: doc.procedure_id };
}
```

### 4.4 Component responsibilities

```
<ChatSurface activeDocId>
├── <TopBar>                              # Docs button + Profile button
├── <DocumentsDrawer />                   # framer-motion slide-over
├── <ProfileMenu />                       # framer-motion dropdown
└── <div data-mode={idle|engaged} class="body-grid">
    ├── <ChatPane>                        # 100% idle / 40% engaged
    │   ├── <ChatStream />                # messages + inline widgets
    │   └── <Composer />                  # textarea + mic + send
    └── <RightPane />                     # 0% idle / 60% engaged
```

| Component | Reads from store | Writes to store | Render highlights |
|---|---|---|---|
| `ChatSurface` | `activeDocId`, `rightPane.kind` | `loadDocument()` on mount if `activeDocId` set | Grid; `data-mode`, `data-kiosk` for CSS variants |
| `TopBar` | `citizen.prenume`, `drawerOpen`, `profileMenuOpen` | `openDrawer()`, toggle profile | Two buttons |
| `DocumentsDrawer` | `drawerOpen` | `loadDocument(id)`, `closeDrawer()` | Lists `api.listDocuments()`; reuses `<DocumentList>` |
| `ProfileMenu` | `citizen`, accessibility prefs | `useAccessibilityPrefs.set()`, sign out, `reset()` | Reuses `<AccessibilityToggles>` |
| `ChatPane` | `messages`, `sending`, `voiceStatus` | — | Scrollable stream + pinned composer |
| `ChatStream` | `messages` | `applyToolResult()` via widget callbacks | Bubbles + widgets (from `WIDGET_REGISTRY`); thinking-token regex strip as defense in depth |
| `Composer` | `sending`, `voiceStatus` | `sendText()`, `startVoice()`, `stopVoice()` | Textarea + mic + send; Enter sends, Shift+Enter newlines |
| `WelcomePane` | `citizen`, procedures list | `startProcedure(id)` (chip click) | Greeting + 3–4 chips filtered by citizen attributes |
| `GuidePane` | `procedure`, `document` | `transitionRightPane({kind: "filling"})` on Continuă | Title + steps + `acte_necesare` + Continuă / Nu |
| `FillingPane` | `procedure`, `document.fields`, `rightPane.activeField` | — | Wraps `<FormPreview>` |
| `ReviewPane` | `procedure`, `document.fields` | `api.patchDocumentFields()` via single-field editor (reuses `ManualFillForm`) | Checklist with edit-pencils; "Trimite cererea" button |
| `PdfPane` | `document.pdf_url` | — | `<iframe>`; "Continuă spre trimitere" button |
| `DeliveryPane` | `document` | `api.deliverDocument()` → transitions to `done` | Three big buttons |

### 4.5 Widget registry (`components/chat/widgets/index.ts`)

```ts
export const WIDGET_REGISTRY: Record<WidgetSpec["type"], React.FC<{
  spec: WidgetSpec;
  onSubmit: (value: string) => void;
}>> = {
  choice: ChoiceWidget,
  confirm: ConfirmWidget,
  date: DateWidget,
};
```

`ChatStream` reads `message.widgets[]` (derived from `tool_calls.propose_widget` entries), looks up the component by `spec.type`, and renders it with an `onSubmit` callback that:

1. Appends `{role: "user", text: value, via: "text"}` to `messages`.
2. If voice WS is connected: `session.sendText(value)`. Otherwise: `api.chat({...message: value})`.
3. Disables itself so the widget can only be answered once.

## 5. Data flow

### 5.1 Start a procedure from idle

```
chip click in WelcomePane
  → store.startProcedure("schimbare-domiciliu")
  → api.createDocument({procedure_id})            → POST /documents
  → store: activeDocId, document, procedure, conversationId = null, messages = [greeting]
  → history.pushState(null, "", `/r/${doc.id}`)
  → store: rightPane = { kind: "guide", procedureId }
```

The first agent message is a deterministic Romanian greeting template (no AI call) so the right pane and chat feel instant. Template:

```
Bun, te ajut cu „<procedure.title>". Vezi în dreapta ce vom face pas cu pas
și ce acte ai nevoie. Apasă „Continuă" sau spune-mi dacă vrei altceva.
```


### 5.2 Text round-trip

```
Composer submit
  → store.sendText(text)
  → store: messages += {role: "user", text, via: "text"}; sending = true
  → api.chat({conversation_id, document_id, message, preferences})
       backend: agent loop — RAG (lookup_procedure), maybe set_field/generate_pdf/deliver/propose_widget
       returns { conversation_id, message: <final stripped of thinking>, tool_calls: [...] }
  → store: conversationId = r.conversation_id
  → store: messages += {role: "agent", text: r.message, widgets: deriveWidgets(r.tool_calls)}
  → for each tool_call in r.tool_calls: store.applyToolResult(name, args, result)
       set_field → refetch document, transitionRightPane({kind:"filling", activeField})
       generate_pdf → refetch document, transitionRightPane({kind:"pdf", url})
       deliver → refetch document, transitionRightPane({kind:"done", refNumber})
       lookup_procedure → noop on state (acte_necesare already in document context server-side)
       find_redirect → append a system note in chat
       set_reminder → toast confirmation
       propose_widget → no state change (widget already rendered from r.tool_calls)
  → store: sending = false
```

### 5.3 Voice round-trip

```
mic button click
  → store.startVoice()
  → api.createVoiceSession({document_id})         → tool_jwt + voice config
  → new GeminiLiveSession(...).connect()
  → store: voiceStatus = "listening"
  → startMicRecorder, startPlayer

  user speaks → live events:
    inputTranscription → store: messages += {role: "user", via: "voice"}
    outputTranscription → store: messages += {role: "agent"} (regex-stripped of thinking)
    audio chunks → player queue (voiceStatus = "speaking" while playing)
    toolCall → fetch ${tool_base_url}/${name} with Bearer JWT → result
            → session.sendToolResponse(name, result)
            → store.applyToolResult(name, args, result)
```

Voice and text share `applyToolResult` so right-pane transitions are identical regardless of modality.

### 5.4 Inline widget submit

See 4.5 above. The user's choice is just a normal chat message; the widget is sugar.

### 5.5 URL sync

```
On store.activeDocId change:
  if null:    history.pushState(null, "", "/")
  else:       history.pushState(null, "", `/r/${id}`)

window.addEventListener("popstate"):
  switch (window.location.pathname):
    "/"              → store.reset()
    "/r/<id>"        → store.loadDocument(id)
```

### 5.6 Drawer switch

```
drawer item click
  → store.loadDocument(targetId)
       store.stopVoice() if active
       parallel: api.getDocument, api.getProcedure
       restore messages from localStorage[civicai:session:<docId>] (or empty)
       restore conversationId from localStorage (or null)
       rightPane = computeInitialRightPaneFrom(doc, procedure)
  → store.closeDrawer()
  → history.pushState(null, "", `/r/${targetId}`)
```

## 6. Backend changes

### 6.1 New tool — `propose_widget`

```python
# backend/app/tools/propose_widget.py
from enum import StrEnum
from uuid import uuid4
from pydantic import BaseModel, Field
from . import ToolContext, register

class WidgetType(StrEnum):
    CHOICE = "choice"
    CONFIRM = "confirm"
    DATE = "date"

class WidgetArgs(BaseModel):
    type: WidgetType
    question: str
    options: list[str] = Field(default_factory=list)
    target_field: str | None = None

class WidgetResult(BaseModel):
    acknowledged: bool = True
    widget_id: str

@register("propose_widget")
async def propose_widget(args: WidgetArgs, ctx: ToolContext) -> WidgetResult:
    if args.type == WidgetType.CHOICE and len(args.options) < 2:
        raise ValueError("choice widget needs >= 2 options")
    if args.type == WidgetType.CHOICE and not args.target_field:
        raise ValueError("choice widget needs a target_field")
    return WidgetResult(widget_id=str(uuid4()))
```

`PHONE_TOOL_ALLOWLIST` is **not** extended — phone has no UI to render widgets.

### 6.2 Thinking-token suppression

Three independent layers:

1. **Gemini config** — both `agent.py` and `voice.py` set `thinking_config={"thinking_budget": 0}` on the model config when constructing the session / chat request.
2. **Prompt directive** — append to `CONVERSATIONAL_SYSTEM` in `prompts.py`:
   ```
   Răspunzi DIRECT, scurt și natural. Niciodată nu descrie procesul tău de
   gândire ("hai să mă gândesc...", "în primul rând...", "trebuie să verific...").
   Acționează imediat cu unelte și răspunde cu rezultatul.
   ```
3. **Defensive regex strip** in `agent.py` before returning `final_text`, and in `voice.py` before forwarding `outputTranscription` deltas:
   ```python
   _THINKING_RE = re.compile(
     r"<(?:thinking|scratchpad|reasoning)>.*?</(?:thinking|scratchpad|reasoning)>",
     re.DOTALL | re.IGNORECASE,
   )
   text = _THINKING_RE.sub("", text).strip()
   ```

### 6.3 Prompt additions (`prompts.py`)

Append to `CONVERSATIONAL_SYSTEM`:

- **Widget directive** — for structured questions with a fixed answer set call `propose_widget(type="choice", question, options, target_field)` instead of listing options as text. For yes/no confirmations use `type="confirm"`. For dates use `type="date"`. Do NOT also list the options in your text reply when you call `propose_widget`.
- **Brevity directive** — keep replies under ~15 words by default. Long content (lists of documents, multi-step instructions) belongs in the right pane via tool calls, not in chat.
- **RAG-first directive** — already in place; reinforced: never invent procedures or `acte_necesare`; always trust `lookup_procedure` results and the active document context.

### 6.4 Endpoints

| Endpoint | Change |
|---|---|
| `POST /agent/chat` | No signature change. `tool_calls` may include `propose_widget`. `message` is regex-stripped of thinking tags. |
| `POST /voice/session` | No change. |
| `POST /tools/propose_widget` | NEW (registered via `@register`). |
| `POST /tools/{name}` for existing tools | Unchanged. |
| Reminders, demo reset, health | Unchanged. |

### 6.5 MSW handlers (frontend mocks)

Add:

- `POST /tools/propose_widget` → `{ acknowledged: true, widget_id: "mock-uuid" }`

All existing handlers (procedures, documents, agent chat, voice session, tool dispatch, reminders, demo reset) are kept.

## 7. Variants

### 7.1 Kiosk (`?kiosk=1` or env flag)

- `data-kiosk="true"` on `ChatSurface`. CSS bumps base font 16→20 px, button min-height 3rem→3.5rem.
- Grid becomes 50 / 50 (more room for the document).
- `TopBar` profile button changes label from `<prenume> ▾` to `Accesibilitate ▾`. `ProfileMenu` is still mounted but hides the sign-out item and the "Conversație nouă" item — only the accessibility toggles remain. (Kiosk users walk away; session times out client-side via existing logic.)
- MRZ scan + OTP login at `/login` is untouched.

### 7.2 Mobile (<768 px)

- Grid collapses to one column.
- `ChatPane` is full-screen; composer at bottom with larger touch targets (mic 56 px).
- `RightPane` renders as a `<dialog>` bottom-sheet that slides up when `rightPane.kind !== "welcome"`. A persistent "Vezi documentul" pill at the top-right of `ChatPane` toggles the sheet.
- `DocumentsDrawer` becomes a full-screen overlay.

### 7.3 Voice-only (`accessibility.voice_only`)

- On mount, after `hydrateCitizen()` resolves, `ChatSurface` auto-invokes `store.startVoice()`.
- `RightPane` is `display: none`; `ChatPane` takes 100% width.
- The existing `VOICE_ONLY_DIRECTIVE` in `prompts.py` keeps the agent from referencing visual elements.

## 8. Error handling

| Failure | Surfaced as |
|---|---|
| `/agent/chat` 5xx | `{role: "system", text: t("chat.error_retry")}` + retry button. Composer re-enabled. |
| `/agent/chat` 401 | Force sign-out → `/login`. |
| `/voice/session` 401 | Same — force sign-out. |
| Voice WS disconnect | `voiceStatus = "error"`, system message "Conexiunea vocală s-a întrerupt. Apasă mic ca să încerci din nou." Composer mic shows red badge. Text still works. |
| Mic permission denied | `VoiceAgentMicDeniedError` caught → `voiceStatus = "error"` + system message with link "Cum permit microfonul?". |
| Tool dispatch 4xx (validation) | Backend's `detail` text appended as `{role: "system"}`. Document not refetched. |
| Tool dispatch 5xx | Generic error message; offer retry. |
| `api.getDocument` 404 from drawer | Toast "Documentul nu mai există"; `store.reset()`. |
| PDF generation fails | System message + Reîncearcă button; `rightPane` stays at `review`. |
| `api.deliverDocument` fails | System message; `rightPane` stays at `delivery`. |
| `navigator.onLine === false` | Composer disabled with "Offline — încearcă mai târziu" placeholder; mic disabled. |

## 9. Persistence

| What | Where | Why |
|---|---|---|
| Document state (fields, status, pdf_url, ref_number) | Supabase (existing) | Source of truth |
| Conversation message history (per doc) | `localStorage["civicai:session:<docId>"]` | Restore on refresh / drawer switch. Hackathon-scoped. |
| `conversation_id` per doc | `localStorage["civicai:conv:<docId>"]` | Lets backend reuse its in-memory conversation if still warm |
| Accessibility prefs | `localStorage` via `useAccessibilityPrefs` (existing) | Already in place |
| Voice session | Not persisted | Always reconnect fresh |
| `activeDocId` | Derived from URL pathname | Single source of truth |

A future migration to a Supabase `messages` table is noted but out of scope.

## 10. Testing

### 10.1 Frontend

| Layer | What | How |
|---|---|---|
| `sessionStore` | All transitions in 4.3; reducer-style action coverage | Vitest unit, no React |
| `rightPaneState` | Table-driven transition table + `computeInitialRightPaneFrom` | Vitest unit |
| Widgets | `onSubmit` posts once; `ConfirmWidget` disables after click; `DateWidget` validates ISO | React Testing Library |
| `ChatStream` | Regex strip works; widgets render from `tool_calls`; auto-scroll | RTL + MSW |
| `Composer` | Enter sends, Shift+Enter newlines; mic state toggles | RTL |
| `ChatSurface` (integration) | Idle → chip → guide → confirm → filling → review → pdf → delivery → done. Drawer switch in middle restores correctly. URL updates without unmount. | RTL + MSW |
| Voice round-trip | Scripted `GeminiLiveSession` mock emitting inputTranscription, outputTranscription, audio, toolCall | Vitest with manual class mock |

### 10.2 Backend

| Layer | What | How |
|---|---|---|
| `propose_widget` | Validates `options >= 2` for choice; validates `target_field` for choice; happy path returns widget_id | pytest in `test_plan3_smoke.py` |
| Thinking-strip | `<thinking>...</thinking>` stripped from `agent.py` final_text and `voice.py` outputTranscription deltas | pytest unit |
| `PHONE_TOOL_ALLOWLIST` | Does NOT include `propose_widget` | pytest assertion (extend existing) |
| Embeddings / lookup_procedure | Existing tests unchanged | pytest |

### 10.3 Manual demo checklist

- Idle → say "vreau să-mi schimb domiciliul" → guide appears with correct `acte_necesare`.
- Confirm guide → filling pane appears.
- Agent asks "Cum locuiești?" via inline `propose_widget(choice)` → tap "Chiriaș" → field updates, chat appends "Chiriaș", form highlights.
- Fill remaining fields → review appears automatically.
- Generate PDF → PDF iframe loads.
- Deliver "Send" → done card with `ref_number`.
- Open drawer → see this doc + others → click another → chat + right pane restore.
- Switch on `voice_only` in profile → reload → mic auto-engages, right pane hidden.
- Switch to kiosk mode → larger fonts, no profile button, 50/50 split.

## 11. Out of scope

- Server-side `messages` table on Supabase (hackathon uses localStorage).
- English UI variant.
- Multiple concurrent in-progress procedures with a thread switcher.
- Push notifications for reminders (existing Plan 4 worker stays as-is — reminders are surfaced in the `Documentele mele` drawer's top section and via the welcome-state hint chip; see 3.1 and 3.5).
- Server-side rendering of the chat shell (it's fully client-side; SSR would complicate the URL/state sync).
- A new login flow (current OTP + MRZ stays).

## 12. Open questions for review

None currently. All decisions above have been confirmed in brainstorming. Update this section if implementation reveals gaps.
