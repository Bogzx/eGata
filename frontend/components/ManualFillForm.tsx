"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Procedure, ProcedureField } from "@/lib/types";

type Props = {
  procedure: Procedure;
  values: Record<string, unknown>;
  onPatch: (delta: Record<string, unknown>) => void | Promise<void>;
};

function isFilled(v: unknown): boolean {
  return v !== undefined && v !== null && String(v).length > 0;
}

export function ManualFillForm({ procedure, values, onPatch }: Props) {
  const remaining: ProcedureField[] = procedure.fields.filter(
    (f) => !isFilled(values[f.name]),
  );
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onPatch(draft);
      setDraft({});
    } finally {
      setSubmitting(false);
    }
  }

  if (remaining.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Toate câmpurile sunt completate.
      </p>
    );
  }

  return (
    <form className="space-y-4" onSubmit={submit}>
      {remaining.map((f) => (
        <div key={f.name} className="space-y-1">
          <Label htmlFor={f.name}>
            {f.label}
            {f.required ? <span aria-hidden> *</span> : null}
          </Label>
          {f.options ? (
            <select
              id={f.name}
              required={f.required}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              value={draft[f.name] ?? ""}
              onChange={(e) =>
                setDraft((d) => ({ ...d, [f.name]: e.target.value }))
              }
            >
              <option value="" disabled>
                — alege —
              </option>
              {f.options.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          ) : (
            <Input
              id={f.name}
              required={f.required}
              value={draft[f.name] ?? f.suggest_default ?? ""}
              onChange={(e) =>
                setDraft((d) => ({ ...d, [f.name]: e.target.value }))
              }
            />
          )}
        </div>
      ))}
      <Button type="submit" disabled={submitting}>
        {submitting ? "Se salvează..." : "Salvează"}
      </Button>
    </form>
  );
}
