-- 002_seed_data.sql
-- 3 demo citizens. Phone numbers must be replaced with real team-member numbers prior to demo.
insert into citizens (id, cnp, nume, prenume, data_nasterii, email, phone, attributes) values
('11111111-1111-1111-1111-111111111111',
 '2851014123456', 'Ionescu', 'Maria', '1985-03-14',
 'maria.ionescu@example.com', '+40712345678',
 jsonb_build_object(
   'owns_vehicle', true,
   'marital_status', 'necăsătorit',
   'has_children', false,
   'employer', 'SC Acme SRL',
   'medic_familie', 'Dr. Popescu, Cluj',
   'preferred_language', 'ro',
   'current_address', 'Str. Avram Iancu 5, Cluj-Napoca',
   'accessibility', jsonb_build_object('voice_only', false, 'simple_language', false, 'large_text', false)
 )),
('22222222-2222-2222-2222-222222222222',
 '1900512123456', 'Popa', 'Andrei', '1990-05-12',
 'andrei.popa@example.com', '+40722345678',
 jsonb_build_object(
   'owns_vehicle', false,
   'marital_status', 'căsătorit',
   'has_children', true,
   'employer', 'Bosch Cluj',
   'medic_familie', 'Dr. Vasilescu, Cluj',
   'preferred_language', 'ro',
   'current_address', 'Str. Memorandumului 12, Cluj-Napoca',
   'accessibility', jsonb_build_object('voice_only', false, 'simple_language', true, 'large_text', false)
 )),
('33333333-3333-3333-3333-333333333333',
 '2620908123456', 'Dumitru', 'Elena', '1962-09-08',
 'elena.dumitru@example.com', '+40732345678',
 jsonb_build_object(
   'owns_vehicle', true,
   'marital_status', 'văduv',
   'has_children', true,
   'employer', null,
   'medic_familie', 'Dr. Munteanu, Cluj',
   'preferred_language', 'ro',
   'current_address', 'Str. Horea 8, Cluj-Napoca',
   'accessibility', jsonb_build_object('voice_only', true, 'simple_language', true, 'large_text', true)
 ));

-- Existing document (1 draft) for Maria
insert into documents (id, citizen_id, procedure_id, status, fields, pdf_url, delivery, ref_number, created_at, delivered_at) values
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
 '11111111-1111-1111-1111-111111111111',
 'schimbare-domiciliu', 'draft',
 jsonb_build_object('nume_complet', 'Maria Ionescu', 'cnp', '2851014123456', 'adresa_curenta', 'Str. Avram Iancu 5, Cluj-Napoca'),
 null, null, null,
 now() - interval '1 day', null);

-- Existing reminders (2 active) for Maria
insert into reminders (id, citizen_id, trigger_doc_id, kind, procedure_id, redirect_target, title, due_date, status) values
('cccccccc-cccc-cccc-cccc-cccccccccccc',
 '11111111-1111-1111-1111-111111111111', null,
 'in_scope_procedure', 'preschimbare-ci', null,
 'Cartea de identitate expiră în 23 de zile — programează preschimbarea',
 current_date + interval '23 days', 'pending'),
('dddddddd-dddd-dddd-dddd-dddddddddddd',
 '11111111-1111-1111-1111-111111111111', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
 'external_redirect', null, 'DRPCIV',
 'După schimbarea domiciliului trebuie să-ți actualizezi certificatul de înmatriculare la DRPCIV',
 current_date + interval '30 days', 'pending');

-- No seeded ledger row.
--
-- There used to be one here, described as "required for hash chain to have a
-- prev_hash to reference". It was not required — ledger_tip_hash() falls back
-- to the genesis constant on an empty chain — and its row_hash was
-- sha256('genesis'), which is not what the hashing rule produces for any
-- payload. It was a fabricated row in an append-only ledger, and because the
-- old chain was global it became the tip that every real row chained against,
-- so the first verification against LEDGER_GENESIS_HASH failed. See
-- migrations/009_ledger_scope_and_immutability.sql.
