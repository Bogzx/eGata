"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Mic, MicOff, MessageSquare, Square, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  useVoiceAgent,
  VoiceAgentMicDeniedError,
} from "@/lib/useVoiceAgent";
import { api, ApiError } from "@/lib/api";
import type { Document, Procedure, VoicePreferences } from "@/lib/types";

type Props = {
  procedure: Procedure;
  documentId: string;
  values: Record<string, unknown>;
  onPatch: (delta: Record<string, unknown>) => void | Promise<void>;
  preferences?: VoicePreferences;
  onTextFallback?: () => void;
};

type VoiceMessage = { role: "user" | "agent"; text: string };

const STATE_LABEL: Record<string, string> = {
  idle: 'Apasă „Pornește" ca să începi. Poți și să scrii direct.',
  connecting: "Se conectează la asistent...",
  listening: "Ascult — vorbește când vrei, sau scrie mai jos.",
  speaking: "Asistentul vorbește.",
  error: "Voce indisponibilă — poți scrie în continuare.",
};

export function VocalFillFlow({
  procedure,
  documentId,
  preferences,
  onPatch,
  onTextFallback,
}: Props) {
  void procedure;
  const agent = useVoiceAgent();
  const [messages, setMessages] = useState<VoiceMessage[]>([]);
  const [micDenied, setMicDenied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const startedRef = useRef(false);
  const listRef = useRef<HTMLOListElement | null>(null);

  // Append-with-grouping: if last message is from same role, extend it
  // (matches Gemini Live's per-turn incremental transcription).
  const append = useCallback((role: "user" | "agent", text: string) => {
    if (!text) return;
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.role === role) {
        const merged = last.text.endsWith(text)
          ? last.text
          : last.text + (last.text.endsWith(" ") ? "" : " ") + text;
        return [...prev.slice(0, -1), { role, text: merged }];
      }
      return [...prev, { role, text }];
    });
  }, []);

  const registerHandler = agent.registerToolHandler;
  useEffect(() => {
    registerHandler(async (name, args) => {
      if (name === "set_field" && (args as { _result?: Document })._result) {
        const result = (args as { _result: Document })._result;
        if (result?.fields) {
          await onPatch(result.fields);
        }
      }
      return {};
    });
  }, [registerHandler, onPatch]);

  const startVoice = useCallback(async () => {
    setError(null);
    setMicDenied(false);
    try {
      await agent.start({
        documentId,
        preferences,
        onAgentMessage: (m) => append("agent", m),
        onTranscript: (t) => append("user", t),
      });
    } catch (e) {
      if (e instanceof VoiceAgentMicDeniedError) {
        setMicDenied(true);
      } else {
        setError((e as Error).message);
      }
    }
  }, [agent, append, documentId, preferences]);

  // Auto-start voice on mount once
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    void startVoice();
    return () => {
      agent.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-scroll to latest
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const submitText = useCallback(async () => {
    const text = draft.trim();
    if (!text || sending) return;

    append("user", text);
    setDraft("");
    setError(null);

    // Path A: voice session is active → forward to Gemini Live via WS
    // (agent will speak back + outputTranscription populates the agent bubble).
    const voiceActive =
      agent.state === "listening" || agent.state === "speaking";
    if (voiceActive) {
      try {
        await agent.sendText(text);
      } catch (e) {
        setError((e as Error).message);
      }
      return;
    }

    // Path B: voice not active → HTTP fallback via /agent/chat so the user can
    // still hold a text-only conversation in the same surface.
    setSending(true);
    try {
      const resp = await api.chat({
        conversation_id: conversationId,
        document_id: documentId,
        message: text,
        preferences,
      });
      setConversationId(resp.conversation_id);
      append("agent", resp.message);
      // If the agent emitted a write-side tool call, refresh document.
      for (const tc of resp.tool_calls ?? []) {
        if (tc.name === "set_field" || tc.name === "deliver" || tc.name === "generate_pdf") {
          try {
            const doc = await api.getDocument(documentId);
            await onPatch(doc.fields);
          } catch {
            /* ignore */
          }
          break;
        }
      }
    } catch (e) {
      if (e instanceof ApiError) {
        setError("Asistentul nu a răspuns. Încearcă din nou.");
      } else {
        setError((e as Error).message);
      }
    } finally {
      setSending(false);
    }
  }, [
    agent,
    append,
    conversationId,
    documentId,
    draft,
    onPatch,
    preferences,
    sending,
  ]);

  const stateLabel = useMemo(
    () => STATE_LABEL[agent.state] ?? agent.state,
    [agent.state],
  );

  if (micDenied) {
    return (
      <div className="flex h-full flex-col rounded-lg border bg-background">
        <div className="space-y-4 border-b border-amber-300 bg-amber-50 p-6 text-amber-900">
          <div className="flex items-center gap-3">
            <MicOff aria-hidden className="h-5 w-5" />
            <h3 className="text-lg font-semibold">
              Microfonul nu este disponibil
            </h3>
          </div>
          <p className="text-sm">
            Browser-ul nu ne-a permis accesul la microfon. Continuă conversația
            scriind mai jos — asistentul răspunde la fel.
          </p>
          {onTextFallback ? (
            <Button onClick={onTextFallback} variant="outline">
              <MessageSquare className="mr-2 h-4 w-4" aria-hidden />
              Treci la modul text
            </Button>
          ) : null}
        </div>
        <ConversationList listRef={listRef} messages={messages} />
        <Composer
          value={draft}
          onChange={setDraft}
          onSubmit={submitText}
          sending={sending}
          hint="Microfonul e blocat — scrie și asistentul îți răspunde."
        />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col rounded-lg border bg-background">
      <header className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-3" aria-live="polite">
          {agent.state === "speaking" ? (
            <Mic
              aria-hidden
              className="h-5 w-5 animate-pulse text-blue-600"
            />
          ) : agent.state === "listening" ? (
            <Mic
              aria-hidden
              className="h-5 w-5 animate-pulse text-green-600"
            />
          ) : (
            <Mic aria-hidden className="h-5 w-5 text-muted-foreground" />
          )}
          <span className="text-sm">{stateLabel}</span>
        </div>
        <div className="flex items-center gap-2">
          {agent.state === "idle" || agent.state === "error" ? (
            <Button size="sm" onClick={startVoice}>
              <Mic className="mr-2 h-4 w-4" aria-hidden />
              Pornește vocea
            </Button>
          ) : (
            <Button size="sm" variant="outline" onClick={() => agent.stop()}>
              <Square className="mr-2 h-4 w-4" aria-hidden />
              Oprește vocea
            </Button>
          )}
        </div>
      </header>

      <ConversationList listRef={listRef} messages={messages} />

      {error ? (
        <p
          role="alert"
          className="border-t bg-destructive/10 px-4 py-2 text-sm text-destructive"
        >
          {error}
        </p>
      ) : null}

      <Composer
        value={draft}
        onChange={setDraft}
        onSubmit={submitText}
        sending={sending}
      />
    </div>
  );
}

function ConversationList({
  listRef,
  messages,
}: {
  listRef: React.RefObject<HTMLOListElement | null>;
  messages: VoiceMessage[];
}) {
  return (
    <ol
      ref={listRef}
      className="flex-1 space-y-3 overflow-auto p-4"
      aria-live="polite"
      aria-label="Conversație"
    >
      {messages.length === 0 ? (
        <li className="text-center text-sm text-muted-foreground">
          Spune sau scrie ce ai nevoie. Conversația apare aici.
        </li>
      ) : (
        messages.map((m, i) => (
          <li
            key={i}
            className={
              m.role === "agent"
                ? "max-w-[85%] rounded-lg bg-muted px-4 py-3 text-sm"
                : "ml-auto max-w-[85%] rounded-lg bg-primary px-4 py-3 text-sm text-primary-foreground"
            }
          >
            <p className="mb-1 text-xs font-medium uppercase opacity-70">
              {m.role === "agent" ? "Asistent" : "Tu"}
            </p>
            <p className="whitespace-pre-wrap">{m.text}</p>
          </li>
        ))
      )}
    </ol>
  );
}

function Composer({
  value,
  onChange,
  onSubmit,
  sending,
  hint,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  sending: boolean;
  hint?: string;
}) {
  return (
    <form
      className="border-t bg-background"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      {hint ? (
        <p className="px-4 pt-2 text-xs text-muted-foreground">{hint}</p>
      ) : null}
      <div className="flex gap-2 p-3">
        <Textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={2}
          placeholder="Scrie un mesaj... (Enter pentru trimite, Shift+Enter pentru linie nouă)"
          aria-label="Mesaj nou"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSubmit();
            }
          }}
        />
        <Button
          type="submit"
          disabled={sending || value.trim().length === 0}
          aria-label="Trimite mesaj"
        >
          {sending ? (
            "..."
          ) : (
            <>
              <Send className="mr-1 h-4 w-4" aria-hidden /> Trimite
            </>
          )}
        </Button>
      </div>
    </form>
  );
}
