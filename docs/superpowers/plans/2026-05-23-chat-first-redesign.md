# Chat-First Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline execution). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert eGata from a multi-route portal into a single chat-first shell at `/` and `/r/[id]`, with a 40/60 split when engaged, voice in the composer, drawer-based documents, and a state machine driving the right pane from agent tool calls.

**Architecture:** A single `<ChatSurface>` React tree, never unmounted during a session. URL flips via `history.pushState`. A Zustand `sessionStore` holds messages, doc, voice status, drawer, and a `rightPane` discriminated union. Backend adds one tool (`propose_widget`) plus three layers of thinking-token suppression. Existing 6 tools, RAG, voice JWT, and Twilio bridge are reused.

**Tech Stack:** Next.js 15.5 App Router, React 19, TypeScript strict + `noUncheckedIndexedAccess`, Tailwind, Zustand 5, framer-motion, MSW 2.6, Vitest, FastAPI, Pydantic v2, `google-genai`.

**Spec:** `docs/superpowers/specs/2026-05-23-chat-first-redesign-design.md`

---

## File Manifest (created / modified / deleted)

**Created — backend:**
- `backend/app/tools/propose_widget.py`

**Modified — backend:**
- `backend/app/tools/__init__.py` (add import)
- `backend/app/agent.py` (thinking-token regex strip + thinking_config + propose_widget declaration)
- `backend/app/voice.py` (thinking_config on Gemini Live + propose_widget in tool list)
- `backend/app/twilio_bridge.py` (do NOT include propose_widget; just confirm allowlist excludes it)
- `backend/app/prompts.py` (widget directive + brevity directive)
- `backend/tests/test_plan3_smoke.py` (tests for propose_widget + thinking-strip + allowlist)

**Created — frontend:**
- `frontend/lib/sessionStore.ts`
- `frontend/lib/rightPaneState.ts`
- `frontend/lib/widgetTools.ts`
- `frontend/lib/__tests__/rightPaneState.test.ts`
- `frontend/lib/__tests__/sessionStore.test.ts`
- `frontend/components/chat/ChatSurface.tsx`
- `frontend/components/chat/TopBar.tsx`
- `frontend/components/chat/DocumentsDrawer.tsx`
- `frontend/components/chat/ProfileMenu.tsx`
- `frontend/components/chat/ChatPane.tsx`
- `frontend/components/chat/ChatStream.tsx`
- `frontend/components/chat/Composer.tsx`
- `frontend/components/chat/RightPane.tsx`
- `frontend/components/chat/widgets/ChoiceWidget.tsx`
- `frontend/components/chat/widgets/ConfirmWidget.tsx`
- `frontend/components/chat/widgets/DateWidget.tsx`
- `frontend/components/chat/widgets/index.ts`
- `frontend/components/right-pane/WelcomePane.tsx`
- `frontend/components/right-pane/GuidePane.tsx`
- `frontend/components/right-pane/FillingPane.tsx`
- `frontend/components/right-pane/ReviewPane.tsx`
- `frontend/components/right-pane/PdfPane.tsx`
- `frontend/components/right-pane/DeliveryPane.tsx`
- `frontend/components/right-pane/DonePane.tsx`
- `frontend/app/r/[id]/page.tsx`
- `frontend/vitest.config.ts`
- `frontend/vitest.setup.ts`

**Modified — frontend:**
- `frontend/app/page.tsx` (replace landing with chat surface entry)
- `frontend/app/home/page.tsx` (replace with redirect-only)
- `frontend/app/req/new/page.tsx` (replace with redirect-only)
- `frontend/app/req/[id]/page.tsx` (replace with redirect to `/r/[id]`)
- `frontend/app/doc/[id]/page.tsx` (replace with redirect to `/r/[id]`)
- `frontend/lib/useVoiceAgent.ts` (add `propose_widget` to `TOOL_SCHEMAS`)
- `frontend/lib/types.ts` (add `WidgetSpec`, `Message`, `RightPaneState`, `VoiceStatus`)
- `frontend/lib/api.ts` (no change unless needed for tests)
- `frontend/mocks/handlers.ts` (add `/tools/propose_widget` handler)
- `frontend/package.json` (add Vitest deps: `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`)
- `frontend/app/login/otp/page.tsx` (redirect to `/` instead of `/home` after success — single line)

**Deleted — frontend (after migration tasks land):**
- `frontend/components/ChatPanel.tsx`
- `frontend/components/VocalFillFlow.tsx`
- `frontend/components/GuidedFillFlow.tsx`
- `frontend/components/CompletionModeSelector.tsx`
- `frontend/components/KioskShell.tsx`
- `frontend/lib/completionMode.ts` (kiosk-related; superseded by data-attributes)

---

## Phase 1 — Backend changes

### Task 1: Add `propose_widget` tool

**Files:**
- Create: `backend/app/tools/propose_widget.py`
- Modify: `backend/app/tools/__init__.py`
- Test: `backend/tests/test_plan3_smoke.py`

- [ ] **Step 1: Create the tool file**

`backend/app/tools/propose_widget.py`:

```python
"""propose_widget — a UI directive tool.

The agent calls this to ask a structured question that the browser renders as
an inline chat widget (choice buttons, yes/no, date picker). Server-side this
is a near-no-op: validate the args and return an ack with a widget_id.

NOT included in PHONE_TOOL_ALLOWLIST — phone has no UI to render widgets.
"""
from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field

from app.tools import ToolContext, register


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

- [ ] **Step 2: Register the tool**

Edit `backend/app/tools/__init__.py`, append `propose_widget` to the import block at the bottom:

```python
from app.tools import (  # noqa: E402, F401
    deliver as _deliver_mod,
    find_redirect as _find_redirect_mod,
    generate_pdf as _generate_pdf_mod,
    lookup_procedure as _lookup_procedure_mod,
    propose_widget as _propose_widget_mod,
    set_field as _set_field_mod,
    set_reminder as _set_reminder_mod,
)
```

- [ ] **Step 3: Add tests**

Append to `backend/tests/test_plan3_smoke.py`:

```python
import pytest
from app.tools import REGISTRY, ToolContext
from app.tools.propose_widget import WidgetArgs


@pytest.mark.asyncio
async def test_propose_widget_choice_happy():
    tool = REGISTRY["propose_widget"]
    args = WidgetArgs(
        type="choice",
        question="Cum locuiești?",
        options=["Proprietar", "Chiriaș", "Găzduit"],
        target_field="tip_locuinta",
    )
    result = await tool(args, ToolContext(citizen_id="c1", document_id="d1"))
    assert result.acknowledged is True
    assert isinstance(result.widget_id, str) and len(result.widget_id) >= 16


@pytest.mark.asyncio
async def test_propose_widget_choice_needs_two_options():
    tool = REGISTRY["propose_widget"]
    with pytest.raises(ValueError, match=">= 2 options"):
        await tool(
            WidgetArgs(type="choice", question="x?", options=["only-one"], target_field="f"),
            ToolContext(citizen_id="c1", document_id="d1"),
        )


@pytest.mark.asyncio
async def test_propose_widget_choice_needs_target_field():
    tool = REGISTRY["propose_widget"]
    with pytest.raises(ValueError, match="target_field"):
        await tool(
            WidgetArgs(type="choice", question="x?", options=["a", "b"], target_field=None),
            ToolContext(citizen_id="c1", document_id="d1"),
        )


@pytest.mark.asyncio
async def test_propose_widget_confirm_ok():
    tool = REGISTRY["propose_widget"]
    result = await tool(
        WidgetArgs(type="confirm", question="Continui?", options=[], target_field=None),
        ToolContext(citizen_id="c1", document_id="d1"),
    )
    assert result.acknowledged is True


def test_propose_widget_registered():
    assert "propose_widget" in REGISTRY
```

Also extend the existing `test_phone_tool_allowlist_*` test to assert `propose_widget` is NOT in `PHONE_TOOL_ALLOWLIST`:

```python
def test_phone_tool_allowlist_excludes_propose_widget():
    from app.twilio_bridge import PHONE_TOOL_ALLOWLIST
    assert "propose_widget" not in PHONE_TOOL_ALLOWLIST
```

- [ ] **Step 4: Run tests**

```
cd backend && python -m pytest tests/test_plan3_smoke.py -v -k "propose_widget or allowlist"
```

Expect: all green.

- [ ] **Step 5: Commit**

```
git add backend/app/tools/propose_widget.py backend/app/tools/__init__.py backend/tests/test_plan3_smoke.py
git commit -m "feat(backend): add propose_widget UI-directive tool"
```

---

### Task 2: Thinking-token strip + Gemini thinking_config

**Files:**
- Modify: `backend/app/agent.py`
- Modify: `backend/app/voice.py`
- Test: `backend/tests/test_plan3_smoke.py`

- [ ] **Step 1: Add a shared regex helper**

Create `backend/app/text_hygiene.py`:

```python
"""Tiny shared helpers for stripping internal-thought artifacts from LLM output."""
from __future__ import annotations

import re

_THINKING_RE = re.compile(
    r"<(?:thinking|scratchpad|reasoning)>.*?</(?:thinking|scratchpad|reasoning)>",
    re.DOTALL | re.IGNORECASE,
)


def strip_thinking(text: str) -> str:
    """Remove <thinking>/<scratchpad>/<reasoning> blocks; collapse extra whitespace."""
    if not text:
        return text
    cleaned = _THINKING_RE.sub("", text)
    return cleaned.strip()
```

- [ ] **Step 2: Apply in agent.py**

In `backend/app/agent.py`, near the top:

```python
from app.text_hygiene import strip_thinking
```

Find where `final_text` is built before returning from the `/agent/chat` handler. Wrap it:

```python
final_text = strip_thinking(final_text)
```

In the same file, when constructing the `GenerateContentConfig` (or equivalent) for `client.aio.models.generate_content` / `client.aio.chats.create`, add `thinking_config={"thinking_budget": 0}` if the SDK supports it. If the parameter is unknown to the installed `google-genai` version, fall back to a try/except with a warning log (do NOT crash startup).

- [ ] **Step 3: Apply in voice.py**

In `backend/app/voice.py`, add import:

```python
from app.text_hygiene import strip_thinking
```

Where the `/voice/session` response builder injects the system prompt and tool list, no change needed (Gemini Live thinking is browser-side now). However, in `backend/app/twilio_bridge.py` where `outputTranscription` deltas are buffered and concatenated server-side before forwarding, apply `strip_thinking` to each full turn before sending. Find the buffer flush point in `_run_phone_gemini_session` and wrap.

- [ ] **Step 4: Tests**

Append to `backend/tests/test_plan3_smoke.py`:

```python
from app.text_hygiene import strip_thinking


def test_strip_thinking_removes_tags():
    assert strip_thinking("<thinking>foo</thinking>bar") == "bar"
    assert strip_thinking("a<scratchpad>x</scratchpad>b") == "ab"
    assert strip_thinking("<reasoning>r</reasoning>") == ""
    # Multiline
    assert strip_thinking("hi<thinking>\nlong\nstuff\n</thinking>there") == "hithere"
    # No tags = passthrough (trimmed)
    assert strip_thinking("  hello  ") == "hello"
    # Mixed case + multiple
    assert strip_thinking("a<Thinking>1</Thinking>b<thinking>2</thinking>c") == "abc"


def test_strip_thinking_empty():
    assert strip_thinking("") == ""
    assert strip_thinking(None) is None  # type: ignore[arg-type]
```

- [ ] **Step 5: Run tests**

```
cd backend && python -m pytest tests/test_plan3_smoke.py -v -k "strip_thinking or thinking"
```

Expect: green.

- [ ] **Step 6: Commit**

```
git add backend/app/text_hygiene.py backend/app/agent.py backend/app/voice.py backend/app/twilio_bridge.py backend/tests/test_plan3_smoke.py
git commit -m "feat(backend): strip thinking tokens from agent + voice output"
```

---

### Task 3: Prompt directives — widgets + brevity

**Files:**
- Modify: `backend/app/prompts.py`

- [ ] **Step 1: Add directives**

Append to the `CONVERSATIONAL_SYSTEM` string in `backend/app/prompts.py` (before the closing `"""`):

```
10. Pentru întrebări cu răspuns dintr-un set fix (de ex. „proprietar/chiriaș/găzduit"),
    folosește tool-ul `propose_widget` cu type="choice", options=[...] și target_field=
    numele câmpului din formular. NU lista opțiunile și în text — widget-ul ESTE întrebarea.
    Pentru confirmări da/nu: type="confirm". Pentru date calendaristice: type="date".
11. Răspunzi DIRECT și scurt — sub 15 cuvinte de obicei. Nu descrie procesul tău
    de gândire („hai să mă gândesc...", „în primul rând trebuie să..."). Acționează
    imediat cu unelte și răspunde cu rezultatul.
12. Conținut lung (liste de pași, acte necesare detaliate) merge în panoul din dreapta
    via tool-uri, NU în chat. În chat: o frază, eventual o întrebare via `propose_widget`.
```

- [ ] **Step 2: Commit**

```
git add backend/app/prompts.py
git commit -m "feat(backend): prompt directives for widgets + brevity + no-thinking"
```

---

## Phase 2 — Frontend types + state

### Task 4: Vitest + RTL setup, shared types

**Files:**
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/lib/types.ts`

- [ ] **Step 1: Install RTL deps**

```
cd frontend && npm i -D @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
```

- [ ] **Step 2: Vitest config**

Create `frontend/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
```

Create `frontend/vitest.setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 3: Add shared frontend types**

Append to `frontend/lib/types.ts`:

```ts
export type RightPaneState =
  | { kind: "welcome" }
  | { kind: "guide"; procedureId: string }
  | { kind: "filling"; activeField?: string }
  | { kind: "review" }
  | { kind: "pdf"; url: string }
  | { kind: "delivery" }
  | { kind: "done"; refNumber: string };

export type WidgetSpec =
  | { type: "choice"; question: string; options: string[]; targetField: string; widgetId: string }
  | { type: "confirm"; question: string; onConfirmTool?: string; widgetId: string }
  | { type: "date"; question: string; targetField: string; widgetId: string };

export type Message =
  | { id: string; role: "user"; text: string; via: "text" | "voice" }
  | { id: string; role: "agent"; text: string; widgets?: WidgetSpec[] }
  | { id: string; role: "system"; text: string };

export type VoiceStatus = "idle" | "connecting" | "listening" | "speaking" | "error";
```

- [ ] **Step 4: Commit**

```
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/vitest.setup.ts frontend/lib/types.ts
git commit -m "test(frontend): vitest + RTL setup; add session types"
```

---

### Task 5: rightPaneState — transitions + computeInitialRightPaneFrom

**Files:**
- Create: `frontend/lib/rightPaneState.ts`
- Test: `frontend/lib/__tests__/rightPaneState.test.ts`

- [ ] **Step 1: Write tests first**

Create `frontend/lib/__tests__/rightPaneState.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { computeInitialRightPaneFrom } from "../rightPaneState";
import type { Document, Procedure } from "../types";

function mkProc(): Procedure {
  return {
    id: "p1",
    title: "P",
    description: "",
    scope: "primarie",
    category: "x",
    synonyms: [],
    sample_queries: [],
    fields: [
      { name: "a", label: "A", source: "ask", required: true },
      { name: "b", label: "B", source: "ask", required: false },
    ],
    template: "x.tex",
    next_steps: [],
  };
}

function mkDoc(over: Partial<Document> = {}): Document {
  return {
    id: "d1",
    citizen_id: "c1",
    procedure_id: "p1",
    status: "draft",
    fields: {},
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  };
}

describe("computeInitialRightPaneFrom", () => {
  it("done when finalized with ref_number", () => {
    const r = computeInitialRightPaneFrom(
      mkDoc({ status: "finalized", ref_number: "REF-123" }),
      mkProc(),
    );
    expect(r).toEqual({ kind: "done", refNumber: "REF-123" });
  });
  it("pdf when pdf_url present and not finalized", () => {
    const r = computeInitialRightPaneFrom(mkDoc({ pdf_url: "u" }), mkProc());
    expect(r).toEqual({ kind: "pdf", url: "u" });
  });
  it("review when all required filled but no pdf yet", () => {
    const r = computeInitialRightPaneFrom(mkDoc({ fields: { a: "x" } }), mkProc());
    expect(r).toEqual({ kind: "review" });
  });
  it("filling when some filled but not all required", () => {
    const proc = mkProc();
    proc.fields = [
      { name: "a", label: "A", source: "ask", required: true },
      { name: "b", label: "B", source: "ask", required: true },
    ];
    const r = computeInitialRightPaneFrom(mkDoc({ fields: { a: "x" } }), proc);
    expect(r).toEqual({ kind: "filling" });
  });
  it("guide when nothing filled", () => {
    const r = computeInitialRightPaneFrom(mkDoc(), mkProc());
    expect(r).toEqual({ kind: "guide", procedureId: "p1" });
  });
});
```

- [ ] **Step 2: Implement**

Create `frontend/lib/rightPaneState.ts`:

```ts
import type { Document, Procedure, RightPaneState } from "./types";

export function isFilled(v: unknown): boolean {
  return v !== undefined && v !== null && String(v).length > 0;
}

export function allRequiredFilled(procedure: Procedure, fields: Record<string, unknown>): boolean {
  return procedure.fields.filter((f) => f.required && !isFilled(fields[f.name])).length === 0;
}

export function computeInitialRightPaneFrom(
  doc: Document,
  procedure: Procedure,
): RightPaneState {
  if (doc.status === "finalized" && doc.ref_number) {
    return { kind: "done", refNumber: doc.ref_number };
  }
  if (doc.pdf_url) {
    return { kind: "pdf", url: doc.pdf_url };
  }
  if (allRequiredFilled(procedure, doc.fields)) {
    return { kind: "review" };
  }
  const anyFilled = Object.keys(doc.fields).some((k) => isFilled(doc.fields[k]));
  return anyFilled
    ? { kind: "filling" }
    : { kind: "guide", procedureId: doc.procedure_id };
}
```

- [ ] **Step 3: Run tests**

```
cd frontend && npm test -- rightPaneState
```

Expect: 5 passing.

- [ ] **Step 4: Commit**

```
git add frontend/lib/rightPaneState.ts frontend/lib/__tests__/rightPaneState.test.ts
git commit -m "feat(frontend): rightPaneState transitions + tests"
```

---

### Task 6: sessionStore (Zustand)

**Files:**
- Create: `frontend/lib/sessionStore.ts`
- Test: `frontend/lib/__tests__/sessionStore.test.ts`

- [ ] **Step 1: Implement the store**

Create `frontend/lib/sessionStore.ts`:

```ts
import { create } from "zustand";
import { api } from "./api";
import { computeInitialRightPaneFrom, allRequiredFilled } from "./rightPaneState";
import type {
  Citizen,
  Document,
  Message,
  Procedure,
  RightPaneState,
  VoiceStatus,
  WidgetSpec,
} from "./types";

const LS_MSG_KEY = (docId: string) => `egata:session:${docId}`;
const LS_CONV_KEY = (docId: string) => `egata:conv:${docId}`;

function makeId(): string {
  return Math.random().toString(36).slice(2, 11);
}

function loadMessages(docId: string): Message[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(LS_MSG_KEY(docId));
    return raw ? (JSON.parse(raw) as Message[]) : [];
  } catch {
    return [];
  }
}

function saveMessages(docId: string, msgs: Message[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(LS_MSG_KEY(docId), JSON.stringify(msgs));
  } catch {
    /* quota */
  }
}

function loadConvId(docId: string): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(LS_CONV_KEY(docId));
}

function saveConvId(docId: string, id: string | null) {
  if (typeof window === "undefined") return;
  if (id) localStorage.setItem(LS_CONV_KEY(docId), id);
  else localStorage.removeItem(LS_CONV_KEY(docId));
}

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
  sendText(text: string, opts?: { viaWs?: boolean }): Promise<void>;
  applyToolResult(toolName: string, args: Record<string, unknown>, result: unknown): Promise<void>;
  appendMessage(m: Message): void;
  transitionRightPane(next: RightPaneState): void;
  setVoiceStatus(s: VoiceStatus): void;
  openDrawer(): void;
  closeDrawer(): void;
  toggleProfileMenu(): void;
  closeProfileMenu(): void;
  reset(): void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  citizen: null,
  activeDocId: null,
  document: null,
  procedure: null,
  conversationId: null,
  messages: [],
  rightPane: { kind: "welcome" },
  voiceStatus: "idle",
  drawerOpen: false,
  profileMenuOpen: false,
  sending: false,

  async hydrateCitizen() {
    const c = await api.getCitizenMe();
    set({ citizen: c });
  },

  async startProcedure(procedureId: string) {
    const procedure = await api.getProcedure(procedureId);
    const doc = await api.createDocument({ procedure_id: procedureId });
    const greeting: Message = {
      id: makeId(),
      role: "agent",
      text: `Bun, te ajut cu „${procedure.title}". Vezi în dreapta ce vom face pas cu pas și ce acte ai nevoie. Apasă „Continuă" sau spune-mi dacă vrei altceva.`,
    };
    const messages = [greeting];
    saveMessages(doc.id, messages);
    set({
      activeDocId: doc.id,
      document: doc,
      procedure,
      conversationId: null,
      messages,
      rightPane: { kind: "guide", procedureId },
    });
    if (typeof window !== "undefined") {
      window.history.pushState(null, "", `/r/${doc.id}`);
    }
  },

  async loadDocument(docId: string) {
    const doc = await api.getDocument(docId);
    const procedure = await api.getProcedure(doc.procedure_id);
    const messages = loadMessages(docId);
    const conversationId = loadConvId(docId);
    set({
      activeDocId: docId,
      document: doc,
      procedure,
      conversationId,
      messages,
      rightPane: computeInitialRightPaneFrom(doc, procedure),
      drawerOpen: false,
    });
    if (typeof window !== "undefined") {
      const expected = `/r/${docId}`;
      if (window.location.pathname !== expected) {
        window.history.pushState(null, "", expected);
      }
    }
  },

  async sendText(text: string, opts) {
    const { activeDocId, conversationId } = get();
    const userMsg: Message = { id: makeId(), role: "user", text, via: "text" };
    get().appendMessage(userMsg);
    if (opts?.viaWs) {
      // The WS layer will surface the agent reply via its own callbacks.
      return;
    }
    set({ sending: true });
    try {
      const r = await api.chat({
        conversation_id: conversationId,
        document_id: activeDocId ?? undefined,
        message: text,
      });
      const widgets = deriveWidgets(r.tool_calls);
      const agentMsg: Message = {
        id: makeId(),
        role: "agent",
        text: r.message,
        widgets: widgets.length ? widgets : undefined,
      };
      get().appendMessage(agentMsg);
      if (r.conversation_id !== conversationId) {
        set({ conversationId: r.conversation_id });
        if (activeDocId) saveConvId(activeDocId, r.conversation_id);
      }
      for (const tc of r.tool_calls ?? []) {
        await get().applyToolResult(tc.name, tc.arguments, null);
      }
    } catch (err) {
      const detail = err instanceof Error ? err.message : "necunoscută";
      get().appendMessage({ id: makeId(), role: "system", text: `Eroare: ${detail}` });
    } finally {
      set({ sending: false });
    }
  },

  async applyToolResult(name, _args, _result) {
    const { activeDocId, document, procedure } = get();
    switch (name) {
      case "set_field":
      case "generate_pdf":
      case "deliver": {
        if (!activeDocId || !procedure) return;
        const fresh = await api.getDocument(activeDocId).catch(() => null);
        if (!fresh) return;
        set({ document: fresh });
        // Re-derive right pane from the fresh doc.
        const next = computeInitialRightPaneFrom(fresh, procedure);
        // Preserve activeField if set_field — capture from arguments.
        if (name === "set_field" && next.kind === "filling") {
          const fieldName = (_args.name as string | undefined) ?? undefined;
          set({ rightPane: { kind: "filling", activeField: fieldName } });
        } else {
          set({ rightPane: next });
        }
        // After set_field, check if everything is filled → move to review.
        if (name === "set_field" && allRequiredFilled(procedure, fresh.fields)) {
          set({ rightPane: { kind: "review" } });
        }
        break;
      }
      case "lookup_procedure":
      case "find_redirect":
      case "set_reminder":
      case "propose_widget":
        // No store mutation — widgets are surfaced through messages already.
        break;
      default:
        break;
    }
    void document;
  },

  appendMessage(m) {
    const next = [...get().messages, m];
    set({ messages: next });
    const id = get().activeDocId;
    if (id) saveMessages(id, next);
  },

  transitionRightPane(next) {
    set({ rightPane: next });
  },

  setVoiceStatus(s) {
    set({ voiceStatus: s });
  },

  openDrawer() {
    set({ drawerOpen: true });
  },
  closeDrawer() {
    set({ drawerOpen: false });
  },
  toggleProfileMenu() {
    set({ profileMenuOpen: !get().profileMenuOpen });
  },
  closeProfileMenu() {
    set({ profileMenuOpen: false });
  },

  reset() {
    set({
      activeDocId: null,
      document: null,
      procedure: null,
      conversationId: null,
      messages: [],
      rightPane: { kind: "welcome" },
      drawerOpen: false,
      profileMenuOpen: false,
    });
    if (typeof window !== "undefined" && window.location.pathname !== "/") {
      window.history.pushState(null, "", "/");
    }
  },
}));

function deriveWidgets(toolCalls: { name: string; arguments: Record<string, unknown> }[] | undefined): WidgetSpec[] {
  if (!toolCalls) return [];
  const out: WidgetSpec[] = [];
  for (const tc of toolCalls) {
    if (tc.name !== "propose_widget") continue;
    const a = tc.arguments as Record<string, unknown>;
    const type = a.type as WidgetSpec["type"] | undefined;
    const question = (a.question as string | undefined) ?? "";
    const widgetId = (a.widget_id as string | undefined) ?? Math.random().toString(36).slice(2);
    if (type === "choice") {
      out.push({
        type: "choice",
        question,
        options: (a.options as string[] | undefined) ?? [],
        targetField: (a.target_field as string | undefined) ?? "",
        widgetId,
      });
    } else if (type === "confirm") {
      out.push({ type: "confirm", question, onConfirmTool: a.on_confirm_tool as string | undefined, widgetId });
    } else if (type === "date") {
      out.push({ type: "date", question, targetField: (a.target_field as string | undefined) ?? "", widgetId });
    }
  }
  return out;
}
```

- [ ] **Step 2: Test store basics**

Create `frontend/lib/__tests__/sessionStore.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useSessionStore } from "../sessionStore";

beforeEach(() => {
  // Reset store
  useSessionStore.setState({
    citizen: null,
    activeDocId: null,
    document: null,
    procedure: null,
    conversationId: null,
    messages: [],
    rightPane: { kind: "welcome" },
    voiceStatus: "idle",
    drawerOpen: false,
    profileMenuOpen: false,
    sending: false,
  });
  localStorage.clear();
});

describe("sessionStore", () => {
  it("starts in welcome state", () => {
    const s = useSessionStore.getState();
    expect(s.rightPane.kind).toBe("welcome");
    expect(s.activeDocId).toBeNull();
    expect(s.messages).toEqual([]);
  });

  it("appendMessage adds and persists", () => {
    useSessionStore.setState({ activeDocId: "d1" });
    useSessionStore.getState().appendMessage({ id: "m1", role: "user", text: "hi", via: "text" });
    expect(useSessionStore.getState().messages).toHaveLength(1);
    const raw = localStorage.getItem("egata:session:d1");
    expect(raw).toContain("hi");
  });

  it("reset clears state", () => {
    useSessionStore.setState({
      activeDocId: "d1",
      messages: [{ id: "m", role: "user", text: "x", via: "text" }],
      rightPane: { kind: "review" },
    });
    useSessionStore.getState().reset();
    const s = useSessionStore.getState();
    expect(s.activeDocId).toBeNull();
    expect(s.messages).toEqual([]);
    expect(s.rightPane.kind).toBe("welcome");
  });

  it("drawer + profile menu toggles", () => {
    const s = useSessionStore.getState();
    s.openDrawer();
    expect(useSessionStore.getState().drawerOpen).toBe(true);
    s.closeDrawer();
    expect(useSessionStore.getState().drawerOpen).toBe(false);
    s.toggleProfileMenu();
    expect(useSessionStore.getState().profileMenuOpen).toBe(true);
    s.closeProfileMenu();
    expect(useSessionStore.getState().profileMenuOpen).toBe(false);
  });
});
```

- [ ] **Step 3: Run tests**

```
cd frontend && npm test -- sessionStore
```

Expect: green.

- [ ] **Step 4: Commit**

```
git add frontend/lib/sessionStore.ts frontend/lib/__tests__/sessionStore.test.ts
git commit -m "feat(frontend): sessionStore with localStorage persistence + tests"
```

---

## Phase 3 — Widget components

### Task 7: Three widget components + registry

**Files:**
- Create: `frontend/components/chat/widgets/ChoiceWidget.tsx`
- Create: `frontend/components/chat/widgets/ConfirmWidget.tsx`
- Create: `frontend/components/chat/widgets/DateWidget.tsx`
- Create: `frontend/components/chat/widgets/index.ts`

- [ ] **Step 1: ChoiceWidget**

```tsx
"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { WidgetSpec } from "@/lib/types";

type Props = {
  spec: Extract<WidgetSpec, { type: "choice" }>;
  onSubmit: (value: string) => void;
};

export function ChoiceWidget({ spec, onSubmit }: Props) {
  const [picked, setPicked] = useState<string | null>(null);
  return (
    <div className="rounded-lg border bg-background/60 p-3" aria-label={spec.question}>
      <p className="mb-2 text-sm font-medium">{spec.question}</p>
      <div className="flex flex-wrap gap-2">
        {spec.options.map((opt) => (
          <Button
            key={opt}
            type="button"
            variant={picked === opt ? "default" : "outline"}
            size="sm"
            disabled={picked !== null}
            onClick={() => {
              setPicked(opt);
              onSubmit(opt);
            }}
          >
            {opt}
          </Button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: ConfirmWidget**

```tsx
"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { WidgetSpec } from "@/lib/types";

type Props = {
  spec: Extract<WidgetSpec, { type: "confirm" }>;
  onSubmit: (value: string) => void;
};

export function ConfirmWidget({ spec, onSubmit }: Props) {
  const [done, setDone] = useState(false);
  function pick(v: "Da" | "Nu") {
    setDone(true);
    onSubmit(v);
  }
  return (
    <div className="rounded-lg border bg-background/60 p-3" aria-label={spec.question}>
      <p className="mb-2 text-sm font-medium">{spec.question}</p>
      <div className="flex gap-2">
        <Button type="button" size="sm" disabled={done} onClick={() => pick("Da")}>
          Da
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={done}
          onClick={() => pick("Nu")}
        >
          Nu
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: DateWidget**

```tsx
"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { WidgetSpec } from "@/lib/types";

type Props = {
  spec: Extract<WidgetSpec, { type: "date" }>;
  onSubmit: (value: string) => void;
};

export function DateWidget({ spec, onSubmit }: Props) {
  const [value, setValue] = useState("");
  const [done, setDone] = useState(false);
  return (
    <div className="rounded-lg border bg-background/60 p-3" aria-label={spec.question}>
      <p className="mb-2 text-sm font-medium">{spec.question}</p>
      <div className="flex gap-2">
        <Input
          type="date"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          disabled={done}
          className="max-w-[180px]"
        />
        <Button
          type="button"
          size="sm"
          disabled={done || !value}
          onClick={() => {
            setDone(true);
            onSubmit(value);
          }}
        >
          OK
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Registry**

```ts
import type { ComponentType } from "react";
import type { WidgetSpec } from "@/lib/types";
import { ChoiceWidget } from "./ChoiceWidget";
import { ConfirmWidget } from "./ConfirmWidget";
import { DateWidget } from "./DateWidget";

type WidgetProps<T extends WidgetSpec["type"]> = {
  spec: Extract<WidgetSpec, { type: T }>;
  onSubmit: (value: string) => void;
};

export const WIDGET_REGISTRY: {
  [K in WidgetSpec["type"]]: ComponentType<WidgetProps<K>>;
} = {
  choice: ChoiceWidget,
  confirm: ConfirmWidget,
  date: DateWidget,
};
```

- [ ] **Step 5: Commit**

```
git add frontend/components/chat/widgets/
git commit -m "feat(frontend): inline chat widget components + registry"
```

---

## Phase 4 — Chat pane

### Task 8: ChatStream + Composer + ChatPane

**Files:**
- Create: `frontend/components/chat/ChatStream.tsx`
- Create: `frontend/components/chat/Composer.tsx`
- Create: `frontend/components/chat/ChatPane.tsx`

- [ ] **Step 1: ChatStream**

```tsx
"use client";
import { useEffect, useRef } from "react";
import { WIDGET_REGISTRY } from "./widgets";
import { useSessionStore } from "@/lib/sessionStore";
import type { Message, WidgetSpec } from "@/lib/types";

const THINKING_RE = /<(?:thinking|scratchpad|reasoning)>[\s\S]*?<\/(?:thinking|scratchpad|reasoning)>/gi;

function cleanText(t: string): string {
  return t.replace(THINKING_RE, "").trim();
}

function bubbleClass(m: Message): string {
  if (m.role === "user") {
    return "ml-12 rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground";
  }
  if (m.role === "system") {
    return "rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive";
  }
  return "rounded-lg bg-muted px-4 py-2 text-sm";
}

type Props = {
  onWidgetSubmit: (spec: WidgetSpec, value: string) => void;
};

export function ChatStream({ onWidgetSubmit }: Props) {
  const messages = useSessionStore((s) => s.messages);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  return (
    <ol
      className="flex-1 space-y-2 overflow-y-auto px-3 py-2"
      aria-live="polite"
      aria-label="Chat"
    >
      {messages.map((m) => (
        <li key={m.id} className={bubbleClass(m)}>
          <p className="whitespace-pre-wrap">{cleanText(m.text)}</p>
          {m.role === "agent" && m.widgets
            ? m.widgets.map((w) => {
                const Comp = WIDGET_REGISTRY[w.type] as React.ComponentType<{
                  spec: typeof w;
                  onSubmit: (v: string) => void;
                }>;
                return (
                  <div key={w.widgetId} className="mt-2">
                    <Comp spec={w} onSubmit={(v) => onWidgetSubmit(w, v)} />
                  </div>
                );
              })
            : null}
        </li>
      ))}
      <div ref={endRef} aria-hidden />
    </ol>
  );
}
```

- [ ] **Step 2: Composer**

```tsx
"use client";
import { useState } from "react";
import { Mic, MicOff, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useSessionStore } from "@/lib/sessionStore";

type Props = {
  onSendText: (text: string) => Promise<void> | void;
  onStartVoice: () => Promise<void> | void;
  onStopVoice: () => void;
};

export function Composer({ onSendText, onStartVoice, onStopVoice }: Props) {
  const [draft, setDraft] = useState("");
  const sending = useSessionStore((s) => s.sending);
  const voiceStatus = useSessionStore((s) => s.voiceStatus);

  const voiceActive = voiceStatus === "listening" || voiceStatus === "speaking" || voiceStatus === "connecting";

  async function submit() {
    const t = draft.trim();
    if (!t || sending) return;
    setDraft("");
    await onSendText(t);
  }

  function micClick() {
    if (voiceActive) onStopVoice();
    else void onStartVoice();
  }

  return (
    <form
      className="flex items-end gap-2 border-t p-2"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <Textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={1}
        placeholder="Scrie aici sau apasă pe microfon..."
        aria-label="Mesaj nou"
        disabled={sending}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            void submit();
          }
        }}
        className="min-h-[40px] flex-1 resize-none"
      />
      <Button
        type="button"
        variant={voiceActive ? "default" : "outline"}
        size="icon"
        onClick={micClick}
        aria-label={voiceActive ? "Oprește microfonul" : "Pornește microfonul"}
        title={voiceActive ? "Oprește microfonul" : "Pornește microfonul"}
        className={voiceActive ? "bg-red-600 text-white hover:bg-red-700" : ""}
      >
        {voiceActive ? <MicOff size={18} /> : <Mic size={18} />}
      </Button>
      <Button
        type="submit"
        size="icon"
        disabled={sending || draft.trim().length === 0}
        aria-label="Trimite"
      >
        <Send size={18} />
      </Button>
    </form>
  );
}
```

- [ ] **Step 3: ChatPane**

```tsx
"use client";
import { ChatStream } from "./ChatStream";
import { Composer } from "./Composer";
import type { WidgetSpec } from "@/lib/types";

type Props = {
  onWidgetSubmit: (spec: WidgetSpec, value: string) => void;
  onSendText: (text: string) => Promise<void> | void;
  onStartVoice: () => Promise<void> | void;
  onStopVoice: () => void;
};

export function ChatPane({ onWidgetSubmit, onSendText, onStartVoice, onStopVoice }: Props) {
  return (
    <section className="flex h-full flex-col" aria-label="Chat cu asistentul">
      <ChatStream onWidgetSubmit={onWidgetSubmit} />
      <Composer onSendText={onSendText} onStartVoice={onStartVoice} onStopVoice={onStopVoice} />
    </section>
  );
}
```

- [ ] **Step 4: Commit**

```
git add frontend/components/chat/ChatStream.tsx frontend/components/chat/Composer.tsx frontend/components/chat/ChatPane.tsx
git commit -m "feat(frontend): ChatPane with ChatStream + Composer + widget rendering"
```

---

## Phase 5 — Right-pane subpages + router

### Task 9: All six right-pane substate components

**Files:**
- Create each in `frontend/components/right-pane/`

- [ ] **Step 1: WelcomePane**

```tsx
"use client";
import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";
import type { Procedure, Reminder } from "@/lib/types";

export function WelcomePane() {
  const citizen = useSessionStore((s) => s.citizen);
  const startProcedure = useSessionStore((s) => s.startProcedure);
  const openDrawer = useSessionStore((s) => s.openDrawer);
  const [procedures, setProcedures] = useState<Procedure[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);

  useEffect(() => {
    void api.listProcedures().then(setProcedures).catch(() => {});
    void api.listReminders().then(setReminders).catch(() => setReminders([]));
  }, []);

  const pendingReminders = reminders.filter((r) => r.status === "pending");
  const suggestions = filterSuggestionsForCitizen(procedures, citizen?.attributes ?? {}).slice(0, 4);

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center gap-5 p-6 text-center">
      <Sparkles className="text-primary" size={36} aria-hidden />
      <h2 className="text-2xl font-semibold">
        Bună{citizen?.prenume ? `, ${citizen.prenume}` : ""}. Cu ce te pot ajuta?
      </h2>
      <p className="text-sm text-muted-foreground">
        Spune-mi în cuvinte simple ce ai nevoie — eu mă ocup de hârtii.
      </p>

      <div className="flex flex-wrap justify-center gap-2 pt-2">
        {pendingReminders.length > 0 ? (
          <Button variant="secondary" size="sm" onClick={() => openDrawer()}>
            🔔 Ai {pendingReminders.length} {pendingReminders.length === 1 ? "amintire activă" : "amintiri active"}
          </Button>
        ) : null}
        {suggestions.map((p) => (
          <Button
            key={p.id}
            variant="outline"
            size="sm"
            onClick={() => void startProcedure(p.id)}
          >
            💡 {p.title}
          </Button>
        ))}
      </div>

      {suggestions.length === 0 && procedures.length === 0 ? (
        <Card className="mt-4">
          <CardContent className="p-4 text-sm text-muted-foreground">
            Se încarcă procedurile...
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function filterSuggestionsForCitizen(
  procs: Procedure[],
  attrs: { owns_vehicle?: boolean; has_children?: boolean; marital_status?: string },
): Procedure[] {
  // Light heuristic — surface a varied set, gate the obvious mismatches.
  const out: Procedure[] = [];
  const seenCategories = new Set<string>();
  for (const p of procs) {
    if (p.category.includes("vehicul") && attrs.owns_vehicle === false) continue;
    if (p.category.includes("copii") && attrs.has_children === false) continue;
    if (seenCategories.has(p.category)) continue;
    seenCategories.add(p.category);
    out.push(p);
    if (out.length >= 6) break;
  }
  return out;
}
```

- [ ] **Step 2: GuidePane**

```tsx
"use client";
import { Button } from "@/components/ui/button";
import { useSessionStore } from "@/lib/sessionStore";

export function GuidePane() {
  const procedure = useSessionStore((s) => s.procedure);
  const sendText = useSessionStore((s) => s.sendText);
  const transition = useSessionStore((s) => s.transitionRightPane);

  if (!procedure) return null;

  return (
    <article className="mx-auto max-w-2xl space-y-5 p-6">
      <header>
        <p className="text-xs uppercase tracking-wider text-muted-foreground">Pas curent · Ghid</p>
        <h2 className="mt-1 text-2xl font-semibold">{procedure.title}</h2>
        {procedure.description ? (
          <p className="mt-1 text-sm text-muted-foreground">{procedure.description}</p>
        ) : null}
      </header>

      <section>
        <h3 className="mb-2 text-sm font-medium">Ce vom face</h3>
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          {procedure.fields
            .filter((f) => f.required)
            .map((f) => (
              <li key={f.name}>{f.label}</li>
            ))}
          <li>Generăm PDF-ul gata de semnat</li>
        </ol>
      </section>

      {procedure.acte_necesare && procedure.acte_necesare.length > 0 ? (
        <section>
          <h3 className="mb-2 text-sm font-medium">Acte pe care să le ai la îndemână</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {procedure.acte_necesare.map((a, i) => (
              <li key={i}>
                {a.denumire}
                {a.obligatoriu === false ? (
                  <span className="text-muted-foreground"> (opțional)</span>
                ) : null}
                {a.observatie ? <span className="text-muted-foreground"> — {a.observatie}</span> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <p className="text-sm text-muted-foreground">
          Nu sunt acte fizice obligatorii pentru această procedură.
        </p>
      )}

      <div className="flex gap-2">
        <Button
          onClick={() => {
            transition({ kind: "filling" });
            void sendText("Da, continuă");
          }}
        >
          ✓ Continuă
        </Button>
        <Button
          variant="outline"
          onClick={() => void sendText("Vreau altceva, nu această procedură")}
        >
          Nu, vreau altceva
        </Button>
      </div>
    </article>
  );
}
```

- [ ] **Step 3: FillingPane**

```tsx
"use client";
import { FormPreview } from "@/components/FormPreview";
import { useSessionStore } from "@/lib/sessionStore";

export function FillingPane() {
  const procedure = useSessionStore((s) => s.procedure);
  const document = useSessionStore((s) => s.document);
  const rightPane = useSessionStore((s) => s.rightPane);
  const activeField = rightPane.kind === "filling" ? rightPane.activeField : undefined;

  if (!procedure || !document) return null;

  return (
    <div className="h-full overflow-auto p-4">
      <FormPreview procedure={procedure} values={document.fields} activeField={activeField} />
    </div>
  );
}
```

- [ ] **Step 4: ReviewPane**

```tsx
"use client";
import { useState } from "react";
import { Pencil, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";

export function ReviewPane() {
  const procedure = useSessionStore((s) => s.procedure);
  const document = useSessionStore((s) => s.document);
  const transition = useSessionStore((s) => s.transitionRightPane);
  const sendText = useSessionStore((s) => s.sendText);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [generating, setGenerating] = useState(false);

  if (!procedure || !document) return null;

  async function commitEdit(name: string) {
    if (!document) return;
    const updated = await api.patchDocumentFields(document.id, { [name]: draft });
    useSessionStore.setState({ document: updated });
    setEditing(null);
    setDraft("");
  }

  async function generatePdf() {
    if (!document) return;
    setGenerating(true);
    try {
      const r = await api.generatePdf(document.id);
      const fresh = await api.getDocument(document.id);
      useSessionStore.setState({ document: fresh });
      transition({ kind: "pdf", url: fresh.pdf_url ?? r.pdf_url });
      void sendText("Am generat PDF-ul, vezi în dreapta.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <article className="mx-auto max-w-2xl space-y-5 p-6">
      <header>
        <p className="text-xs uppercase tracking-wider text-muted-foreground">Verifică datele</p>
        <h2 className="mt-1 text-2xl font-semibold">{procedure.title}</h2>
      </header>

      <ul className="space-y-2">
        {procedure.fields.map((f) => {
          const v = document.fields[f.name];
          const filled = v !== undefined && v !== null && String(v).length > 0;
          const isEditing = editing === f.name;
          return (
            <li
              key={f.name}
              className="grid grid-cols-[1fr_auto] items-center gap-3 rounded-lg border bg-card p-3 text-sm"
            >
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground">{f.label}</p>
                {isEditing ? (
                  <Input
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") void commitEdit(f.name);
                    }}
                    autoFocus
                  />
                ) : (
                  <p className={filled ? "" : "text-muted-foreground"}>
                    {filled ? String(v) : "—"}
                  </p>
                )}
              </div>
              {isEditing ? (
                <Button size="icon" onClick={() => void commitEdit(f.name)} aria-label="Salvează">
                  <Check size={14} />
                </Button>
              ) : (
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => {
                    setEditing(f.name);
                    setDraft(filled ? String(v) : "");
                  }}
                  aria-label={`Editează ${f.label}`}
                >
                  <Pencil size={14} />
                </Button>
              )}
            </li>
          );
        })}
      </ul>

      <Button onClick={() => void generatePdf()} disabled={generating} size="lg">
        {generating ? "Se generează..." : "Generează PDF"}
      </Button>
    </article>
  );
}
```

- [ ] **Step 5: PdfPane**

```tsx
"use client";
import { Button } from "@/components/ui/button";
import { useSessionStore } from "@/lib/sessionStore";

export function PdfPane() {
  const rightPane = useSessionStore((s) => s.rightPane);
  const transition = useSessionStore((s) => s.transitionRightPane);
  if (rightPane.kind !== "pdf") return null;
  return (
    <div className="flex h-full flex-col p-4">
      <iframe
        src={rightPane.url}
        title="Previzualizare PDF"
        className="flex-1 rounded border bg-white"
      />
      <div className="mt-3 flex justify-end">
        <Button onClick={() => transition({ kind: "delivery" })}>Continuă spre trimitere</Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: DeliveryPane**

```tsx
"use client";
import { useState } from "react";
import { Printer, Save, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";

export function DeliveryPane() {
  const document = useSessionStore((s) => s.document);
  const transition = useSessionStore((s) => s.transitionRightPane);
  const [busy, setBusy] = useState<null | "save" | "send" | "print">(null);

  if (!document) return null;

  async function pick(channel: "save" | "send" | "print") {
    if (!document) return;
    setBusy(channel);
    try {
      const updated = await api.deliverDocument(document.id, channel);
      useSessionStore.setState({ document: updated });
      if (updated.ref_number) {
        transition({ kind: "done", refNumber: updated.ref_number });
      }
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col items-stretch gap-3 p-8">
      <h2 className="mb-2 text-xl font-semibold">Cum vrei să primești cererea?</h2>
      <Button size="lg" onClick={() => void pick("send")} disabled={busy !== null}>
        <Send className="mr-2" size={16} /> Trimite la primărie
      </Button>
      <Button size="lg" variant="outline" onClick={() => void pick("save")} disabled={busy !== null}>
        <Save className="mr-2" size={16} /> Salvează în contul meu
      </Button>
      <Button size="lg" variant="outline" onClick={() => void pick("print")} disabled={busy !== null}>
        <Printer className="mr-2" size={16} /> Tipărește acum
      </Button>
    </div>
  );
}
```

- [ ] **Step 7: DonePane**

```tsx
"use client";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSessionStore } from "@/lib/sessionStore";

export function DonePane() {
  const rightPane = useSessionStore((s) => s.rightPane);
  const reset = useSessionStore((s) => s.reset);
  if (rightPane.kind !== "done") return null;
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 p-10 text-center">
      <CheckCircle2 className="text-green-600" size={48} aria-hidden />
      <h2 className="text-2xl font-semibold">Gata.</h2>
      <p className="text-sm">
        Numărul tău de referință:{" "}
        <strong className="font-mono">{rightPane.refNumber}</strong>
      </p>
      <Button onClick={() => reset()}>Conversație nouă</Button>
    </div>
  );
}
```

- [ ] **Step 8: RightPane router**

```tsx
"use client";
import { useSessionStore } from "@/lib/sessionStore";
import { WelcomePane } from "@/components/right-pane/WelcomePane";
import { GuidePane } from "@/components/right-pane/GuidePane";
import { FillingPane } from "@/components/right-pane/FillingPane";
import { ReviewPane } from "@/components/right-pane/ReviewPane";
import { PdfPane } from "@/components/right-pane/PdfPane";
import { DeliveryPane } from "@/components/right-pane/DeliveryPane";
import { DonePane } from "@/components/right-pane/DonePane";

export function RightPane() {
  const kind = useSessionStore((s) => s.rightPane.kind);
  switch (kind) {
    case "welcome":
      return <WelcomePane />;
    case "guide":
      return <GuidePane />;
    case "filling":
      return <FillingPane />;
    case "review":
      return <ReviewPane />;
    case "pdf":
      return <PdfPane />;
    case "delivery":
      return <DeliveryPane />;
    case "done":
      return <DonePane />;
  }
}
```

- [ ] **Step 9: Commit**

```
git add frontend/components/right-pane/ frontend/components/chat/RightPane.tsx
git commit -m "feat(frontend): right-pane subpages + router"
```

---

## Phase 6 — Shell + TopBar + Drawer + ProfileMenu

### Task 10: TopBar, ProfileMenu, DocumentsDrawer

**Files:**
- Create: `frontend/components/chat/TopBar.tsx`
- Create: `frontend/components/chat/ProfileMenu.tsx`
- Create: `frontend/components/chat/DocumentsDrawer.tsx`

- [ ] **Step 1: TopBar**

```tsx
"use client";
import { FolderOpen, ChevronDown, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSessionStore } from "@/lib/sessionStore";
import { useKioskMode } from "@/lib/kioskMode";

export function TopBar() {
  const citizen = useSessionStore((s) => s.citizen);
  const openDrawer = useSessionStore((s) => s.openDrawer);
  const toggleProfile = useSessionStore((s) => s.toggleProfileMenu);
  const isKiosk = useKioskMode();

  return (
    <header className="flex items-center justify-between border-b bg-background px-4 py-2">
      <Button variant="outline" size="sm" onClick={openDrawer} aria-label="Documentele mele">
        <FolderOpen className="mr-2" size={16} aria-hidden />
        Documentele mele
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={toggleProfile}
        aria-label={isKiosk ? "Accesibilitate" : "Profil"}
        aria-haspopup="menu"
      >
        <User className="mr-2" size={16} aria-hidden />
        {isKiosk ? "Accesibilitate" : (citizen?.prenume ?? "Profil")}
        <ChevronDown className="ml-1" size={14} aria-hidden />
      </Button>
    </header>
  );
}
```

- [ ] **Step 2: ProfileMenu**

```tsx
"use client";
import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AccessibilityToggles } from "@/components/AccessibilityToggles";
import { Button } from "@/components/ui/button";
import { useSessionStore } from "@/lib/sessionStore";
import { useKioskMode } from "@/lib/kioskMode";
import { clearSession } from "@/lib/session";

export function ProfileMenu() {
  const open = useSessionStore((s) => s.profileMenuOpen);
  const close = useSessionStore((s) => s.closeProfileMenu);
  const reset = useSessionStore((s) => s.reset);
  const isKiosk = useKioskMode();
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) close();
    }
    if (open) document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open, close]);

  function signOut() {
    clearSession();
    window.location.href = "/login";
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          ref={ref}
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.15 }}
          role="menu"
          className="fixed right-3 top-12 z-50 w-[300px] rounded-lg border bg-background p-3 shadow-lg"
        >
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Accesibilitate
          </p>
          <AccessibilityToggles />
          {!isKiosk ? (
            <div className="mt-3 flex flex-col gap-1 border-t pt-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  reset();
                  close();
                }}
                className="justify-start"
              >
                ↻ Conversație nouă
              </Button>
              <Button variant="ghost" size="sm" onClick={signOut} className="justify-start">
                ⎋ Ieșire din cont
              </Button>
            </div>
          ) : null}
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
```

- [ ] **Step 3: DocumentsDrawer**

```tsx
"use client";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";
import type { Document, Procedure, Reminder } from "@/lib/types";

export function DocumentsDrawer() {
  const open = useSessionStore((s) => s.drawerOpen);
  const close = useSessionStore((s) => s.closeDrawer);
  const loadDocument = useSessionStore((s) => s.loadDocument);

  const [documents, setDocuments] = useState<Document[]>([]);
  const [procedures, setProcedures] = useState<Procedure[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);

  useEffect(() => {
    if (!open) return;
    void Promise.all([
      api.listDocuments(),
      api.listProcedures(),
      api.listReminders().catch(() => [] as Reminder[]),
    ]).then(([d, p, r]) => {
      setDocuments(d);
      setProcedures(p);
      setReminders(r);
    });
  }, [open]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, close]);

  const titleOf = (id: string) => procedures.find((p) => p.id === id)?.title ?? id;
  const pending = reminders.filter((r) => r.status === "pending");

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-40 bg-black/30"
            onClick={close}
            aria-hidden
          />
          <motion.aside
            initial={{ x: -380 }}
            animate={{ x: 0 }}
            exit={{ x: -380 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="fixed inset-y-0 left-0 z-50 flex w-[380px] max-w-[90vw] flex-col border-r bg-background shadow-xl"
            role="dialog"
            aria-label="Documentele mele"
          >
            <header className="flex items-center justify-between border-b px-4 py-3">
              <h2 className="text-lg font-semibold">Documentele mele</h2>
              <Button variant="ghost" size="icon" onClick={close} aria-label="Închide">
                <X size={18} />
              </Button>
            </header>

            <div className="flex-1 overflow-y-auto p-3">
              {pending.length > 0 ? (
                <section className="mb-4">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Pentru tine acum
                  </p>
                  <ul className="space-y-2">
                    {pending.map((r) => (
                      <li key={r.id}>
                        <Card>
                          <CardContent className="space-y-2 p-3">
                            <p className="text-sm font-medium">{r.title}</p>
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                onClick={async () => {
                                  const out = await api.startReminder(r.id);
                                  await loadDocument(out.document_id);
                                }}
                              >
                                Începe
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={async () => {
                                  await api.dismissReminder(r.id);
                                  setReminders((rs) => rs.filter((x) => x.id !== r.id));
                                }}
                              >
                                Renunță
                              </Button>
                            </div>
                          </CardContent>
                        </Card>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Documentele mele
              </p>
              {documents.length === 0 ? (
                <p className="text-sm text-muted-foreground">Niciun document încă.</p>
              ) : (
                <ul className="space-y-2">
                  {documents.map((d) => (
                    <li key={d.id}>
                      <button
                        type="button"
                        onClick={() => void loadDocument(d.id)}
                        className="w-full rounded-lg border bg-card p-3 text-left text-sm transition hover:bg-accent/40 focus:outline-none focus:ring-2"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium">{titleOf(d.procedure_id)}</p>
                            <p className="text-xs text-muted-foreground">
                              {new Date(d.created_at).toLocaleDateString("ro-RO")}
                            </p>
                            {d.ref_number ? (
                              <p className="font-mono text-xs text-muted-foreground">{d.ref_number}</p>
                            ) : null}
                          </div>
                          {d.status === "finalized" ? (
                            <Badge>Trimisă</Badge>
                          ) : (
                            <Badge variant="secondary">În lucru</Badge>
                          )}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}
```

- [ ] **Step 4: Commit**

```
git add frontend/components/chat/TopBar.tsx frontend/components/chat/ProfileMenu.tsx frontend/components/chat/DocumentsDrawer.tsx
git commit -m "feat(frontend): TopBar, ProfileMenu, DocumentsDrawer shell pieces"
```

---

### Task 11: ChatSurface (top-level shell) + voice integration

**Files:**
- Create: `frontend/components/chat/ChatSurface.tsx`
- Modify: `frontend/lib/useVoiceAgent.ts`

- [ ] **Step 1: Register propose_widget tool schema**

In `frontend/lib/useVoiceAgent.ts`, add to `TOOL_SCHEMAS`:

```ts
propose_widget: {
  name: "propose_widget",
  description: "Ask a structured UI question (choice/confirm/date) that the browser renders inline.",
  parameters: {
    type: "object",
    properties: {
      type: { type: "string", enum: ["choice", "confirm", "date"] },
      question: { type: "string" },
      options: { type: "array", items: { type: "string" } },
      target_field: { type: "string" },
    },
    required: ["type", "question"],
  },
},
```

- [ ] **Step 2: ChatSurface**

`frontend/components/chat/ChatSurface.tsx`:

```tsx
"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useSessionStore } from "@/lib/sessionStore";
import {
  useVoiceAgent,
  VoiceAgentMicDeniedError,
} from "@/lib/useVoiceAgent";
import { useAccessibilityPrefs, useLargeTextClass } from "@/lib/accessibilityStore";
import { useKioskMode } from "@/lib/kioskMode";
import { getSession } from "@/lib/session";
import { TopBar } from "./TopBar";
import { ProfileMenu } from "./ProfileMenu";
import { DocumentsDrawer } from "./DocumentsDrawer";
import { ChatPane } from "./ChatPane";
import { RightPane } from "./RightPane";
import type { WidgetSpec } from "@/lib/types";

type Props = {
  activeDocId: string | null;
};

export function ChatSurface({ activeDocId }: Props) {
  useLargeTextClass();
  const router = useRouter();
  const isKiosk = useKioskMode();
  const voiceOnly = useAccessibilityPrefs((s) => s.voiceOnly);
  const simpleLanguage = useAccessibilityPrefs((s) => s.simpleLanguage);

  const citizen = useSessionStore((s) => s.citizen);
  const hydrateCitizen = useSessionStore((s) => s.hydrateCitizen);
  const loadDocument = useSessionStore((s) => s.loadDocument);
  const sendText = useSessionStore((s) => s.sendText);
  const appendMessage = useSessionStore((s) => s.appendMessage);
  const setVoiceStatus = useSessionStore((s) => s.setVoiceStatus);
  const applyToolResult = useSessionStore((s) => s.applyToolResult);
  const reset = useSessionStore((s) => s.reset);
  const rightPaneKind = useSessionStore((s) => s.rightPane.kind);

  const voice = useVoiceAgent();
  const voiceStartedRef = useRef(false);

  // Auth gate.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!getSession()) router.replace("/login");
  }, [router]);

  // Hydrate citizen once.
  useEffect(() => {
    if (citizen) return;
    void hydrateCitizen().catch(() => {});
  }, [citizen, hydrateCitizen]);

  // Hydrate the active doc if URL has /r/<id>.
  useEffect(() => {
    if (!activeDocId) {
      reset();
      return;
    }
    void loadDocument(activeDocId).catch(() => {});
  }, [activeDocId, loadDocument, reset]);

  // Browser back/forward sync.
  useEffect(() => {
    function onPop() {
      const path = window.location.pathname;
      if (path === "/") reset();
      else if (path.startsWith("/r/")) {
        const id = path.slice(3);
        void loadDocument(id);
      }
    }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [reset, loadDocument]);

  // Mirror voice status into the store.
  useEffect(() => {
    setVoiceStatus(voice.state);
  }, [voice.state, setVoiceStatus]);

  // Wire voice transcripts → messages.
  const lastUserT = voice.lastTranscript;
  const lastAgentT = voice.lastAgentMessage;
  const prevUserT = useRef("");
  const prevAgentT = useRef("");
  useEffect(() => {
    if (lastUserT && lastUserT !== prevUserT.current) {
      appendMessage({
        id: Math.random().toString(36).slice(2),
        role: "user",
        text: lastUserT,
        via: "voice",
      });
      prevUserT.current = lastUserT;
    }
  }, [lastUserT, appendMessage]);
  useEffect(() => {
    if (lastAgentT && lastAgentT !== prevAgentT.current) {
      appendMessage({
        id: Math.random().toString(36).slice(2),
        role: "agent",
        text: lastAgentT,
      });
      prevAgentT.current = lastAgentT;
    }
  }, [lastAgentT, appendMessage]);

  // Register a tool handler that forwards into the store.
  useEffect(() => {
    voice.registerToolHandler(async (name, args) => {
      const { _result, ...realArgs } = args as { _result?: unknown };
      await applyToolResult(name, realArgs, _result);
      return {};
    });
  }, [voice, applyToolResult]);

  // Auto-start voice when voice_only and not yet started.
  useEffect(() => {
    if (!voiceOnly || !citizen || voiceStartedRef.current) return;
    voiceStartedRef.current = true;
    void voice
      .start({
        documentId: activeDocId ?? undefined,
        preferences: { simple_language: simpleLanguage, voice_only: voiceOnly },
      })
      .catch((err) => {
        if (err instanceof VoiceAgentMicDeniedError) {
          appendMessage({
            id: Math.random().toString(36).slice(2),
            role: "system",
            text: "Microfonul nu este permis. Folosește textul.",
          });
        }
      });
  }, [voiceOnly, citizen, activeDocId, simpleLanguage, voice, appendMessage]);

  async function startVoice() {
    if (!citizen) return;
    try {
      await voice.start({
        documentId: useSessionStore.getState().activeDocId ?? undefined,
        preferences: { simple_language: simpleLanguage, voice_only: voiceOnly },
      });
    } catch (err) {
      if (err instanceof VoiceAgentMicDeniedError) {
        appendMessage({
          id: Math.random().toString(36).slice(2),
          role: "system",
          text: "Microfonul nu este permis. Folosește textul.",
        });
      }
    }
  }

  function stopVoice() {
    voice.stop();
  }

  function onWidgetSubmit(_spec: WidgetSpec, value: string) {
    if (voice.state === "listening" || voice.state === "speaking") {
      // Voice is open — send as text into the live session, append as user msg.
      void voice.sendText(value);
      appendMessage({
        id: Math.random().toString(36).slice(2),
        role: "user",
        text: value,
        via: "text",
      });
    } else {
      void sendText(value);
    }
  }

  if (!citizen) {
    return <p className="p-6 text-muted-foreground">Se încarcă...</p>;
  }

  const engaged = rightPaneKind !== "welcome";
  const hideRightPane = voiceOnly;

  return (
    <div
      data-mode={engaged ? "engaged" : "idle"}
      data-kiosk={isKiosk ? "true" : "false"}
      className="flex h-screen w-screen flex-col bg-background text-foreground"
    >
      <TopBar />
      <ProfileMenu />
      <DocumentsDrawer />
      <main
        className={
          hideRightPane
            ? "grid h-full min-h-0 grid-cols-1 overflow-hidden"
            : engaged
              ? "grid h-full min-h-0 grid-cols-1 overflow-hidden md:grid-cols-[40%_60%]"
              : "grid h-full min-h-0 grid-cols-1 overflow-hidden"
        }
      >
        <ChatPane
          onWidgetSubmit={onWidgetSubmit}
          onSendText={(t) => {
            if (voice.state === "listening" || voice.state === "speaking") {
              return voice.sendText(t).then(() => {
                appendMessage({
                  id: Math.random().toString(36).slice(2),
                  role: "user",
                  text: t,
                  via: "text",
                });
              });
            }
            return sendText(t);
          }}
          onStartVoice={startVoice}
          onStopVoice={stopVoice}
        />
        {engaged && !hideRightPane ? (
          <aside className="overflow-y-auto border-l" aria-label="Document">
            <RightPane />
          </aside>
        ) : null}
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```
git add frontend/components/chat/ChatSurface.tsx frontend/lib/useVoiceAgent.ts
git commit -m "feat(frontend): ChatSurface shell + voice integration; add propose_widget tool schema"
```

---

## Phase 7 — Routing + redirects

### Task 12: Replace root + add /r/[id] + redirects from old routes

**Files:**
- Modify: `frontend/app/page.tsx`
- Create: `frontend/app/r/[id]/page.tsx`
- Modify: `frontend/app/home/page.tsx`
- Modify: `frontend/app/req/new/page.tsx`
- Modify: `frontend/app/req/[id]/page.tsx`
- Modify: `frontend/app/doc/[id]/page.tsx`
- Modify: `frontend/app/login/otp/page.tsx`

- [ ] **Step 1: Root page**

Replace `frontend/app/page.tsx`:

```tsx
"use client";
import { ChatSurface } from "@/components/chat/ChatSurface";

export default function HomePage() {
  return <ChatSurface activeDocId={null} />;
}
```

- [ ] **Step 2: /r/[id]**

Create `frontend/app/r/[id]/page.tsx`:

```tsx
"use client";
import { useParams } from "next/navigation";
import { ChatSurface } from "@/components/chat/ChatSurface";

export default function DocChatPage() {
  const params = useParams<{ id: string }>();
  return <ChatSurface activeDocId={params.id ?? null} />;
}
```

- [ ] **Step 3: Redirect stubs**

`frontend/app/home/page.tsx`:

```tsx
"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function HomeRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/");
  }, [router]);
  return null;
}
```

`frontend/app/req/new/page.tsx`:

```tsx
"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function ReqNewRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/");
  }, [router]);
  return null;
}
```

`frontend/app/req/[id]/page.tsx`:

```tsx
"use client";
import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function ReqIdRedirect() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  useEffect(() => {
    if (params.id) router.replace(`/r/${params.id}`);
    else router.replace("/");
  }, [router, params.id]);
  return null;
}
```

`frontend/app/doc/[id]/page.tsx`:

```tsx
"use client";
import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function DocIdRedirect() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  useEffect(() => {
    if (params.id) router.replace(`/r/${params.id}`);
    else router.replace("/");
  }, [router, params.id]);
  return null;
}
```

- [ ] **Step 4: Login redirect target**

In `frontend/app/login/otp/page.tsx`, find the line that redirects after OTP success (looks like `router.push("/home")` or similar) and change to `router.push("/")`.

- [ ] **Step 5: Commit**

```
git add frontend/app/page.tsx frontend/app/r/[id]/page.tsx frontend/app/home/page.tsx frontend/app/req/new/page.tsx frontend/app/req/[id]/page.tsx frontend/app/doc/[id]/page.tsx frontend/app/login/otp/page.tsx
git commit -m "feat(frontend): wire ChatSurface at / and /r/[id]; retire old routes"
```

---

## Phase 8 — MSW handler + cleanup + verification

### Task 13: MSW handler for propose_widget

**Files:**
- Modify: `frontend/mocks/handlers.ts`

- [ ] **Step 1: Add handler**

Append to `frontend/mocks/handlers.ts`:

```ts
// Inside the array of handlers, add a handler if not already covered by a wildcard:
// http.post("http://localhost:8000/tools/propose_widget", () =>
//   HttpResponse.json({ acknowledged: true, widget_id: "mock-" + Math.random().toString(36).slice(2) }),
// ),
```

Concretely, find the existing tool handler block (`http.post(":base/tools/:name", ...)` if it exists) — if it already proxies all tool names, no change needed. Otherwise add the specific handler.

- [ ] **Step 2: Commit**

```
git add frontend/mocks/handlers.ts
git commit -m "test(frontend): MSW handler for propose_widget"
```

---

### Task 14: Delete retired components

**Files:**
- Delete: `frontend/components/ChatPanel.tsx`
- Delete: `frontend/components/VocalFillFlow.tsx`
- Delete: `frontend/components/GuidedFillFlow.tsx`
- Delete: `frontend/components/CompletionModeSelector.tsx`
- Delete: `frontend/components/KioskShell.tsx`
- Delete (if unused after removals): `frontend/lib/completionMode.ts`

- [ ] **Step 1: Verify nothing imports them anymore**

```
cd frontend && npx tsc --noEmit
```

Expect: no errors. If errors, fix the offending imports before deletion.

- [ ] **Step 2: Delete the files**

```
rm frontend/components/ChatPanel.tsx
rm frontend/components/VocalFillFlow.tsx
rm frontend/components/GuidedFillFlow.tsx
rm frontend/components/CompletionModeSelector.tsx
rm frontend/components/KioskShell.tsx
rm frontend/lib/completionMode.ts  # only if grep -r confirms no imports
```

- [ ] **Step 3: Re-verify**

```
cd frontend && npx tsc --noEmit && npm run lint
```

- [ ] **Step 4: Commit**

```
git add -A frontend/components/ frontend/lib/
git commit -m "chore(frontend): delete retired multi-route components"
```

---

### Task 15: Final smoke — build + tests

- [ ] **Step 1: Frontend build**

```
cd frontend && npm run build
```

Expect: 9-ish routes (the old redirect stubs still produce routes), no type errors.

- [ ] **Step 2: Frontend tests**

```
cd frontend && npm test
```

Expect: rightPaneState + sessionStore tests passing.

- [ ] **Step 3: Backend tests**

```
cd backend && python -m pytest -v
```

Expect: full suite green (including new propose_widget + strip_thinking + allowlist tests).

- [ ] **Step 4: Commit any incidental fixes from the smoke**

```
git add -A
git commit -m "chore: smoke fixes"
# (only if anything actually changed; otherwise skip)
```

---

## Done.

When all tasks above are checked off:

1. Open `http://localhost:3000` after `cd frontend && npm run dev`.
2. Log in via `/login` (existing flow).
3. Click a suggestion chip → guide pane appears.
4. Continuă → filling pane.
5. Inline widgets and text both fill fields, mic also works.
6. Right pane progresses guide → filling → review → pdf → delivery → done.
7. Drawer opens, lists docs and reminders, click loads a doc.
8. Profile menu opens, toggles accessibility, signs out.
9. Refresh `/r/<id>` hydrates correctly.
10. Browser back returns to `/`.
