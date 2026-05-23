---
type: meta
title: "Conventions"
updated: 2026-05-23
---

# Conventions

## Frontmatter

Every page declares at least:

```yaml
---
type: module | component | flow | decision | dependency | contract | meta
status: active | deprecated | experimental | planned | living
path: "backend/app/foo.py"        # for module pages
created: 2026-05-23
updated: 2026-05-23
tags: [optional, freeform]
---
```

## Filenames

Filenames are unique across the vault. Obsidian's wikilinks (`[[Note Name]]`) are name-only, no paths. When two concepts collide (e.g. `health` the module vs. `health` the endpoint), disambiguate in the title (`[[health]]` → `# health module`).

Backend module pages use the **module basename** (`auth`, `documents`, `ledger`). Agent-tool pages use the **tool name** (`set_field`, `complete_document`). Flow pages start with `Flow ` (`Flow Login + OTP`). ADR pages start with `ADR ` (`ADR Hash-Chain Ledger`). Contract pages use the contract object name (`HTTP API Surface`, `SSE Frame Schema`).

## Code references

Always cite source as `backend/app/<file>.py:<line>`. Editors render these as clickable links. Do not paraphrase line numbers — if you can't verify them, omit them.

## Wikilinks vs prose

- New facts about an entity → add to that entity's page, not a passing mention elsewhere.
- Cross-cutting facts (a flow, a decision) → its own page; link both endpoints.
- Don't repeat what the code already says clearly. The wiki is *why* and *how it connects*, not *what the code reads as*.
