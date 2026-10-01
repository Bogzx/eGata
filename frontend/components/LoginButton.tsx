"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { t } from "@/lib/i18n";
import { personas } from "@/mocks/fixtures";
import type { LoginChallenge } from "@/lib/types";

type Props = {
  onChallenge: (c: LoginChallenge) => void;
};

export function LoginButton({ onChallenge }: Props) {
  const demoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "1";
  const [persona, setPersona] = useState<string>(personas[0]?.id ?? "maria-ionescu");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setLoading(true);
    setError(null);
    try {
      const r = await api.loginRoeid(demoMode ? { persona_id: persona } : {});
      onChallenge(r);
    } catch (e) {
      // fetch rejects (TypeError) when the server cannot be reached at all;
      // an ApiError means it answered. Only the second is the user's to retry.
      setError(t(e instanceof ApiError ? "common.error" : "common.server_unreachable"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      {demoMode ? (
        <div className="space-y-1">
          <Label htmlFor="persona">{t("login.persona_label")}</Label>
          <select
            id="persona"
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            value={persona}
            onChange={(e) => setPersona(e.target.value)}
          >
            {personas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      ) : null}
      <Button onClick={handleClick} disabled={loading} className="w-full" size="lg">
        {loading ? t("common.loading") : t("login.roeid_button")}
      </Button>
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}
