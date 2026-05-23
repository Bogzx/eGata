"use client";

import { type ReactNode } from "react";
import { useAccessibilityClasses } from "@/lib/accessibilityStore";
import { t } from "@/lib/i18n";

type Props = {
  children: ReactNode;
};

export function KioskShell({ children }: Props) {
  useAccessibilityClasses();

  return (
    <div className="fixed inset-0 flex flex-col bg-background text-foreground">
      <header className="flex items-center border-b px-4 py-3 sm:px-8 sm:py-4">
        <h1 className="text-xl sm:text-3xl font-bold">{t("app.title")}</h1>
      </header>
      <main className="flex-1 overflow-auto px-4 py-4 sm:px-8 sm:py-8 [&_button]:min-h-[3rem] [&_input]:min-h-[3rem]">
        {children}
      </main>
    </div>
  );
}
