"use client";

import { type ReactNode, useState } from "react";
import { Button } from "@/components/ui/button";
import { AccessibilityToggles } from "@/components/AccessibilityToggles";
import { useLargeTextClass } from "@/lib/accessibilityStore";
import { t } from "@/lib/i18n";

type Props = {
  children: ReactNode;
};

export function KioskShell({ children }: Props) {
  useLargeTextClass();
  const [accessibilityOpen, setAccessibilityOpen] = useState(false);

  return (
    <div className="fixed inset-0 flex flex-col bg-background text-foreground">
      <header className="flex items-center justify-between border-b px-8 py-4">
        <h1 className="text-3xl font-bold">{t("app.title")}</h1>
        <Button
          variant="outline"
          size="lg"
          className="text-lg"
          onClick={() => setAccessibilityOpen((v) => !v)}
          aria-expanded={accessibilityOpen}
        >
          {t("kiosk.accessibility_corner")}
        </Button>
      </header>
      {accessibilityOpen ? (
        <section className="border-b bg-muted/30 px-8 py-6">
          <AccessibilityToggles />
        </section>
      ) : null}
      <main className="flex-1 overflow-auto px-8 py-8 [&_button]:min-h-[3rem] [&_input]:min-h-[3rem]">
        {children}
      </main>
    </div>
  );
}
