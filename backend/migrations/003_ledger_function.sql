-- 003_ledger_function.sql
-- Append-only ledger insert function that enforces hash-chain integrity at the DB level.
create or replace function append_ledger(
  p_citizen_id uuid,
  p_document_id uuid,
  p_event_type text,
  p_payload jsonb,
  p_payload_hash text,
  p_expected_prev_hash text,
  p_row_hash text
) returns bigint as $$
declare
  v_last_hash text;
  v_id bigint;
begin
  if p_event_type not in (
    'doc_created', 'completed_draft', 'pdf_generated',
    'delivered', 'redirected', 'reminder_created'
  ) then
    raise exception 'append_ledger: invalid event_type %', p_event_type;
  end if;

  select row_hash into v_last_hash
  from ledger
  order by id desc
  limit 1;

  if v_last_hash is null then
    v_last_hash := '0x0000000000000000000000000000000000000000000000000000000000000000';
  end if;

  if v_last_hash <> p_expected_prev_hash then
    raise exception 'append_ledger: prev_hash mismatch. expected=% got=%', v_last_hash, p_expected_prev_hash;
  end if;

  insert into ledger (citizen_id, document_id, event_type, payload, payload_hash, prev_hash, row_hash)
  values (p_citizen_id, p_document_id, p_event_type, p_payload, p_payload_hash, p_expected_prev_hash, p_row_hash)
  returning id into v_id;

  return v_id;
end;
$$ language plpgsql;

create or replace function ledger_tip_hash() returns text as $$
declare
  v_hash text;
begin
  select row_hash into v_hash from ledger order by id desc limit 1;
  if v_hash is null then
    return '0x0000000000000000000000000000000000000000000000000000000000000000';
  end if;
  return v_hash;
end;
$$ language plpgsql stable;
