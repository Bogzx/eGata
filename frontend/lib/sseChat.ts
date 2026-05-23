/**
 * SSE-over-POST helper for /agent/chat/stream.
 *
 * The browser's EventSource only does GET. To stream a POST body we open a
 * fetch(), grab the ReadableStream, decode UTF-8, and split on the SSE
 * blank-line delimiter. Each frame looks like:
 *
 *     event: delta
 *     data: {"text":"..."}
 *
 *     event: tool_call
 *     data: {"name":"...","arguments":{...}}
 *
 *     event: done
 *     data: {"conversation_id":"...","message":"...","tool_calls":[...]}
 */
import { getSession } from "./session";

const LOG = (...args: unknown[]) => console.log("[civicai:sse]", ...args);
const ERR = (...args: unknown[]) => console.error("[civicai:sse]", ...args);

const BASE_URL =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL) ||
  "http://localhost:8000";

export type StreamChatRequest = {
  conversation_id?: string | null;
  document_id?: string;
  message: string;
  preferences?: { simple_language?: boolean; voice_only?: boolean };
};

export type StreamChatToolCall = {
  name: string;
  arguments: Record<string, unknown>;
};

export type StreamChatHandlers = {
  onConversation?: (conversationId: string) => void;
  /** Fired with the *full* accumulated text every time the backend emits a delta. */
  onDelta?: (text: string) => void;
  /** Fired BEFORE the tool runs server-side. */
  onToolCall?: (call: StreamChatToolCall) => void;
  /** Fired AFTER the tool runs server-side with its raw output. */
  onToolResult?: (name: string, output: unknown) => void;
  /** SP4: full session-state snapshot pushed by the server after every mutation. */
  onSessionSnapshot?: (snapshot: import("./types").SessionSnapshot) => void;
  /** SP4: structured frontend event from a tool (document_opened, widget_proposed, etc.). */
  onFrontendEvent?: (event: import("./types").FrontendEvent) => void;
  /** Fired exactly once at the end of the stream. */
  onDone?: (final: {
    conversation_id: string;
    message: string;
    tool_calls: StreamChatToolCall[];
  }) => void;
  onError?: (err: unknown) => void;
};

type ParsedFrame = { event: string; data: string };

function parseFrames(buffer: string): { frames: ParsedFrame[]; rest: string } {
  const frames: ParsedFrame[] = [];
  let rest = buffer;
  // SSE frames are delimited by a blank line (\n\n). Some proxies use \r\n.
  const normalized = rest.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  rest = parts.pop() ?? "";
  for (const raw of parts) {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of raw.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (dataLines.length > 0) {
      frames.push({ event, data: dataLines.join("\n") });
    }
  }
  return { frames, rest };
}

export async function streamChat(
  req: StreamChatRequest,
  handlers: StreamChatHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  const s = getSession();
  if (s) headers["Authorization"] = `Bearer ${s.access_token}`;

  LOG("POST /agent/chat/stream", {
    convId: req.conversation_id,
    docId: req.document_id,
    msgLen: req.message.length,
  });

  let resp: Response;
  try {
    resp = await fetch(`${BASE_URL}/agent/chat/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(req),
      signal,
    });
  } catch (e) {
    ERR("fetch failed", e);
    handlers.onError?.(e);
    throw e;
  }

  if (!resp.ok || !resp.body) {
    const body = await resp.text().catch(() => "");
    const err = new Error(`/agent/chat/stream → ${resp.status}: ${body}`);
    ERR(err.message);
    handlers.onError?.(err);
    throw err;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { frames, rest } = parseFrames(buffer);
      buffer = rest;
      for (const f of frames) dispatchFrame(f, handlers);
    }
    // Flush any trailing frame in the buffer.
    buffer += decoder.decode();
    if (buffer.trim()) {
      const { frames } = parseFrames(buffer + "\n\n");
      for (const f of frames) dispatchFrame(f, handlers);
    }
  } catch (e) {
    ERR("stream read failed", e);
    handlers.onError?.(e);
    throw e;
  }
}

function dispatchFrame(frame: ParsedFrame, h: StreamChatHandlers): void {
  let payload: unknown;
  try {
    payload = JSON.parse(frame.data);
  } catch {
    ERR("malformed JSON in frame", frame);
    return;
  }
  switch (frame.event) {
    case "conversation": {
      const p = payload as { conversation_id?: string };
      if (p.conversation_id) h.onConversation?.(p.conversation_id);
      return;
    }
    case "delta": {
      const p = payload as { text?: string };
      if (typeof p.text === "string") h.onDelta?.(p.text);
      return;
    }
    case "tool_call": {
      const p = payload as { name?: string; arguments?: Record<string, unknown> };
      if (p.name) h.onToolCall?.({ name: p.name, arguments: p.arguments ?? {} });
      return;
    }
    case "tool_result": {
      const p = payload as { name?: string; output?: unknown };
      if (p.name) h.onToolResult?.(p.name, p.output);
      return;
    }
    case "session_snapshot": {
      h.onSessionSnapshot?.(payload as import("./types").SessionSnapshot);
      return;
    }
    case "frontend_event": {
      h.onFrontendEvent?.(payload as import("./types").FrontendEvent);
      return;
    }
    case "done": {
      const p = payload as {
        conversation_id?: string;
        message?: string;
        tool_calls?: StreamChatToolCall[];
      };
      h.onDone?.({
        conversation_id: p.conversation_id ?? "",
        message: p.message ?? "",
        tool_calls: p.tool_calls ?? [],
      });
      return;
    }
    case "error": {
      const p = payload as { detail?: string };
      h.onError?.(new Error(p.detail || "unknown stream error"));
      return;
    }
    default:
      LOG("ignoring unknown frame", frame.event);
  }
}

// Exported for unit tests.
export const _internal = { parseFrames, dispatchFrame };
