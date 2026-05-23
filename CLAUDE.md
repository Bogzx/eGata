# CivicAI — Backend Architecture Wiki

Mode: B (GitHub / Repository)
Purpose: Map the CivicAI backend architecture, every router and module, the agent state machine, the hash-chain ledger, and how the frontend connects.
Owner: Tudor Cucuteanu
Created: 2026-05-23

## Vault layout

```
.obsidian/                Obsidian config + CSS snippet
wiki/
├── index.md              Master catalog of every page
├── log.md                Append-only operation log (newest on top)
├── hot.md                ~500-word recent-context cache (overwrite each session)
├── overview.md           Executive summary of the whole backend
├── modules/              One note per Python module under backend/app/
├── components/           Reusable backend primitives (Pydantic models, JWT, etc.)
├── flows/                End-to-end request paths and data flows
├── decisions/            Architecture decisions with rationale
├── dependencies/         External services and Python deps
├── contracts/            HTTP / WebSocket / SSE wire-level contracts
└── meta/                 Conventions, glossary, dashboards
```

## Conventions

- All notes use YAML frontmatter: `type`, `status`, `created`, `updated`, plus type-specific keys.
- Wikilinks use `[[Note Name]]`. Filenames are unique → no paths needed.
- `wiki/index.md` is the master catalog. Update on every new page.
- `wiki/log.md` is append-only; new entries go at the TOP.
- `wiki/hot.md` is overwritten in full at the end of every session (max ~500 words).
- Code references use `backend/app/file.py:line` so they're clickable in editors.

## Operations

- **Query**: ask any question about the backend — Claude reads `wiki/hot.md` → `wiki/index.md` → individual pages.
- **Ingest**: drop new sources (specs, transcripts, PR notes) in `.raw/` and say "ingest <filename>".
- **Lint**: say "lint the wiki" for orphans, dead links, stale claims.

## Source of truth

The wiki summarizes the repo state as of the commits visible on the `main` branch on 2026-05-23. When the code drifts, the wiki rots — re-ingest the changed module rather than letting the page lie.
