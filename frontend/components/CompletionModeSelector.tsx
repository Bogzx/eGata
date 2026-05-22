"use client";

import { Button } from "@/components/ui/button";
import { t } from "@/lib/i18n";
import type { CompletionMode } from "@/lib/completionMode";

type Props = {
  current: CompletionMode | null;
  onChange: (mode: CompletionMode) => void;
  variant?: "initial" | "switcher";
};

const MODES: CompletionMode[] = ["manual", "guided", "voice"];
const LABEL: Record<CompletionMode, "mode.manual" | "mode.guided" | "mode.voice"> = {
  manual: "mode.manual",
  guided: "mode.guided",
  voice: "mode.voice",
};

export function CompletionModeSelector({ current, onChange, variant = "initial" }: Props) {
  return (
    <div
      role="radiogroup"
      aria-label={variant === "switcher" ? t("mode.switch") : "Mod de completare"}
      className={
        variant === "switcher" ? "flex gap-2" : "grid grid-cols-1 gap-3 sm:grid-cols-3"
      }
    >
      {MODES.map((m) => {
        const isActive = current === m;
        return (
          <Button
            key={m}
            role="radio"
            aria-checked={isActive}
            variant={isActive ? "default" : "outline"}
            size={variant === "switcher" ? "sm" : "lg"}
            className={variant === "initial" ? "h-20 text-lg" : ""}
            onClick={() => onChange(m)}
          >
            {t(LABEL[m])}
          </Button>
        );
      })}
    </div>
  );
}
