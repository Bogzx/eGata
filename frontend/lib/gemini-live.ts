/**
 * Minimal browser WebSocket client for Gemini Live (BidiGenerateContent).
 *
 * URL pattern (subject to SDK changes — verified against google-genai docs):
 *   wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=API_KEY
 *
 * Bidi protocol fragments we care about:
 *   - setup: model, voice, response modality (audio), tools, system instruction
 *   - clientContent / realtimeInput: stream audio + text in
 *   - toolCall: server emits a function-call → we dispatch HTTP to FastAPI
 *   - toolResponse: we send the tool result back
 *   - serverContent: agent text + base64 PCM16 24 kHz audio
 *   - generationComplete / turnComplete / interrupted: end-of-turn / barge-in
 *
 * Buffering: Gemini emits transcripts as a stream of partials ("Bun", "Bună",
 * "Bună zi", ...). We buffer per turn and emit ONE message via onUserMessage /
 * onAgentMessage when the turn boundary fires (turnComplete, generationComplete,
 * or when the other side starts talking).
 */

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
// A leading markdown bold-header followed by a paragraph is treated as
// thinking and stripped. We repeat the strip up to 3 times in case there
// are multiple thinking blocks back-to-back.
const LEADING_THINKING_BLOCK_RE =
  /^\s*\*\*[^*\n]+\*\*[^\n]*\n(?:\s*\n)*(?:[^\n]+\n)+(?:\s*\n)*/;
// Any remaining ``**Heading**`` lines anywhere — strip the line entirely.
const ANY_MD_HEADING_BOLD_RE = /^\s*\*\*[^*\n]+\*\*\s*$/gm;
// Legacy XML-style tags (defense in depth alongside the server-side strip).
const XML_THINKING_RE =
  /<(?:thinking|scratchpad|reasoning)>[\s\S]*?<\/(?:thinking|scratchpad|reasoning)>/gi;

function scrubAgentText(text: string): string {
  if (!text) return text;
  let out = text.replace(XML_THINKING_RE, "");
  // Strip leading thinking-block(s).
  for (let i = 0; i < 3; i++) {
    const before = out;
    out = out.replace(LEADING_THINKING_BLOCK_RE, "");
    if (out === before) break;
  }
  // Strip any stray markdown-bold-header lines mid-response.
  out = out.replace(ANY_MD_HEADING_BOLD_RE, "");
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

  constructor(opts: GeminiLiveOpts) {
    this.opts = opts;
  }

  connect(): Promise<void> {
    const url =
      `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=${encodeURIComponent(this.opts.apiKey)}`;

    return new Promise((resolve, reject) => {
      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";
      ws.onopen = () => {
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
              // Let Gemini 2.5 think internally (dynamic budget) but exclude
              // thought parts from the response stream so the chat UI shows
              // only the final answer. The model still reasons — we just hide
              // the scratchpad.
              thinkingConfig: {
                thinkingBudget: -1,
                includeThoughts: false,
              },
            },
            systemInstruction: {
              role: "system",
              parts: [{ text: this.opts.systemPrompt }],
            },
            tools: [{ functionDeclarations: this.opts.functionDeclarations }],
            // Tighter VAD so background noise / clicks don't trigger ghost
            // turns the STT then mis-recognizes as English/Arabic/Russian.
            realtimeInputConfig: {
              automaticActivityDetection: {
                disabled: false,
                startOfSpeechSensitivity: "START_SENSITIVITY_LOW",
                endOfSpeechSensitivity: "END_SENSITIVITY_LOW",
                prefixPaddingMs: 200,
                silenceDurationMs: 1200,
              },
            },
            // Pin user-side STT to Romanian. Gemini Live's auto-detect drifts
            // when audio is quiet/noisy.
            inputAudioTranscription: { languageCode: "ro-RO" },
            outputAudioTranscription: { languageCode: "ro-RO" },
          },
        };
        ws.send(JSON.stringify(setup));
        this.opened = true;
        this.ws = ws;
        resolve();
      };
      ws.onerror = (e) => {
        this.opts.onError(e);
        if (!this.opened) reject(e);
      };
      ws.onclose = () => {
        this.opened = false;
        this.ws = null;
        // Flush whatever's left so the UI sees it.
        this.flushUser();
        this.flushAgent();
      };
      ws.onmessage = (e) => void this.handleMessage(e);
    });
  }

  private flushUser(): void {
    const t = this.userBuf.trim();
    this.userBuf = "";
    if (t) this.opts.onUserMessage(t);
  }

  private flushAgent(): void {
    const cleaned = scrubAgentText(this.agentBuf);
    const calls = this.agentToolCalls;
    this.agentBuf = "";
    this.agentToolCalls = [];
    if (cleaned || calls.length > 0) {
      this.opts.onAgentMessage(cleaned, calls);
    }
  }

  private setActive(next: "user" | "agent"): void {
    if (this.active === "user" && next === "agent") this.flushUser();
    if (this.active === "agent" && next === "user") this.flushAgent();
    this.active = next;
  }

  private async handleMessage(event: MessageEvent): Promise<void> {
    let msg: Record<string, unknown>;
    try {
      msg =
        typeof event.data === "string"
          ? JSON.parse(event.data)
          : JSON.parse(new TextDecoder().decode(event.data as ArrayBuffer));
    } catch {
      return;
    }

    const sc = msg.serverContent as Record<string, unknown> | undefined;
    if (sc) {
      if (sc.interrupted) {
        this.opts.onInterrupted();
        // Drop any half-buffered agent text; the model was cut off.
        this.agentBuf = "";
      }

      // Agent text / audio (modelTurn). Skip any part Gemini flags as a thought.
      const modelTurn = sc.modelTurn as { parts?: unknown[] } | undefined;
      const parts = (modelTurn?.parts ?? []) as Array<Record<string, unknown>>;
      for (const p of parts) {
        // Gemini marks internal-reasoning parts with thought=true. Drop them.
        if (p.thought === true) continue;
        if (typeof p.text === "string") {
          this.setActive("agent");
          this.agentBuf += p.text;
        }
        const inline = p.inlineData as
          | { mimeType?: string; data?: string }
          | undefined;
        if (inline?.mimeType?.startsWith("audio/") && inline.data) {
          this.opts.onAgentAudio(base64ToArrayBuffer(inline.data));
        }
      }

      // User STT
      const inputT = sc.inputTranscription as { text?: string } | undefined;
      if (inputT?.text) {
        this.setActive("user");
        this.userBuf += inputT.text;
      }

      // Agent TTS transcript (audio captioning)
      const outputT = sc.outputTranscription as { text?: string } | undefined;
      if (outputT?.text) {
        this.setActive("agent");
        this.agentBuf += outputT.text;
      }

      // Turn boundary signals → flush agent buffer
      if (sc.turnComplete || sc.generationComplete) {
        this.flushAgent();
        this.active = null;
      }
    }

    const tc = msg.toolCall as
      | { functionCalls?: ToolCallFromServer[] }
      | undefined;
    if (tc && Array.isArray(tc.functionCalls)) {
      this.setActive("agent");
      // Buffer the tool calls so they're attached to the next agent message flush.
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
          } catch (e) {
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
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
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
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    // The user typed something — finalize any in-flight buffers first.
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
    this.ws.send(
      JSON.stringify({ toolResponse: { functionResponses: responses } }),
    );
  }

  close(): void {
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
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i] as number);
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
