"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useVoiceAgent } from "@/lib/useVoiceAgent";
import type { Procedure, VoicePreferences } from "@/lib/types";

type Props = {
  procedure: Procedure;
  documentId: string;
  values: Record<string, unknown>;
  onPatch: (delta: Record<string, unknown>) => void | Promise<void>;
  preferences?: VoicePreferences;
};

export function VocalFillFlow({ procedure, documentId, preferences }: Props) {
  void procedure;
  const agent = useVoiceAgent();
  const [transcript, setTranscript] = useState("");
  const [agentMsg, setAgentMsg] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setError(null);
    try {
      await agent.start({
        documentId,
        preferences,
        onAgentMessage: (m) => setAgentMsg(m),
        onTranscript: (t) => setTranscript(t),
      });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => () => agent.stop(), [agent]);

  return (
    <div className="space-y-4 rounded-lg border bg-muted/30 p-4">
      <div className="flex items-center gap-3">
        <Button onClick={start} disabled={agent.state !== "idle"} size="lg">
          {agent.state === "idle" ? "Pornește conversația vocală" : agent.state}
        </Button>
        <span className="text-xs text-muted-foreground">
          Stare: {agent.state}
        </span>
      </div>

      <section aria-live="polite" className="space-y-2">
        <div>
          <p className="text-xs font-medium uppercase text-muted-foreground">Tu</p>
          <p className="rounded bg-background p-3 text-sm">
            {transcript || "..."}
          </p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase text-muted-foreground">
            Asistent
          </p>
          <p className="rounded bg-background p-3 text-sm">{agentMsg || "..."}</p>
        </div>
      </section>

      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error} — folosește butoanele de text până la activare.
        </p>
      ) : null}
    </div>
  );
}
