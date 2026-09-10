import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DocumentReview } from "../DocumentReview";
import { useSessionStore } from "@/lib/sessionStore";

beforeEach(() => {
  useSessionStore.setState({
    document: null,
    procedure: null,
  });
});

describe("DocumentReview loading state", () => {
  it("renders the loading fallback when document is null", () => {
    render(<DocumentReview onConfirm={() => {}} onAmend={() => {}} />);
    expect(
      screen.getByRole("heading", { name: /Se încarcă cererea/i }),
    ).toBeInTheDocument();
  });

  it("renders the loading fallback when procedure is null", () => {
    useSessionStore.setState({
      document: { id: "d1", procedure_id: "x", fields: {} } as never,
      procedure: null,
    });
    render(<DocumentReview onConfirm={() => {}} onAmend={() => {}} />);
    expect(
      screen.getByRole("heading", { name: /Se încarcă cererea/i }),
    ).toBeInTheDocument();
  });
});

describe("DocumentReview rendered state", () => {
  beforeEach(() => {
    useSessionStore.setState({
      document: {
        id: "d1",
        procedure_id: "certificat-fiscal",
        fields: {
          nume_complet: "Maria Ionescu",
          cnp: "2851014123456",
          email: "maria@example.com",
          scop: "Credit ipotecar",
          data_cerere: "2026-05-24",
        },
      } as never,
      procedure: {
        id: "certificat-fiscal",
        title: "Certificat fiscal",
        description: "x",
        scope: "primarie",
        category: "fiscalitate-locala",
        synonyms: [],
        sample_queries: [],
        acte_necesare: [],
        template: "x.tex",
        next_steps: [],
        fields: [
          { name: "nume_complet", label: "Nume complet", source: "profile", required: true },
          { name: "cnp", label: "CNP", source: "profile", required: true },
          { name: "email", label: "Email", source: "profile", required: false },
          { name: "scop", label: "Scopul", source: "ask", required: true },
          { name: "data_cerere", label: "Data cererii", source: "ask", required: true },
        ],
      } as never,
    });
  });

  it("renders the procedure title in the doc paper", () => {
    render(<DocumentReview onConfirm={() => {}} onAmend={() => {}} />);
    expect(screen.getByText(/Certificat fiscal/)).toBeInTheDocument();
  });

  it("renders one row per procedure field with the right label + value", () => {
    render(<DocumentReview onConfirm={() => {}} onAmend={() => {}} />);
    expect(screen.getByText("Nume complet")).toBeInTheDocument();
    expect(screen.getByText("Maria Ionescu")).toBeInTheDocument();
    expect(screen.getByText("CNP")).toBeInTheDocument();
    expect(screen.getByText("2851014123456")).toBeInTheDocument();
    expect(screen.getByText("Scopul")).toBeInTheDocument();
    expect(screen.getByText("Credit ipotecar")).toBeInTheDocument();
  });

  it("formats ISO dates as DD.MM.YYYY", () => {
    render(<DocumentReview onConfirm={() => {}} onAmend={() => {}} />);
    expect(screen.getByText("24.05.2026")).toBeInTheDocument();
  });

  it("shows the auto badge on profile-sourced fields with values", () => {
    render(<DocumentReview onConfirm={() => {}} onAmend={() => {}} />);
    const autoBadges = screen.getAllByText("✓ auto");
    // 3 profile-sourced fields with non-empty values: nume_complet, cnp, email
    expect(autoBadges).toHaveLength(3);
  });

  it("does NOT show the auto badge on source='ask' fields", () => {
    render(<DocumentReview onConfirm={() => {}} onAmend={() => {}} />);
    const scopRow = screen.getByText("Scopul").closest(".dfg-row");
    expect(scopRow).not.toBeNull();
    expect(scopRow?.querySelector(".doc-auto")).toBeNull();
  });

  it("renders em dash for fields with no value", () => {
    useSessionStore.setState({
      document: { id: "d1", procedure_id: "certificat-fiscal", fields: {} } as never,
    });
    render(<DocumentReview onConfirm={() => {}} onAmend={() => {}} />);
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });

  it("calls onConfirm when 'Da, e corect' clicked", () => {
    const onConfirm = vi.fn();
    render(<DocumentReview onConfirm={onConfirm} onAmend={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Da, e corect/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("calls onAmend when 'Mai am o corectură' clicked", () => {
    const onAmend = vi.fn();
    render(<DocumentReview onConfirm={() => {}} onAmend={onAmend} />);
    fireEvent.click(screen.getByRole("button", { name: /Mai am o corectură/i }));
    expect(onAmend).toHaveBeenCalledTimes(1);
  });
});
