import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DoneScreen } from "../DoneScreen";
import { useSessionStore } from "@/lib/sessionStore";

beforeEach(() => {
  useSessionStore.setState({ document: null });
});

describe("DoneScreen", () => {
  it("renders the city-method headline", () => {
    render(<DoneScreen method="city" onRestart={() => {}} />);
    expect(
      screen.getByRole("heading", {
        name: /Cererea a fost trimis direct la primărie/i,
      }),
    ).toBeInTheDocument();
  });

  it("renders the email-method headline", () => {
    render(<DoneScreen method="email" onRestart={() => {}} />);
    expect(
      screen.getByRole("heading", { name: /trimis pe email/i }),
    ).toBeInTheDocument();
  });

  it("renders REG-PENDING when document has no ref_number", () => {
    render(<DoneScreen method="city" onRestart={() => {}} />);
    expect(screen.getByText("REG-PENDING")).toBeInTheDocument();
  });

  it("renders the real ref_number from sessionStore when present", () => {
    useSessionStore.setState({
      document: {
        id: "d1",
        procedure_id: "x",
        fields: {},
        ref_number: "REG-2026-08412",
      } as never,
    });
    render(<DoneScreen method="city" onRestart={() => {}} />);
    expect(screen.getByText("REG-2026-08412")).toBeInTheDocument();
    expect(screen.queryByText("REG-PENDING")).toBeNull();
  });

  it("fires onRestart when the restart CTA is clicked", () => {
    const onRestart = vi.fn();
    render(<DoneScreen method="city" onRestart={onRestart} />);
    fireEvent.click(
      screen.getByRole("button", { name: /Începe o nouă conversație/i }),
    );
    expect(onRestart).toHaveBeenCalledTimes(1);
  });
});
