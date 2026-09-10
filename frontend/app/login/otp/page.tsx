"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OtpInput } from "@/components/OtpInput";
import { api, ApiError } from "@/lib/api";
import { setSession } from "@/lib/session";
import { getGhiseuPref } from "@/lib/ghiseuPref";
import { t } from "@/lib/i18n";

function OtpForm() {
  const params = useSearchParams();
  const router = useRouter();
  const challengeId = params.get("challenge_id") ?? "";
  const phoneHint = params.get("phone_hint") ?? "";
  const [error, setError] = useState<string | null>(null);

  async function submit(code: string) {
    setError(null);
    try {
      const session = await api.otp({ challenge_id: challengeId, code });
      setSession(session);
      router.push(getGhiseuPref() ? "/ghiseu" : "/");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setError(t("otp.error"));
      } else {
        setError(t("common.error"));
      }
    }
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>{t("otp.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {t("otp.phone_hint", { phone_hint: phoneHint })}
        </p>
        <OtpInput onComplete={submit} error={error} />
      </CardContent>
    </Card>
  );
}

export default function OtpPage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-4 sm:p-6">
      <Suspense fallback={null}>
        <OtpForm />
      </Suspense>
    </main>
  );
}
