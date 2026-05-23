---
type: module
path: "backend/app/security.py"
status: active
language: python
purpose: "JWT mint / decode / current-citizen FastAPI dependency."
depends_on: [config]
used_by: [auth, citizens, documents, procedures, reminders, agent, agent_voice]
created: 2026-05-23
updated: 2026-05-23
---

# security

Three functions:

| Function | Returns | Used by |
|---|---|---|
| `mint_access_token(citizen_id)` | JWT string | [[auth]] after OTP exchange |
| `decode_token(token)` | claims dict | [[agent_voice]] (validates the token from inside the `start` WS frame) |
| `current_citizen_id` (FastAPI Depends) | `UUID` | every authenticated route |

## Claims

```json
{
  "sub": "<citizen_uuid>",
  "iat": <unix>,
  "exp": <unix + JWT_EXPIRES_SECONDS>,
  "iss": "civicai"
}
```

No audience, no scope. The citizen identity IS the authorization — backend code checks `doc["citizen_id"] == session.citizen_id` everywhere a document is touched.

## Algorithm

HS256. `JWT_SIGNING_SECRET` must be set. Tokens are valid for 24 hours by default.

## How the voice WS gets the token

Browsers cannot set `Authorization` on a WebSocket upgrade. So:

- HTTP routes: `Bearer <token>` header (HTTPBearer dep).
- Voice WS (`/agent/voice/ws`): the **first JSON frame** the client sends is `{"type":"start","token":"<jwt>", ...}` and the bridge calls `decode_token()` to resolve the citizen.

See [[Voice WS Frame Schema]] + [[agent_voice]].
