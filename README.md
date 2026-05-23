# eGata

Conversational AI agent for Romanian primărie procedures. Built for the Cluj Hackathon 2026 (Bosch Cluj, May 22-24).

Spune-i ce ai nevoie. Îți spune ce acte îți trebuie. Le și completează cu tine.

## Repo layout

```
backend/            FastAPI + Supabase + LaTeX PDF + hash-chain ledger (Plan 2)
frontend/           Next.js 15 app: kiosk + web + mobile-responsive citizen UI (Plan 1)
contracts/          OpenAPI 3.1 spec exported from FastAPI
docs/superpowers/   Design spec + the four implementation plans + execution roadmap
```

See `docs/superpowers/specs/2026-05-23-egata-design.md` for the full product+architecture spec.

## Checkpoint 1 — running the integrated stack

At Checkpoint 1, frontend (Plan 1) talks to backend (Plan 2) directly — no MSW in the loop.

### 1. Backend

Prereqs: Python 3.12, a Supabase project (EU region), an Azure OpenAI resource with a chat deployment + embedding deployment + a VoiceLive realtime model.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -e .
cp ../.env.example .env                                # fill in SUPABASE_* + AZURE_OPENAI_* + AZURE_VOICELIVE_*
python scripts/apply_migrations.py                     # creates schema + seeds 3 demo citizens
python -m scripts.index_rag                            # embeds procedures + scenarios (text-embedding-3-large, 768 dims)
uvicorn app.main:app --reload --port 8000
```

Verify:
```bash
curl http://localhost:8000/health     # → {"status":"ok"}
```

### 2. Frontend

```bash
cd frontend
npm install --legacy-peer-deps
cp .env.local.example .env.local
# In .env.local set:
#   NEXT_PUBLIC_USE_MOCKS=0
#   NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev                                            # http://localhost:3000
```

### 3. Demo walk-through

1. Open http://localhost:3000 → "Intră în cont"
2. Choose persona "Maria Ionescu" → "Login cu ROeID"
3. OTP code: `123456` (works only while `MOCK_OTP=1`)
4. Home screen: see Maria's seeded documents + 2 reminders
5. "Începe o cerere nouă" → search "vreau să-mi schimb domiciliul"
6. Pick **Schimbare domiciliu** → guided mode fills auto-known fields, asks for the rest
7. Once required fields are filled, the three delivery buttons appear: save / send / print
8. After delivery, the ref number appears (`CV-XXXX`) and the ledger picks up the event
9. Click the document on `/home` to see the full `AuditTimeline`

### 4. Wave 1 dev with frontend only (no backend)

Set `NEXT_PUBLIC_USE_MOCKS=1` and run `npm run dev` — MSW serves the same contract from `frontend/mocks/handlers.ts` with the same 3 personas. Useful for solo frontend work.

## Personas and demo data

The 3 demo citizens are seeded by `backend/migrations/002_seed_data.sql`. Frontend MSW fixtures (`frontend/mocks/fixtures.ts`) mirror these exactly.

| Persona ID | Name | CNP | Accessibility profile |
|---|---|---|---|
| `maria-ionescu` | Maria Ionescu (40) | 2851014123456 | Standard |
| `andrei-popa` | Andrei Popa (36) | 1900512123456 | Simple-language |
| `elena-dumitru` | Elena Dumitru (63) | 2620908123456 | Voice-only + simple + large-text |

Demo phone numbers in the seed are placeholders. Replace with real team-member numbers before the live demo to receive actual SMS confirmations.

## Procedures shipped

All procedures live in `backend/procedures/*.json`. Headline flows:

- `schimbare-domiciliu` — full flow (the headline demo)
- `preschimbare-ci`
- `certificat-fiscal`

Each JSON file defines field schemas, the LaTeX template name, and `next_steps[]` for the proactive layer (Plan 4).

## Roadmap

- **Wave 1 ✅** — Plans 1 (frontend) + 2 (backend) merged.
- **Wave 2 (next)** — Plans 3 (agent + Azure VoiceLive voice bridge) + 4 (proactive worker, polish, a11y final pass).
- **Checkpoint 2** — full agent-driven flow + reminders worker + a11y certification.

See `docs/superpowers/plans/2026-05-23-egata-execution-roadmap.md` for the full execution model.

## Regenerating the OpenAPI contract

When backend routes change, regenerate `contracts/openapi.yaml`:

```bash
cd backend
python scripts/export_openapi.py
```

The frontend's `lib/types.ts` and `lib/api.ts` should be hand-aligned after major route changes — they're not auto-generated to keep the codebase simple at hackathon pace.

## Running tests

Backend:
```bash
cd backend && pytest
```

Frontend (Vitest + Playwright are installed but most test files were skipped to ship faster — see `docs/superpowers/plans/2026-05-23-egata-plan-1-frontend-foundation.md` for the full test plan if you want to backfill).
