---
type: module
path: "frontend/app/login/"
status: active
language: typescript
created: 2026-05-23
updated: 2026-05-23
---

# Frontend Auth Flow

How the FE turns a click into a usable JWT.

## Two paths

### ROeID (demo)

1. `/login` shows a persona dropdown (Maria / Andrei / Elena) when `NEXT_PUBLIC_DEMO_MODE=1`.
2. User picks one → `api.loginRoeid({persona_id: "maria-ionescu"})`.
3. Backend returns `{challenge_id, phone_hint}`.
4. FE navigates to `/login/otp?phone=***1234&challenge=ch_xxx`.

### MRZ (real)

1. `/login` has an MRZ scanner (camera + tesseract.js OCR) or a paste field.
2. Parsed CNP + nume + prenume → `api.loginMrz({cnp, nume, prenume})`.
3. Same `{challenge_id, phone_hint}` response.

## OTP

1. `/login/otp` shows a 6-digit code input.
2. User types `123456` (mock) or the SMS code (prod) → `api.otp({challenge_id, code})`.
3. Backend returns `{access_token, citizen_id}`.
4. FE writes to localStorage: `localStorage.setItem("civicai:session", JSON.stringify({access_token, citizen_id}))`.
5. FE navigates to `/home`.

## Token use

`lib/api.ts:request()` reads `getSession()` from localStorage and attaches `Authorization: Bearer <token>` on every authenticated call. The voice WS reads the same token and sends it inside the `start` frame.

## Logout

`session.ts:clearSession()` removes the localStorage key. Routes that require auth (everything except `/`, `/login`, `/login/otp`) redirect to `/login` when no session is found.

## Token expiry

24h default. The FE doesn't proactively check `exp`; the next API call returns 401 and the FE redirects to login.

## See also

- [[auth]]
- [[security]]
- [[Flow Login + OTP]]
- [[ADR Mock OTP Flag]]
