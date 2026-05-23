"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoginButton } from "@/components/LoginButton";
import { ModulGhiseuToggle } from "@/components/ModulGhiseuToggle";
import { MrzScanner } from "@/components/MrzScanner";
import { KioskShell } from "@/components/KioskShell";
import { useKioskMode } from "@/lib/kioskMode";
import { api, ApiError } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { LoginChallenge } from "@/lib/types";
import type { MrzResult } from "@/lib/mrz";

function nav(router: ReturnType<typeof useRouter>, c: LoginChallenge) {
  const params = new URLSearchParams({
    challenge_id: c.challenge_id,
    phone_hint: c.phone_hint,
  });
  router.push(`/login/otp?${params.toString()}`);
}

function LoginCard({ onChallenge }: { onChallenge: (c: LoginChallenge) => void }) {
  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>{t("login.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">{t("login.subtitle")}</p>
        <ModulGhiseuToggle />
        <LoginButton onChallenge={onChallenge} />
      </CardContent>
    </Card>
  );
}

function KioskLogin() {
  const router = useRouter();
  const [path, setPath] = useState<"chooser" | "roeid" | "mrz">("chooser");
  const [error, setError] = useState<string | null>(null);

  async function submitMrz(r: MrzResult) {
    setError(null);
    try {
      const c = await api.loginMrz({ cnp: r.cnp, nume: r.nume, prenume: r.prenume });
      nav(router, c);
    } catch (e) {
      if (e instanceof ApiError) setError(t("common.error"));
      else throw e;
    }
  }

  return (
    <KioskShell>
      <div className="mx-auto max-w-3xl space-y-8">
        {path === "chooser" ? (
          <div className="space-y-6">
            <ModulGhiseuToggle />
            <div className="grid gap-4 sm:grid-cols-2">
              <Button
                size="xl"
                className="h-24 text-xl sm:h-32 sm:text-2xl"
                onClick={() => setPath("roeid")}
              >
                {t("login.roeid_button")}
              </Button>
              <Button
                size="xl"
                variant="outline"
                className="h-24 text-xl sm:h-32 sm:text-2xl"
                onClick={() => setPath("mrz")}
              >
                {t("login.scan_id_button")}
              </Button>
            </div>
          </div>
        ) : null}

        {path === "roeid" ? <LoginCard onChallenge={(c) => nav(router, c)} /> : null}
        {path === "mrz" ? <MrzScanner onParsed={submitMrz} /> : null}
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}

        {path !== "chooser" ? (
          <Button variant="ghost" onClick={() => setPath("chooser")}>
            {t("common.back")}
          </Button>
        ) : null}
      </div>
    </KioskShell>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const isKiosk = useKioskMode();
  if (isKiosk) return <KioskLogin />;
  return (
    <main className="flex min-h-screen items-center justify-center p-4 sm:p-6">
      <LoginCard onChallenge={(c) => nav(router, c)} />
    </main>
  );
}
