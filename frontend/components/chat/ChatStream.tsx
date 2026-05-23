"use client";

import { useEffect, useRef } from "react";
import { useSessionStore } from "@/lib/sessionStore";
import type { Message, WidgetSpec } from "@/lib/types";
import { WIDGET_REGISTRY } from "./widgets";

const THINKING_RE =
  /<(?:thinking|scratchpad|reasoning)>[\s\S]*?<\/(?:thinking|scratchpad|reasoning)>/gi;

function cleanText(t: string): string {
  return t.replace(THINKING_RE, "").trim();
}

type Props = {
  onWidgetSubmit: (spec: WidgetSpec, value: string) => void;
};

type WidgetComponent<T extends WidgetSpec["type"]> = React.ComponentType<{
  spec: Extract<WidgetSpec, { type: T }>;
  onSubmit: (v: string) => void;
}>;

function renderWidget(w: WidgetSpec, onSubmit: (v: string) => void) {
  if (w.type === "choice") {
    const Comp = WIDGET_REGISTRY.choice as WidgetComponent<"choice">;
    return <Comp spec={w} onSubmit={onSubmit} />;
  }
  if (w.type === "confirm") {
    const Comp = WIDGET_REGISTRY.confirm as WidgetComponent<"confirm">;
    return <Comp spec={w} onSubmit={onSubmit} />;
  }
  const Comp = WIDGET_REGISTRY.date as WidgetComponent<"date">;
  return <Comp spec={w} onSubmit={onSubmit} />;
}

function StreamingCaret() {
  return (
    <span aria-hidden="true" className="ml-0.5 inline-block w-[1ch] animate-pulse">
      |
    </span>
  );
}

function MsgUser({ text, streaming }: { text: string; streaming?: boolean }) {
  return (
    <div className="msg msg-user">
      <span className="sr-only">Tu:</span>
      <div className="bubble bubble-user">
        {text}
        {streaming ? <StreamingCaret /> : null}
      </div>
    </div>
  );
}

function MsgAgent({
  text,
  widgets,
  streaming,
  onWidgetSubmit,
}: {
  text: string;
  widgets?: WidgetSpec[];
  streaming?: boolean;
  onWidgetSubmit: (w: WidgetSpec, v: string) => void;
}) {
  return (
    <div className="msg msg-agent">
      <div className="agent-avatar" aria-hidden="true">
        <svg
          viewBox="0 0 24 24"
          width="14"
          height="14"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
        >
          <path d="M12 2v3M12 19v3M4 12H1M23 12h-3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2" />
          <circle cx="12" cy="12" r="4" />
        </svg>
      </div>
      <div className="bubble bubble-agent">
        <div className="bubble-name" aria-hidden="true">
          CivicAI
        </div>
        <span className="sr-only">CivicAI:</span>
        <div>
          {text}
          {streaming ? <StreamingCaret /> : null}
        </div>
        {widgets && widgets.length > 0 ? (
          <div className="widget">
            {widgets.map((w) => (
              <div key={w.widgetId}>
                {renderWidget(w, (v) => onWidgetSubmit(w, v))}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function MsgSystem({ text }: { text: string }) {
  return (
    <div className="msg msg-system" role="status">
      <div className="bubble">{text}</div>
    </div>
  );
}

export function ChatStream({ onWidgetSubmit }: Props) {
  const messages = useSessionStore((s) => s.messages);
  const sending = useSessionStore((s) => s.sending);
  const pendingUser = useSessionStore((s) => s.pendingUser);
  const pendingAgent = useSessionStore((s) => s.pendingAgent);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending, pendingUser?.text, pendingAgent?.text]);

  const showTyping =
    sending && !(pendingAgent && pendingAgent.text.trim().length > 0);

  return (
    <ol
      className="chat-stream"
      role="log"
      aria-live="polite"
      aria-relevant="additions"
      aria-label="Conversație cu asistentul CivicAI"
    >
      {messages.map((m: Message) => (
        <li key={m.id}>
          {m.role === "user" ? (
            <MsgUser text={cleanText(m.text)} />
          ) : m.role === "agent" ? (
            <MsgAgent
              text={cleanText(m.text)}
              widgets={m.widgets}
              onWidgetSubmit={onWidgetSubmit}
            />
          ) : (
            <MsgSystem text={cleanText(m.text)} />
          )}
        </li>
      ))}

      {pendingUser && pendingUser.text.trim() ? (
        <li
          key={`pending-user-${pendingUser.id}`}
          aria-label="Mesajul tău se transcrie"
        >
          <MsgUser text={cleanText(pendingUser.text)} streaming />
        </li>
      ) : null}

      {pendingAgent && pendingAgent.text.trim() ? (
        <li
          key={`pending-agent-${pendingAgent.id}`}
          aria-label="Asistentul răspunde"
        >
          <MsgAgent
            text={cleanText(pendingAgent.text)}
            streaming
            onWidgetSubmit={onWidgetSubmit}
          />
        </li>
      ) : null}

      {showTyping ? (
        <li aria-label="Asistentul scrie">
          <div className="msg msg-agent">
            <div className="agent-avatar" aria-hidden="true">
              <svg
                viewBox="0 0 24 24"
                width="14"
                height="14"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.4"
                strokeLinecap="round"
              >
                <circle cx="12" cy="12" r="4" />
              </svg>
            </div>
            <div className="bubble bubble-agent typing" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <span className="sr-only">Asistentul scrie un răspuns…</span>
          </div>
        </li>
      ) : null}

      <div ref={endRef} aria-hidden />
    </ol>
  );
}
