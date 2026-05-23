import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { useGhiseuStore } from "../ghiseuStore";

beforeEach(() => {
  useGhiseuStore.setState({
    state: "idle",
    muted: true,
    exportMethod: null,
  });
  vi.useFakeTimers();
});

afterEach(() => {
  useGhiseuStore.getState().reset();
  vi.useRealTimers();
});

describe("ghiseuStore initial state", () => {
  it("starts idle, muted, no export method", () => {
    const s = useGhiseuStore.getState();
    expect(s.state).toBe("idle");
    expect(s.muted).toBe(true);
    expect(s.exportMethod).toBeNull();
  });
});

describe("ghiseuStore toggleMute from idle", () => {
  it("unmutes and runs the scripted listening→thinking→speaking→review flow", () => {
    useGhiseuStore.getState().toggleMute();
    expect(useGhiseuStore.getState().muted).toBe(false);
    expect(useGhiseuStore.getState().state).toBe("listening");

    vi.advanceTimersByTime(2800);
    expect(useGhiseuStore.getState().state).toBe("thinking");

    vi.advanceTimersByTime(1500); // +4300 total
    expect(useGhiseuStore.getState().state).toBe("speaking");

    vi.advanceTimersByTime(3100); // +7400 total
    expect(useGhiseuStore.getState().state).toBe("review");
  });
});

describe("ghiseuStore mid-conversation mute", () => {
  it("flips muted without changing state when not in idle", () => {
    useGhiseuStore.setState({ state: "listening", muted: false });
    useGhiseuStore.getState().toggleMute();
    expect(useGhiseuStore.getState().muted).toBe(true);
    expect(useGhiseuStore.getState().state).toBe("listening");
  });
});

describe("ghiseuStore interrupt", () => {
  it("returns to listening and unmutes when called while speaking", () => {
    useGhiseuStore.setState({ state: "speaking", muted: true });
    useGhiseuStore.getState().interrupt();
    expect(useGhiseuStore.getState().state).toBe("listening");
    expect(useGhiseuStore.getState().muted).toBe(false);
  });
});

describe("ghiseuStore confirmDoc + amendDoc", () => {
  it("confirmDoc transitions review → export", () => {
    useGhiseuStore.setState({ state: "review" });
    useGhiseuStore.getState().confirmDoc();
    expect(useGhiseuStore.getState().state).toBe("export");
  });

  it("amendDoc transitions to listening then speaking after 1.8s", () => {
    useGhiseuStore.setState({ state: "review" });
    useGhiseuStore.getState().amendDoc();
    expect(useGhiseuStore.getState().state).toBe("listening");
    vi.advanceTimersByTime(1800);
    expect(useGhiseuStore.getState().state).toBe("speaking");
  });
});

describe("ghiseuStore pickExport", () => {
  it("transitions export → done and stores method", () => {
    useGhiseuStore.setState({ state: "export" });
    useGhiseuStore.getState().pickExport("city");
    expect(useGhiseuStore.getState().state).toBe("done");
    expect(useGhiseuStore.getState().exportMethod).toBe("city");
  });
});

describe("ghiseuStore backToTalk", () => {
  it("returns to listening and unmutes", () => {
    useGhiseuStore.setState({ state: "export", muted: true });
    useGhiseuStore.getState().backToTalk();
    expect(useGhiseuStore.getState().state).toBe("listening");
    expect(useGhiseuStore.getState().muted).toBe(false);
  });
});

describe("ghiseuStore reset", () => {
  it("returns to idle, mutes, clears export method", () => {
    useGhiseuStore.setState({ state: "done", muted: false, exportMethod: "email" });
    useGhiseuStore.getState().reset();
    expect(useGhiseuStore.getState().state).toBe("idle");
    expect(useGhiseuStore.getState().muted).toBe(true);
    expect(useGhiseuStore.getState().exportMethod).toBeNull();
  });
});
