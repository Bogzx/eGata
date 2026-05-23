import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ControlsDock } from "../ControlsDock";

const noop = () => {};

describe("ControlsDock — idle / talk states", () => {
  it("shows 'Pornește microfonul' when muted", () => {
    render(
      <ControlsDock
        state="idle"
        muted={true}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Pornește microfonul/i }),
    ).toBeInTheDocument();
  });

  it("shows 'Oprește microfonul' when unmuted", () => {
    render(
      <ControlsDock
        state="listening"
        muted={false}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Oprește microfonul/i }),
    ).toBeInTheDocument();
  });

  it("calls onToggleMute when mic is clicked", () => {
    const onToggleMute = vi.fn();
    render(
      <ControlsDock
        state="idle"
        muted={true}
        onToggleMute={onToggleMute}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Pornește microfonul/i }));
    expect(onToggleMute).toHaveBeenCalledTimes(1);
  });

  it("disables Întrerupe outside of speaking", () => {
    render(
      <ControlsDock
        state="listening"
        muted={false}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(screen.getByRole("button", { name: /Întrerupe/i })).toBeDisabled();
  });

  it("enables Întrerupe in speaking and fires onInterrupt", () => {
    const onInterrupt = vi.fn();
    render(
      <ControlsDock
        state="speaking"
        muted={false}
        onToggleMute={noop}
        onInterrupt={onInterrupt}
        onBackToTalk={noop}
      />,
    );
    const btn = screen.getByRole("button", { name: /Întrerupe/i });
    expect(btn).not.toBeDisabled();
    fireEvent.click(btn);
    expect(onInterrupt).toHaveBeenCalledTimes(1);
  });

  it("emits ripple data attribute only when listening + unmuted", () => {
    const { rerender, container } = render(
      <ControlsDock
        state="listening"
        muted={false}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(container.querySelector('[data-emit="true"]')).toBeTruthy();
    rerender(
      <ControlsDock
        state="listening"
        muted={true}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(container.querySelector('[data-emit="true"]')).toBeNull();
  });
});

describe("ControlsDock — review / export ghost button", () => {
  it("renders 'Vorbește din nou' in review and fires onBackToTalk", () => {
    const onBackToTalk = vi.fn();
    render(
      <ControlsDock
        state="review"
        muted={false}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={onBackToTalk}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Vorbește din nou/i }));
    expect(onBackToTalk).toHaveBeenCalledTimes(1);
  });

  it("renders 'Întreabă altceva' in export", () => {
    render(
      <ControlsDock
        state="export"
        muted={false}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Întreabă altceva/i }),
    ).toBeInTheDocument();
  });

  it("renders nothing in done / error / mic-denied", () => {
    const { container, rerender } = render(
      <ControlsDock
        state="done"
        muted={false}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(container.firstChild).toBeNull();
    rerender(
      <ControlsDock
        state="error"
        muted={false}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});
