-- 014_ledger_signatures_and_app_role.sql
--
-- Two steps toward a ledger that is tamper-evident against whoever runs the
-- database, not just against the application.
--
-- 1. SIGNATURES. Every ledger row gets an Ed25519 signature over
--    {citizen_id, document_id, row id, row_hash} (app/ledger_signing.py).
--    row_hash commits to the whole chain before it, so each signature attests
--    the chain up to that row. The private key lives outside the database
--    (LEDGER_SIGNING_KEY / LEDGER_SIGNING_KEY_FILE): someone who can write to
--    Postgres but does not hold the key can no longer rebuild a chain that
--    still verifies, and a citizen who kept a signed head (a "receipt") can
--    prove a later rewrite. Rows written before this migration are signed by
--    the backend at its next start (signed_at shows when).
--
-- 2. A LEAST-PRIVILEGE ROLE. The backend used to connect as the owner, which
--    can drop the append-only triggers and INSERT hand-made ledger rows. The
--    role `egata_app` gets ordinary DML on everything except the ledger:
--    SELECT only, with appends going through append_ledger(), now SECURITY
--    DEFINER. scripts/bootstrap_local_db.py gives the role a login and a
--    password when APP_DB_PASSWORD is set; docker-compose connects the
--    backend with it. Deployments that keep connecting as the owner keep
--    working unchanged (see README "Upgrading an existing database").

-- ---------------------------------------------------------------------------
-- Signatures (append-only, like the ledger itself)
-- ---------------------------------------------------------------------------
create table if not exists ledger_signatures (
  ledger_id  bigint primary key references ledger(id),
  key_id     text not null,
  signature  text not null,
  signed_at  timestamptz not null default now()
);

-- Own function: ledger_reject_mutation() reports old.id, which this table
-- does not have.
create or replace function ledger_signatures_reject_mutation() returns trigger as $$
begin
  raise exception
    'ledger_signatures is append-only: % is not permitted (ledger id %)',
    tg_op, old.ledger_id
    using errcode = 'restrict_violation';
end;
$$ language plpgsql;

drop trigger if exists ledger_signatures_no_update on ledger_signatures;
create trigger ledger_signatures_no_update
  before update on ledger_signatures
  for each row execute function ledger_signatures_reject_mutation();

drop trigger if exists ledger_signatures_no_delete on ledger_signatures;
create trigger ledger_signatures_no_delete
  before delete on ledger_signatures
  for each row execute function ledger_signatures_reject_mutation();

drop trigger if exists ledger_signatures_no_truncate on ledger_signatures;
create trigger ledger_signatures_no_truncate
  before truncate on ledger_signatures
  for each statement execute function ledger_reject_truncate();

-- ---------------------------------------------------------------------------
-- append_ledger() runs with its owner's rights, so a role that may not INSERT
-- into `ledger` can still append — but only rows whose hashes the function
-- derives itself. search_path is pinned so a caller cannot shadow `ledger` or
-- ledger_tip_hash() with objects of its own.
-- ---------------------------------------------------------------------------
alter function append_ledger(uuid, uuid, text, text)
  security definer
  set search_path = public, pg_temp;

-- Default EXECUTE-to-PUBLIC would also let Supabase's `anon` role call it
-- through the REST API with the public anon key.
revoke all on function append_ledger(uuid, uuid, text, text) from public;

-- ---------------------------------------------------------------------------
-- The application role
-- ---------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'egata_app') then
    begin
      create role egata_app nologin;
    exception when insufficient_privilege then
      raise notice 'egata_app not created (%). The backend keeps connecting as the owner.', sqlerrm;
    end;
  end if;
end $$;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'egata_app') then
    return;
  end if;

  grant usage on schema public to egata_app;
  grant select, insert, update, delete on all tables in schema public to egata_app;
  grant usage, select on all sequences in schema public to egata_app;

  -- The ledger: read, and append only through the function.
  revoke insert, update, delete, truncate on ledger from egata_app;
  grant execute on function append_ledger(uuid, uuid, text, text) to egata_app;

  -- Signatures verify themselves; the role may add one, never change one.
  revoke update, delete, truncate on ledger_signatures from egata_app;

  -- Migration bookkeeping belongs to the owner.
  revoke insert, update, delete, truncate on schema_migrations from egata_app;

  -- Row-level security (migrations/004) keys on Supabase's auth.uid(), which
  -- is NULL for a backend connection, so it would deny egata_app every row.
  -- Authorization is application-level (documents._require_owner, the
  -- conversation checks in agent.py); give the backend role an explicit
  -- pass-through policy rather than the superuser-only BYPASSRLS. Table-level
  -- grants above still decide what it may do — on the ledger, only SELECT.
  declare
    t text;
  begin
    for t in
      select c.relname from pg_class c
       where c.relnamespace = 'public'::regnamespace and c.relkind = 'r' and c.relrowsecurity
    loop
      execute format('drop policy if exists egata_app_access on %I', t);
      execute format(
        'create policy egata_app_access on %I for all to egata_app using (true) with check (true)', t
      );
    end loop;
  end;

  -- Tables later migrations create get ordinary DML; any new ledger-like
  -- table must revoke explicitly, as above.
  alter default privileges in schema public
    grant select, insert, update, delete on tables to egata_app;
  alter default privileges in schema public
    grant usage, select on sequences to egata_app;
end $$;
