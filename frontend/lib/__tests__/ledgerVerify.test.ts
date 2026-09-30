// The fixture was produced by the backend's own implementation
// (app/ledger.py + documents.pdf_generated_payload), so these tests check
// that the browser re-derives byte-identical hashes — including Romanian
// diacritics, typographic quotes, backslashes and newlines in payloads.
import { describe, expect, it } from "vitest";
import fixture from "./fixtures/ledger.json";
import { canonicalJson, verifyLedger } from "@/lib/ledgerVerify";
import type { LedgerEntry, LedgerResponse } from "@/lib/types";

const entries = () => structuredClone(fixture.entries) as LedgerEntry[];
const ctx = () => structuredClone(fixture) as unknown as LedgerResponse;

describe("verifyLedger", () => {
  it("verifies a chain written by the backend", async () => {
    const r = await verifyLedger(entries());
    expect(r.status).toBe("verified");
    if (r.status !== "verified") return;
    expect(r.rows).toBe(4);
    expect(r.head).toBe(fixture.entries[3]!.row_hash);
    expect(r.pdfSha256).toMatch(/^0x[0-9a-f]{64}$/);
  });

  it("detects an edited payload", async () => {
    const e = entries();
    (e[3]!.payload as Record<string, unknown>).ref_number = "CV-FAKE";
    expect((await verifyLedger(e)).status).toBe("broken");
  });

  it("detects a removed row", async () => {
    const e = entries();
    e.splice(1, 1);
    expect((await verifyLedger(e)).status).toBe("broken");
  });

  it("detects a changed timestamp", async () => {
    const e = entries();
    e[0]!.hashed_at = e[0]!.hashed_at!.replace("09:00:00", "08:00:00");
    expect((await verifyLedger(e)).status).toBe("broken");
  });

  it("says so when the server did not send payloads", async () => {
    const e = entries().map(({ payload: _p, ...rest }) => rest as LedgerEntry);
    expect((await verifyLedger(e)).status).toBe("unavailable");
  });
});

describe("canonicalJson", () => {
  it("matches Python's json.dumps(sort_keys, compact, ensure_ascii=False)", () => {
    expect(canonicalJson({ b: "ș", a: [1, { d: null, c: true }] })).toBe(
      '{"a":[1,{"c":true,"d":null}],"b":"ș"}',
    );
  });
});

describe("signatures", () => {
  it("accepts every row signed by the published key", async () => {
    const r = await verifyLedger(entries(), ctx());
    expect(r.status).toBe("verified");
    if (r.status !== "verified") return;
    expect(r.signatures).toEqual({ status: "valid", keyIds: [fixture.signing_keys[0]!.key_id] });
  });

  it("rejects a forged signature", async () => {
    const e = entries();
    const sig = e[2]!.signature!;
    e[2]!.signature = (sig[0] === "A" ? "B" : "A") + sig.slice(1);
    expect((await verifyLedger(e, ctx())).status).toBe("broken");
  });

  it("rejects a signature bound to another document", async () => {
    const c = ctx();
    c.document_id = "55555555-5555-5555-5555-555555555555";
    expect((await verifyLedger(entries(), c)).status).toBe("broken");
  });

  it("rejects a key the server does not publish", async () => {
    const c = ctx();
    c.signing_keys = [];
    expect((await verifyLedger(entries(), c)).status).toBe("broken");
  });

  it("reports unsigned rows without calling the chain broken", async () => {
    const e = entries().map((x) => ({ ...x, signature: null }));
    const r = await verifyLedger(e, ctx());
    expect(r.status).toBe("verified");
    if (r.status === "verified") expect(r.signatures).toEqual({ status: "partial", unsigned: 4 });
  });
});
