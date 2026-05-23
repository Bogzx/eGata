---
type: meta
title: "Glossary"
updated: 2026-05-23
---

# CivicAI Glossary

## Domain

- **Primărie** — Romanian city hall / municipality office. The institutions the agent represents.
- **Procedure** (`backend/procedures/*.json`) — A single administrative request the agent can complete (e.g. `schimbare-domiciliu`). Has fields, required documents (`acte_necesare`), a LaTeX template, and a list of `next_steps`.
- **Scenario** (`backend/scenarios/*.json`) — A real-life situation that chains several procedures + external steps (e.g. "buying an apartment"). See [[scenarios]].
- **Institution** (`backend/institutions/*.json`) — An external body (DRPCIV, ANAF, CNAS, ANCPI, etc.) that issues documents the user needs to bring.
- **Persona** — One of three seeded demo citizens: Maria Ionescu, Andrei Popa, Elena Dumitru. Each has different accessibility settings to demo the modes.
- **CNP** — 13-digit Romanian national ID number. Never read aloud (see [[prompts]]).
- **ROeID** — Romanian e-ID. In the hackathon build, ROeID login is mocked via the persona dropdown.
- **MRZ** — Machine-Readable Zone on Romanian ID cards; the citizen can paste / OCR it and we look up the citizen by CNP+name.

## Session machine

- **EXPLORING** — citizen hasn't picked a procedure yet. Lookup and redirect tools are active.
- **CONFIRMING_MATCH** — agent has proposed a procedure; awaiting confirmation.
- **FILLING** — document is open; `set_field` / `propose_widget` are active.
- **REVIEWING** — all required fields satisfied; `complete_document` is offered.
- **DELIVERED** — document finalized; the next procedure of a scenario can begin.
- **REDIRECTED** — request is out of primărie scope; user nudged to ANAF/CNAS/DRPCIV.

## Wire vocabulary

- **`frontend_event`** — A structured directive emitted by a tool that the FE acts on directly (`document_opened`, `widget_proposed`, `field_updated`, `document_delivered`, `redirect`, `lookup_returned`). See [[Frontend Event Schema]].
- **`session_snapshot`** — Full state push after every mutation. The FE replaces its mirror; `seq` ordering protects against reorder during reconnect. See [[Session Snapshot Schema]].
- **PendingWidget** — Server-side record of an unanswered widget. Tracked by `widget_id`; resolved by the user clicking a widget in the FE which sends a `widget_submission` (voice WS) or POSTs `/agent/widget-result` (HTTP).
- **applies_if** — A tiny boolean DSL evaluated against `{**citizen.attributes, **document.fields}`. Used both for conditional fields and conditional reminders. See [[applies_if]].

## Operations

- **Hash-chain ledger** — every important event is hashed and chained via `prev_hash → row_hash`. The chain has a genesis row written in the seed migration. See [[ledger]] + [[ADR Hash-Chain Ledger]].
- **Mock OTP** — when `MOCK_OTP=1`, the backend skips Twilio and accepts code `123456`. See [[ADR Mock OTP Flag]].
- **Demo reset** — `POST /demo/reset` with `X-Demo-Token` wipes a citizen's docs + ledger + reminders and re-seeds. See [[demo]].
