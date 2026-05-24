import { vi } from "vitest";
import type {
  VoiceAgentHook,
  VoiceAgentState,
  VoiceAgentStartOpts,
} from "../../useVoiceAgentBridge";

export type MockVoiceAgentHandle = {
  hook: VoiceAgentHook;
  capturedOpts: VoiceAgentStartOpts | null;
  setState(state: VoiceAgentState): void;
  setMicOn(on: boolean): void;
  setWsReady(ready: boolean): void;
};

export function createMockVoiceAgentHook(): MockVoiceAgentHandle {
  const handle: MockVoiceAgentHandle = {
    capturedOpts: null,
    setState(state) {
      (handle.hook as { state: VoiceAgentState }).state = state;
    },
    setMicOn(on) {
      (handle.hook as { micOn: boolean }).micOn = on;
    },
    setWsReady(ready) {
      (handle.hook as { wsReady: boolean }).wsReady = ready;
    },
    hook: {
      state: "idle",
      wsReady: false,
      micOn: false,
      start: vi.fn(async (opts: VoiceAgentStartOpts) => {
        handle.capturedOpts = opts;
        handle.setWsReady(true);
        handle.setState("listening");
      }),
      stop: vi.fn(() => {
        handle.setWsReady(false);
        handle.setMicOn(false);
        handle.setState("idle");
        handle.capturedOpts = null;
      }),
      enableMic: vi.fn(async () => {
        handle.setMicOn(true);
      }),
      disableMic: vi.fn(() => {
        handle.setMicOn(false);
      }),
      interrupt: vi.fn(),
      sendText: vi.fn().mockResolvedValue(undefined),
      submitWidget: vi.fn().mockResolvedValue(undefined),
      registerToolHandler: vi.fn(),
    },
  };
  return handle;
}
