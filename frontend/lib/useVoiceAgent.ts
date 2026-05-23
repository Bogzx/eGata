"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { VoicePreferences } from "./types";
import {
  GeminiLiveSession,
  type AgentToolCall,
  type FunctionDecl,
} from "./gemini-live";
import {
  startMicRecorder,
  startPlayer,
  type PlayerHandle,
  type RecorderHandle,
} from "./audioWorklet";

const LOG = (...args: unknown[]) =>
  console.log("[civicai:voice]", ...args);
const ERR = (...args: unknown[]) =>
  console.error("[civicai:voice]", ...args);

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

export type VoiceAgentStartOpts = {
  documentId?: string;
  preferences?: VoicePreferences;
  /** Called once per finalized user turn with the full transcript. */
  onUserMessage?: (text: string) => void;
  /** Called once per finalized agent turn with text + emitted tool calls. */
  onAgentMessage?: (text: string, toolCalls: AgentToolCall[]) => void;
};

export type VoiceAgentHook = {
  state: VoiceAgentState;
  start: (opts: VoiceAgentStartOpts) => Promise<void>;
  stop: () => void;
  sendText: (text: string) => Promise<void>;
  registerToolHandler: (handler: ToolCallHandler) => void;
};

export class VoiceAgentMicDeniedError extends Error {
  constructor() {
    super("Microphone permission denied — fall back to text chat.");
    this.name = "VoiceAgentMicDeniedError";
  }
}

// JSON-Schema parameter shapes per tool name, in sync with backend Python tool
// signatures. Gemini Live needs explicit declarations to emit function-calls.
const TOOL_SCHEMAS: Record<string, FunctionDecl> = {
  lookup_procedure: {
    name: "lookup_procedure",
    description:
      "Find the best primărie procedure for a free-text Romanian query.",
    parameters: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "User's plain-language need.",
        },
      },
      required: ["query"],
    },
  },
  set_field: {
    name: "set_field",
    description: "Set a single form field on the active document.",
    parameters: {
      type: "object",
      properties: {
        name: { type: "string" },
        value: { type: "string" },
      },
      required: ["name", "value"],
    },
  },
  generate_pdf: {
    name: "generate_pdf",
    description: "Compile the active document to PDF.",
    parameters: { type: "object", properties: {} },
  },
  deliver: {
    name: "deliver",
    description: "Finalize document. delivery ∈ {save, send, print}.",
    parameters: {
      type: "object",
      properties: {
        delivery: { type: "string", enum: ["save", "send", "print"] },
      },
      required: ["delivery"],
    },
  },
  find_redirect: {
    name: "find_redirect",
    description:
      "Decide if a query is out of primărie scope (ANAF/CNAS/DRPCIV).",
    parameters: {
      type: "object",
      properties: {
        query: { type: "string" },
        target: { type: "string" },
      },
      required: ["query"],
    },
  },
  set_reminder: {
    name: "set_reminder",
    description:
      "Create a proactive reminder (rare; only on explicit citizen request).",
    parameters: {
      type: "object",
      properties: {
        kind: {
          type: "string",
          enum: ["in_scope_procedure", "external_redirect"],
        },
        title: { type: "string" },
        procedure_id: { type: "string" },
        redirect_target: { type: "string" },
        deadline_days: { type: "number" },
      },
      required: ["kind", "title"],
    },
  },
  propose_widget: {
    name: "propose_widget",
    description:
      "Ask a structured UI question that the browser renders as an inline chat widget. Use for fixed-set choices, yes/no confirms, or date pickers.",
    parameters: {
      type: "object",
      properties: {
        type: { type: "string", enum: ["choice", "confirm", "date"] },
        question: { type: "string" },
        options: { type: "array", items: { type: "string" } },
        target_field: { type: "string" },
      },
      required: ["type", "question"],
    },
  },
};

export function useVoiceAgent(): VoiceAgentHook {
  const [state, setState] = useState<VoiceAgentState>("idle");

  const sessionRef = useRef<GeminiLiveSession | null>(null);
  const recorderRef = useRef<RecorderHandle | null>(null);
  const playerRef = useRef<PlayerHandle | null>(null);
  const userToolHandlerRef = useRef<ToolCallHandler | null>(null);
  const tokenRef = useRef<{ jwt: string; baseUrl: string } | null>(null);

  const registerToolHandler = useCallback((handler: ToolCallHandler) => {
    userToolHandlerRef.current = handler;
  }, []);

  const dispatchTool = useCallback(
    async (
      name: string,
      args: Record<string, unknown>,
    ): Promise<Record<string, unknown>> => {
      const tok = tokenRef.current;
      if (!tok) {
        ERR("dispatchTool", name, "but no JWT — session not started");
        throw new Error("No tool JWT — session not started");
      }
      LOG("dispatchTool →", name, args);
      const resp = await fetch(`${tok.baseUrl}/${name}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${tok.jwt}`,
        },
        body: JSON.stringify(args),
      });
      if (!resp.ok) {
        const detail = await resp.text();
        ERR("dispatchTool", name, "→", resp.status, detail);
        throw new Error(`Tool ${name} failed (${resp.status}): ${detail}`);
      }
      const result = (await resp.json()) as Record<string, unknown>;
      LOG("dispatchTool", name, "← OK", result);
      try {
        await userToolHandlerRef.current?.(name, { ...args, _result: result });
      } catch (e) {
        ERR("UI side-effect handler threw", e);
      }
      return result;
    },
    [],
  );

  const stop = useCallback(() => {
    LOG("stop()");
    sessionRef.current?.close();
    recorderRef.current?.stop();
    playerRef.current?.stop();
    sessionRef.current = null;
    recorderRef.current = null;
    playerRef.current = null;
    tokenRef.current = null;
    setState("idle");
  }, []);

  const start: VoiceAgentHook["start"] = useCallback(
    async (opts) => {
      try {
        LOG("start()", {
          documentId: opts.documentId,
          preferences: opts.preferences,
        });
        setState("connecting");

        const session = await api.createVoiceSession({
          document_id: opts.documentId,
          preferences: opts.preferences,
        });
        LOG("createVoiceSession OK", {
          session_id: session.session_id,
          gemini_model: session.gemini_model,
          gemini_voice: session.gemini_voice,
          tool_names: session.tool_names,
          tool_base_url: session.tool_base_url,
          system_prompt_len: session.system_prompt.length,
        });
        tokenRef.current = {
          jwt: session.tool_jwt,
          baseUrl: session.tool_base_url,
        };

        const declarations: FunctionDecl[] = session.tool_names
          .map((n) => TOOL_SCHEMAS[n])
          .filter((d): d is FunctionDecl => Boolean(d));

        const player = await startPlayer();
        playerRef.current = player;

        const gemini = new GeminiLiveSession({
          apiKey: session.gemini_api_key,
          model: session.gemini_model,
          voiceName: session.gemini_voice,
          systemPrompt: session.system_prompt,
          functionDeclarations: declarations,
          onAgentAudio: (pcm) => {
            setState("speaking");
            player.feed(pcm);
          },
          onUserMessage: (text) => {
            LOG("onUserMessage (finalized)", text);
            opts.onUserMessage?.(text);
            setState("listening");
          },
          onAgentMessage: (text, toolCalls) => {
            LOG(
              "onAgentMessage (finalized)",
              text.slice(0, 120),
              "tools:",
              toolCalls.map((t) => t.name),
            );
            opts.onAgentMessage?.(text, toolCalls);
          },
          onInterrupted: () => {
            LOG("interrupted");
            player.flush();
            setState("listening");
          },
          onToolCall: dispatchTool,
          onError: (err) => {
            ERR("Gemini error", err);
            setState("error");
          },
        });
        sessionRef.current = gemini;
        await gemini.connect();
        LOG("gemini.connect() returned — WS open");

        let recorder: RecorderHandle;
        try {
          recorder = await startMicRecorder((chunk) => {
            gemini.sendAudio(chunk);
          });
        } catch (micErr) {
          ERR("mic denied; text fallback", micErr);
          setState("error");
          throw new VoiceAgentMicDeniedError();
        }
        recorderRef.current = recorder;

        LOG("listening — fully wired");
        setState("listening");
      } catch (err) {
        ERR("start() failed", err);
        if (!(err instanceof VoiceAgentMicDeniedError)) {
          stop();
        }
        setState("error");
        throw err;
      }
    },
    [dispatchTool, stop],
  );

  const sendText: VoiceAgentHook["sendText"] = useCallback(async (text) => {
    if (!sessionRef.current) {
      throw new Error("Voice session not started; call start() first.");
    }
    sessionRef.current.sendText(text);
  }, []);

  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  return {
    state,
    start,
    stop,
    sendText,
    registerToolHandler,
  };
}
