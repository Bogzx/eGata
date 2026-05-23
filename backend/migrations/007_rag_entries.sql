-- 007_rag_entries.sql (Multi-procedure RAG)
-- Rename procedures_embeddings to rag_entries and add a kind column so we can
-- hold both procedure and scenario embeddings in one table.

alter table procedures_embeddings rename to rag_entries;
alter table rag_entries rename column procedure_id to id;
alter table rag_entries add column if not exists kind text not null default 'procedure'
  check (kind in ('procedure', 'scenario'));

create index if not exists idx_rag_entries_kind on rag_entries(kind);
