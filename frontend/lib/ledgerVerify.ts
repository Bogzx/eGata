/**
 * Re-derive a document's audit chain in the browser.
 *
 * The API's `verified` flag is computed by the same server that stores the
 * rows, so it cannot vouch for itself. This recomputes every hash from the
 * rows the API returns — the same format as migrations/009 and
 * backend/scripts/verify_ledger.py:
 *
 *   payload_hash = sha256(canonical_json(payload))
 *   row_hash     = sha256(event_type + payload_hash + prev_hash + hashed_at)
 *
 * canonical_json is Python's json.dumps(sort_keys=True, separators=(",", ":"),
 * ensure_ascii=False). JSON.stringify produces the same bytes for the
 * payloads the ledger holds (strings, integers, nested objects).
 *
 * Each row is also Ed25519-signed (migrations/014, app/ledger_signing.py)
 * over canonical_json({v, type, key_id, citizen_id, document_id, row_id,
 * row_hash}); those are checked with WebCrypto where the browser supports
 * Ed25519, against the keys the server publishes.
 */
import type { LedgerEntry, LedgerResponse } from "@/lib/types";

export const GENESIS_HASH = "0x" + "0".repeat(64);

/** valid: every row signed by a published key · partial: some rows carry no
 * signature yet · unsupported: this browser has no Ed25519 in WebCrypto. */
export type SignatureCheck =
  | { status: "valid"; keyIds: string[] }
  | { status: "partial"; unsigned: number }
  | { status: "unsupported" };

export type LedgerCheck =
  | {
      status: "verified";
      rows: number;
      head: string;
      pdfSha256: string | null;
      signatures: SignatureCheck;
    }
  | { status: "broken"; rows: number; reason: string }
  | { status: "unavailable"; reason: string };

/** Python sorts dict keys by code point; Array.prototype.sort compares UTF-16
 * code units, which orders an astral character before U+E000–U+FFFF. */
function compareCodePoints(a: string, b: string): number {
  const x = Array.from(a);
  const y = Array.from(b);
  for (let i = 0; i < Math.min(x.length, y.length); i++) {
    const d = x[i]!.codePointAt(0)! - y[i]!.codePointAt(0)!;
    if (d !== 0) return d;
  }
  return x.length - y.length;
}

export function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) {
    return "[" + value.map(canonicalJson).join(",") + "]";
  }
  if (value !== null && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    return (
      "{" +
      Object.keys(obj)
        .sort(compareCodePoints)
        .map((k) => JSON.stringify(k) + ":" + canonicalJson(obj[k]))
        .join(",") +
      "}"
    );
  }
  return JSON.stringify(value);
}

async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return (
    "0x" +
    Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("")
  );
}

function b64ToBytes(b64: string): Uint8Array<ArrayBuffer> {
  const bin = atob(b64);
  const out = new Uint8Array(new ArrayBuffer(bin.length));
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function ed25519Available(): Promise<boolean> {
  try {
    await crypto.subtle.importKey("raw", new Uint8Array(32).fill(1), { name: "Ed25519" }, false, [
      "verify",
    ]);
    return true;
  } catch {
    return false;
  }
}

async function checkSignatures(
  entries: LedgerEntry[],
  ctx: Pick<LedgerResponse, "citizen_id" | "document_id" | "signing_keys">,
): Promise<SignatureCheck | string> {
  if (!(await ed25519Available())) return { status: "unsupported" };
  const keys = new Map((ctx.signing_keys ?? []).map((k) => [k.key_id, k.public_key]));
  let unsigned = 0;
  const used = new Set<string>();
  for (const [i, e] of entries.entries()) {
    if (!e.signature || !e.key_id) {
      unsigned++;
      continue;
    }
    const pub = keys.get(e.key_id);
    if (!pub) return `Pasul ${i + 1}: semnat cu o cheie nepublicată.`;
    const statement = canonicalJson({
      v: 1,
      type: "egata-ledger-head",
      key_id: e.key_id,
      citizen_id: ctx.citizen_id,
      document_id: ctx.document_id,
      row_id: e.id,
      row_hash: e.row_hash,
    });
    const key = await crypto.subtle.importKey("raw", b64ToBytes(pub), { name: "Ed25519" }, false, [
      "verify",
    ]);
    const ok = await crypto.subtle.verify(
      { name: "Ed25519" },
      key,
      b64ToBytes(e.signature),
      new TextEncoder().encode(statement),
    );
    if (!ok) return `Pasul ${i + 1}: semnătură invalidă.`;
    used.add(e.key_id);
  }
  return unsigned ? { status: "partial", unsigned } : { status: "valid", keyIds: [...used] };
}

export async function verifyLedger(
  entries: LedgerEntry[],
  ctx?: Pick<LedgerResponse, "citizen_id" | "document_id" | "signing_keys">,
): Promise<LedgerCheck> {
  if (entries.length === 0) {
    return { status: "unavailable", reason: "Jurnalul este gol." };
  }
  if (typeof crypto === "undefined" || !crypto.subtle) {
    // WebCrypto exists only in secure contexts (https, localhost).
    return {
      status: "unavailable",
      reason: "Browserul nu poate calcula SHA-256 pe o conexiune nesecurizată.",
    };
  }
  if (entries.some((e) => e.payload === undefined || !e.hashed_at)) {
    return {
      status: "unavailable",
      reason: "Serverul nu a trimis datele necesare verificării.",
    };
  }

  let prev = GENESIS_HASH;
  for (const [i, e] of entries.entries()) {
    const label = `Pasul ${i + 1}`;
    if (e.prev_hash !== prev) {
      return { status: "broken", rows: entries.length, reason: `${label}: legătură ruptă.` };
    }
    if ((await sha256Hex(canonicalJson(e.payload))) !== e.payload_hash) {
      return { status: "broken", rows: entries.length, reason: `${label}: conținut modificat.` };
    }
    const rowHash = await sha256Hex(e.event_type + e.payload_hash + e.prev_hash + e.hashed_at);
    if (rowHash !== e.row_hash) {
      return { status: "broken", rows: entries.length, reason: `${label}: hash invalid.` };
    }
    prev = e.row_hash;
  }

  let signatures: SignatureCheck = { status: "partial", unsigned: entries.length };
  if (ctx?.citizen_id && ctx.document_id) {
    const sig = await checkSignatures(entries, ctx);
    if (typeof sig === "string") {
      return { status: "broken", rows: entries.length, reason: sig };
    }
    signatures = sig;
  }

  const pdfRows = entries.filter((e) => e.event_type === "pdf_generated");
  const pdf = pdfRows[pdfRows.length - 1]?.payload?.pdf_sha256;
  return {
    status: "verified",
    rows: entries.length,
    head: prev,
    pdfSha256: typeof pdf === "string" ? pdf : null,
    signatures,
  };
}
