"""Verify a document's audit ledger (and optionally its PDF) independently.

The `verified` flag in `GET /documents/{id}/ledger` is computed by the same
server that stores the rows, so on its own it proves nothing to a citizen.
This script re-derives every hash and checks every signature from the rows
the API hands out, using only the Python standard library (Ed25519 included)
and deliberately *not* importing `app` — it is a second implementation of
the format in migrations/009 + 014, not a wrapper around the first.

    # from a saved API response
    python scripts/verify_ledger.py ledger.json --pdf cerere.pdf

    # straight from a running backend
    python scripts/verify_ledger.py --api http://localhost:8000 \\
        --token "$JWT" --document <document-uuid> --pdf cerere.pdf

    # keep a signed receipt of today's head; later, prove history still holds it
    python scripts/verify_ledger.py ledger.json --save-receipt receipt.json
    python scripts/verify_ledger.py --api ... --receipt receipt.json

What it checks, per row:
  payload_hash == sha256(canonical_json(payload))
  prev_hash    == previous row's row_hash (the first: the genesis hash)
  row_hash     == sha256(event_type || payload_hash || prev_hash || hashed_at)
  signature    == Ed25519 over the head statement, by a pinned public key
and with --pdf, that the file's sha256 equals `pdf_sha256` in the latest
`pdf_generated` row; with --receipt, that the receipt's signed head is still
in the chain.

Pin the key: pass --public-key (base64) or --keys-file (a copy of
/.well-known/egata-ledger-keys.json obtained independently). Without either,
the keys in the export are used and the script says so — that only proves
the export is self-consistent, not who signed it.

What it cannot check without a receipt or an external anchor: that the
signing-key holder did not rebuild history and re-sign it.
Exit status: 0 when everything verifies, 1 otherwise.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

GENESIS_HASH = "0x" + "0" * 64
STATEMENT_TYPE = "egata-ledger-head"


def _sha256(data: bytes) -> str:
    return "0x" + hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ---- Ed25519 verification (RFC 8032 §5.1.7), standard library only ----------

_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _recover_x(y: int, sign: int) -> int | None:
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_Point = tuple[int, int, int, int]


def _add(p: _Point, q: _Point) -> _Point:
    a = (p[1] - p[0]) * (q[1] - q[0]) % _P
    b = (p[1] + p[0]) * (q[1] + q[0]) % _P
    c = 2 * p[3] * q[3] * _D % _P
    d = 2 * p[2] * q[2] % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _mul(s: int, p: _Point) -> _Point:
    q: _Point = (0, 1, 1, 0)
    while s:
        if s & 1:
            q = _add(q, p)
        p = _add(p, p)
        s >>= 1
    return q


def _same(p: _Point, q: _Point) -> bool:
    return (p[0] * q[2] - q[0] * p[2]) % _P == 0 and (p[1] * q[2] - q[1] * p[2]) % _P == 0


def _decode_point(b: bytes) -> _Point | None:
    if len(b) != 32:
        return None
    y = int.from_bytes(b, "little")
    sign, y = y >> 255, y & ((1 << 255) - 1)
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _P)


_GY = 4 * pow(5, _P - 2, _P) % _P
_GX = _recover_x(_GY, 0) or 0
_G: _Point = (_GX, _GY, 1, _GX * _GY % _P)


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if len(public_key) != 32 or len(signature) != 64:
        return False
    a, r = _decode_point(public_key), _decode_point(signature[:32])
    if a is None or r is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:
        return False
    h = int.from_bytes(hashlib.sha512(signature[:32] + public_key + message).digest(), "little") % _L
    return _same(_mul(s, _G), _add(r, _mul(h, a)))


# ---- ledger checks -----------------------------------------------------------


def _statement(key_id: str, citizen_id: str, document_id: str | None, row_id: int, row_hash: str) -> bytes:
    return _canonical_json(
        {
            "v": 1,
            "type": STATEMENT_TYPE,
            "key_id": key_id,
            "citizen_id": citizen_id,
            "document_id": document_id,
            "row_id": row_id,
            "row_hash": row_hash,
        }
    ).encode("utf-8")


def key_id_for(public_raw: bytes) -> str:
    return "ed25519:" + hashlib.sha256(public_raw).hexdigest()[:16]


def verify_entries(entries: list[dict[str, Any]]) -> list[str]:
    """Hash chain only. Returns a list of problems; empty means it verifies."""
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


def verify_signatures(
    entries: list[dict[str, Any]], keys: dict[str, bytes], citizen_id: str, document_id: str | None
) -> list[str]:
    problems: list[str] = []
    for i, e in enumerate(entries):
        label = f"row {i + 1} ({e.get('event_type')}, id={e.get('id')})"
        key_id, signature = e.get("key_id"), e.get("signature")
        if not key_id or not signature:
            problems.append(f"{label}: not signed")
            continue
        if key_id not in keys:
            problems.append(f"{label}: signed by unknown key {key_id}")
            continue
        msg = _statement(key_id, citizen_id, document_id, int(e["id"]), e["row_hash"])
        if not ed25519_verify(keys[key_id], msg, base64.b64decode(signature)):
            problems.append(f"{label}: signature does not verify")
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


def make_receipt(body: dict[str, Any]) -> dict[str, Any]:
    head = body["entries"][-1]
    return {
        "receipt": "egata-ledger-head/v1",
        "citizen_id": body["citizen_id"],
        "document_id": body["document_id"],
        "row_id": head["id"],
        "row_hash": head["row_hash"],
        "key_id": head["key_id"],
        "signature": head["signature"],
    }


def check_receipt(receipt: dict[str, Any], body: dict[str, Any], keys: dict[str, bytes]) -> list[str]:
    key = keys.get(receipt.get("key_id", ""))
    if key is None:
        return [f"receipt signed by unknown key {receipt.get('key_id')}"]
    msg = _statement(
        receipt["key_id"], receipt["citizen_id"], receipt["document_id"],
        int(receipt["row_id"]), receipt["row_hash"],
    )
    if not ed25519_verify(key, msg, base64.b64decode(receipt["signature"])):
        return ["receipt signature does not verify"]
    if receipt["document_id"] != body.get("document_id"):
        return ["receipt is for another document"]
    held = {int(e["id"]): e["row_hash"] for e in body.get("entries", [])}
    if held.get(int(receipt["row_id"])) != receipt["row_hash"]:
        return [
            "HISTORY REWRITTEN: the chain no longer contains the head this receipt "
            f"was signed for (row {receipt['row_id']}, {receipt['row_hash']})"
        ]
    return []


def _fetch_json(url: str, token: str | None = None) -> dict[str, Any]:
    if not url.startswith(("http://", "https://")):
        raise SystemExit(f"--api must be an http(s) URL, got {url!r}")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = urllib.request.Request(url, headers=headers)  # noqa: S310 — scheme checked above
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.load(resp)


def _keys_from(listing: list[dict[str, Any]]) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for k in listing:
        raw = base64.b64decode(k["public_key"])
        if key_id_for(raw) == k.get("key_id"):
            out[k["key_id"]] = raw
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("ledger_json", nargs="?", help="saved GET /documents/{id}/ledger response")
    ap.add_argument("--api", help="backend base URL, e.g. http://localhost:8000")
    ap.add_argument("--token", help="bearer token (with --api)")
    ap.add_argument("--document", help="document id (with --api)")
    ap.add_argument("--pdf", type=Path, help="PDF file to check against the ledger")
    ap.add_argument("--public-key", action="append", default=[], help="pinned base64 Ed25519 key")
    ap.add_argument("--keys-file", type=Path, help="independent copy of egata-ledger-keys.json")
    ap.add_argument("--save-receipt", type=Path, help="write a signed receipt of the current head")
    ap.add_argument("--receipt", type=Path, help="check a previously saved receipt")
    ap.add_argument("--allow-unsigned", action="store_true", help="accept rows with no signature")
    args = ap.parse_args(argv)

    if args.api:
        if not (args.token and args.document):
            ap.error("--api needs --token and --document")
        body = _fetch_json(f"{args.api.rstrip('/')}/documents/{args.document}/ledger", args.token)
    elif args.ledger_json:
        body = json.loads(Path(args.ledger_json).read_text(encoding="utf-8"))
    else:
        ap.error("give a ledger JSON file or --api/--token/--document")

    entries = body.get("entries", [])
    problems: list[str] = []
    notes: list[str] = []
    if body.get("genesis_hash", GENESIS_HASH) != GENESIS_HASH:
        problems.append(f"server reports a non-standard genesis {body['genesis_hash']}")
    if not entries:
        problems.append("ledger is empty")
    problems += verify_entries(entries)

    if args.public_key:
        keys = {key_id_for(base64.b64decode(k)): base64.b64decode(k) for k in args.public_key}
    elif args.keys_file:
        keys = _keys_from(json.loads(args.keys_file.read_text(encoding="utf-8")).get("keys", []))
    else:
        keys = _keys_from(body.get("signing_keys", []))
        notes.append(
            "signing key taken from the export itself (trust on first use) — compare the "
            "key id with one you got elsewhere, or pass --public-key / --keys-file"
        )
    if not body.get("citizen_id") or not body.get("document_id"):
        problems.append("export has no citizen_id/document_id — cannot check signatures")
    else:
        sig_problems = verify_signatures(entries, keys, body["citizen_id"], body["document_id"])
        unsigned = [p for p in sig_problems if p.endswith("not signed")]
        if args.allow_unsigned and len(unsigned) == len(sig_problems):
            if unsigned:
                notes.append(f"{len(unsigned)} rows unsigned (accepted with --allow-unsigned)")
        else:
            problems += sig_problems

    if args.pdf:
        problems += verify_pdf(entries, args.pdf.read_bytes())
    if args.receipt:
        problems += check_receipt(json.loads(args.receipt.read_text(encoding="utf-8")), body, keys)

    for e in entries:
        signed = "signed" if e.get("signature") else "UNSIGNED"
        print(f"  {e.get('hashed_at') or e.get('created_at')}  {e['event_type']:<16} {e['row_hash']}  {signed}")
    for n in notes:
        print(f"\nnote: {n}")
    if problems:
        print("\nNOT VERIFIED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(
        f"\nVERIFIED: {len(entries)} rows, hashes and signatures"
        + (", PDF matches" if args.pdf else "")
        + (", receipt still in history" if args.receipt else "")
    )
    print(f"Signing key(s): {', '.join(sorted({e['key_id'] for e in entries if e.get('key_id')}))}")
    print(f"Head hash: {entries[-1]['row_hash']}")
    if args.save_receipt:
        args.save_receipt.write_text(json.dumps(make_receipt(body), indent=2) + "\n", encoding="utf-8")
        print(f"Signed receipt written to {args.save_receipt} — keep it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
