---
type: contract
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Session Snapshot Schema

The wire shape of `Session.snapshot()`. Pushed by both SSE and voice WS after every state mutation.

## Shape

```ts
type SessionSnapshot = {
  id: string;                       // "sess_..." or legacy "conv_..."
  citizen_id: string;
  state: "exploring" | "confirming_match" | "filling" | "reviewing" | "delivered" | "redirected";
  active_document_id: string | null;
  scenario_id: string | null;
  step_index: number | null;
  pending_widgets: PendingWidget[];
  seq?: number;                     // monotonic per-process counter
};

type PendingWidget = {
  widget_id: string;
  type: "choice" | "confirm" | "date";
  question: string;
  target_field?: string | null;
  options: string[];
};
```

## What it does NOT carry

- `history` — too large and agent-internal. The FE doesn't need it.
- Field values for the active document — those come from `field_updated` events and from `GET /documents/{id}`.
- Citizen attributes — those live in the `citizen` slice of the FE store, populated by `GET /citizens/me`.

## The `seq` field

`time.monotonic_ns()` from the backend process. The FE store applies snapshots only if `seq > lastAppliedSeq` — out-of-order arrivals (during reconnect / proxy buffering / two transports racing) are dropped.

## FE store reaction

`sessionStore.applySnapshot(snapshot)`:

1. If `snapshot.seq <= lastSeq` → drop.
2. Update `session` slice.
3. If `active_document_id` changed → fetch the doc.
4. Reconcile pending widgets — drop locally-displayed widgets that are no longer in the snapshot (server resolved them).

## See also

- [[sessions]]`.snapshot()`
- [[Frontend Session Mirror]]
- [[PendingWidget]]
