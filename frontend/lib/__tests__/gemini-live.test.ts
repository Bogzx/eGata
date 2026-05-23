import { describe, it, expect } from "vitest";
import { _internal } from "../gemini-live";

const { scrubAgentText } = _internal;

describe("scrubAgentText", () => {
  it("strips a leading markdown 'thinking' block before a Romanian reply", () => {
    const input = `**Initiating Communication Strategy**

I've got a tricky starting point here, an ellipsis alone! Given the voice_only profile, I'm thinking I must offer a warm Romanian greeting and a direct, clear prompt.

Bună ziua! Cu ce te pot ajuta?`;
    const out = scrubAgentText(input);
    expect(out.startsWith("Bună")).toBe(true);
    expect(out).not.toContain("**");
    expect(out).not.toContain("Initiating");
    expect(out).not.toContain("I've got");
  });

  it("strips the second example from the bug report", () => {
    const input = `**Greeting the User**

Salut! I have started by understanding my role: I am CivicAI, here to assist with city hall procedures.

Salut! Cu ce te pot ajuta legat de procedurile primăriei?`;
    const out = scrubAgentText(input);
    expect(out).not.toContain("**Greeting");
    expect(out).not.toContain("understanding my role");
    expect(out).toContain("Salut! Cu ce");
  });

  it("strips XML-style thinking tags too", () => {
    expect(scrubAgentText("<thinking>foo</thinking>Bună")).toBe("Bună");
    expect(scrubAgentText("Hi<scratchpad>x</scratchpad>there")).toBe("Hithere");
  });

  it("passes clean text through unchanged", () => {
    expect(scrubAgentText("Bună ziua! Cum vă pot ajuta?")).toBe(
      "Bună ziua! Cum vă pot ajuta?",
    );
  });

  it("handles empty and whitespace-only inputs", () => {
    expect(scrubAgentText("")).toBe("");
    expect(scrubAgentText("   ")).toBe("");
  });

  it("PRESERVES Romanian bold headings — diacritics signal a real header", () => {
    const input = `**Pași:**

Mai întâi spune-mi adresa nouă.`;
    const out = scrubAgentText(input);
    expect(out).toContain("**Pași:**");
    expect(out).toContain("Mai întâi");
  });

  it("PRESERVES a stray bold line mid-message (no longer blanket-stripped)", () => {
    const input = `Salut!

**Continuăm**

Cum locuiești?`;
    const out = scrubAgentText(input);
    expect(out).toContain("**Continuăm**");
    expect(out).toContain("Salut!");
    expect(out).toContain("Cum locuiești?");
  });
});
