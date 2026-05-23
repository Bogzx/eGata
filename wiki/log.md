---
type: meta
title: "Operation Log"
updated: 2026-05-23
---

# Operation Log

Append-only. **New entries go at the TOP of the file.** Never edit past entries — flag corrections as a new entry that references the original by date.

---

## 2026-05-23 — Vault scaffold

- Mode B (Repository) chosen for the CivicAI codebase.
- Created `.obsidian/` config, CSS snippet, graph color groups.
- Created `wiki/` skeleton: index, log, hot, overview.
- Wrote full module set (28 backend modules + 7 agent tools).
- Wrote flows: login, lookup, agent text turn, voice browser, voice phone, document lifecycle, reminders worker, state machine, widget round-trip.
- Wrote contracts: HTTP, SSE, Voice WS, Twilio WS, Frontend Event, Session Snapshot, Procedure JSON, Scenario JSON.
- Wrote 9 ADRs covering the key architectural decisions.
- Wrote dependency notes (Supabase, Gemini, Twilio, Sentry, APScheduler, pdflatex, FastAPI stack).
- Wrote Frontend Map + 5 lib pages + auth/voice/session-mirror/MSW flows.
- Wrote deployment notes (Railway, Dockerfile, migrations).

Built by Claude in one session against a clean repo state.
