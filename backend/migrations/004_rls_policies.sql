-- 004_rls_policies.sql
-- RLS: citizens see only their own rows. FastAPI uses service role key, which bypasses RLS.
alter table citizens enable row level security;
alter table documents enable row level security;
alter table ledger enable row level security;
alter table reminders enable row level security;

-- Service-role bypass is automatic. We define policies for anon/authenticated for completeness.
create policy citizens_self_select on citizens
  for select using (id::text = auth.uid()::text);

create policy documents_owner_select on documents
  for select using (citizen_id::text = auth.uid()::text);

create policy documents_owner_modify on documents
  for all using (citizen_id::text = auth.uid()::text)
  with check (citizen_id::text = auth.uid()::text);

create policy ledger_owner_select on ledger
  for select using (citizen_id::text = auth.uid()::text);

create policy reminders_owner_select on reminders
  for select using (citizen_id::text = auth.uid()::text);

create policy reminders_owner_modify on reminders
  for all using (citizen_id::text = auth.uid()::text)
  with check (citizen_id::text = auth.uid()::text);
