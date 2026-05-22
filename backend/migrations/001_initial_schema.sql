-- 001_initial_schema.sql
create extension if not exists "pgcrypto";
create extension if not exists "vector";

create table citizens (
  id            uuid primary key default gen_random_uuid(),
  cnp           text unique not null,
  nume          text not null,
  prenume       text not null,
  data_nasterii date not null,
  email         text,
  phone         text not null,
  attributes    jsonb not null default '{}'::jsonb,
  created_at    timestamptz not null default now()
);

create table documents (
  id            uuid primary key default gen_random_uuid(),
  citizen_id    uuid not null references citizens(id) on delete cascade,
  procedure_id  text not null,
  status        text not null default 'draft' check (status in ('draft', 'finalized')),
  fields        jsonb not null default '{}'::jsonb,
  pdf_url       text,
  delivery      text check (delivery in ('save', 'send', 'print')),
  ref_number    text,
  created_at    timestamptz not null default now(),
  delivered_at  timestamptz
);
create index idx_documents_citizen on documents(citizen_id);
create index idx_documents_status on documents(status);

create table ledger (
  id            bigserial primary key,
  citizen_id    uuid not null,
  document_id   uuid,
  event_type    text not null check (event_type in (
    'doc_created', 'completed_draft', 'pdf_generated',
    'delivered', 'redirected', 'reminder_created'
  )),
  payload       jsonb not null default '{}'::jsonb,
  payload_hash  text not null,
  prev_hash     text not null,
  row_hash      text not null,
  created_at    timestamptz not null default now()
);
create index idx_ledger_citizen on ledger(citizen_id);
create index idx_ledger_document on ledger(document_id);

create table reminders (
  id              uuid primary key default gen_random_uuid(),
  citizen_id      uuid not null references citizens(id) on delete cascade,
  trigger_doc_id  uuid references documents(id) on delete set null,
  kind            text not null check (kind in ('in_scope_procedure', 'external_redirect')),
  procedure_id    text,
  redirect_target text,
  title           text not null,
  due_date        date,
  status          text not null default 'pending' check (status in ('pending', 'started', 'done', 'dismissed')),
  created_at      timestamptz not null default now()
);
create index idx_reminders_citizen on reminders(citizen_id);
create index idx_reminders_status on reminders(status);

create table procedures_embeddings (
  procedure_id  text primary key,
  embedding     vector(1536) not null,
  source_text   text not null,
  updated_at    timestamptz not null default now()
);

create table otp_challenges (
  id            text primary key,
  citizen_id    uuid not null references citizens(id) on delete cascade,
  phone         text not null,
  twilio_sid    text,
  expires_at    timestamptz not null,
  consumed      boolean not null default false,
  created_at    timestamptz not null default now()
);
create index idx_otp_expires on otp_challenges(expires_at);
