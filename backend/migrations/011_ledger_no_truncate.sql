-- 011_ledger_no_truncate.sql
--
-- Closes the one mutation path 009 left open. Its row-level triggers reject
-- UPDATE and DELETE, and it revokes TRUNCATE from the non-owner roles — but
-- row-level triggers do not fire on TRUNCATE, and the table owner keeps the
-- privilege, so `truncate ledger` (with a cascade into processed_events)
-- still emptied the ledger in one statement. That is exactly the "accidental
-- `delete from ledger`" class of mistake 009 set out to stop.
--
-- Same honest scope note as 009: the owner can still drop this trigger. This
-- is tamper-evidence for the application and for fat-fingered SQL, not
-- tamper-proof storage.
--
-- Separate function rather than reusing ledger_reject_mutation(): OLD is only
-- assigned in row-level triggers, and a statement-level TRUNCATE trigger
-- referencing old.id would fail at runtime instead of raising our error.

create or replace function ledger_reject_truncate() returns trigger as $$
begin
  raise exception 'ledger is append-only: TRUNCATE is not permitted'
    using errcode = 'restrict_violation';
end;
$$ language plpgsql;

drop trigger if exists ledger_no_truncate on ledger;
create trigger ledger_no_truncate
  before truncate on ledger
  for each statement execute function ledger_reject_truncate();
