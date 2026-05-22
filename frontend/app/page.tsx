"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { getSession } from "@/lib/session";
import { t } from "@/lib/i18n";

export default function LandingPage() {
  const router = useRouter();

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (getSession()) router.replace("/home");
  }, [router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-8">
      <div className="max-w-2xl text-center">
        <h1 className="text-5xl font-bold tracking-tight">{t("app.title")}</h1>
        <p className="mt-4 text-xl text-muted-foreground">{t("app.tagline")}</p>
      </div>
      <Button size="lg" onClick={() => router.push("/login")}>
        Intră în cont
      </Button>
    </main>
  );
}
