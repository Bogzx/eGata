"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { WidgetSpec } from "@/lib/types";

type Props = {
  spec: Extract<WidgetSpec, { type: "date" }>;
  onSubmit: (value: string) => void;
};

export function DateWidget({ spec, onSubmit }: Props) {
  const [value, setValue] = useState("");
  const [done, setDone] = useState(false);
  return (
    <div
      className="rounded-lg border bg-background/60 p-3"
      aria-label={spec.question}
    >
      <p className="mb-2 text-sm font-medium">{spec.question}</p>
      <div className="flex gap-2">
        <Input
          type="date"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          disabled={done}
          className="max-w-[180px]"
        />
        <Button
          type="button"
          size="sm"
          disabled={done || !value}
          onClick={() => {
            setDone(true);
            onSubmit(value);
          }}
        >
          OK
        </Button>
      </div>
    </div>
  );
}
