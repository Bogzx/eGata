-- 008_sessions.sql
-- Adds the Session aggregate that drives the new state-machine architecture.
-- A Session owns: state, active document, conversation history (OpenAI
-- chat messages serialized to JSON), pending UI widgets, optional scenario
-- pointer for multi-procedure flows.

create table sessions (
  id                  text primary key,                            -- e.g. "sess_abc123" or legacy "conv_xxx"
  citizen_id          uuid not null references citizens(id) on delete cascade,
  state               text not null
                        check (state in (
                          'exploring',
                          'confirming_match',
                          'filling',
                          'reviewing',
                          'delivered',
                          'redirected'
                        ))
                        default 'exploring',
  active_document_id  uuid references documents(id) on delete set null,
  scenario_id         text,
  step_index          int,
  pending_widgets     jsonb not null default '[]'::jsonb,
  history             jsonb not null default '[]'::jsonb,          -- OpenAI chat messages
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);
create index idx_sessions_citizen    on sessions(citizen_id);
create index idx_sessions_active_doc on sessions(active_document_id);
create index idx_sessions_state      on sessions(state);
