/**
 * Raw WebSocket client for the backend /agent/voice/ws bridge.
 *
 * Frame protocol — see docs/superpowers/specs/2026-05-23-voice-ws-bridge-design.md §5.
 *
 * Auth: the `start` frame carries the same Bearer JWT used for HTTP requests
 * (browsers can't set Authorization on a WS upgrade, so the token rides
 * inside the first frame).
 */

const LOG = (...args: unknown[]) =>
  console.log("[egata:voiceWs]", ...args);
const ERR = (...args: unknown[]) =>
  console.error("[egata:voiceWs]", ...args);

export type VoiceWsToolCall = {
  name: string;
  arguments: Record<string, unknown>;
};

export type VoiceWsHandlers = {
  onReady: (conversationId: string) => void;
  onUserDelta: (text: string) => void;
  onUserDone: (text: string) => void;
  onAgentDelta: (text: string) => void;
  onAgentDone: (text: string, toolCalls: VoiceWsToolCall[]) => void;
  onToolCall: (name: string, args: Record<string, unknown>) => void;
  onToolResult: (name: string, output: Record<string, unknown>) => void;
  /** SP4: full session-state snapshot pushed after every mutation. */
  onSessionSnapshot?: (snapshot: import("./types").SessionSnapshot) => void;
  /** SP4: structured frontend event from a tool. */
  onFrontendEvent?: (event: import("./types").FrontendEvent) => void;
  onAudio: (pcm: ArrayBuffer) => void;
  onInterrupted: () => void;
  onError: (detail: string) => void;
  onClose: () => void;
};

export type VoiceWsStartPayload = {
  token: string;
  documentId?: string;
  conversationId?: string;
  preferences?: {
    simpleLanguage?: boolean;
    voiceOnly?: boolean;
  };
};

export class VoiceWs {
  private ws: WebSocket | null = null;
  private opened = false;
  private toolCallsThisTurn: VoiceWsToolCall[] = [];

  constructor(private handlers: VoiceWsHandlers) {}

  connect(url: string): Promise<void> {
    LOG("connect", url);
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";

      ws.onopen = () => {
        LOG("onopen");
        this.opened = true;
        this.ws = ws;
        resolve();
      };

      ws.onerror = (e) => {
        ERR("onerror", e);
        if (!this.opened) reject(new Error("WebSocket open failed"));
      };

      ws.onclose = (e) => {
        LOG("onclose", { code: e.code, reason: e.reason });
        this.opened = false;
        this.ws = null;
        this.handlers.onClose();
      };

      ws.onmessage = (e) => this.handleMessage(e);
    });
  }

  sendStart(payload: VoiceWsStartPayload): void {
    this.send({
      type: "start",
      token: payload.token,
      document_id: payload.documentId,
      conversation_id: payload.conversationId,
      preferences: {
        simple_language: payload.preferences?.simpleLanguage ?? false,
        voice_only: payload.preferences?.voiceOnly ?? false,
      },
    });
  }

  sendText(text: string): void {
    this.send({ type: "text", text });
  }

  /** Submit a previously-proposed widget's answer through the live session.
   *
   * The bridge resolves the widget server-side (popping it off
   * `session.pending_widgets`), dispatches `set_field` if the widget had a
   * `target_field`, and injects a synthetic note into the live session's
   * context so the model knows the field was answered without us having
   * to bounce through the HTTP /widget-result endpoint. */
  sendWidgetSubmission(widgetId: string, value: unknown): void {
    this.send({ type: "widget_submission", widget_id: widgetId, value });
  }

  sendInterrupt(): void {
    this.send({ type: "interrupt" });
  }

  sendAudio(chunk: ArrayBuffer): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(chunk);
  }

  close(): void {
    LOG("close");
    try {
      this.ws?.close();
    } catch {
      /* noop */
    }
    this.ws = null;
  }

  private send(obj: Record<string, unknown>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      // Throw, do NOT silently drop: ChatSurface.onSendText catches this
      // and falls back to /agent/chat/stream SSE. If we returned, the
      // user's text would vanish without any visible failure (bubble
      // appears locally, agent never sees it).
      ERR("send on non-OPEN ws — throwing for SSE fallback", obj);
      throw new Error("WS not open");
    }
    this.ws.send(JSON.stringify(obj));
  }

  private handleMessage(event: MessageEvent): void {
    if (event.data instanceof ArrayBuffer) {
      this.handlers.onAudio(event.data);
      return;
    }
    let msg: Record<string, unknown>;
    try {
      msg = JSON.parse(event.data as string);
    } catch (e) {
      ERR("bad JSON frame:", event.data, e);
      return;
    }
    const type = msg.type as string;
    switch (type) {
      case "ready":
        this.handlers.onReady(msg.conversation_id as string);
        break;
      case "user_delta":
        this.handlers.onUserDelta((msg.text as string) ?? "");
        break;
      case "user_done":
        this.handlers.onUserDone((msg.text as string) ?? "");
        break;
      case "agent_delta":
        this.handlers.onAgentDelta((msg.text as string) ?? "");
        break;
      case "agent_done": {
        const text = (msg.text as string) ?? "";
        const calls = this.toolCallsThisTurn;
        this.toolCallsThisTurn = [];
        this.handlers.onAgentDone(text, calls);
        break;
      }
      case "tool_call": {
        const name = msg.name as string;
        const args = (msg.arguments as Record<string, unknown>) ?? {};
        this.toolCallsThisTurn.push({ name, arguments: args });
        this.handlers.onToolCall(name, args);
        break;
      }
      case "tool_result":
        this.handlers.onToolResult(
          msg.name as string,
          (msg.output as Record<string, unknown>) ?? {},
        );
        break;
      case "interrupted":
        this.handlers.onInterrupted();
        break;
      case "session_snapshot":
        this.handlers.onSessionSnapshot?.(
          msg.snapshot as import("./types").SessionSnapshot,
        );
        break;
      case "frontend_event":
        this.handlers.onFrontendEvent?.(
          msg.event as import("./types").FrontendEvent,
        );
        break;
      case "error":
        this.handlers.onError((msg.detail as string) ?? "Eroare necunoscută");
        break;
      default:
        ERR("unknown frame type:", type, msg);
    }
  }
}

/**
 * Build a ws:// or wss:// URL relative to the configured API base.
 */
export function voiceWsUrl(path = "/agent/voice/ws"): string {
  const base =
    (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL) ||
    "http://localhost:8000";
  const url = new URL(path, base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}
