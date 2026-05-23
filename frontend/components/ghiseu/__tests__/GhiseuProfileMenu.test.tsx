import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GhiseuProfileMenu } from "../GhiseuProfileMenu";
import { useAccessibilityPrefs } from "@/lib/accessibilityStore";

beforeEach(() => {
  localStorage.clear();
  useAccessibilityPrefs.setState({
    voiceOnly: false,
    simpleLanguage: false,
    largeText: false,
    highContrast: false,
    dyslexic: false,
    hydrated: true,
  });
});

describe("GhiseuProfileMenu", () => {
  it("opens the dropdown when the chip is clicked", () => {
    render(<GhiseuProfileMenu />);
    expect(screen.queryByText(/Mod contrast ridicat/i)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Accesibilitate/i }));
    expect(screen.getByText(/Mod contrast ridicat/i)).toBeInTheDocument();
  });

  it("toggles the highContrast preference in the shared store", () => {
    render(<GhiseuProfileMenu />);
    fireEvent.click(screen.getByRole("button", { name: /Accesibilitate/i }));
    const toggle = screen.getByRole("switch", { name: /Mod contrast ridicat/i });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(useAccessibilityPrefs.getState().highContrast).toBe(true);
  });

  it("reflects an externally set preference (large text)", () => {
    useAccessibilityPrefs.setState({ largeText: true });
    render(<GhiseuProfileMenu />);
    fireEvent.click(screen.getByRole("button", { name: /Accesibilitate/i }));
    expect(
      screen.getByRole("switch", { name: /Mod text mare/i }),
    ).toHaveAttribute("aria-checked", "true");
  });
});
