-- 009_ledger_scope_and_immutability.sql
--
-- Fixes three defects in the hash-chain ledger introduced by 003.
--
-- 1. SCOPE. 003 chained every row against a *global* tip
--    (`select row_hash from ledger order by id desc limit 1`) but the API
--    reads a chain back filtered by document_id and verifies that slice
--    against the genesis hash. From the second document onwards, the first
--    row of a slice pointed at some other document's row_hash — a hash that
--    is not in the slice — so verification failed and the UI showed the red
--    "neverificat" badge. Chains are now scoped to (citizen_id, document_id),
--    matching how they are read. Rows with no document (reminder events) form
--    one per-citizen chain of their own.
--
-- 2. SELF-CERTIFYING HASHES. 003 took `p_payload_hash` and `p_row_hash` from
--    the caller and inserted them verbatim: nothing forced the stored hash to
--    describe the stored payload. The function now takes the canonical JSON
--    text and derives both hashes itself, from its own prev_hash and its own
--    timestamp. `sha256()` is a Postgres builtin (PG 11+); no extension needed.
--
--    The old function also hashed a timestamp it computed client-side but
--    never sent, so `created_at` fell through to `default now()` — a
--    different instant from the one inside row_hash. That alone made every
--    row unverifiable. The timestamp used in the hash is now the one stored,
--    and `ledger_row_ts_iso()` reproduces the exact string on read so
--    verification does not depend on the session's TimeZone setting.
--
-- 3. APPEND-ONLY IN NAME ONLY. Nothing revoked UPDATE/DELETE and the demo
--    reset endpoint hard-deleted rows. A trigger now rejects both, and
--    privileges are revoked from the non-owner roles.
--
-- Rows written before this migration verified against neither scheme; they
-- stay in the table and will read as unverified. `POST /demo/reset` appends a
-- `demo_reset` marker, so a demo run starts from a clean per-document chain.

-- ---------------------------------------------------------------------------
-- New event type for the demo reset marker (replaces the old hard delete).
-- ---------------------------------------------------------------------------
alter table ledger drop constraint if exists ledger_event_type_check;
alter table ledger add constraint ledger_event_type_check check (event_type in (
  'doc_created', 'completed_draft', 'pdf_generated',
  'delivered', 'redirected', 'reminder_created', 'demo_reset'
));

-- ---------------------------------------------------------------------------
-- Canonical timestamp rendering. Must match Python's
-- datetime.strftime('%Y-%m-%dT%H:%M:%S.%f') + '+00:00' exactly, and must not
-- depend on the connection's TimeZone.
-- ---------------------------------------------------------------------------
create or replace function ledger_row_ts_iso(p_ts timestamptz) returns text as $$
  select to_char(p_ts at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US') || '+00:00';
$$ language sql immutable;

create or replace function ledger_sha256_hex(p_text text) returns text as $$
  select '0x' || encode(sha256(convert_to(p_text, 'UTF8')), 'hex');
$$ language sql immutable;

-- ---------------------------------------------------------------------------
-- Scoped tip. `is not distinct from` so document_id IS NULL matches NULL
-- rather than yielding NULL (which `=` would).
-- ---------------------------------------------------------------------------
drop function if exists ledger_tip_hash();

create or replace function ledger_tip_hash(
  p_citizen_id uuid,
  p_document_id uuid
) returns text as $$
  select coalesce(
    (select row_hash
       from ledger
      where citizen_id = p_citizen_id
        and document_id is not distinct from p_document_id
      order by id desc
      limit 1),
    '0x0000000000000000000000000000000000000000000000000000000000000000'
  );
$$ language sql stable;

-- ---------------------------------------------------------------------------
-- Append. No hash-shaped argument: the server derives everything it stores.
-- ---------------------------------------------------------------------------
drop function if exists append_ledger(uuid, uuid, text, jsonb, text, text, text);
drop function if exists append_ledger(uuid, uuid, text, text);

-- Returns the `ledger` row type rather than a `returns table (...)` list:
-- OUT parameters named `id` / `payload_hash` / ... would collide with the
-- table's own column names inside the function body.
create or replace function append_ledger(
  p_citizen_id uuid,
  p_document_id uuid,
  p_event_type text,
  p_payload_canonical text
) returns ledger as $$
declare
  v_prev_hash    text;
  v_payload_hash text;
  v_row_hash     text;
  v_ts           timestamptz := clock_timestamp();
  v_ts_iso       text;
  v_row          ledger;
begin
  if p_event_type not in (
    'doc_created', 'completed_draft', 'pdf_generated',
    'delivered', 'redirected', 'reminder_created', 'demo_reset'
  ) then
    raise exception 'append_ledger: invalid event_type %', p_event_type;
  end if;

  -- Serialize concurrent appends to the same chain so two transactions
  -- cannot read the same tip and both extend it (which would fork the chain).
  perform pg_advisory_xact_lock(
    hashtextextended(p_citizen_id::text || ':' || coalesce(p_document_id::text, ''), 0)
  );

  v_prev_hash    := ledger_tip_hash(p_citizen_id, p_document_id);
  v_payload_hash := ledger_sha256_hex(p_payload_canonical);
  v_ts_iso       := ledger_row_ts_iso(v_ts);
  v_row_hash     := ledger_sha256_hex(
                      p_event_type || v_payload_hash || v_prev_hash || v_ts_iso
                    );

  insert into ledger (
    citizen_id, document_id, event_type, payload,
    payload_hash, prev_hash, row_hash, created_at
  ) values (
    p_citizen_id, p_document_id, p_event_type, p_payload_canonical::jsonb,
    v_payload_hash, v_prev_hash, v_row_hash, v_ts
  )
  returning * into v_row;

  return v_row;
end;
$$ language plpgsql;

-- ---------------------------------------------------------------------------
-- Append-only enforcement.
--
-- Honest scope note: a superuser or the table owner can still drop the
-- trigger. This stops the application, its service-role key, and an
-- accidental `delete from ledger` — it is not tamper-proof storage.
-- ---------------------------------------------------------------------------
create or replace function ledger_reject_mutation() returns trigger as $$
begin
  raise exception
    'ledger is append-only: % is not permitted (row id %)',
    tg_op, coalesce(old.id, -1)
    using errcode = 'restrict_violation';
end;
$$ language plpgsql;

drop trigger if exists ledger_no_update on ledger;
create trigger ledger_no_update
  before update on ledger
  for each row execute function ledger_reject_mutation();

drop trigger if exists ledger_no_delete on ledger;
create trigger ledger_no_delete
  before delete on ledger
  for each row execute function ledger_reject_mutation();

revoke update, delete, truncate on ledger from public;

-- Supabase's built-in roles; skipped silently on a plain Postgres.
do $$
declare
  r text;
begin
  foreach r in array array['anon', 'authenticated', 'service_role'] loop
    if exists (select 1 from pg_roles where rolname = r) then
      execute format('revoke update, delete, truncate on ledger from %I', r);
    end if;
  end loop;
end $$;

-- processed_events cascades on ledger delete; deletes can no longer happen,
-- so the cascade is now dead weight but harmless. Left as-is.
