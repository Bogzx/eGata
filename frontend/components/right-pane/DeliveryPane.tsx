"use client";

import { useState } from "react";
import { Printer, Save, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";

export function DeliveryPane() {
  const document = useSessionStore((s) => s.document);
  const transition = useSessionStore((s) => s.transitionRightPane);
  const [busy, setBusy] = useState<null | "save" | "send" | "print">(null);

  if (!document) return null;

  async function pick(channel: "save" | "send" | "print") {
    const doc = useSessionStore.getState().document;
    if (!doc) return;
    setBusy(channel);
    try {
      const updated = await api.deliverDocument(doc.id, channel);
      useSessionStore.setState({ document: updated });
      if (updated.ref_number) {
        transition({ kind: "done", refNumber: updated.ref_number });
      }
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col items-stretch gap-3 p-8">
      <h2 className="mb-2 text-xl font-semibold">
        Cum vrei să primești cererea?
      </h2>
      <Button
        size="lg"
        onClick={() => void pick("send")}
        disabled={busy !== null}
      >
        <Send className="mr-2" size={16} /> Trimite la primărie
      </Button>
      <Button
        size="lg"
        variant="outline"
        onClick={() => void pick("save")}
        disabled={busy !== null}
      >
        <Save className="mr-2" size={16} /> Salvează în contul meu
      </Button>
      <Button
        size="lg"
        variant="outline"
        onClick={() => void pick("print")}
        disabled={busy !== null}
      >
        <Printer className="mr-2" size={16} /> Tipărește acum
      </Button>
    </div>
  );
}
