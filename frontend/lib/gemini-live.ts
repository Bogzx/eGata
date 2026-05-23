/**
 * Minimal browser WebSocket client for Gemini Live (BidiGenerateContent).
 *
 * URL pattern:
 *   wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=API_KEY
 *
 * Bidi protocol fragments we care about:
 *   - setup: model, voice, response modality (audio), tools, system instruction
 *   - clientContent / realtimeInput: stream audio + text in
 *   - toolCall: server emits a function-call → we dispatch HTTP to FastAPI
 *   - toolResponse: we send the tool result back
 *   - serverContent: agent text + base64 PCM16 24 kHz audio
 *   - generationComplete / turnComplete / interrupted: end-of-turn / barge-in
 *   - setupComplete / goAway: connection lifecycle
 *
 * Buffering: Gemini emits transcripts as a stream of partials. We accumulate
 * per turn into ``userBuf`` / ``agentBuf`` and expose them two ways:
 *   - ``onUserDelta`` / ``onAgentDelta`` — fired on every partial with the
 *     full accumulated buffer (the UI replaces the in-progress bubble).
 *   - ``onUserMessage`` / ``onAgentMessage`` — fired ONCE per finalized turn
 *     with the cleaned final text + any emitted tool calls.
 *
 * Logging: every WS lifecycle event + every parsed serverContent path is
 * console.log'd with the `[civicai:live]` prefix so you can filter in DevTools.
 */

const LOG = (...args: unknown[]) =>
  console.log("[civicai:live]", ...args);
const WARN = (...args: unknown[]) =>
  console.warn("[civicai:live]", ...args);
const ERR = (...args: unknown[]) =>
  console.error("[civicai:live]", ...args);

export type FunctionDecl = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
};

export type AgentToolCall = {
  name: string;
  args: Record<string, unknown>;
};

export type GeminiLiveOpts = {
  apiKey: string;
  model: string;
  voiceName: string;
  systemPrompt: string;
  functionDeclarations: FunctionDecl[];
  onAgentAudio: (pcm: ArrayBuffer) => void;
  /** Fired on every partial with the full accumulated user transcript. */
  onUserDelta?: (text: string) => void;
  /** Fired on every partial with the full accumulated agent transcript. */
  onAgentDelta?: (text: string) => void;
  /** Fired once per completed user turn with the full transcript. */
  onUserMessage: (text: string) => void;
  /** Fired once per completed agent turn with the full text + any tool calls. */
  onAgentMessage: (text: string, toolCalls: AgentToolCall[]) => void;
  onInterrupted: () => void;
  onToolCall: (
    name: string,
    args: Record<string, unknown>,
    callId: string,
  ) => Promise<Record<string, unknown>>;
  onError: (err: unknown) => void;
};

type ToolCallFromServer = {
  id?: string;
  name: string;
  args?: Record<string, unknown>;
};

// Gemini 2.5 Flash native-audio sometimes leaks its scratchpad into the
// response text, formatted like:
//   **Initiating Communication Strategy**
//
//   I've got a tricky starting point here, an ellipsis alone! ...
//
//   Bună ziua! Cu ce te pot ajuta?
// A leading markdown bold-header followed by one or more paragraphs is
// treated as thinking and stripped — but ONLY when the heading has no
// Romanian diacritics (so real Romanian bold headings like "**Pași:**" are
// left alone). XML thinking tags are also stripped anywhere.
const LEADING_THINKING_BLOCK_RE =
  /^\s*\*\*([^*\n]+)\*\*[^\n]*\n(?:\s*\n)*(?:[^\n]+\n)+(?:\s*\n)*/;
const XML_THINKING_RE =
  /<(?:thinking|scratchpad|reasoning)>[\s\S]*?<\/(?:thinking|scratchpad|reasoning)>/gi;
const RO_DIACRITICS_RE = /[ăâîșțĂÂÎȘȚ]/;

function scrubAgentText(text: string): string {
  if (!text) return text;
  let out = text.replace(XML_THINKING_RE, "");
  for (let i = 0; i < 3; i++) {
    const m = LEADING_THINKING_BLOCK_RE.exec(out);
    if (!m) break;
    if (RO_DIACRITICS_RE.test(m[1] ?? "")) break;
    out = out.slice(m[0].length);
  }
  return out.replace(/\n{3,}/g, "\n\n").trim();
}

export class GeminiLiveSession {
  private ws: WebSocket | null = null;
  private opts: GeminiLiveOpts;
  private opened = false;

  // Turn buffering state
  private userBuf = "";
  private agentBuf = "";
  private agentToolCalls: AgentToolCall[] = [];
  private active: "user" | "agent" | null = null;

  // Debug counters
  private audioChunksOut = 0;
  private audioChunksIn = 0;
  private setupSentAt = 0;
  private lastChunkLogAt = 0;

  constructor(opts: GeminiLiveOpts) {
    this.opts = opts;
  }

  connect(): Promise<void> {
    const url =
      `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=${encodeURIComponent(this.opts.apiKey)}`;

    LOG("connect()", {
      model: this.opts.model,
      voice: this.opts.voiceName,
      tools: this.opts.functionDeclarations.map((d) => d.name),
      systemPromptLen: this.opts.systemPrompt.length,
    });

    return new Promise((resolve, reject) => {
      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";

      ws.onopen = () => {
        LOG("ws.onopen — sending setup");
        // CRITICAL: Keep setup minimal. Adding unsupported fields (e.g.
        // `languageCode` on transcription configs, `includeThoughts` on
        // thinkingConfig for some models) makes the server silently drop
        // the setup → session looks dead. Only documented v1beta fields.
        const setup = {
          setup: {
            model: `models/${this.opts.model}`,
            generationConfig: {
              responseModalities: ["AUDIO"],
              speechConfig: {
                voiceConfig: {
                  prebuiltVoiceConfig: { voiceName: this.opts.voiceName },
                },
                languageCode: "ro-RO",
              },
              temperature: 0.6,
            },
            systemInstruction: {
              role: "system",
              parts: [{ text: this.opts.systemPrompt }],
            },
            tools: [{ functionDeclarations: this.opts.functionDeclarations }],
            inputAudioTranscription: {},
            outputAudioTranscription: {},
          },
        };
        LOG("setup payload bytes:", JSON.stringify(setup).length);
        ws.send(JSON.stringify(setup));
        this.setupSentAt = Date.now();
        this.opened = true;
        this.ws = ws;
        resolve();
      };

      ws.onerror = (e) => {
        ERR("ws.onerror", e);
        this.opts.onError(e);
        if (!this.opened) reject(e);
      };

      ws.onclose = (e) => {
        LOG("ws.onclose", {
          code: e.code,
          reason: e.reason,
          wasClean: e.wasClean,
          audioChunksOut: this.audioChunksOut,
          audioChunksIn: this.audioChunksIn,
          openedForMs: this.setupSentAt ? Date.now() - this.setupSentAt : 0,
        });
        this.opened = false;
        this.ws = null;
        this.flushUser();
        this.flushAgent();
      };

      ws.onmessage = (e) => void this.handleMessage(e);
    });
  }

  private flushUser(): void {
    const t = this.userBuf.trim();
    this.userBuf = "";
    if (t) {
      LOG("flushUser →", t.length, "chars:", t.slice(0, 80));
      this.opts.onUserMessage(t);
    }
  }

  private flushAgent(): void {
    const cleaned = scrubAgentText(this.agentBuf);
    const calls = this.agentToolCalls;
    this.agentBuf = "";
    this.agentToolCalls = [];
    if (cleaned || calls.length > 0) {
      LOG(
        "flushAgent →",
        cleaned.length,
        "chars,",
        calls.length,
        "tool call(s):",
        cleaned.slice(0, 80),
        calls.map((c) => c.name),
      );
      this.opts.onAgentMessage(cleaned, calls);
    }
  }

  private setActive(next: "user" | "agent"): void {
    if (this.active === next) return;
    if (this.active === "user" && next === "agent") this.flushUser();
    if (this.active === "agent" && next === "user") this.flushAgent();
    LOG("setActive", this.active, "→", next);
    this.active = next;
  }

  private async handleMessage(event: MessageEvent): Promise<void> {
    let raw: string;
    try {
      raw =
        typeof event.data === "string"
          ? event.data
          : new TextDecoder().decode(event.data as ArrayBuffer);
    } catch (e) {
      WARN("could not decode incoming frame", e);
      return;
    }

    let msg: Record<string, unknown>;
    try {
      msg = JSON.parse(raw);
    } catch (e) {
      WARN("could not JSON.parse incoming frame:", raw.slice(0, 200), e);
      return;
    }

    // Surface lifecycle frames immediately.
    if (msg.setupComplete) {
      LOG("setupComplete received — session ready");
    }
    if (msg.goAway) {
      WARN("goAway:", msg.goAway);
    }

    const sc = msg.serverContent as Record<string, unknown> | undefined;
    if (sc) {
      if (sc.interrupted) {
        LOG("serverContent.interrupted — drop agent buffer + flush player");
        this.opts.onInterrupted();
        this.agentBuf = "";
        this.opts.onAgentDelta?.("");
      }

      // Agent text / audio (modelTurn). Skip thought parts.
      const modelTurn = sc.modelTurn as { parts?: unknown[] } | undefined;
      const parts = (modelTurn?.parts ?? []) as Array<Record<string, unknown>>;
      for (const p of parts) {
        if (p.thought === true) continue;
        if (typeof p.text === "string") {
          this.setActive("agent");
          this.agentBuf += p.text;
          this.opts.onAgentDelta?.(scrubAgentText(this.agentBuf));
        }
        const inline = p.inlineData as
          | { mimeType?: string; data?: string }
          | undefined;
        if (inline?.mimeType?.startsWith("audio/") && inline.data) {
          this.audioChunksIn += 1;
          if (Date.now() - this.lastChunkLogAt > 1000) {
            LOG(
              "audio in — chunks total:",
              this.audioChunksIn,
              "this chunk b64 bytes:",
              inline.data.length,
            );
            this.lastChunkLogAt = Date.now();
          }
          this.opts.onAgentAudio(base64ToArrayBuffer(inline.data));
        }
      }

      const inputT = sc.inputTranscription as { text?: string } | undefined;
      if (inputT?.text) {
        this.setActive("user");
        this.userBuf += inputT.text;
        this.opts.onUserDelta?.(this.userBuf);
        LOG("inputTranscription += ", JSON.stringify(inputT.text));
      }

      const outputT = sc.outputTranscription as { text?: string } | undefined;
      if (outputT?.text) {
        this.setActive("agent");
        this.agentBuf += outputT.text;
        this.opts.onAgentDelta?.(scrubAgentText(this.agentBuf));
        LOG("outputTranscription += ", JSON.stringify(outputT.text));
      }

      if (sc.turnComplete || sc.generationComplete) {
        LOG("turnComplete/generationComplete — flushing agent buffer");
        this.flushAgent();
        this.active = null;
      }
    }

    const tc = msg.toolCall as
      | { functionCalls?: ToolCallFromServer[] }
      | undefined;
    if (tc && Array.isArray(tc.functionCalls)) {
      LOG(
        "toolCall — count:",
        tc.functionCalls.length,
        "names:",
        tc.functionCalls.map((f) => f.name),
      );
      this.setActive("agent");
      for (const fc of tc.functionCalls) {
        this.agentToolCalls.push({
          name: fc.name,
          args: fc.args || {},
        });
      }
      const responses = await Promise.all(
        tc.functionCalls.map(async (fc) => {
          const callId = fc.id ?? "";
          let output: Record<string, unknown>;
          try {
            output = await this.opts.onToolCall(
              fc.name,
              fc.args || {},
              callId,
            );
            LOG("tool result", fc.name, output);
          } catch (e) {
            ERR("tool dispatch failed", fc.name, e);
            output = { error: (e as Error).message };
          }
          return {
            id: callId,
            name: fc.name,
            response: { output },
          };
        }),
      );
      this.sendToolResponse(responses);
    }
  }

  sendAudio(chunk: ArrayBuffer): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      if (this.audioChunksOut === 0) {
        WARN("sendAudio called before WS open — dropping chunk");
      }
      return;
    }
    this.audioChunksOut += 1;
    if (this.audioChunksOut === 1 || this.audioChunksOut % 50 === 0) {
      LOG(
        "sendAudio chunk #" + this.audioChunksOut,
        "bytes:",
        chunk.byteLength,
      );
    }
    this.ws.send(
      JSON.stringify({
        realtimeInput: {
          mediaChunks: [
            {
              mimeType: "audio/pcm;rate=16000",
              data: arrayBufferToBase64(chunk),
            },
          ],
        },
      }),
    );
  }

  sendText(text: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      WARN("sendText called before WS open — dropping");
      return;
    }
    LOG("sendText", JSON.stringify(text).slice(0, 120));
    this.flushUser();
    this.flushAgent();
    this.ws.send(
      JSON.stringify({
        clientContent: {
          turns: [{ role: "user", parts: [{ text }] }],
          turnComplete: true,
        },
      }),
    );
  }

  sendToolResponse(responses: unknown[]): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    LOG("sendToolResponse", responses.length, "response(s)");
    this.ws.send(
      JSON.stringify({ toolResponse: { functionResponses: responses } }),
    );
  }

  close(): void {
    LOG("close()");
    try {
      this.ws?.close();
    } catch {
      /* noop */
    }
    this.ws = null;
  }
}

function arrayBufferToBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let bin = "";
  for (let i = 0; i < bytes.length; i++)
    bin += String.fromCharCode(bytes[i] as number);
  return btoa(bin);
}

function base64ToArrayBuffer(b64: string): ArrayBuffer {
  const bin = atob(b64);
  const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  return buf.buffer as ArrayBuffer;
}

// Exported for unit tests.
export const _internal = { scrubAgentText };
