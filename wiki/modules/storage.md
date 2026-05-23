---
type: module
path: "backend/app/storage.py"
status: active
language: python
purpose: "Supabase Storage uploader for generated PDFs."
depends_on: [db]
used_by: [documents, agent_tools/complete_document]
created: 2026-05-23
updated: 2026-05-23
---

# storage

A single function, a single bucket.

## `upload_pdf_to_storage(object_path, data) → str`

- Bucket name: `pdfs` (public).
- Idempotently `create_bucket("pdfs", {"public": True})` — errors suppressed since the bucket survives between runs.
- Uploads with `content-type: application/pdf` and `upsert: true` (overwrite on re-render).
- Returns `client.storage.from_("pdfs").get_public_url(object_path)`.

## Object path convention

```
<citizen_uuid>/<document_uuid>.pdf
```

Set in [[documents]]`.generate_pdf` and [[complete_document]]. Keeps PDFs grouped per citizen for easy bulk-delete during demo reset (if you ever extend [[demo]] to clean storage).

## See also

- [[Dep Supabase]]
