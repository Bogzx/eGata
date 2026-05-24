import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { CaptionStrip } from "../CaptionStrip";
import { useGhiseuStore } from "@/lib/ghiseuStore";

beforeEach(() => {
  useGhiseuStore.setState({
    state: "idle",
    muted: true,
    exportMethod: null,
    caption: { user: null, agent: null },
    _bridge: null,
  });
});

describe("CaptionStrip fallback (no live caption)", () => {
  it("renders the agent greeting in idle", () => {
    render(<CaptionStrip state="idle" />);
    expect(
      screen.getByText(/Bună! Spune-mi cu ce te pot ajuta/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Tu$/)).toBeNull();
  });

  it("renders nothing in error", () => {
    const { container } = render(<CaptionStrip state="error" />);
    expect(container.firstChild).toBeNull();
  });
});

describe("CaptionStrip live caption (from store)", () => {
  it("renders the live user partial with the partial wrapper", () => {
    useGhiseuStore.setState({
      caption: {
        user: { text: "vreau o adeverin", live: true },
        agent: null,
      },
    });
    render(<CaptionStrip state="listening" />);
    expect(screen.getByText(/^Tu$/)).toBeInTheDocument();
    const userText = screen.getByText(/vreau o adeverin/);
    expect(userText.tagName).toBe("SPAN");
    expect(userText.className).toContain("partial");
  });

  it("renders both Tu and eGata bubbles when both captions present", () => {
    useGhiseuStore.setState({
      caption: {
        user: { text: "vreau o adeverință", live: false },
        agent: { text: "te ajut imediat", live: true },
      },
    });
    render(<CaptionStrip state="speaking" />);
    expect(screen.getByText(/vreau o adeverință/)).toBeInTheDocument();
    expect(screen.getByText(/te ajut imediat/)).toBeInTheDocument();
  });

  it("live caption overrides fallback when set", () => {
    useGhiseuStore.setState({
      caption: {
        user: null,
        agent: { text: "salut concret", live: false },
      },
    });
    render(<CaptionStrip state="idle" />);
    expect(screen.getByText(/salut concret/)).toBeInTheDocument();
    expect(screen.queryByText(/Bună! Spune-mi/i)).toBeNull();
  });
});
