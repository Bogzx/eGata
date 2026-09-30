"""Verify a document's audit ledger (and optionally its PDF) independently.

The `verified` flag in `GET /documents/{id}/ledger` is computed by the same
server that stores the rows, so on its own it proves nothing to a citizen.
This script re-derives every hash from the rows the API hands out, using only
the Python standard library and deliberately *not* importing `app` — it is a
second implementation of the format in migrations/009, not a wrapper around
the first.

    # from a saved API response
    python scripts/verify_ledger.py ledger.json --pdf cerere.pdf

    # straight from a running backend
    python scripts/verify_ledger.py --api http://localhost:8000 \\
        --token "$JWT" --document <document-uuid> --pdf cerere.pdf

What it checks, per row:
  payload_hash == sha256(canonical_json(payload))
  prev_hash    == previous row's row_hash (the first: the genesis hash)
  row_hash     == sha256(event_type || payload_hash || prev_hash || hashed_at)
and with --pdf, that the file's sha256 equals `pdf_sha256` in the latest
`pdf_generated` row.

What it cannot check: that rows were never appended by someone with database
write access who recomputed the hashes (the chain is unkeyed), or that the
tail was not cut off. Keep the printed head hash; if a later export no longer
contains it, history was rewritten. See README "Hash-chain audit ledger".
Exit status: 0 when everything verifies, 1 otherwise.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

GENESIS_HASH = "0x" + "0" * 64


def _sha256(data: bytes) -> str:
    return "0x" + hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def verify_entries(entries: list[dict[str, Any]]) -> list[str]:
    """Return a list of problems; empty means the chain verifies."""
    problems: list[str] = []
    prev = GENESIS_HASH
    for i, e in enumerate(entries):
        label = f"row {i + 1} ({e.get('event_type')}, id={e.get('id')})"
        if "payload" not in e or not e.get("hashed_at"):
            problems.append(f"{label}: no payload/hashed_at — cannot recompute")
            prev = e.get("row_hash", "")
            continue
        payload_hash = _sha256(_canonical_json(e["payload"]).encode("utf-8"))
        if payload_hash != e["payload_hash"]:
            problems.append(f"{label}: payload does not match payload_hash")
        if e["prev_hash"] != prev:
            problems.append(f"{label}: prev_hash does not link to the previous row")
        row_hash = _sha256(
            (e["event_type"] + e["payload_hash"] + e["prev_hash"] + e["hashed_at"]).encode("utf-8")
        )
        if row_hash != e["row_hash"]:
            problems.append(f"{label}: row_hash does not match its contents")
        prev = e["row_hash"]
    return problems


def verify_pdf(entries: list[dict[str, Any]], pdf_bytes: bytes) -> list[str]:
    rendered = [e for e in entries if e.get("event_type") == "pdf_generated"]
    if not rendered:
        return ["no pdf_generated row in this ledger"]
    expected = (rendered[-1].get("payload") or {}).get("pdf_sha256")
    if not expected:
        return ["latest pdf_generated row predates PDF hashing (no pdf_sha256)"]
    actual = _sha256(pdf_bytes)
    if actual != expected:
        return [f"PDF sha256 {actual} != ledger {expected}"]
    return []


def _fetch(api: str, token: str, document: str) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{api.rstrip('/')}/documents/{document}/ledger",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.load(resp)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("ledger_json", nargs="?", help="saved GET /documents/{id}/ledger response")
    ap.add_argument("--api", help="backend base URL, e.g. http://localhost:8000")
    ap.add_argument("--token", help="bearer token (with --api)")
    ap.add_argument("--document", help="document id (with --api)")
    ap.add_argument("--pdf", type=Path, help="PDF file to check against the ledger")
    args = ap.parse_args(argv)

    if args.api:
        if not (args.token and args.document):
            ap.error("--api needs --token and --document")
        body = _fetch(args.api, args.token, args.document)
    elif args.ledger_json:
        body = json.loads(Path(args.ledger_json).read_text(encoding="utf-8"))
    else:
        ap.error("give a ledger JSON file or --api/--token/--document")

    entries = body.get("entries", [])
    problems: list[str] = []
    if body.get("genesis_hash", GENESIS_HASH) != GENESIS_HASH:
        problems.append(f"server reports a non-standard genesis {body['genesis_hash']}")
    if not entries:
        problems.append("ledger is empty")
    problems += verify_entries(entries)
    if args.pdf:
        problems += verify_pdf(entries, args.pdf.read_bytes())

    for e in entries:
        print(f"  {e.get('hashed_at') or e.get('created_at')}  {e['event_type']:<16} {e['row_hash']}")
    if problems:
        print("\nNOT VERIFIED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"\nVERIFIED: {len(entries)} rows" + (", PDF matches" if args.pdf else ""))
    print(f"Head hash (keep this as your receipt): {entries[-1]['row_hash']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
