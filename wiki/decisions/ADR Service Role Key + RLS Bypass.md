---
type: decision
status: active
created: 2026-05-23
updated: 2026-05-23
---

# ADR: Service Role Key + RLS Bypass

## Decision

The backend uses Supabase's **service role key** for both Postgres and Storage access. Service role bypasses Row-Level Security. RLS policies still exist in `migrations/004_rls_policies.sql` as defense in depth for anon/authenticated callers that might appear later.

## Why service role

The backend IS the authority — it has already verified the JWT and resolved `citizen_id`. Letting RLS re-enforce the citizen identity would require setting `auth.uid()` per connection, which psycopg doesn't natively support and the supabase-py client doesn't expose.

## Why keep RLS policies

Three reasons:

1. If we ever expose Postgres directly to authenticated browser sessions (Supabase JWT, not ours), RLS catches anything our app code missed.
2. The Supabase dashboard's SQL editor runs under `authenticated` — the policies stop a careless query.
3. Reviewer comfort.

## Where the backend enforces ownership

| Resource | Check |
|---|---|
| Documents | `_require_owner(doc, citizen_id)` ([[documents]]) — `doc.citizen_id == jwt.sub` |
| Reminders | Inline check (`existing.citizen_id != citizen_id` → 403) |
| Ledger | Read filtered by `document_id` (which is in turn owner-checked) |
| Storage | Bucket is public, but object paths are `<citizen_uuid>/<doc_uuid>.pdf` — knowing the UUIDs is the "auth" |

> [!gotcha] PDFs are technically public-by-URL
> The `pdfs` bucket is set public. We rely on UUIDs being unguessable. Acceptable for hackathon; tighten to signed URLs + private bucket for production.

## See also

- [[storage]]
- [[Dep Supabase]]
- migrations/004_rls_policies.sql
