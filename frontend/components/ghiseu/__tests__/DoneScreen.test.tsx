import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { DoneScreen } from "../DoneScreen";

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

  it("renders the registration number", () => {
    render(<DoneScreen method="city" onRestart={() => {}} />);
    expect(screen.getByText(/REG-2026-08412/)).toBeInTheDocument();
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
