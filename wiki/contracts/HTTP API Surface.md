---
type: contract
status: active
created: 2026-05-23
updated: 2026-05-23
---

# HTTP API Surface

Every REST route, grouped by router. Auth column shows whether `Authorization: Bearer <jwt>` is required.

## /auth ([[auth]])

| Verb | Path | Body | Returns | Auth |
|---|---|---|---|---|
| POST | `/auth/login-roeid` | `{persona_id?: str}` | `ChallengeResponse {challenge_id, phone_hint}` | — |
| POST | `/auth/login-mrz` | `{cnp, nume, prenume}` | `ChallengeResponse` | — |
| POST | `/auth/otp` | `{challenge_id, code}` | `OTPResponse {access_token, citizen_id}` | — |

## /citizens ([[citizens]])

| Verb | Path | Body | Returns | Auth |
|---|---|---|---|---|
| GET | `/citizens/me` | — | `CitizenResponse` | ✓ |
| PATCH | `/citizens/me/attributes` | `{attributes: {...}}` | `CitizenResponse` | ✓ |

## /procedures ([[procedures]])

| Verb | Path | Body | Returns | Auth |
|---|---|---|---|---|
| GET | `/procedures` | — | `list[Procedure]` | — |
| GET | `/procedures/{id}` | — | `ResolvedProcedure` | — |
| POST | `/procedures/lookup` | `{query}` | `ProcedureLookupResponse {matches, redirect_candidate}` | ✓ |

## /scenarios ([[scenarios]])

| Verb | Path | Body | Returns | Auth |
|---|---|---|---|---|
| GET | `/scenarios` | — | `list[ScenarioSummary]` | — |
| GET | `/scenarios/{id}` | — | `ScenarioPlan` | — |

## /documents ([[documents]])

| Verb | Path | Body | Returns | Auth |
|---|---|---|---|---|
| POST | `/documents` | `{procedure_id}` | `DocumentResponse` (201) | ✓ |
| GET | `/documents` | — | `list[DocumentResponse]` | ✓ |
| GET | `/documents/{id}` | — | `DocumentResponse` | ✓ |
| PATCH | `/documents/{id}/fields` | `{fields: {...}}` | `DocumentResponse` | ✓ |
| POST | `/documents/{id}/generate-pdf` | — | `{pdf_url}` | ✓ |
| POST | `/documents/{id}/deliver` | `{delivery: save\|send\|print}` | `DocumentResponse` | ✓ |
| GET | `/documents/{id}/ledger` | — | `LedgerResponse {entries, verified}` | ✓ |

## /agent ([[agent]] + [[agent_voice]])

| Verb | Path | Body | Returns | Auth |
|---|---|---|---|---|
| POST | `/agent/chat` | `AgentChatRequest` | `AgentChatResponse` | ✓ |
| POST | `/agent/chat/stream` | `AgentChatRequest` | `text/event-stream` | ✓ |
| POST | `/agent/widget-result` | `WidgetResultRequest` | `WidgetResultResponse` | ✓ |
| WSS | `/agent/voice/ws` | — (token in first frame) | binary + JSON | ✓ via start frame |

## /reminders ([[reminders]])

| Verb | Path | Body | Returns | Auth |
|---|---|---|---|---|
| GET | `/reminders` | — | `list[ReminderResponse]` | ✓ |
| PATCH | `/reminders/{id}` | `{status}` | `ReminderResponse` | ✓ |
| POST | `/reminders/{id}/start` | — | `StartReminderResponse` | ✓ |
| POST | `/reminders/{id}/dismiss` | — | `ReminderResponse` | ✓ |

## /voice/twilio ([[twilio_bridge]])

| Verb | Path | Body | Returns | Auth |
|---|---|---|---|---|
| POST | `/voice/twilio/webhook` | Twilio form-encoded | TwiML XML | Twilio shared secret (out of scope) |
| WSS | `/voice/twilio` | — | Twilio Media Streams envelopes | Twilio session |

## /demo ([[demo]])

| Verb | Path | Body | Returns | Auth |
|---|---|---|---|---|
| POST | `/demo/reset` | `{citizen_id?}` | `ResetResponse` | `X-Demo-Token` header |

## /health, /healthz ([[health]])

| Verb | Path | Returns | Auth |
|---|---|---|---|
| GET | `/health` | `{"status":"ok","service":"civicai-backend"}` | — |
| GET | `/healthz` | `{ok, checks: {supabase, gemini_key, twilio_token}}` | — |

## CORS

[[main]] sets origins from `ALLOW_ORIGINS` (csv). `allow_credentials=True`, so `*` is forbidden in browsers — use explicit origins.

## OpenAPI

`backend/scripts/export_openapi.py` writes `contracts/openapi.yaml` from FastAPI's runtime schema. The frontend's `lib/types.ts` is **hand-aligned** to this — not auto-generated (intentional for hackathon pace). When backend models change, regenerate the YAML and align by hand.
