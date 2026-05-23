-- 005_processed_events.sql (Plan 4)
-- Watermark table so the background reminders worker is idempotent.
-- Each row records that ledger entry N has been processed by the reminders evaluator.

create table if not exists processed_events (
    ledger_id    bigint primary key references ledger(id) on delete cascade,
    processed_at timestamptz not null default now()
);

create index if not exists idx_processed_events_processed_at
    on processed_events (processed_at desc);

-- Helper view: ledger rows that are 'delivered' and not yet processed.
create or replace view pending_delivered_events as
select l.*
from ledger l
left join processed_events p on p.ledger_id = l.id
where l.event_type = 'delivered'
  and p.ledger_id is null
order by l.id asc;
