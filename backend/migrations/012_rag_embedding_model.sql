-- 012_rag_embedding_model.sql
--
-- Tag every RAG vector with the model that produced it.
--
-- Vectors from different embedding models are not comparable, but nothing
-- recorded which model built the index: a query embedded by one model was
-- scored against vectors from another and retrieval degraded silently
-- (README: "The embedding deployment used to build the index must be the same
-- one used at query time"). Search now filters on the current model, so a
-- mismatch returns no matches instead of wrong ones.
--
-- The primary key becomes (id, embedding_model) so the offline index
-- (app/local_embeddings.py, built automatically by bootstrap_local_db) and an
-- Azure-built index can live side by side; adding or removing an Azure key
-- switches which one is searched, with no re-index.
--
-- Rows that predate this migration were built by the Azure deployment — the
-- only embedder that existed — and are tagged 'azure'.

alter table rag_entries add column if not exists embedding_model text;
update rag_entries set embedding_model = 'azure' where embedding_model is null;
alter table rag_entries alter column embedding_model set not null;

do $$
declare
  pk text;
begin
  select conname into pk
    from pg_constraint
   where conrelid = 'rag_entries'::regclass and contype = 'p';
  if pk is not null then
    execute format('alter table rag_entries drop constraint %I', pk);
  end if;
end $$;

alter table rag_entries add primary key (id, embedding_model);
create index if not exists idx_rag_entries_model on rag_entries(embedding_model);
