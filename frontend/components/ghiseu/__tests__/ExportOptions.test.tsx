import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ExportOptions } from "../ExportOptions";

describe("ExportOptions", () => {
  it("renders the header and both cards", () => {
    render(<ExportOptions onPick={() => {}} />);
    expect(
      screen.getByRole("heading", { name: /Cum trimitem actul\?/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Trimite la primărie/i)).toBeInTheDocument();
    expect(screen.getByText(/Trimite pe email/i)).toBeInTheDocument();
  });

  it("marks the primărie card as recommended", () => {
    const { container } = render(<ExportOptions onPick={() => {}} />);
    expect(
      container.querySelector('[data-recommended="true"]'),
    ).toBeTruthy();
  });

  it("fires onPick('city') when 'Trimite la primărie' is clicked", () => {
    const onPick = vi.fn();
    render(<ExportOptions onPick={onPick} />);
    fireEvent.click(screen.getByText(/Trimite la primărie/i).closest("button")!);
    expect(onPick).toHaveBeenCalledWith("city");
  });

  it("fires onPick('email') when 'Trimite pe email' is clicked", () => {
    const onPick = vi.fn();
    render(<ExportOptions onPick={onPick} />);
    fireEvent.click(screen.getByText(/Trimite pe email/i).closest("button")!);
    expect(onPick).toHaveBeenCalledWith("email");
  });
});
