"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { DocumentList } from "@/components/DocumentList";
import { ReminderCard } from "@/components/ReminderCard";
import { KioskShell } from "@/components/KioskShell";
import { useAccessibilityPrefs, useLargeTextClass } from "@/lib/accessibilityStore";
import { api } from "@/lib/api";
import { getVariant, t } from "@/lib/i18n";
import { useKioskMode } from "@/lib/kioskMode";
import { getSession } from "@/lib/session";
import type { Citizen, Document, Procedure, Reminder } from "@/lib/types";

function HomeBody({
  citizen,
  documents,
  procedures,
  reminders,
}: {
  citizen: Citizen;
  documents: Document[];
  procedures: Procedure[];
  reminders: Reminder[];
}) {
  const simpleLanguage = useAccessibilityPrefs((s) => s.simpleLanguage);
  const variant = simpleLanguage ? "simple" : getVariant(citizen.attributes);
  return (
    <div className="mx-auto max-w-3xl space-y-8 p-6">
      <h1 className="text-3xl font-bold">
        {t("home.greeting", { prenume: citizen.prenume }, variant)}
      </h1>

      <section aria-labelledby="reminders-heading" className="space-y-3">
        <h2 id="reminders-heading" className="text-xl font-semibold">
          {t("home.recommended_title", {}, variant)}
        </h2>
        <div className="space-y-3">
          {reminders.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("home.empty_reminders", {}, variant)}
            </p>
          ) : (
            reminders.map((r) => <ReminderCard key={r.id} reminder={r} />)
          )}
        </div>
      </section>

      <section aria-labelledby="documents-heading" className="space-y-3">
        <h2 id="documents-heading" className="text-xl font-semibold">
          {t("home.documents_title")}
        </h2>
        <DocumentList documents={documents} procedures={procedures} />
      </section>

      <div>
        <Link href="/req/new">
          <Button size="lg">+ {t("home.start_new")}</Button>
        </Link>
      </div>
    </div>
  );
}

export default function HomePage() {
  useLargeTextClass();
  const router = useRouter();
  const isKiosk = useKioskMode();
  const [citizen, setCitizen] = useState<Citizen | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [procedures, setProcedures] = useState<Procedure[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!getSession()) {
      router.replace("/login");
      return;
    }
    void (async () => {
      try {
        const [c, docs, procs, rs] = await Promise.all([
          api.getCitizenMe(),
          api.listDocuments(),
          api.listProcedures(),
          api.listReminders().catch(() => [] as Reminder[]),
        ]);
        setCitizen(c);
        setDocuments(docs);
        setProcedures(procs);
        setReminders(rs);
      } catch {
        setError(t("common.error"));
      }
    })();
  }, [router]);

  if (error)
    return (
      <p role="alert" className="p-6 text-destructive">
        {error}
      </p>
    );
  if (!citizen)
    return <p className="p-6 text-muted-foreground">{t("common.loading")}</p>;

  const body = (
    <HomeBody
      citizen={citizen}
      documents={documents}
      procedures={procedures}
      reminders={reminders}
    />
  );

  return isKiosk ? <KioskShell>{body}</KioskShell> : <main>{body}</main>;
}
