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
import { VoiceWs, voiceWsUrl } from "./voiceWs";
import {
  VoiceAgentMicDeniedError,
  type ToolCallHandler,
  type VoiceAgentHook,
  type VoiceAgentStartOpts,
  type VoiceAgentState,
} from "./useVoiceAgent";

const LOG = (...args: unknown[]) =>
  console.log("[civicai:voice-bridge]", ...args);
const ERR = (...args: unknown[]) =>
  console.error("[civicai:voice-bridge]", ...args);

/**
 * Drop-in replacement for useVoiceAgent that talks to the backend
 * /agent/voice/ws bridge instead of opening a browser-direct WS to
 * Gemini. Same hook surface — swappable behind NEXT_PUBLIC_VOICE_BRIDGE.
 */
export function useVoiceAgentBridge(): VoiceAgentHook {
  const [state, setState] = useState<VoiceAgentState>("idle");

  const wsRef = useRef<VoiceWs | null>(null);
  const recorderRef = useRef<RecorderHandle | null>(null);
  const playerRef = useRef<PlayerHandle | null>(null);
  const userToolHandlerRef = useRef<ToolCallHandler | null>(null);
  const liveUserIdRef = useRef<string | null>(null);
  const liveAgentIdRef = useRef<string | null>(null);
  const stateRef = useRef<VoiceAgentState>("idle");

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
            setState("listening");
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
          onAudio: (pcm) => {
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
          },
          onClose: () => {
            LOG("ws closed");
            if (stateRef.current !== "error") setState("idle");
          },
        });
        wsRef.current = ws;

        await ws.connect(voiceWsUrl());
        ws.sendStart({
          token: sess.access_token,
          documentId: opts.documentId,
          preferences: {
            simpleLanguage: opts.preferences?.simple_language,
            voiceOnly: opts.preferences?.voice_only,
          },
        });

        let recorder: RecorderHandle;
        try {
          recorder = await startMicRecorder((chunk) => ws.sendAudio(chunk));
        } catch (micErr) {
          ERR("mic denied", micErr);
          stop();
          throw new VoiceAgentMicDeniedError();
        }
        recorderRef.current = recorder;

        LOG("listening — fully wired");
      } catch (err) {
        ERR("start failed", err);
        if (!(err instanceof VoiceAgentMicDeniedError)) stop();
        setState("error");
        throw err;
      }
    },
    [stop],
  );

  const sendText: VoiceAgentHook["sendText"] = useCallback(async (text) => {
    if (!wsRef.current) {
      throw new Error("Voice bridge not started; call start() first.");
    }
    wsRef.current.sendText(text);
  }, []);

  useEffect(() => {
    return () => stop();
  }, [stop]);

  return { state, start, stop, sendText, registerToolHandler };
}
