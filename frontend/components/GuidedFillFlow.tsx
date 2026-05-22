"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Procedure, ProcedureField } from "@/lib/types";

type Props = {
  procedure: Procedure;
  values: Record<string, unknown>;
  onPatch: (delta: Record<string, unknown>) => void | Promise<void>;
  onActiveFieldChange?: (name: string | undefined) => void;
};

function isFilled(v: unknown): boolean {
  return v !== undefined && v !== null && String(v).length > 0;
}

export function GuidedFillFlow({
  procedure,
  values,
  onPatch,
  onActiveFieldChange,
}: Props) {
  const remaining: ProcedureField[] = useMemo(
    () => procedure.fields.filter((f) => !isFilled(values[f.name])),
    [procedure.fields, values],
  );
  const current = remaining[0];
  const [draft, setDraft] = useState("");

  useEffect(() => {
    onActiveFieldChange?.(current?.name);
  }, [current, onActiveFieldChange]);

  if (!current) {
    return (
      <p className="text-sm text-muted-foreground">
        Toate câmpurile sunt completate.
      </p>
    );
  }

  async function submit() {
    if (!current) return;
    const value = draft.trim() || current.suggest_default || "";
    if (!value && current.required) return;
    await onPatch({ [current.name]: value });
    setDraft("");
  }

  return (
    <div className="space-y-4 rounded-lg border bg-muted/30 p-4">
      <p className="text-base">
        <strong>{current.label}</strong>
        {current.suggest_default ? (
          <span className="ml-2 text-sm text-muted-foreground">
            (sugestie: {current.suggest_default})
          </span>
        ) : null}
      </p>

      {current.options ? (
        <div className="flex flex-wrap gap-2">
          {current.options.map((opt) => (
            <Button
              key={opt}
              size="lg"
              variant="outline"
              onClick={async () => {
                await onPatch({ [current.name]: opt });
              }}
            >
              {opt}
            </Button>
          ))}
        </div>
      ) : (
        <div className="flex gap-2">
          <Label htmlFor={`guided-${current.name}`} className="sr-only">
            {current.label}
          </Label>
          <Input
            id={`guided-${current.name}`}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={current.suggest_default ?? ""}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void submit();
              }
            }}
          />
          <Button onClick={submit}>OK</Button>
        </div>
      )}
    </div>
  );
}
