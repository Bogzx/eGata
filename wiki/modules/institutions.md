---
type: module
path: "backend/app/institutions.py"
status: active
language: python
purpose: "External institution catalog loader."
depends_on: [models]
used_by: [scenarios, agent_tools/find_redirect (indirectly via scope text)]
created: 2026-05-23
updated: 2026-05-23
---

# institutions

Loads `backend/institutions/*.json` into a `dict[str, Institutie]`. Validates that filename matches `id`. Cached with `lru_cache(maxsize=1)`.

## Why a registry

`acte_necesare` items in a procedure can reference an external issuer via `emitent_id`. When that's present, [[scenarios]]`.resolve_act` reaches into this registry to enrich the response with the human-readable institution name and an explanatory note (`note_ai_cannot_complete`) that tells the agent the user has to fetch this document themselves.

## `Institutie` shape

```yaml
id: ocpi-ancpi
nume_scurt: ANCPI
nume_complet: Agenția Națională de Cadastru și Publicitate Imobiliară
scope: cadastru
url: https://www.ancpi.ro
phone: +40-...
online_disponibil: false
note_ai_cannot_complete: "Documentul se obține personal de la ANCPI / OCPI."
```

## See also

- [[scenarios]]
- [[Scenario JSON Schema]]
