---
type: module
path: "frontend/lib/"
status: active
language: typescript
created: 2026-05-23
updated: 2026-05-23
---

# Frontend Lib

The glue between React and the backend. Five files matter for the connection.

## `api.ts` — REST client

```ts
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export const api = {
  loginRoeid, loginMrz, otp,
  getCitizenMe, patchCitizenAttributes,
  lookupProcedure, listProcedures, getProcedure,
  listScenarios, getScenarioPlan,
  createDocument, getDocument, listDocuments,
  patchDocumentFields, generatePdf, deliverDocument, getDocumentLedger,
  listReminders, patchReminderStatus, startReminder, dismissReminder,
  resetDemo,
  chat, submitWidget,
};
```

Every method:
- Reads `localStorage.civicai:session` for the bearer token.
- Adds `Authorization: Bearer <token>` (unless `auth: false`).
- Throws `ApiError(status, body, message)` on non-2xx.

The `chat()` method is the **non-streaming** counterpart of `streamChat()`. Both hit the same backend; the streaming one is preferred in production code paths.

## `sseChat.ts` — SSE consumer

```ts
streamChat(req, {
  onConversation, onDelta, onToolCall, onToolResult,
  onSessionSnapshot, onFrontendEvent,
  onDone, onError,
}, signal?)
```

Streams `POST /agent/chat/stream` via fetch + ReadableStream. SSE frames split on blank line (`\n\n` or `\r\n\r\n`). Each frame:

- `conversation` → `onConversation`
- `delta` → `onDelta` (text is **cumulative**, not delta — replace, don't append)
- `tool_call` / `tool_result` → optional UI breadcrumbs
- `frontend_event` → `onFrontendEvent` (carries a `FrontendEvent`)
- `session_snapshot` → `onSessionSnapshot` (carries `SessionSnapshot`)
- `done` → terminal happy
- `error` → terminal sad

See [[SSE Frame Schema]].

## `voiceWs.ts` — raw WS client

```ts
class VoiceWs {
  connect(url): Promise<void>
  sendStart({token, documentId?, conversationId?, preferences?})
  sendText(text)
  sendWidgetSubmission(widgetId, value)
  sendInterrupt()
  sendAudio(chunk)
  close()
}
```

Handles JSON control frames + binary audio. Surface mirrors [[Voice WS Frame Schema]].

> [!gotcha] `send()` throws when WS not OPEN
> Specifically the `sendText` path. ChatSurface catches the throw and falls back to SSE — so if voice is down the message still gets to the agent.

## `useVoiceAgentBridge.ts` — React hook

```ts
const { state, wsReady, micOn, start, stop, enableMic, disableMic, sendText, submitWidget, registerToolHandler } = useVoiceAgentBridge();
```

- `state`: "idle" | "connecting" | "listening" | "speaking" | "error"
- `wsReady`: WS open + Live ready
- `micOn`: mic recording (orthogonal to wsReady)
- `start({documentId?, preferences?, callbacks...})` opens WS + speaker; does NOT start mic.
- `enableMic()` starts mic capture (may throw `VoiceAgentMicDeniedError`).
- `submitWidget(id, value)` round-trips through the WS — falls back to HTTP `/agent/widget-result` via `sessionStore` if WS is down.

See [[Frontend Voice Bridge]].

## `sessionStore.ts` — Zustand mirror

The single source of truth on the FE. Tracks:
- `citizen`, `document`, `procedure`, `activeDocId`, `conversationId`
- `messages` (chat bubbles, localStorage-persisted per docId)
- `voiceStatus`, `micOn`, `drawerOpen`
- `session` — the backend `SessionSnapshot` mirror

The store applies `FrontendEvent`s to drive UI mutations: `document_opened` → `pushPath("/r/<id>")`, `widget_proposed` → render widget on latest agent bubble, etc.

See [[Frontend Session Mirror]].

## Other lib files

- `session.ts` — tiny `getSession()` / `setSession()` localStorage helpers
- `audioWorklet.ts` — mic capture worklet + audio playback queue
- `i18n.ts` — Romanian + English strings
- `accessibilityStore.ts` — `large_text` / `simple_language` / `voice_only` toggles (mirrored to `citizens.attributes.accessibility`)
- `kioskMode.ts` — kiosk-shell behaviors (auto-logout, idle timer)
- `motion.ts` — Framer Motion variants
- `mrz.ts` — MRZ scanner / OCR helpers (tesseract.js)

## See also

- [[Frontend Map]]
- [[Frontend Voice Bridge]]
- [[Frontend Session Mirror]]
- [[Frontend MSW Mocks]]
