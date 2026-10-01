import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { LedgerStatus } from "../DocumentsDrawer";

describe("LedgerStatus", () => {
  it("names the eGata server's key as the signer, not the primărie", () => {
    const { container } = render(
      <LedgerStatus
        check={{
          status: "verified",
          rows: 4,
          head: "0x" + "ab".repeat(32),
          pdfSha256: "0x" + "cd".repeat(32),
          signatures: { status: "valid", keyIds: ["ed25519:5f8eb5c430bd215b"] },
        }}
        serverVerified={true}
      />,
    );
    const text = container.textContent ?? "";
    expect(text).toContain("Verificat în browserul tău: 4 pași, lanț intact.");
    expect(text).toContain("semnat cu cheia serverului eGata");
    expect(text).toContain("30bd215b");
    // The key is this server's (LEDGER_SIGNING_KEY); no institution signs anything.
    expect(text).not.toMatch(/primări/i);
  });
});
