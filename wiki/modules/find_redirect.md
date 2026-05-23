---
type: module
path: "backend/app/agent_tools/find_redirect.py"
status: active
language: python
purpose: "Agent tool: detect out-of-primărie scope and transition to REDIRECTED."
depends_on: [sessions]
used_by: [session_engine, agent_voice, twilio_bridge]
valid_states: [EXPLORING, CONFIRMING_MATCH, DELIVERED, REDIRECTED]
created: 2026-05-23
updated: 2026-05-23
---

# find_redirect

Out-of-scope detector. The primărie covers a fixed surface; everything else goes to one of three external institutions. The tool matches a keyword and emits a redirect card.

## Parameters

```json
{ "query": "string (required)", "target": "string (optional override)" }
```

## Known targets

| Target | Scope | URL | Phone |
|---|---|---|---|
| `ANAF` | Impozite, taxe, fiscalitate | https://www.anaf.ro | 031 403 9160 |
| `CNAS` | Medic de familie, asigurare medicală, card de sănătate | https://cnas.ro | 0800 800 950 |
| `DRPCIV` | Talon, permis, înmatriculare | https://drpciv.ro | 021 9665 |

## Keyword map

Static mapping in `_KEYWORDS`. Examples: `"medic de familie" → CNAS`, `"talon" → DRPCIV`, `"impozit" → ANAF`, `"declaraț" → ANAF`. Both diacritic and ASCII variants are listed so transcription noise doesn't break it.

## Why it's OFF during FILLING / REVIEWING

A user mid-fill saying "vreau și impozit cândva" should NOT trigger a redirect and abandon the draft. The agent can still reply with text about ANAF — it just can't fire the tool.

## Output

```json
{
  "target": "ANAF" | "CNAS" | "DRPCIV" | null,
  "name": "...",
  "url": "...",
  "phone": "...",
  "scope": "...",
  "explanation": "..."
}
```

Plus `frontend_event: redirect` with `{target, name, url}` for the right-pane card.

## See also

- [[procedures]]`.REDIRECT_HINTS` — same map used by the legacy `POST /procedures/lookup`
- [[Flow Session State Machine]]
