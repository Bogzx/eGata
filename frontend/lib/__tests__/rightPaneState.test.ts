import { describe, it, expect } from "vitest";
import {
  allRequiredFilled,
  computeInitialRightPaneFrom,
  isFilled,
} from "../rightPaneState";
import type { Document, Procedure } from "../types";

function mkProc(over: Partial<Procedure> = {}): Procedure {
  return {
    id: "p1",
    title: "Procedură test",
    description: "",
    scope: "primarie",
    category: "x",
    synonyms: [],
    sample_queries: [],
    fields: [
      { name: "a", label: "A", source: "ask", required: true },
      { name: "b", label: "B", source: "ask", required: false },
    ],
    template: "x.tex",
    next_steps: [],
    ...over,
  };
}

function mkDoc(over: Partial<Document> = {}): Document {
  return {
    id: "d1",
    citizen_id: "c1",
    procedure_id: "p1",
    status: "draft",
    fields: {},
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  };
}

describe("isFilled", () => {
  it("rejects empty / null / undefined", () => {
    expect(isFilled("")).toBe(false);
    expect(isFilled(null)).toBe(false);
    expect(isFilled(undefined)).toBe(false);
  });
  it("accepts strings, numbers, booleans, objects", () => {
    expect(isFilled("x")).toBe(true);
    expect(isFilled(0)).toBe(true);
    expect(isFilled(false)).toBe(true);
    expect(isFilled({ a: 1 })).toBe(true);
  });
});

describe("allRequiredFilled", () => {
  it("true when no required fields", () => {
    const proc = mkProc({
      fields: [{ name: "a", label: "A", source: "ask", required: false }],
    });
    expect(allRequiredFilled(proc, {})).toBe(true);
  });
  it("false when some required are missing", () => {
    expect(allRequiredFilled(mkProc(), {})).toBe(false);
  });
  it("true when required filled, optional missing", () => {
    expect(allRequiredFilled(mkProc(), { a: "x" })).toBe(true);
  });
});

describe("computeInitialRightPaneFrom", () => {
  it("done when finalized with ref_number", () => {
    const r = computeInitialRightPaneFrom(
      mkDoc({ status: "finalized", ref_number: "REF-123" }),
      mkProc(),
    );
    expect(r).toEqual({ kind: "done", refNumber: "REF-123" });
  });
  it("pdf when pdf_url present and not finalized", () => {
    const r = computeInitialRightPaneFrom(mkDoc({ pdf_url: "u" }), mkProc());
    expect(r).toEqual({ kind: "pdf", url: "u" });
  });
  it("review when all required filled but no pdf yet", () => {
    const r = computeInitialRightPaneFrom(
      mkDoc({ fields: { a: "x" } }),
      mkProc(),
    );
    expect(r).toEqual({ kind: "review" });
  });
  it("filling when some filled but not all required", () => {
    const proc = mkProc({
      fields: [
        { name: "a", label: "A", source: "ask", required: true },
        { name: "b", label: "B", source: "ask", required: true },
      ],
    });
    const r = computeInitialRightPaneFrom(mkDoc({ fields: { a: "x" } }), proc);
    expect(r).toEqual({ kind: "filling" });
  });
  it("guide when nothing filled", () => {
    const r = computeInitialRightPaneFrom(mkDoc(), mkProc());
    expect(r).toEqual({ kind: "guide", procedureId: "p1" });
  });
  it("pdf takes precedence over review", () => {
    const r = computeInitialRightPaneFrom(
      mkDoc({ fields: { a: "x" }, pdf_url: "u" }),
      mkProc(),
    );
    expect(r).toEqual({ kind: "pdf", url: "u" });
  });
});
