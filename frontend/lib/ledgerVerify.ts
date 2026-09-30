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
 */
import type { LedgerEntry } from "@/lib/types";

export const GENESIS_HASH = "0x" + "0".repeat(64);

export type LedgerCheck =
  | { status: "verified"; rows: number; head: string; pdfSha256: string | null }
  | { status: "broken"; rows: number; reason: string }
  | { status: "unavailable"; reason: string };

export function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) {
    return "[" + value.map(canonicalJson).join(",") + "]";
  }
  if (value !== null && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    return (
      "{" +
      Object.keys(obj)
        .sort()
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

export async function verifyLedger(entries: LedgerEntry[]): Promise<LedgerCheck> {
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

  const pdfRows = entries.filter((e) => e.event_type === "pdf_generated");
  const pdf = pdfRows[pdfRows.length - 1]?.payload?.pdf_sha256;
  return {
    status: "verified",
    rows: entries.length,
    head: prev,
    pdfSha256: typeof pdf === "string" ? pdf : null,
  };
}
