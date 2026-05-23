---
type: module
path: "frontend/mocks/"
status: active
language: typescript
created: 2026-05-23
updated: 2026-05-23
---

# Frontend MSW Mocks

When `NEXT_PUBLIC_USE_MOCKS=1`, MSW (Mock Service Worker) intercepts every backend call from the FE and serves canned responses from `mocks/handlers.ts`. Useful for:

- Solo frontend dev without running a backend.
- Reproducing edge cases (network errors, slow responses).
- Demo recordings when the backend is unstable.

## Persona fixtures

`mocks/fixtures.ts` mirrors the 3 seeded citizens (Maria, Andrei, Elena) **exactly**:

- Same CNPs
- Same attribute shape
- Same persona dropdown labels

This is the FE-BE contract you must keep in sync when the seed migration ([[Database Schema]] `migrations/002_seed_data.sql`) changes.

## Limitations

MSW can't intercept WebSockets. So:

- Text chat: mocked (`POST /agent/chat`, `POST /agent/chat/stream`).
- Voice WS: there is no mock. With `USE_MOCKS=1`, voice is effectively disabled — `useVoiceAgentBridge.start()` will fail to connect, and the FE shows a "voice unavailable" state.

For a full demo, use `USE_MOCKS=0` and a real backend.

## See also

- [[Frontend Lib]]
- frontend/mocks/handlers.ts
- frontend/mocks/fixtures.ts
