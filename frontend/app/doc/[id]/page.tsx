"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AuditTimeline } from "@/components/AuditTimeline";
import { FormPreview } from "@/components/FormPreview";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getSession } from "@/lib/session";
import type { Document, LedgerResponse, Procedure } from "@/lib/types";

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [doc, setDoc] = useState<Document | null>(null);
  const [procedure, setProcedure] = useState<Procedure | null>(null);
  const [ledger, setLedger] = useState<LedgerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined" && !getSession()) router.replace("/login");
  }, [router]);

  useEffect(() => {
    if (!params.id) return;
    void (async () => {
      try {
        const d = await api.getDocument(params.id);
        const [p, l] = await Promise.all([
          api.getProcedure(d.procedure_id),
          api.getDocumentLedger(d.id),
        ]);
        setDoc(d);
        setProcedure(p);
        setLedger(l);
      } catch {
        setError(t("common.error"));
      }
    })();
  }, [params.id]);

  if (error)
    return (
      <p role="alert" className="p-6 text-destructive">
        {error}
      </p>
    );
  if (!doc || !procedure || !ledger)
    return <p className="p-6 text-muted-foreground">{t("common.loading")}</p>;

  return (
    <main className="mx-auto grid max-w-5xl gap-6 p-6 md:grid-cols-[2fr_3fr]">
      <div className="space-y-4">
        <Card>
          <CardContent className="space-y-3 p-4">
            <h1 className="text-2xl font-bold">{procedure.title}</h1>
            <p className="text-sm text-muted-foreground">
              Stare: {doc.status === "finalized" ? "Trimisă" : "În lucru"}
              {doc.ref_number
                ? ` · ${t("doc.ref_number", { ref: doc.ref_number })}`
                : ""}
            </p>
            <div className="flex flex-wrap gap-2">
              {doc.pdf_url ? (
                <a href={doc.pdf_url} target="_blank" rel="noreferrer">
                  <Button variant="outline">{t("doc.download_pdf")}</Button>
                </a>
              ) : null}
              {doc.status !== "finalized" ? (
                <Link href={`/req/${doc.id}`}>
                  <Button>{t("common.continue")}</Button>
                </Link>
              ) : null}
              <Link href="/home">
                <Button variant="ghost">{t("common.back")}</Button>
              </Link>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <AuditTimeline ledger={ledger} />
          </CardContent>
        </Card>
      </div>
      <FormPreview procedure={procedure} values={doc.fields} />
    </main>
  );
}
