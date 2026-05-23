"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { WidgetSpec } from "@/lib/types";

type Props = {
  spec: Extract<WidgetSpec, { type: "confirm" }>;
  onSubmit: (value: string) => void;
};

export function ConfirmWidget({ spec, onSubmit }: Props) {
  const [pickedLocal, setPickedLocal] = useState<string | null>(null);
  const picked = spec.submittedValue ?? pickedLocal;
  const isDisabled = picked !== null && picked !== undefined;
  function pick(v: "Da" | "Nu") {
    if (isDisabled) return;
    setPickedLocal(v);
    onSubmit(v);
  }
  return (
    <div
      className="rounded-lg border bg-background/60 p-3"
      aria-label={spec.question}
    >
      <p className="mb-2 text-sm font-medium">{spec.question}</p>
      <div className="flex gap-2">
        <Button
          type="button"
          size="sm"
          variant={picked === "Da" ? "default" : undefined}
          disabled={isDisabled}
          onClick={() => pick("Da")}
        >
          Da
        </Button>
        <Button
          type="button"
          variant={picked === "Nu" ? "default" : "outline"}
          size="sm"
          disabled={isDisabled}
          onClick={() => pick("Nu")}
        >
          Nu
        </Button>
      </div>
    </div>
  );
}
