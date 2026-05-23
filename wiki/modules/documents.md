---
type: module
path: "backend/app/documents.py"
status: active
language: python
purpose: "Document CRUD + ledger writes + PDF render + delivery."
depends_on: [config, db, ledger, models, pdf, procedures, security, storage]
used_by: [frontend req page, agent_tools/start_procedure, agent_tools/set_field, agent_tools/complete_document, session_engine]
created: 2026-05-23
updated: 2026-05-23
---

# documents

The document lifecycle owner. Owns table `documents` ([[Database Schema]]) and gates every state change behind ownership checks (`_require_owner`).

## Routes

| Route | Verb | Body / Path | Returns | Side effects |
|---|---|---|---|---|
| `/documents` | POST | `{procedure_id}` | `DocumentResponse` | Insert row, append `doc_created` to [[ledger]]. |
| `/documents` | GET | — | `list[DocumentResponse]` | Citizen's docs sorted by `created_at desc`. |
| `/documents/{id}` | GET | path | `DocumentResponse` | Owner check. |
| `/documents/{id}/fields` | PATCH | `{fields: {...}}` | `DocumentResponse` | `jsonb \|\| jsonb` merge. If this PATCH crosses the "all required satisfied" line, appends `completed_draft` to the ledger. |
| `/documents/{id}/generate-pdf` | POST | — | `{pdf_url}` | Render LaTeX, upload to Supabase Storage at `<citizen_id>/<doc_id>.pdf`, set `pdf_url`, append `pdf_generated`. |
| `/documents/{id}/deliver` | POST | `{delivery: save\|send\|print}` | `DocumentResponse` | Set `status='finalized'`, `delivery`, `ref_number=CV-XXXX`, `delivered_at`, append `delivered`. If `send`, fire Twilio SMS (best-effort, [[twilio_bridge]] is NOT involved — direct `messages.create`). |
| `/documents/{id}/ledger` | GET | — | `LedgerResponse` | Returns chain + `verified` boolean computed via `verify_chain`. |

## Required-set transition

```python
was_complete = _all_required_present(doc.procedure_id, doc.fields)
updated = update_document_fields(doc_id, fields)
now_complete = _all_required_present(updated.procedure_id, updated.fields)
if not was_complete and now_complete:
    append_ledger(... event_type=COMPLETED_DRAFT ...)
```

> [!gotcha] `_all_required_present` here is **not** applies_if-aware
> It checks `proc.fields[*].required` directly. The applies_if-aware path is `procedure_state.all_required_satisfied` ([[procedure_state]]) used by [[set_field]] and [[complete_document]]. This HTTP-PATCH path is **the legacy** route — the new agent path bypasses it.

## ref_number generation

```python
def generate_ref_number(doc_id):
    return "CV-" + str(doc_id).replace("-", "").upper()[:4]
```

Cheap and demo-friendly. **Not collision-proof at scale** — replace with a sequence in production.

## Twilio SMS (delivery == "send")

`send_delivery_sms` checks `MOCK_OTP` first (yes, the OTP flag also gates SMS to avoid Twilio costs during dev). Then `TWILIO_ACCOUNT_SID` + `TWILIO_PHONE_NUMBER`. Body is a fixed Romanian template with the ref number.

## See also

- [[Flow Document Lifecycle]]
- [[ledger]]
- [[pdf]]
- [[storage]]
- [[complete_document]] — agent-side equivalent of generate-pdf + deliver in one call
