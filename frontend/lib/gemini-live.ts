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
 *   - generationComplete / interrupted: end-of-turn / barge-in events
 */

export type FunctionDecl = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
};

export type GeminiLiveOpts = {
  apiKey: string;
  model: string;
  voiceName: string;
  systemPrompt: string;
  functionDeclarations: FunctionDecl[];
  onAgentAudio: (pcm: ArrayBuffer) => void;
  onAgentText: (text: string) => void;
  onUserTranscript: (text: string) => void;
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

export class GeminiLiveSession {
  private ws: WebSocket | null = null;
  private opts: GeminiLiveOpts;
  private opened = false;

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
              temperature: 0.7,
            },
            systemInstruction: {
              role: "system",
              parts: [{ text: this.opts.systemPrompt }],
            },
            tools: [{ functionDeclarations: this.opts.functionDeclarations }],
            realtimeInputConfig: {
              automaticActivityDetection: { disabled: false },
            },
            inputAudioTranscription: {},
            outputAudioTranscription: {},
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
      };
      ws.onmessage = (e) => void this.handleMessage(e);
    });
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
      if (sc.interrupted) this.opts.onInterrupted();
      const modelTurn = sc.modelTurn as { parts?: unknown[] } | undefined;
      const parts = (modelTurn?.parts ?? []) as Array<Record<string, unknown>>;
      for (const p of parts) {
        if (typeof p.text === "string") this.opts.onAgentText(p.text);
        const inline = p.inlineData as
          | { mimeType?: string; data?: string }
          | undefined;
        if (inline?.mimeType?.startsWith("audio/") && inline.data) {
          this.opts.onAgentAudio(base64ToArrayBuffer(inline.data));
        }
      }
      const inputT = sc.inputTranscription as { text?: string } | undefined;
      if (inputT?.text) this.opts.onUserTranscript(inputT.text);
      const outputT = sc.outputTranscription as { text?: string } | undefined;
      if (outputT?.text) this.opts.onAgentText(outputT.text);
    }

    const tc = msg.toolCall as
      | { functionCalls?: ToolCallFromServer[] }
      | undefined;
    if (tc && Array.isArray(tc.functionCalls)) {
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
