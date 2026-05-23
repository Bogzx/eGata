import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { VoiceStage } from "../VoiceStage";

describe("VoiceStage", () => {
  it("renders the idle title from the design copy", () => {
    render(<VoiceStage state="idle" />);
    expect(
      screen.getByRole("heading", {
        name: /Bună\. Apasă microfonul pentru ajutor\./i,
      }),
    ).toBeInTheDocument();
  });

  it("renders the listening title", () => {
    render(<VoiceStage state="listening" />);
    expect(screen.getByRole("heading", { name: /Te ascult/i })).toBeInTheDocument();
  });

  it("renders the error title and hint without a caption strip", () => {
    render(<VoiceStage state="error" />);
    expect(
      screen.getByRole("heading", { name: /S-a pierdut conexiunea/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Verificăm legătura/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Tu$/)).toBeNull();
  });

  it("renders the mic-denied title with a slash icon container", () => {
    const { container } = render(<VoiceStage state="mic-denied" />);
    expect(
      screen.getByRole("heading", { name: /Microfonul este blocat/i }),
    ).toBeInTheDocument();
    expect(container.querySelector(".gh-error-icon")).toBeTruthy();
  });
});
