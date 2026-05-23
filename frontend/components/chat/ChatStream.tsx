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

function bubbleClass(m: Message): string {
  if (m.role === "user") {
    return "ml-12 rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground";
  }
  if (m.role === "system") {
    return "rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive";
  }
  return "rounded-lg bg-muted px-4 py-2 text-sm";
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

export function ChatStream({ onWidgetSubmit }: Props) {
  const messages = useSessionStore((s) => s.messages);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  return (
    <ol
      className="flex-1 space-y-2 overflow-y-auto px-3 py-2"
      aria-live="polite"
      aria-label="Conversație"
    >
      {messages.map((m) => (
        <li key={m.id} className={bubbleClass(m)}>
          <p className="whitespace-pre-wrap">{cleanText(m.text)}</p>
          {m.role === "agent" && m.widgets
            ? m.widgets.map((w) => (
                <div key={w.widgetId} className="mt-2">
                  {renderWidget(w, (v) => onWidgetSubmit(w, v))}
                </div>
              ))
            : null}
        </li>
      ))}
      <div ref={endRef} aria-hidden />
    </ol>
  );
}
