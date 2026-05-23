import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MobileViewToggle } from "../MobileViewToggle";

describe("MobileViewToggle", () => {
  it("renders both segments with the active one aria-pressed", () => {
    render(<MobileViewToggle value="chat" onChange={() => {}} />);
    const chat = screen.getByRole("button", { name: /chat/i });
    const doc = screen.getByRole("button", { name: /document/i });
    expect(chat).toHaveAttribute("aria-pressed", "true");
    expect(doc).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onChange with the other view when the inactive segment is clicked", () => {
    const onChange = vi.fn();
    render(<MobileViewToggle value="chat" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /document/i }));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("doc");
  });

  it("does not call onChange when the active segment is clicked", () => {
    const onChange = vi.fn();
    render(<MobileViewToggle value="chat" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /chat/i }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("adds the is-hinted class on the document segment when hinted", () => {
    render(<MobileViewToggle value="chat" onChange={() => {}} hinted />);
    const doc = screen.getByRole("button", { name: /document/i });
    expect(doc.className).toMatch(/is-hinted/);
  });
});
