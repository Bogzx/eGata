import { describe, it, expect, beforeEach, vi } from "vitest";
import { useGhiseuStore } from "../ghiseuStore";
import { createMockVoiceAgentHook } from "./__helpers__/mockVoiceAgentHook";

beforeEach(() => {
  useGhiseuStore.setState({
    state: "idle",
    muted: true,
    exportMethod: null,
    caption: { user: null, agent: null },
    _bridge: null,
  });
});

describe("ghiseuStore.attachVoiceBridge", () => {
  it("stores the bridge reference and returns a cleanup that stops + nulls", () => {
    const mock = createMockVoiceAgentHook();
    const cleanup = useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    expect(useGhiseuStore.getState()._bridge).toBe(mock.hook);

    cleanup();
    expect(mock.hook.stop).toHaveBeenCalledTimes(1);
    expect(useGhiseuStore.getState()._bridge).toBeNull();
  });
});

describe("ghiseuStore.enterVoiceMode", () => {
  it("throws when no bridge attached", async () => {
    await expect(useGhiseuStore.getState().enterVoiceMode()).rejects.toThrow(
      /attachVoiceBridge/,
    );
  });

  it("calls bridge.start with the four event callbacks and bridge.enableMic", async () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);

    await useGhiseuStore.getState().enterVoiceMode();

    expect(mock.hook.start).toHaveBeenCalledTimes(1);
    expect(mock.hook.enableMic).toHaveBeenCalledTimes(1);
    expect(mock.capturedOpts).not.toBeNull();
    expect(mock.capturedOpts?.onUserDelta).toBeTypeOf("function");
    expect(mock.capturedOpts?.onUserMessage).toBeTypeOf("function");
    expect(mock.capturedOpts?.onAgentDelta).toBeTypeOf("function");
    expect(mock.capturedOpts?.onAgentMessage).toBeTypeOf("function");
    expect(useGhiseuStore.getState().state).toBe("listening");
    expect(useGhiseuStore.getState().muted).toBe(false);
  });

  it("calls bridge.stop first if bridge.wsReady was true (evicts leftover session)", async () => {
    const mock = createMockVoiceAgentHook();
    mock.setWsReady(true);
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);

    await useGhiseuStore.getState().enterVoiceMode();

    expect(mock.hook.stop).toHaveBeenCalled();
    const stopOrder = (mock.hook.stop as ReturnType<typeof vi.fn>).mock.invocationCallOrder[0];
    const startOrder = (mock.hook.start as ReturnType<typeof vi.fn>).mock.invocationCallOrder[0];
    expect(stopOrder).toBeLessThan(startOrder ?? Infinity);
  });

  it("transitions to mic-denied when enableMic throws VoiceAgentMicDeniedError", async () => {
    const mock = createMockVoiceAgentHook();
    const err = new Error("denied");
    err.name = "VoiceAgentMicDeniedError";
    (mock.hook.enableMic as ReturnType<typeof vi.fn>).mockRejectedValueOnce(err);
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);

    await expect(useGhiseuStore.getState().enterVoiceMode()).rejects.toThrow();
    expect(useGhiseuStore.getState().state).toBe("mic-denied");
  });

  it("transitions to error when start rejects", async () => {
    const mock = createMockVoiceAgentHook();
    (mock.hook.start as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("ws boom"),
    );
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);

    await expect(useGhiseuStore.getState().enterVoiceMode()).rejects.toThrow(/ws boom/);
    expect(useGhiseuStore.getState().state).toBe("error");
  });
});

describe("ghiseuStore captured callbacks update store state", () => {
  it("onUserDelta updates caption.user.text", async () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    await useGhiseuStore.getState().enterVoiceMode();

    mock.capturedOpts?.onUserDelta?.("partial user text");
    expect(useGhiseuStore.getState().caption.user).toEqual({
      text: "partial user text",
      live: true,
    });
  });

  it("onAgentDelta updates caption.agent and flips state to speaking", async () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    await useGhiseuStore.getState().enterVoiceMode();

    mock.capturedOpts?.onAgentDelta?.("agent reply");
    expect(useGhiseuStore.getState().caption.agent).toEqual({
      text: "agent reply",
      live: true,
    });
    expect(useGhiseuStore.getState().state).toBe("speaking");
  });
});

describe("ghiseuStore.interrupt", () => {
  it("calls bridge.interrupt and sets state to listening", () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    useGhiseuStore.setState({ state: "speaking" });

    useGhiseuStore.getState().interrupt();

    expect(mock.hook.interrupt).toHaveBeenCalledTimes(1);
    expect(useGhiseuStore.getState().state).toBe("listening");
  });

  it("is a no-op on the bridge when nothing is attached", () => {
    useGhiseuStore.setState({ state: "speaking" });
    expect(() => useGhiseuStore.getState().interrupt()).not.toThrow();
    expect(useGhiseuStore.getState().state).toBe("listening");
  });
});

describe("ghiseuStore.reset stops the bridge", () => {
  it("reset() calls bridge.stop via exitVoiceMode", async () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    await useGhiseuStore.getState().enterVoiceMode();

    useGhiseuStore.getState().reset();
    expect(mock.hook.stop).toHaveBeenCalledTimes(1);
    expect(useGhiseuStore.getState().state).toBe("idle");
    expect(useGhiseuStore.getState().caption).toEqual({ user: null, agent: null });
  });
});

describe("ghiseuStore.toggleMute", () => {
  it("calls enableMic when ghiseuStore.muted is true (mic is off)", async () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    await useGhiseuStore.getState().enterVoiceMode();
    (mock.hook.enableMic as ReturnType<typeof vi.fn>).mockClear();

    // Simulate the GhiseuShell mirror: voice.micOn=false → store.muted=true
    useGhiseuStore.setState({ state: "listening", muted: true });
    useGhiseuStore.getState().toggleMute();

    expect(mock.hook.enableMic).toHaveBeenCalledTimes(1);
  });

  it("calls disableMic when ghiseuStore.muted is false (mic is on)", async () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    await useGhiseuStore.getState().enterVoiceMode();

    // After enterVoiceMode, muted=false (the success path sets it).
    useGhiseuStore.setState({ state: "listening" });
    useGhiseuStore.getState().toggleMute();

    expect(mock.hook.disableMic).toHaveBeenCalledTimes(1);
  });

  it("from idle, calls enterVoiceMode (which calls start + enableMic)", () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    useGhiseuStore.setState({ state: "idle" });

    useGhiseuStore.getState().toggleMute();

    expect(mock.hook.start).toHaveBeenCalled();
  });
});
