-- 010_seed_address_parts.sql
--
-- Moves demo fixtures off a request path.
--
-- app/citizens.py used to carry a dict of three literal persona UUIDs mapped
-- to hardcoded apartment numbers, injected into `attributes` on every
-- /citizens/me call — i.e. demo data compiled into code that runs for every
-- citizen, including any real one. The values belong with the rest of the
-- seed data, which is here.
--
-- The seed stores the address as one `current_address` string; procedures
-- such as placuta-numar-postal ask for the parts separately, so the parts are
-- seeded alongside it. Idempotent: only fills a key that is absent or empty.

update citizens
set attributes = attributes || jsonb_build_object('apartament', v.apartament)
from (values
  ('2851014123456', '3'),    -- Maria Ionescu
  ('1900512123456', '12'),   -- Andrei Popa
  ('2620908123456', '7B')    -- Elena Dumitru
) as v(cnp, apartament)
where citizens.cnp = v.cnp
  and coalesce(citizens.attributes ->> 'apartament', '') = '';
