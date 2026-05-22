# Plan 2 — Checkpoint 1 Status

## Backend requirements per roadmap §5

- [x] Deploy config ready (railway.json, Procfile, Dockerfile). Live deploy pending.
- [x] Supabase Postgres EU schema authored: migrations 001–004 with RLS enabled, 3 seeded citizens. Apply pending.
- [x] `/auth/login-roeid`, `/auth/login-mrz`, `/auth/otp` all wired (mock OTP code "123456" when `MOCK_OTP=1`).
- [x] `/citizens/me` returns full profile.
- [x] `/procedures/lookup` RAG endpoint wired with embed + pgvector search + redirect fallback (threshold 0.55).
- [x] 7 procedure JSON files loaded; embed pipeline ready (run `scripts/embed_procedures.py` after live Supabase is up).
- [x] Document CRUD endpoints work; ledger writes for `doc_created` and `completed_draft`.
- [x] `/documents/{id}/generate-pdf` renders LaTeX template + `pdflatex` subprocess + Supabase Storage upload + `pdf_generated` ledger.
- [x] `/documents/{id}/deliver` finalizes + writes `delivered` ledger + optional Twilio SMS for `send`.
- [x] `/documents/{id}/ledger` returns chain with `verified` computed via `verify_chain`.
- [x] `/agent/chat` returns canned RO responses + tool_calls hint (Wave 1 contract).

## Test coverage (key functionalities only, per execution instructions)

- `test_health.py` — health endpoint smoke.
- `test_ledger.py` — 7 tests covering canonical JSON, payload hash, row hash, enum, valid chain, tampered payload rejection, broken link rejection.
- `test_pdf.py` — 5 tests for LaTeX escape + render_template (security-critical).
- `test_embeddings.py` — 5 tests for cosine, source_text, registry validation.
- `test_end_to_end_mocked.py` — 1 full happy-path integration test login → otp → me → create → patch → generate-pdf → deliver → ledger.

Total: 19 tests, all passing.

## Handoff notes for Plan 3
- `app/agent.py` body is replaceable; keep `POST /agent/chat` signature stable.
- `app/tools/` directory does not exist yet — Plan 3 creates it.
- `app/voice.py`, `app/twilio_bridge.py` are new modules for Plan 3.

## Handoff notes for Plan 4
- `app/reminders.py`, `app/demo.py` are new modules.
- Background worker should reuse `app/ledger.py:append_ledger` for `reminder_created`.
- `applies_if` expression parser lives in Plan 4 (the field is already present on next_steps in the JSONs).

## Deviations from plan

- `pydantic` pinned to `>=2.10,<2.12` instead of `==2.9.2` because `pydantic-ai==0.0.13` requires `pydantic>=2.10`. No API-level impact.
- Skipped writing tests for: auth router, citizen profile, procedure registry HTTP layer, documents CRUD HTTP layer, generate-pdf HTTP layer, deliver HTTP layer, agent mock, migration file content checks, procedure file content checks, template file content checks. The end-to-end mocked test exercises every endpoint and ledger writes paths through real wiring.
