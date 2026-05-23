"use client";

import { useState } from "react";
import { Mic, MicOff, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useSessionStore } from "@/lib/sessionStore";

type Props = {
  onSendText: (text: string) => Promise<void> | void;
  onStartVoice: () => Promise<void> | void;
  onStopVoice: () => void;
};

export function Composer({ onSendText, onStartVoice, onStopVoice }: Props) {
  const [draft, setDraft] = useState("");
  const sending = useSessionStore((s) => s.sending);
  const voiceStatus = useSessionStore((s) => s.voiceStatus);

  const voiceActive =
    voiceStatus === "listening" ||
    voiceStatus === "speaking" ||
    voiceStatus === "connecting";

  async function submit() {
    const t = draft.trim();
    if (!t || sending) return;
    setDraft("");
    await onSendText(t);
  }

  function micClick() {
    if (voiceActive) onStopVoice();
    else void onStartVoice();
  }

  return (
    <form
      className="flex items-end gap-2 border-t p-2"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <Textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={1}
        placeholder="Scrie aici sau apasă pe microfon..."
        aria-label="Mesaj nou"
        disabled={sending}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            void submit();
          }
        }}
        className="min-h-[40px] flex-1 resize-none"
      />
      <Button
        type="button"
        variant={voiceActive ? "default" : "outline"}
        size="icon"
        onClick={micClick}
        aria-label={voiceActive ? "Oprește microfonul" : "Pornește microfonul"}
        title={voiceActive ? "Oprește microfonul" : "Pornește microfonul"}
        className={voiceActive ? "bg-red-600 text-white hover:bg-red-700" : ""}
      >
        {voiceActive ? <MicOff size={18} /> : <Mic size={18} />}
      </Button>
      <Button
        type="submit"
        size="icon"
        disabled={sending || draft.trim().length === 0}
        aria-label="Trimite"
      >
        <Send size={18} />
      </Button>
    </form>
  );
}
