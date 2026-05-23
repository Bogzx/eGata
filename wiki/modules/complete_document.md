---
type: module
path: "backend/app/agent_tools/complete_document.py"
status: active
language: python
purpose: "Agent tool: render PDF + deliver + transition to DELIVERED in one call."
depends_on: [documents, ledger, pdf, procedures, procedure_state, sessions, storage]
used_by: [session_engine, agent_voice]
valid_states: [REVIEWING]
created: 2026-05-23
updated: 2026-05-23
---

# complete_document

Collapses the old `generate_pdf` + `deliver` HTTP routes into a single agent-facing call. The agent never juggles "did I PDF yet?" — it's one call that does both atomically (from the user's perspective).

## Parameters

```json
{ "delivery": "save|send|print" }
```

## Behavior (happy path)

1. Verify `delivery` is valid.
2. Resolve `active_document_id`. Owner check.
3. **Idempotency short-circuit**: if the doc is already finalized, re-emit `document_delivered` with cached values and return. Stops LLM retries from double-PDF-ing or double-SMS-ing.
4. Verify all applies_if-aware required fields are satisfied ([[procedure_state]]).
5. Render PDF: `render_and_compile(template, fields)` ([[pdf]]) — runs in a thread via `asyncio.to_thread` (pdflatex blocks for 5–15s; the voice WS audio pumps must keep flowing).
6. Upload to Supabase Storage at `<citizen>/<doc>.pdf`. Set `pdf_url` on the doc.
7. Append `pdf_generated` to [[ledger]].
8. `generate_ref_number(doc_id)` → `CV-XXXX`.
9. `finalize_document(doc_id, delivery, ref_number)` — sets `status='finalized'`, `delivered_at`, etc.
10. Append `delivered` to ledger.
11. If `delivery == "send"`, fire Twilio SMS **best-effort** — failures don't unwind the finalize. Logged + carried on.
12. Emit `frontend_event: document_delivered` and request `transition_to=DELIVERED`.

## Why best-effort SMS

The doc is already finalized when the SMS attempt happens. A Twilio blip MUST NOT cause the LLM to retry and double-finalize. We log + move on.

## Why idempotency matters

Voice sessions can stutter — the model might emit `complete_document` twice in a row. The second call sees `status='finalized'` and returns cached output, re-emits `document_delivered` for the UI, and skips the work.

## See also

- [[Flow Document Lifecycle]]
- [[documents]] — the HTTP equivalent
- [[pdf]] + [[storage]]
- [[ADR Hash-Chain Ledger]]
