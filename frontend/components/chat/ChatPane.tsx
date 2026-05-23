"use client";

import type { WidgetSpec } from "@/lib/types";
import { ChatStream } from "./ChatStream";
import { Composer } from "./Composer";

type Props = {
  onWidgetSubmit: (spec: WidgetSpec, value: string) => void;
  onSendText: (text: string) => Promise<void> | void;
  onStartVoice: () => Promise<void> | void;
  onStopVoice: () => void;
};

export function ChatPane({
  onWidgetSubmit,
  onSendText,
  onStartVoice,
  onStopVoice,
}: Props) {
  return (
    <section
      className="flex h-full min-h-0 flex-col"
      aria-label="Chat cu asistentul"
    >
      <ChatStream onWidgetSubmit={onWidgetSubmit} />
      <Composer
        onSendText={onSendText}
        onStartVoice={onStartVoice}
        onStopVoice={onStopVoice}
      />
    </section>
  );
}
