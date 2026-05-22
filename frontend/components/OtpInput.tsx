"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Props = {
  onComplete: (code: string) => void;
  error?: string | null;
};

export function OtpInput({ onComplete, error }: Props) {
  const [value, setValue] = useState("");

  return (
    <div className="space-y-2">
      <Label htmlFor="otp">Cod OTP</Label>
      <Input
        id="otp"
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={6}
        value={value}
        onChange={(e) => {
          const next = e.target.value.replace(/\D/g, "").slice(0, 6);
          setValue(next);
          if (next.length === 6) onComplete(next);
        }}
        aria-invalid={error ? "true" : undefined}
        className="text-center text-2xl tracking-[0.5em]"
      />
      <p className="text-xs text-muted-foreground">Demo: codul corect este 123456.</p>
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}
