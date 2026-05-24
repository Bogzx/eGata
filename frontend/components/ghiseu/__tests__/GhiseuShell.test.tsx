import { describe, it, expect, beforeEach, vi } from "vitest";
import { render } from "@testing-library/react";
import { GhiseuShell } from "../GhiseuShell";
import { useGhiseuStore } from "@/lib/ghiseuStore";
import { useSessionStore } from "@/lib/sessionStore";
import {
  createMockVoiceAgentHook,
  type MockVoiceAgentHandle,
} from "@/lib/__tests__/__helpers__/mockVoiceAgentHook";

let currentMock: MockVoiceAgentHandle;

vi.mock("@/lib/voiceContext", () => ({
  useVoiceContext: () => currentMock.hook,
}));

vi.mock("@/lib/accessibilityStore", () => ({
  useAccessibilityClasses: () => {},
  useAccessibilityPrefs: () => ({}),
}));

beforeEach(() => {
  currentMock = createMockVoiceAgentHook();
  useGhiseuStore.setState({
    state: "idle",
    muted: true,
    exportMethod: null,
    caption: { user: null, agent: null },
    _bridge: null,
  });
  // Override hydrateCitizen with a noop so tests don't hit the network.
  useSessionStore.setState({
    kioskMode: false,
    citizen: {
      id: "c1",
      phone: "+40700000000",
      name: "Test User",
      roeid_attributes: {},
    } as never,
    hydrateCitizen: vi.fn().mockResolvedValue(undefined) as never,
  });
});

describe("GhiseuShell lifecycle", () => {
  it("attaches the voice bridge on mount", () => {
    render(<GhiseuShell />);
    expect(useGhiseuStore.getState()._bridge).toBe(currentMock.hook);
  });

  it("sets kioskMode=true on mount and clears it on unmount", () => {
    const { unmount } = render(<GhiseuShell />);
    expect(useSessionStore.getState().kioskMode).toBe(true);
    unmount();
    expect(useSessionStore.getState().kioskMode).toBe(false);
  });

  it("on unmount, stops the bridge via attach-cleanup", () => {
    const { unmount } = render(<GhiseuShell />);
    unmount();
    expect(currentMock.hook.stop).toHaveBeenCalled();
    expect(useGhiseuStore.getState()._bridge).toBeNull();
  });

  it("auto-calls enterVoiceMode when a citizen is hydrated", async () => {
    render(<GhiseuShell />);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(currentMock.hook.start).toHaveBeenCalledTimes(1);
    expect(currentMock.hook.enableMic).toHaveBeenCalledTimes(1);
  });

  it("does NOT call enterVoiceMode when citizen is null", async () => {
    useSessionStore.setState({ citizen: null });
    render(<GhiseuShell />);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(currentMock.hook.start).not.toHaveBeenCalled();
  });

  it("calls hydrateCitizen when citizen is null on mount", async () => {
    const hydrateSpy = vi.fn().mockResolvedValue(undefined);
    useSessionStore.setState({
      citizen: null,
      hydrateCitizen: hydrateSpy as never,
    });
    render(<GhiseuShell />);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(hydrateSpy).toHaveBeenCalledTimes(1);
  });

  it("does NOT call hydrateCitizen when citizen is already hydrated", async () => {
    const hydrateSpy = vi.fn().mockResolvedValue(undefined);
    useSessionStore.setState({
      hydrateCitizen: hydrateSpy as never,
    });
    render(<GhiseuShell />);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(hydrateSpy).not.toHaveBeenCalled();
  });
});
