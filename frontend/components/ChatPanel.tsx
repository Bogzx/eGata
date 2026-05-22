"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { ChatMessage, VoicePreferences } from "@/lib/types";

type Props = {
  documentId: string;
  messages: ChatMessage[];
  onMessagesChange: (m: ChatMessage[]) => void;
  preferences?: VoicePreferences;
};

export function ChatPanel({
  documentId,
  messages,
  onMessagesChange,
  preferences,
}: Props) {
  const [draft, setDraft] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    setError(null);
    const userMsg: ChatMessage = { role: "user", text };
    const next = [...messages, userMsg];
    onMessagesChange(next);
    setDraft("");
    try {
      const r = await api.chat({
        conversation_id: conversationId,
        document_id: documentId,
        message: text,
        preferences,
      });
      setConversationId(r.conversation_id);
      const agentMsg: ChatMessage = {
        role: "agent",
        text: r.message,
        tool_calls: r.tool_calls,
      };
      onMessagesChange([...next, agentMsg]);
    } catch (e) {
      if (e instanceof ApiError) setError(t("common.error"));
      else throw e;
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex h-full flex-col" aria-label="Chat cu asistentul">
      <ol
        className="flex-1 space-y-3 overflow-auto p-4"
        aria-live="polite"
      >
        {messages.map((m, i) => (
          <li
            key={i}
            className={
              m.role === "agent"
                ? "rounded-lg bg-muted px-4 py-3 text-sm"
                : "ml-12 rounded-lg bg-primary px-4 py-3 text-sm text-primary-foreground"
            }
          >
            <p className="whitespace-pre-wrap">{m.text}</p>
            {m.tool_calls && m.tool_calls.length > 0 ? (
              <ul className="mt-2 space-y-1 text-xs opacity-70">
                {m.tool_calls.map((tc, j) => (
                  <li key={j}>
                    <code>
                      {tc.name}({JSON.stringify(tc.arguments)})
                    </code>
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ol>
      {error ? (
        <p role="alert" className="px-4 text-sm text-destructive">
          {error}
        </p>
      ) : null}
      <form
        className="flex gap-2 border-t p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={2}
          placeholder={t("chat.input_placeholder")}
          aria-label="Mesaj nou"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
        />
        <Button type="submit" disabled={sending || draft.trim().length === 0}>
          {sending ? t("common.loading") : t("chat.send")}
        </Button>
      </form>
    </div>
  );
}
