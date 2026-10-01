import { afterEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { useSessionStore } from "@/lib/sessionStore";
import type { Document } from "@/lib/types";
import { DonePane } from "../DonePane";

function finalized(delivery: Document["delivery"]): Document {
  return {
    id: "11111111-2222-3333-4444-555555555555",
    citizen_id: "c1",
    procedure_id: "schimbare-domiciliu",
    status: "finalized",
    fields: {},
    created_at: "2026-10-01T10:00:00Z",
    delivered_at: "2026-10-01T10:05:00Z",
    pdf_url: "https://example.test/files/pdf/x?sig=1",
    delivery,
    ref_number: "CV-1111-2222",
  } as Document;
}

// The pane must never claim what eGata does not do: file the request with the
// primărie, e-mail it, print it, or book an appointment.
const FALSE_CLAIMS =
  /trimis[ăa]? la primări|ajuns la primări|inbox|pe email|trimis la imprimant|programare confirmat|programare pentru ridicare/i;

afterEach(() => {
  useSessionStore.setState({ document: null, smsStatus: null });
});

describe("DonePane", () => {
  it.each(["save", "send", "print", "download"] as const)(
    "delivery=%s: states the reference and the next step, claims nothing false",
    (delivery) => {
      useSessionStore.setState({ document: finalized(delivery), smsStatus: "not_configured" });
      const { container } = render(<DonePane />);
      expect(container.textContent).not.toMatch(FALSE_CLAIMS);
      expect(screen.getByText("CV-1111-2222")).toBeInTheDocument();
      expect(screen.getByText(/eGata nu depune cererea pentru tine/)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Descarcă PDF/ })).toHaveAttribute(
        "href",
        "https://example.test/files/pdf/x?sig=1",
      );
    },
  );

  it("says an SMS left only when the backend reported one", () => {
    useSessionStore.setState({ document: finalized("send"), smsStatus: "sent" });
    const { unmount } = render(<DonePane />);
    expect(screen.getByText("Ți-am trimis referința pe SMS.")).toBeInTheDocument();
    unmount();

    useSessionStore.setState({ document: finalized("send"), smsStatus: "not_configured" });
    render(<DonePane />);
    expect(screen.queryByText("Ți-am trimis referința pe SMS.")).toBeNull();
    expect(screen.getByText(/nu e configurat pe acest server/)).toBeInTheDocument();
  });

  it("tells a rejected SMS apart from a server without SMS", () => {
    useSessionStore.setState({ document: finalized("send"), smsStatus: "failed" });
    render(<DonePane />);
    expect(screen.getByText(/SMS-ul nu a putut fi trimis/)).toBeInTheDocument();
    expect(screen.queryByText(/nu e configurat/)).toBeNull();
    expect(screen.queryByText("Ți-am trimis referința pe SMS.")).toBeNull();
  });

  it("does not guess after a reload, when the SMS outcome is unknown", () => {
    useSessionStore.setState({ document: finalized("send"), smsStatus: null });
    render(<DonePane />);
    expect(screen.queryByText("Ți-am trimis referința pe SMS.")).toBeNull();
    expect(screen.getByText("Ai cerut confirmarea pe SMS.")).toBeInTheDocument();
  });
});
