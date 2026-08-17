# eGata Backend Runbook

## Local dev

```bash
cd backend
py -3.12 -m venv .venv
.venv/Scripts/activate     # Windows; on Linux/Mac: source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example .env    # single canonical example, at the repo root
pytest
uvicorn app.main:app --reload
```

## Supabase setup

1. Create Supabase project in EU region (preferred: eu-central-1).
2. Enable `vector` and `pgcrypto` extensions in the SQL editor.
3. Apply migrations:
   ```bash
   python scripts/apply_migrations.py
   ```
4. Populate embeddings:
   ```bash
   python scripts/embed_procedures.py
   ```
5. The `pdfs` storage bucket is auto-created on first upload, and is
   **private** — downloads go through short-lived signed URLs (app/storage.py).

> For local work you do not need Supabase at all: `docker compose up` brings
> up Postgres+pgvector with the migrations and seed applied, and the backend
> stores PDFs on a local volume. See the repo README.

## Railway deploy

1. `railway login` and `railway link` (or use the web UI).
2. Set environment variables from the repo-root `.env.example` in the Railway dashboard.
   - `MOCK_OTP=0` for production. `MOCK_OTP=1` during demo.
3. Deploy:
   ```bash
   railway up
   ```
4. Smoke test:
   ```bash
   curl https://<your-railway-url>.up.railway.app/health
   ```

## Demo prep checklist

- [ ] Replace seed phone numbers with team members' phones in `002_seed_data.sql`.
- [ ] Re-apply migrations after edits.
- [ ] Re-run `embed_procedures.py` whenever JSONs change.
- [ ] Verify `/procedures/lookup` returns sensible results for 5 sample queries.
