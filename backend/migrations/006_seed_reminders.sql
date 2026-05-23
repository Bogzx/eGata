-- 006_seed_reminders.sql (Plan 4)
-- Seed pending reminders so every demo citizen's home screen is rich on first login.
-- Maria (CNP 2851014123456) already has 2 reminders from 002_seed_data.sql; this
-- migration only adds a reminder for Elena.
-- Idempotent: deletes any row with the well-known stable UUID before inserting.

delete from reminders where id = '11111111-1111-1111-1111-111111111104'::uuid;

-- Elena Dumitru (CNP 2620908123456) — owns_vehicle=true and has_children=true
insert into reminders (id, citizen_id, kind, procedure_id, redirect_target, title, due_date, status)
select
    '11111111-1111-1111-1111-111111111104'::uuid,
    id,
    'external_redirect',
    null,
    'DRPCIV',
    'Actualizare certificat înmatriculare auto (termen 30 zile)',
    current_date + interval '30 days',
    'pending'
from citizens where cnp = '2620908123456';
