import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useVoiceAgentBridge } from "../useVoiceAgentBridge";

const sendInterruptSpy = vi.fn();
const closeSpy = vi.fn();

vi.mock("../voiceWs", () => ({
  voiceWsUrl: () => "ws://test",
  VoiceWs: vi.fn().mockImplementation(() => ({
    connect: vi.fn().mockResolvedValue(undefined),
    sendStart: vi.fn(),
    sendInterrupt: sendInterruptSpy,
    close: closeSpy,
    sendText: vi.fn(),
    sendAudio: vi.fn(),
    sendWidgetSubmission: vi.fn(),
  })),
}));

vi.mock("../session", () => ({
  getSession: () => ({ access_token: "test-token" }),
}));

vi.mock("../audioWorklet", () => ({
  prewarmMicPermission: vi.fn().mockResolvedValue(undefined),
  startPlayer: vi.fn().mockResolvedValue({
    feed: vi.fn(),
    flush: vi.fn(),
    stop: vi.fn(),
  }),
  startMicRecorder: vi.fn(),
}));

beforeEach(() => {
  sendInterruptSpy.mockClear();
  closeSpy.mockClear();
});

describe("useVoiceAgentBridge.interrupt", () => {
  it("throws when called before start (WS not open)", () => {
    const { result } = renderHook(() => useVoiceAgentBridge());
    expect(() => result.current.interrupt()).toThrow(/not started/i);
    expect(sendInterruptSpy).not.toHaveBeenCalled();
  });
});
