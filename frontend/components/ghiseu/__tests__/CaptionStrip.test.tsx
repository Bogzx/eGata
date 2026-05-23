import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CaptionStrip } from "../CaptionStrip";

describe("CaptionStrip", () => {
  it("renders nothing in idle and shows only the agent greeting", () => {
    render(<CaptionStrip state="idle" />);
    expect(screen.getByText(/Bună! Spune-mi cu ce te pot ajuta/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Tu$/)).toBeNull();
  });

  it("renders both Tu and eGata bubbles in speaking", () => {
    render(<CaptionStrip state="speaking" />);
    expect(screen.getByText(/Tu/)).toBeInTheDocument();
    expect(screen.getByText(/eGata/)).toBeInTheDocument();
    expect(screen.getByText(/Vreau o.*pentru bancă/)).toBeInTheDocument();
    expect(screen.getByText(/Am completat datele tale din ROeID/i)).toBeInTheDocument();
  });

  it("renders nothing when state is error", () => {
    const { container } = render(<CaptionStrip state="error" />);
    expect(container.firstChild).toBeNull();
  });
});
