---
type: flow
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Flow: Document Lifecycle

How a document goes from "not yet" to a printed/finalized PDF with a tamper-evident audit trail.

## States

| `documents.status` | `documents.delivery` | `documents.ref_number` | `documents.pdf_url` |
|---|---|---|---|
| `draft` | `null` | `null` | `null` |
| `draft` (all required fields filled) | `null` | `null` | `null` (or a previous URL if regenerated) |
| `finalized` | `save`/`send`/`print` | `CV-XXXX` | url |

## Two paths into this lifecycle

The repo has both:

1. **Legacy HTTP** — frontend POSTs `/documents`, PATCHes fields, then POSTs `/documents/{id}/generate-pdf` and `/documents/{id}/deliver`. Used by the manual form-fill page.
2. **Agent-driven** — the agent calls [[start_procedure]] (which inserts the doc), [[set_field]] (PATCH-equivalent with applies_if), and [[complete_document]] (the PDF + deliver fused into one tool).

The two paths write to the **same table** and the **same ledger**. The applies_if-aware path is the only one that handles conditional fields correctly — see [[procedure_state]].

## Ledger events fired

| When | Event | Payload |
|---|---|---|
| Document created | `doc_created` | `{document_id, procedure_id}` (+ `source: reminder, reminder_id` if started from a reminder) |
| Required-set transition crossed (PATCH path only) | `completed_draft` | `{document_id}` |
| PDF rendered + uploaded | `pdf_generated` | `{document_id, pdf_url}` |
| Delivery applied | `delivered` | `{document_id, delivery, ref_number}` |
| Worker writes a reminder | `reminder_created` | `{reminder_id, kind, title, procedure_id?, redirect_target?}` |

Every event is signed by the hash chain ([[ledger]]).

## Diagram (agent path)

```
agent
  │
  ▼  start_procedure(procedure_id)
documents.insert            ─►  ledger: doc_created
session.active_document_id=…
session.state = FILLING
  │
  ▼  set_field(name=adresa_noua, value=…)
documents.fields ||= {...}   (NO ledger event — too noisy)
session.state stays FILLING
  │   …more set_fields…
  ▼  set_field that satisfies the last applies_if-required field
session.state = REVIEWING
  │
  ▼  complete_document(delivery=send)
pdflatex (in thread)
storage.upload_pdf_to_storage  ─►  ledger: pdf_generated
finalize_document               ─►  ledger: delivered
maybe Twilio SMS (best-effort)
session.state = DELIVERED
```

After `delivered` lands in the ledger, the [[worker]] sees it on its next poll (within 5s) and writes reminders for the procedure's `next_steps` ([[Flow Reminders Worker]]).

## Idempotency

`complete_document` re-emits cached output if `status=finalized` already — protects against LLM retries double-PDF-ing or double-SMS-ing.

## See also

- [[documents]] — HTTP routes
- [[complete_document]] — tool
- [[ledger]]
- [[Flow Reminders Worker]]
- [[Flow Session State Machine]]
