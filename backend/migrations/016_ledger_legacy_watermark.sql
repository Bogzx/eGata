-- 016_ledger_legacy_watermark.sql
--
-- Which ledger rows the backend may sign after the fact.
--
-- 014 had the backend sign, at every start, *every* row without a signature.
-- That was meant for history written before signing existed, but it also
-- covered rows appended since by anything other than the backend: a call to
-- append_ledger() with the egata_app password (or by the owner) creates an
-- unsigned row, the chain reads as unverified, and the next restart signed
-- the row and turned it green. Signing needs the key; that made the key
-- sign whatever the database held.
--
-- Rows written since signing exists are signed in the transaction that
-- appends them (app/ledger.py), so an unsigned row after that point was not
-- written by the backend. This records the last row that predates signing:
-- the newest row created before the first signature, or, when nothing has
-- been signed yet (an upgrade from before 014), the newest row there is.
-- The backend signs rows up to this id and never beyond it.
--
-- The backend role may read it and nothing else. The owner can still move
-- it, like everything else it owns; see the README on what the signing key
-- does and does not protect against.

create table if not exists ledger_legacy_watermark (
  singleton    boolean primary key default true check (singleton),
  max_id       bigint not null,
  recorded_at  timestamptz not null default now()
);

insert into ledger_legacy_watermark (max_id)
select coalesce(
  (select max(l.id) from ledger l
    where l.created_at < (select min(s.signed_at) from ledger_signatures s)),
  case when exists (select 1 from ledger_signatures) then 0
       else (select coalesce(max(id), 0) from ledger) end
)
on conflict (singleton) do nothing;

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'egata_app') then
    -- 014's default privileges hand new tables ordinary DML; take it back.
    revoke insert, update, delete, truncate on ledger_legacy_watermark from egata_app;
    grant select on ledger_legacy_watermark to egata_app;
  end if;
end $$;
