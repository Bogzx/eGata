"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { WidgetSpec } from "@/lib/types";

type Props = {
  spec: Extract<WidgetSpec, { type: "choice" }>;
  onSubmit: (value: string) => void;
};

export function ChoiceWidget({ spec, onSubmit }: Props) {
  // submittedValue is persisted in the store. Local state guards against
  // double-click between submit and the next render.
  const [picked, setPicked] = useState<string | null>(null);
  const submitted = spec.submittedValue ?? picked;
  const isDisabled = submitted !== null && submitted !== undefined;
  return (
    <div
      className="rounded-lg border bg-background/60 p-3"
      aria-label={spec.question}
    >
      <p className="mb-2 text-sm font-medium">{spec.question}</p>
      <div className="flex flex-wrap gap-2">
        {spec.options.map((opt) => (
          <Button
            key={opt}
            type="button"
            variant={submitted === opt ? "default" : "outline"}
            size="sm"
            disabled={isDisabled}
            onClick={() => {
              if (isDisabled) return;
              setPicked(opt);
              onSubmit(opt);
            }}
          >
            {opt}
          </Button>
        ))}
      </div>
    </div>
  );
}
