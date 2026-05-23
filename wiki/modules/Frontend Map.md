---
type: module
path: "frontend/"
status: active
language: typescript
purpose: "Next.js 15 app — how it connects to the backend."
depends_on: [main, agent, agent_voice, documents, citizens, procedures, scenarios, reminders, auth]
created: 2026-05-23
updated: 2026-05-23
---

# Frontend Map

The Next.js 15 app. Detailed page layout is out of scope for this wiki, but the **connection points** are.

## Stack

- Next.js 15.5, React 19, TypeScript 5.6
- Zustand for client state ([[Frontend Session Mirror]])
- TailwindCSS + Radix UI primitives
- Framer Motion for transitions
- MSW for mocked dev mode (see [[Frontend MSW Mocks]])
- Vitest + Playwright (mostly skipped per hackathon ship-fast plan)

## Routes

| Route | Purpose |
|---|---|
| `/` | Splash / "Intră în cont" |
| `/login` | ROeID persona dropdown + MRZ scanner |
| `/login/otp` | OTP code entry |
| `/home` | Authenticated dashboard: docs + reminders + accessibility toggles |
| `/req/new` | Search/lookup for a new request (text field, calls `lookup_procedure`) |
| `/req/[id]` | Active request page — the chat surface + right pane |
| `/r/[id]` | Alias / direct deep link to a document by id |
| `/doc/[id]` | Read-only completed document view (audit timeline + PDF link) |
| `/p/[id]` | Procedure detail page (catalog browse) |

## Lib glue (everything in `frontend/lib/`)

See [[Frontend Lib]] for details. The five files that own the backend conversation:

- `api.ts` — REST client. Every backend route has a typed wrapper.
- `sseChat.ts` — `POST /agent/chat/stream` SSE consumer.
- `voiceWs.ts` — raw `/agent/voice/ws` client.
- `useVoiceAgentBridge.ts` — React hook composing voiceWs + mic + speaker.
- `sessionStore.ts` — Zustand store that mirrors the backend `SessionSnapshot` + applies `FrontendEvent`s.

## Auth bootstrap

See [[Frontend Auth Flow]].

## Right pane state machine

The right pane on `/req/[id]` mirrors the backend session state:

| Backend state | Right pane |
|---|---|
| EXPLORING | `WelcomePane` (catalog suggestion / lookup results) |
| CONFIRMING_MATCH | `MatchesPane` or `PlanPane` (scenario) |
| FILLING | `FillingPane` (live form preview from `document.fields`) |
| REVIEWING | `ReviewPane` (deliver options) |
| DELIVERED | `DonePane` (success + ref number + PDF link + audit timeline) |
| REDIRECTED | redirect card |

## Components worth knowing

- `ChatSurface` / `ChatStream` — chat bubbles, widget rendering
- `Composer` — text input that switches between SSE chat and voice WS
- `AuditTimeline` — reads `/documents/{id}/ledger` and shows hash-chain visualization
- `DemoResetButton` — calls `/demo/reset`
- `AccessibilityToggles` — toggles `simple_language` / `voice_only` / `large_text` and PATCHes `/citizens/me/attributes`

## Two operational modes

- `NEXT_PUBLIC_USE_MOCKS=1` — MSW intercepts every backend call, serves from `mocks/handlers.ts`. Lets you build/demo the FE without a running backend. See [[Frontend MSW Mocks]].
- `NEXT_PUBLIC_USE_MOCKS=0` — calls the real backend at `NEXT_PUBLIC_API_BASE_URL`.

## See also

- [[Frontend Lib]]
- [[Frontend Auth Flow]]
- [[Frontend Voice Bridge]]
- [[Frontend Session Mirror]]
- [[Frontend MSW Mocks]]
