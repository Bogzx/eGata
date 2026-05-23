"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getSession } from "./session";
import { useSessionStore } from "./sessionStore";
import {
  startMicRecorder,
  startPlayer,
  type PlayerHandle,
  type RecorderHandle,
} from "./audioWorklet";
import type { VoicePreferences } from "./types";
import { VoiceWs, type VoiceWsToolCall, voiceWsUrl } from "./voiceWs";

const LOG = (...args: unknown[]) =>
  console.log("[civicai:voice-bridge]", ...args);
const ERR = (...args: unknown[]) =>
  console.error("[civicai:voice-bridge]", ...args);

// ---- Voice hook surface (was previously in useVoiceAgent.ts; now lives
// here since the bridge is the only voice path).

export type VoiceAgentState =
  | "idle"
  | "connecting"
  | "listening"
  | "speaking"
  | "error";

export type ToolCallHandler = (
  name: string,
  args: Record<string, unknown>,
) => Promise<Record<string, unknown>>;

export type VoiceAgentToolCall = {
  name: string;
  args: Record<string, unknown>;
};

export type VoiceAgentStartOpts = {
  documentId?: string;
  preferences?: VoicePreferences;
  onUserDelta?: (text: string) => void;
  onAgentDelta?: (text: string) => void;
  onUserMessage?: (text: string) => void;
  onAgentMessage?: (text: string, toolCalls: VoiceAgentToolCall[]) => void;
};

export type VoiceAgentHook = {
  state: VoiceAgentState;
  /** WS is open and Gemini Live is connected. True for state in
   * `listening` / `speaking`, false during `connecting` and after `stop`. */
  wsReady: boolean;
  /** Microphone is currently recording. Orthogonal to wsReady — you can
   * have wsReady=true with micOn=false (text-only mode using the same
   * Live session). */
  micOn: boolean;
  /** Open the WS + audio player. Does NOT start the microphone — call
   * `enableMic()` if you want voice input. Used by text-only sessions
   * that want to share the Live session with potential later voice. */
  start: (opts: VoiceAgentStartOpts) => Promise<void>;
  stop: () => void;
  /** Start microphone capture. WS must be open (call `start()` first).
   * Throws `VoiceAgentMicDeniedError` on permission deny. */
  enableMic: () => Promise<void>;
  /** Stop microphone capture but keep WS open. */
  disableMic: () => void;
  sendText: (text: string) => Promise<void>;
  /** Submit a widget answer through the active WS bridge. Throws if the
   * bridge isn't started — callers should check `wsReady` first or fall
   * back to the HTTP `/widget-result` endpoint via `sessionStore.submitWidget`. */
  submitWidget: (widgetId: string, value: unknown) => Promise<void>;
  registerToolHandler: (handler: ToolCallHandler) => void;
};

export class VoiceAgentMicDeniedError extends Error {
  constructor() {
    super("Microphone permission denied — fall back to text chat.");
    this.name = "VoiceAgentMicDeniedError";
  }
}

/**
 * The voice hook. Talks to the backend /agent/voice/ws bridge,
 * pipes mic chunks up, agent audio down, transcripts straight to the
 * sessionStore's live-message lifecycle, and snapshot frames straight to
 * sessionStore.session.
 */
type ReadyDeferred = {
  promise: Promise<void>;
  resolve: () => void;
  reject: (e: Error) => void;
};

function makeReadyDeferred(): ReadyDeferred {
  let resolve!: () => void;
  let reject!: (e: Error) => void;
  const promise = new Promise<void>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

export function useVoiceAgentBridge(): VoiceAgentHook {
  const [state, setState] = useState<VoiceAgentState>("idle");
  const [wsReady, setWsReady] = useState(false);
  const [micOn, setMicOn] = useState(false);

  const wsRef = useRef<VoiceWs | null>(null);
  const recorderRef = useRef<RecorderHandle | null>(null);
  const playerRef = useRef<PlayerHandle | null>(null);
  const userToolHandlerRef = useRef<ToolCallHandler | null>(null);
  const liveUserIdRef = useRef<string | null>(null);
  const liveAgentIdRef = useRef<string | null>(null);
  const stateRef = useRef<VoiceAgentState>("idle");
  // Resolves when the backend sends the `ready` frame (Live connected
  // + tools registered). start() awaits this so that callers can sendText
  // / sendAudio / submitWidget immediately after start() resolves without
  // racing the Live handshake.
  const readyDeferredRef = useRef<ReadyDeferred | null>(null);

  // Keep stateRef in sync so async callbacks see the latest value
  // without forcing re-renders / stale closures.
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const registerToolHandler = useCallback((handler: ToolCallHandler) => {
    userToolHandlerRef.current = handler;
  }, []);

  const stop = useCallback(() => {
    LOG("stop()");
    wsRef.current?.close();
    recorderRef.current?.stop();
    playerRef.current?.stop();
    wsRef.current = null;
    recorderRef.current = null;
    playerRef.current = null;
    liveUserIdRef.current = null;
    liveAgentIdRef.current = null;
    setState("idle");
    setWsReady(false);
    setMicOn(false);
    readyDeferredRef.current?.reject(new Error("Bridge stopped"));
    readyDeferredRef.current = null;
  }, []);

  const start: VoiceAgentHook["start"] = useCallback(
    async (opts: VoiceAgentStartOpts) => {
      try {
        LOG("start", opts);
        setState("connecting");

        const sess = getSession();
        if (!sess) {
          throw new Error("Nu există sesiune autentificată.");
        }

        const player = await startPlayer();
        playerRef.current = player;

        const store = useSessionStore.getState;

        const finalizeLiveUser = (text: string) => {
          const id = liveUserIdRef.current;
          if (id) store().finalizeLiveMessage(id, text);
          liveUserIdRef.current = null;
        };

        const finalizeLiveAgent = (text: string) => {
          const id = liveAgentIdRef.current;
          if (id) store().finalizeLiveMessage(id, text);
          liveAgentIdRef.current = null;
        };

        const ws = new VoiceWs({
          onReady: (convId) => {
            LOG("ready", convId);
            // If the bridge picked up a stored conv_id, this is a no-op.
            // If the backend minted a fresh one, capture it so subsequent
            // text turns and voice reconnects target the same conversation.
            if (convId && useSessionStore.getState().conversationId !== convId) {
              useSessionStore.setState({ conversationId: convId });
            }
            setState("listening");
            setWsReady(true);
            readyDeferredRef.current?.resolve();
            readyDeferredRef.current = null;
          },
          onUserDelta: (text) => {
            if (liveAgentIdRef.current) {
              // The agent was talking; finalize whatever it just said
              // so we don't leave a ghost live-bubble open.
              finalizeLiveAgent(text);
            }
            if (!liveUserIdRef.current) {
              liveUserIdRef.current = store().beginLiveMessage("user");
            }
            store().updateLiveMessage(liveUserIdRef.current, text);
            opts.onUserDelta?.(text);
          },
          onUserDone: (text) => {
            finalizeLiveUser(text);
            opts.onUserMessage?.(text);
          },
          onAgentDelta: (text) => {
            if (liveUserIdRef.current) {
              finalizeLiveUser(liveUserIdRef.current ? "" : "");
            }
            if (!liveAgentIdRef.current) {
              liveAgentIdRef.current = store().beginLiveMessage("agent");
              setState("speaking");
            }
            store().updateLiveMessage(liveAgentIdRef.current, text);
            opts.onAgentDelta?.(text);
          },
          onAgentDone: (text, toolCalls) => {
            finalizeLiveAgent(text);
            setState("listening");
            opts.onAgentMessage?.(
              text,
              toolCalls.map((c) => ({ name: c.name, args: c.arguments })),
            );
          },
          onToolCall: (name, args) => {
            LOG("tool_call", name, args);
            // Backend executes; the browser side-effect handler runs
            // when the result arrives.
            void Promise.resolve();
            // Forward the call event to the UI handler so it can show
            // intermediate state if it wants to.
            void userToolHandlerRef.current?.(name, args).catch(() => undefined);
          },
          onToolResult: (name, output) => {
            LOG("tool_result", name, output);
            // The store's applyToolResult-like handler reacts to
            // tool effects (right pane updates, doc refresh, etc.).
            void userToolHandlerRef.current?.(name, {
              _result: output,
            }).catch(() => undefined);
          },
          onSessionSnapshot: (snapshot) => {
            store().setSession(snapshot);
          },
          onFrontendEvent: (event) => {
            void store().handleFrontendEvent(event);
          },
          onAudio: (pcm) => {
            // Mic-gated playback: drop audio when the user hasn't engaged
            // the microphone (text-only sessions still receive audio from
            // Live but we don't play it — per UX choice). recorderRef is
            // our authoritative micOn flag (synchronous, unlike state).
            if (!recorderRef.current) return;
            playerRef.current?.feed(pcm);
          },
          onInterrupted: () => {
            LOG("interrupted");
            playerRef.current?.flush();
            setState("listening");
          },
          onError: (detail) => {
            ERR("bridge error:", detail);
            setState("error");
            readyDeferredRef.current?.reject(new Error(detail));
            readyDeferredRef.current = null;
          },
          onClose: () => {
            LOG("ws closed");
            if (stateRef.current !== "error") setState("idle");
            setWsReady(false);
            setMicOn(false);
            readyDeferredRef.current?.reject(
              new Error("WS closed before ready frame arrived"),
            );
            readyDeferredRef.current = null;
          },
        });
        wsRef.current = ws;

        await ws.connect(voiceWsUrl());

        // Arm the ready-deferred BEFORE sendStart so any auth-fail close
        // frame the backend sends back is observed via the WS handlers
        // and translated into a rejected promise here.
        readyDeferredRef.current = makeReadyDeferred();

        // Reuse the existing conversation_id from the store so a voice
        // reconnect picks up the text-chat history instead of getting a
        // fresh `conv_*` minted server-side and an amnesic agent.
        const existingConvId = useSessionStore.getState().conversationId;
        ws.sendStart({
          token: sess.access_token,
          documentId: opts.documentId,
          conversationId: existingConvId ?? undefined,
          preferences: {
            simpleLanguage: opts.preferences?.simple_language,
            voiceOnly: opts.preferences?.voice_only,
          },
        });

        // Block until the backend confirms Live is up. Callers can then
        // immediately sendText / submitWidget without a Live handshake race.
        await readyDeferredRef.current.promise;

        LOG("Live ready — call enableMic() to add voice input");
      } catch (err) {
        ERR("start failed", err);
        if (!(err instanceof VoiceAgentMicDeniedError)) stop();
        setState("error");
        throw err;
      }
    },
    [stop],
  );

  const enableMic: VoiceAgentHook["enableMic"] = useCallback(async () => {
    if (!wsRef.current) {
      throw new Error("WS not open; call start() first.");
    }
    if (recorderRef.current) return; // already on
    try {
      const ws = wsRef.current;
      const recorder = await startMicRecorder((chunk) => ws.sendAudio(chunk));
      recorderRef.current = recorder;
      setMicOn(true);
      LOG("mic enabled");
    } catch (micErr) {
      ERR("mic denied", micErr);
      throw new VoiceAgentMicDeniedError();
    }
  }, []);

  const disableMic: VoiceAgentHook["disableMic"] = useCallback(() => {
    if (!recorderRef.current) return;
    recorderRef.current.stop();
    recorderRef.current = null;
    // Flush any buffered agent audio so the speech doesn't keep playing
    // for a second after the user has muted the mic.
    playerRef.current?.flush();
    setMicOn(false);
    LOG("mic disabled");
  }, []);

  const sendText: VoiceAgentHook["sendText"] = useCallback(async (text) => {
    if (!wsRef.current) {
      throw new Error("Voice bridge not started; call start() first.");
    }
    wsRef.current.sendText(text);
  }, []);

  const submitWidget: VoiceAgentHook["submitWidget"] = useCallback(
    async (widgetId, value) => {
      if (!wsRef.current) {
        throw new Error("Voice bridge not started; call start() first.");
      }
      wsRef.current.sendWidgetSubmission(widgetId, value);
    },
    [],
  );

  useEffect(() => {
    return () => stop();
  }, [stop]);

  return {
    state,
    wsReady,
    micOn,
    start,
    stop,
    enableMic,
    disableMic,
    sendText,
    submitWidget,
    registerToolHandler,
  };
}
