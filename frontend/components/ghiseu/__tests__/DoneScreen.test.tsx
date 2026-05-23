import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DoneScreen } from "../DoneScreen";

describe("DoneScreen", () => {
  it("renders the city-method headline", () => {
    render(<DoneScreen method="city" />);
    expect(
      screen.getByRole("heading", {
        name: /Cererea a fost trimis direct la primărie/i,
      }),
    ).toBeInTheDocument();
  });

  it("renders the email-method headline", () => {
    render(<DoneScreen method="email" />);
    expect(
      screen.getByRole("heading", { name: /trimis pe email/i }),
    ).toBeInTheDocument();
  });

  it("renders the registration number", () => {
    render(<DoneScreen method="city" />);
    expect(screen.getByText(/REG-2026-08412/)).toBeInTheDocument();
  });
});
