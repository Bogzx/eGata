"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { WidgetSpec } from "@/lib/types";

type Props = {
  spec: Extract<WidgetSpec, { type: "choice" }>;
  onSubmit: (value: string) => void;
};

export function ChoiceWidget({ spec, onSubmit }: Props) {
  const [picked, setPicked] = useState<string | null>(null);
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
            variant={picked === opt ? "default" : "outline"}
            size="sm"
            disabled={picked !== null}
            onClick={() => {
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
