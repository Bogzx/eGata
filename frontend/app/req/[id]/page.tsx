"use client";

import { useEffect, useMemo, useReducer, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ChatPanel } from "@/components/ChatPanel";
import { CompletionModeSelector } from "@/components/CompletionModeSelector";
import { FormPreview } from "@/components/FormPreview";
import { GuidedFillFlow } from "@/components/GuidedFillFlow";
import { KioskShell } from "@/components/KioskShell";
import { ManualFillForm } from "@/components/ManualFillForm";
import { VocalFillFlow } from "@/components/VocalFillFlow";
import { useAccessibilityPrefs, useLargeTextClass } from "@/lib/accessibilityStore";
import { api } from "@/lib/api";
import {
  loadPersistedMode,
  persistMode,
  reduceCompletionMode,
  type CompletionMode,
} from "@/lib/completionMode";
import { getVariant, t } from "@/lib/i18n";
import { useKioskMode } from "@/lib/kioskMode";
import { getSession } from "@/lib/session";
import type { ChatMessage, Citizen, Document, Procedure } from "@/lib/types";

function isFilled(v: unknown): boolean {
  return v !== undefined && v !== null && String(v).length > 0;
}

function buildAutoFillSummary(
  procedure: Procedure,
  values: Record<string, unknown>,
): {
  filled: { label: string; value: string }[];
  missingCount: number;
} {
  const filled: { label: string; value: string }[] = [];
  let missing = 0;
  for (const f of procedure.fields) {
    const v = values[f.name];
    if (isFilled(v)) filled.push({ label: f.label, value: String(v) });
    else if (f.required) missing += 1;
  }
  return { filled, missingCount: missing };
}

export default function ProcedureFlowPage() {
  useLargeTextClass();
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const docId = params.id;
  const isKiosk = useKioskMode();
  const simpleLanguage = useAccessibilityPrefs((s) => s.simpleLanguage);
  const voiceOnly = useAccessibilityPrefs((s) => s.voiceOnly);

  const [doc, setDoc] = useState<Document | null>(null);
  const [procedure, setProcedure] = useState<Procedure | null>(null);
  const [citizen, setCitizen] = useState<Citizen | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeField, setActiveField] = useState<string | undefined>(undefined);
  const [delivering, setDelivering] = useState<"save" | "send" | "print" | null>(null);
  const [refNumber, setRefNumber] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [modeState, dispatchMode] = useReducer(reduceCompletionMode, { mode: null });

  useEffect(() => {
    if (typeof window !== "undefined" && !getSession()) router.replace("/login");
  }, [router]);

  useEffect(() => {
    if (!docId) return;
    void (async () => {
      try {
        const d = await api.getDocument(docId);
        const p = await api.getProcedure(d.procedure_id);
        const c = await api.getCitizenMe();
        setDoc(d);
        setProcedure(p);
        setCitizen(c);
        if (d.ref_number) setRefNumber(d.ref_number);
        const persisted = loadPersistedMode(d.id);
        if (persisted) dispatchMode({ type: "CHOOSE", mode: persisted });
      } catch {
        setError(t("common.error"));
      }
    })();
  }, [docId]);

  useEffect(() => {
    if (doc) persistMode(doc.id, modeState.mode);
  }, [doc, modeState.mode]);

  // Auto-select voice mode for citizens with voice_only accessibility preference,
  // unless they've already picked a different mode (persisted choice wins).
  useEffect(() => {
    if (!doc || modeState.mode) return;
    if (voiceOnly || citizen?.attributes.accessibility?.voice_only) {
      dispatchMode({ type: "CHOOSE", mode: "voice" });
    }
  }, [doc, modeState.mode, voiceOnly, citizen]);

  const variant = useMemo(
    () => (simpleLanguage ? "simple" : getVariant(citizen?.attributes)),
    [citizen, simpleLanguage],
  );

  if (error)
    return (
      <p role="alert" className="p-6 text-destructive">
        {error}
      </p>
    );
  if (!doc || !procedure || !citizen)
    return <p className="p-6 text-muted-foreground">{t("common.loading")}</p>;

  const summary = buildAutoFillSummary(procedure, doc.fields);
  const allFilled =
    procedure.fields.filter((f) => f.required && !isFilled(doc.fields[f.name]))
      .length === 0;

  async function patchFields(delta: Record<string, unknown>) {
    if (!doc) return;
    const updated = await api.patchDocumentFields(doc.id, delta);
    setDoc(updated);
  }

  async function deliver(channel: "save" | "send" | "print") {
    if (!doc) return;
    setDelivering(channel);
    try {
      await api.generatePdf(doc.id);
      const updated = await api.deliverDocument(doc.id, channel);
      setDoc(updated);
      if (updated.ref_number) setRefNumber(updated.ref_number);
    } catch {
      setError(t("common.error"));
    } finally {
      setDelivering(null);
    }
  }

  const completionPane = (() => {
    if (!modeState.mode) {
      return (
        <div className="space-y-4">
          <p>{t("req.auto_filled_intro", {}, variant)}</p>
          <ul className="space-y-1 text-sm">
            {summary.filled.map((f) => (
              <li key={f.label}>
                <span aria-hidden>✓ </span>
                <strong>{f.label}:</strong> {f.value}
              </li>
            ))}
          </ul>
          <p>
            {t("req.more_needed", { count: summary.missingCount }, variant)}
          </p>
          <CompletionModeSelector
            current={null}
            onChange={(m) => dispatchMode({ type: "CHOOSE", mode: m })}
          />
        </div>
      );
    }
    if (modeState.mode === "manual") {
      return (
        <ManualFillForm
          procedure={procedure}
          values={doc.fields}
          onPatch={patchFields}
        />
      );
    }
    if (modeState.mode === "guided") {
      return (
        <GuidedFillFlow
          procedure={procedure}
          values={doc.fields}
          onPatch={patchFields}
          onActiveFieldChange={setActiveField}
        />
      );
    }
    return (
      <VocalFillFlow
        procedure={procedure}
        documentId={doc.id}
        values={doc.fields}
        onPatch={patchFields}
        preferences={{
          simple_language:
            simpleLanguage || citizen.attributes.accessibility?.simple_language,
          voice_only:
            voiceOnly || citizen.attributes.accessibility?.voice_only,
        }}
        onTextFallback={() => dispatchMode({ type: "SWITCH", mode: "guided" })}
      />
    );
  })();

  const body = (
    <div className="grid h-[calc(100vh-3rem)] gap-4 p-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="flex flex-col gap-4 overflow-auto">
        <Card>
          <CardContent className="space-y-2 p-4">
            <h1 className="text-2xl font-bold">
              {t("req.title", { title: procedure.title })}
            </h1>
            {modeState.mode ? (
              <CompletionModeSelector
                current={modeState.mode}
                variant="switcher"
                onChange={(m) => dispatchMode({ type: "SWITCH", mode: m })}
              />
            ) : null}
          </CardContent>
        </Card>

        <Card className="flex-1">
          <CardContent className="space-y-4 p-4">{completionPane}</CardContent>
        </Card>

        <Card className="h-[40%] min-h-[16rem]">
          <CardContent className="h-full p-0">
            <ChatPanel
              documentId={doc.id}
              messages={messages}
              onMessagesChange={setMessages}
              preferences={{
                simple_language:
                  simpleLanguage || citizen.attributes.accessibility?.simple_language,
                voice_only:
                  voiceOnly || citizen.attributes.accessibility?.voice_only,
              }}
              onDocumentSideEffect={async (toolName) => {
                if (toolName === "set_field" || toolName === "deliver" || toolName === "generate_pdf") {
                  try {
                    const fresh = await api.getDocument(doc.id);
                    setDoc(fresh);
                    if (fresh.ref_number) setRefNumber(fresh.ref_number);
                  } catch { /* swallow */ }
                }
              }}
            />
          </CardContent>
        </Card>

        {allFilled && doc.status !== "finalized" ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-wrap gap-2"
          >
            <Button
              onClick={() => void deliver("save")}
              disabled={delivering !== null}
              variant="outline"
            >
              {t("delivery.save")}
            </Button>
            <Button
              onClick={() => void deliver("send")}
              disabled={delivering !== null}
            >
              {t("delivery.send")}
            </Button>
            <Button
              onClick={() => void deliver("print")}
              disabled={delivering !== null}
              variant="outline"
            >
              {t("delivery.print")}
            </Button>
          </motion.div>
        ) : null}

        {refNumber ? (
          <Card className="border-green-600">
            <CardContent className="p-4">
              <p className="font-medium">
                {t("delivery.confirmation", { ref: refNumber }, variant)}
              </p>
            </CardContent>
          </Card>
        ) : null}
      </div>

      <div className="overflow-auto">
        <FormPreview
          procedure={procedure}
          values={doc.fields}
          activeField={activeField}
        />
      </div>
    </div>
  );

  return isKiosk ? <KioskShell>{body}</KioskShell> : <main>{body}</main>;
}
