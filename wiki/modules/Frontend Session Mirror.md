---
type: module
path: "frontend/lib/sessionStore.ts"
status: active
language: typescript
created: 2026-05-23
updated: 2026-05-23
---

# Frontend Session Mirror

A Zustand store that mirrors the backend `SessionSnapshot` and applies `FrontendEvent`s as they arrive over SSE / WS.

## Why a mirror

The UI needs to react to backend state changes WITHOUT polling. Three things flow over the wire:

1. `session_snapshot` → full state replacement
2. `frontend_event` → discrete UI directive
3. `delta` / `agent_done` / `user_done` → message bubble text

The store has one handler per shape. Pages just subscribe to slices.

## Slices

```ts
interface SessionState {
  citizen: Citizen | null
  activeDocId: string | null
  document: Document | null
  procedure: Procedure | null
  conversationId: string | null
  messages: Message[]
  voiceStatus: VoiceStatus
  micOn: boolean
  drawerOpen: boolean
  profileMenuOpen: boolean
  sending: boolean
  scenarioPlan: ScenarioPlan | null
  lookupMatches: LookupMatch[]
  session: SessionSnapshot | null
  // ... + actions
}
```

## Local persistence

- `messages` per `docId` → `localStorage["civicai:session:<docId>"]`. Survives reloads.
- `conversationId` per `docId` → `localStorage["civicai:conv:<docId>"]`. Lets the FE re-attach to the same backend Session on reload.

## Navigation indirection

The store has `setNavigate(fn)` so the React tree replaces the default `window.history.pushState` with the Next.js router. Without that, `useParams()` stays stale after a store-driven navigation and only `popstate` ever re-syncs. The patch is set in the root layout.

## Snapshot reconciliation

`applySnapshot(snapshot)`:

1. **`seq` guard** — drop if `snapshot.seq <= lastSeq`.
2. Replace `session` slice.
3. If `active_document_id` changed → fetch the doc.
4. Reconcile `pending_widgets` — drop any FE-side widgets that are no longer present.

## Frontend event handlers

The store's `applyFrontendEvent(e)` dispatches on `e.type`:

| Event | Action |
|---|---|
| `document_opened` | `pushPath("/r/<id>")`, fetch document, mark activeDocId |
| `widget_proposed` | Append `WidgetSpec` to latest agent message; render inline |
| `field_updated` | `setDocument(d => ({...d, fields: {...d.fields, [name]: value}}))` |
| `document_delivered` | Mark doc finalized; refresh `AuditTimeline` |
| `redirect` | Open redirect card; mark messages |
| `lookup_returned` | Set `lookupMatches` + `scenarioPlan` for the right pane |

## See also

- [[Session Snapshot Schema]]
- [[Frontend Event Schema]]
- [[Frontend Lib]]
