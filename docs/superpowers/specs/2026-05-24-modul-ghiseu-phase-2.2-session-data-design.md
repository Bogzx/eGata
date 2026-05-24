# Modul Ghișeu — Phase 2.2: Real Session + Document Data (Design)

**Date:** 2026-05-24
**Status:** Approved for plan generation
**Roadmap parent:** `docs/superpowers/plans/2026-05-24-modul-ghiseu-phase-2-integration.md`
**Prior phase:** `docs/superpowers/specs/2026-05-24-modul-ghiseu-phase-2.1-voice-bridge-design.md`

---

## Goal

Replace the hard-coded sample data in `DocumentReview` and `DoneScreen` with the real procedure + document data the agent has been collecting. After Phase 2.2 a citizen finishing a voice flow on `/ghiseu` sees the actual fields the agent set (auto-filled from profile or asked verbally), with the procedure's real title and labels — not "Popescu Ana-Maria, Adeverință de venit, REG-2026-08412".

Phase 2.2 is **read-only from the frontend perspective**. The backend already collects the data (via Phase 2.1's voice bridge + today's profile-prefill fix). All that's missing is the kiosk surfaces consuming `sessionStore.document` + `sessionStore.procedure` instead of static arrays.

---

## In scope

- `DocumentReview` renders from `sessionStore.document.fields` × `sessionStore.procedure.fields`. Drops the static `FIELDS` array.
- "✓ auto" badge is derived: `field.source.includes("profile") && value present`. No schema migration.
- `DocumentReview` doc-paper header: title from `procedure.title`; the fake "Cerere nr. 2026-AV-08412" line is removed (real ref number only exists post-delivery — Phase 2.3).
- `DoneScreen` reads `sessionStore.document.ref_number` with `"REG-PENDING"` fallback.
- `GhiseuShell` mirrors `sessionStore.session.state` into ghiseu state: `"reviewing" → "review"`, `"delivered" → "done"`. Guarded to not override `error` / `mic-denied`.
- `ghiseuStore.amendDoc()` becomes a no-op for state — user stays on review screen, talks, agent fires `set_field`, the field grid updates live from the underlying `sessionStore.document` subscription.
- Small helper `formatValue(value: unknown): string` for null/bool/date rendering.

## Out of scope (deferred)

- Real export API call → **Phase 2.3**. Until then `ref_number` stays null and `DoneScreen` shows the `"REG-PENDING"` fallback.
- Source enum migration → not needed. Reusing the existing `source: string`.
- New backend signal for review-readiness → reusing `session.state`.
- Mic-denied recovery, WS reconnect, telemetry, e2e — **Phase 2.4**.

---

## Architecture decisions

### D1. No mirror — consumers read sessionStore directly

`DocumentReview` and `DoneScreen` call `useSessionStore` themselves. We considered snapshotting `activeDocument` / `activeProcedure` into `ghiseuStore`, but that duplicates state and adds a sync effect with no benefit. The components are inside the kiosk surface and Zustand selectors are cheap.

### D2. Auto-badge from existing source string

`auto = field.source.includes("profile") && value != null && value !== ""`. Aligned with today's `compute_profile_prefill`: anything we pre-fill from the citizen profile gets the badge; anything the agent asked the user for doesn't. No new enum, no backend migration.

### D3. Review-screen trigger via session.state mirror

A new effect in `GhiseuShell` watches `sessionStore.session?.state`:

| backend session.state | ghiseu state action |
|---|---|
| `"reviewing"` | `setState("review")` |
| `"delivered"` | `setState("done")` |
| any other | no-op (voice mirror owns it) |

Guarded the same way as the voice.state mirror: skip when ghiseu state is `error` / `mic-denied`. The agent's monologue keeps playing while the screen swaps — audio is independent of the displayed view.

### D4. Amend stays on review

`amendDoc` becomes `() => {}` for state (still clears any pending thinking-timer for safety). Rationale: the user is already looking at the field grid; switching them back to the voice ripple is jarring. As the agent calls `set_field`, `sessionStore.document.fields` updates and the visible row re-renders in place. User clicks "Da, e corect" when satisfied.

This is the simplest UX and matches the "live transcripts" feel of Phase 2.1 — kiosk reactive, no manual mode-switching.

### D5. Field rendering helper

`formatValue(value)`:
- `null` / `undefined` / `""` → `"—"`
- `boolean` → `"Da"` / `"Nu"`
- ISO date string matching `^\d{4}-\d{2}-\d{2}` → `DD.MM.YYYY`
- anything else → `String(value)`

Lives at `frontend/lib/format.ts` so other surfaces can reuse it later. Unit-tested directly.

---

## Touch list

| File | Action |
|---|---|
| `frontend/lib/format.ts` | **Create.** Export `formatValue(value: unknown): string`. |
| `frontend/lib/__tests__/format.test.ts` | **Create.** Cases for null/bool/date/string. |
| `frontend/lib/ghiseuStore.ts` | **Modify.** `amendDoc` becomes no-op for state (just clears thinking timer). |
| `frontend/lib/__tests__/ghiseuStore.test.ts` | **Modify.** Update the `amendDoc` test — assert state stays unchanged. |
| `frontend/components/ghiseu/DocumentReview.tsx` | **Rewrite body.** Drop `FIELDS`. Read from `useSessionStore`. Render `procedure.fields` × `document.fields`. Loading fallback when either is null. Title from `procedure.title`. |
| `frontend/components/ghiseu/__tests__/DocumentReview.test.tsx` | **Rewrite.** Loading state, full render with mocked session store, auto badge for profile-sourced fields. |
| `frontend/components/ghiseu/DoneScreen.tsx` | **Modify.** Read `ref_number` from `useSessionStore` with fallback. |
| `frontend/components/ghiseu/__tests__/DoneScreen.test.tsx` | **Modify.** Cases for real ref and `REG-PENDING`. |
| `frontend/components/ghiseu/GhiseuShell.tsx` | **Modify.** New Effect E — mirror `sessionStore.session?.state` → ghiseu state for `reviewing` / `delivered`. |
| `frontend/components/ghiseu/__tests__/GhiseuShell.test.tsx` | **Modify.** New test cases: session state transitions drive ghiseu state. |

---

## Acceptance criteria

- [ ] When the agent finishes filling required fields for any procedure (e.g., `certificat-fiscal`), `DocumentReview` shows the real procedure title in the doc paper, the real labels from `procedure.fields`, and the real values from `document.fields`.
- [ ] Profile-prefilled fields (cnp, nume_complet, email, etc.) display with `✓ auto`. Fields the agent asked for display without the badge.
- [ ] Backend session transitioning to `"reviewing"` swaps the kiosk to the review screen without explicit user action.
- [ ] Clicking "Mai am o corectură" keeps the field grid visible. Speaking a correction that fires `set_field` updates the displayed value live.
- [ ] `DoneScreen` shows `"REG-PENDING"` (since Phase 2.3 isn't landed yet) and will pick up the real ref number automatically once 2.3 wires the submit endpoint.
- [ ] All listed tests pass; no static FIELDS array remains in `DocumentReview.tsx`.

---

## Testing strategy

| Test file | Status | Coverage |
|---|---|---|
| `frontend/lib/__tests__/format.test.ts` | **New** | null → "—", true/false → "Da"/"Nu", ISO date → DD.MM.YYYY, plain string passthrough. |
| `frontend/lib/__tests__/ghiseuStore.test.ts` | **Modify** | `amendDoc` no longer changes state — assert before/after is equal. |
| `frontend/components/ghiseu/__tests__/DocumentReview.test.tsx` | **Rewrite** | Loading fallback when document/procedure null. Renders procedure.title in header. Renders one row per procedure field with correct label and value. Auto badge on `source: "profile"` rows with a non-empty value. No auto badge on `source: "ask"` rows. |
| `frontend/components/ghiseu/__tests__/DoneScreen.test.tsx` | **Modify** | Renders REG-PENDING when ref_number is null. Renders real ref_number when set. |
| `frontend/components/ghiseu/__tests__/GhiseuShell.test.tsx` | **Modify** | session.state="reviewing" → ghiseu state "review". session.state="delivered" → "done". No override when ghiseu state is "error" or "mic-denied". |

No new backend tests required — the data flow already exists; this phase just consumes it.

---

## Risks

| Risk | Mitigation |
|---|---|
| `session.state` transitions to `"reviewing"` before `sessionStore.document` is populated (race between session snapshot and document load) | `DocumentReview` has a loading fallback when `document` or `procedure` is null. The race is brief (sub-100ms in practice) and the fallback renders harmlessly. |
| Some procedure fields might have values that aren't string-renderable (e.g., nested objects from future schema additions) | `formatValue` falls back to `String(value)` — won't crash, will display `"[object Object]"` which is a clear "fix the schema" signal during dev. |
| User clicks "Da, e corect" while the agent is still amending a field | The export screen renders, then if a `set_field` lands afterward it just updates `document.fields` but the user has already moved on. Worst case: the value on the final PDF differs from what they saw on screen. Acceptable for v1; Phase 2.4 polish could add a "agent still talking, please wait" indicator. |
| Frontend `procedure.fields[].source` shape might not match `"profile"` literal in all procedures (e.g., uppercase, whitespace) | The check `field.source.includes("profile")` is case-sensitive and matches substring — already handles `"id_scan|profile"`. Audited against `backend/procedures/*.json`: all sources are lowercase, no surprises. |

---

## Implementation order (for writing-plans handoff)

1. `formatValue` + unit test (smallest, fully independent).
2. `ghiseuStore.amendDoc` → no-op for state, test update.
3. `GhiseuShell` Effect E — session.state mirror, test update.
4. `DocumentReview` rewrite + test rewrite.
5. `DoneScreen` modification + test update.
6. Manual smoke: run a procedure end-to-end on `/ghiseu`, confirm real fields render.
