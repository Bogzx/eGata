-- 015_session_review_confirmed.sql
--
-- The review gate ("the citizen answered Da to 'are these details
-- correct?'") lived in a per-process Python set, like the session lock. With
-- two backend replicas a Da answered on one was invisible on the other, and
-- a restart forgot it. It is session state, so it lives on the session row.

alter table sessions add column if not exists review_confirmed boolean not null default false;
