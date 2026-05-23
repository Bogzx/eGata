---
type: component
status: active
created: 2026-05-23
updated: 2026-05-23
---

# JWT Auth

## Claims

```json
{
  "sub": "<citizen_uuid>",
  "iat": <unix>,
  "exp": <unix + 86400>,
  "iss": "civicai"
}
```

- HS256, secret in `JWT_SIGNING_SECRET`.
- No audience claim. The citizen identity IS the authorization.
- Every authenticated route uses `Depends(current_citizen_id)` ([[security]]) which decodes + extracts `sub` as a UUID.

## Two transports

| Transport | How the token is sent |
|---|---|
| REST + SSE | `Authorization: Bearer <jwt>` header |
| Voice WS | Inside the first JSON frame: `{"type":"start","token":"<jwt>", ...}` |

Browsers cannot set `Authorization` on a WS upgrade — see [[ADR Single Live Session Text + Voice]].

## Ownership checks

JWT identity is necessary but **not sufficient**. Every document touch additionally verifies `doc.citizen_id == jwt.sub` via `_require_owner` ([[documents]]). Reminders do the same inline.

## Refresh

No refresh tokens. The token lasts 24h (env `JWT_EXPIRES_SECONDS`). After expiry the user re-logs through OTP.

## See also

- [[security]]
- [[auth]]
- [[Flow Login + OTP]]
