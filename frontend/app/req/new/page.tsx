"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getSession } from "@/lib/session";
import type { ProcedureLookupMatch } from "@/lib/types";

export default function NewRequestPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<ProcedureLookupMatch[] | null>(null);
  const [redirectCandidate, setRedirectCandidate] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined" && !getSession()) router.replace("/login");
  }, [router]);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMatches(null);
    setRedirectCandidate(null);
    try {
      const r = await api.lookupProcedure({ query });
      setMatches(r.matches);
      setRedirectCandidate(r.redirect_candidate);
    } catch (e) {
      if (e instanceof ApiError) setError(t("common.error"));
      else throw e;
    } finally {
      setLoading(false);
    }
  }

  async function pick(procedureId: string) {
    const doc = await api.createDocument({ procedure_id: procedureId });
    router.push(`/req/${doc.id}`);
  }

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-6">
      <Card>
        <CardHeader>
          <CardTitle>{t("req.search_title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="flex gap-2" onSubmit={search}>
            <div className="flex-1">
              <Label htmlFor="query" className="sr-only">
                Descrie ce ai nevoie
              </Label>
              <Input
                id="query"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("req.search_placeholder")}
                required
              />
            </div>
            <Button type="submit" disabled={loading || !query.trim()}>
              {loading ? t("common.loading") : t("req.search_button")}
            </Button>
          </form>
        </CardContent>
      </Card>

      {matches && matches.length > 0 ? (
        <ul className="space-y-3">
          {matches.map((m) => (
            <li key={m.procedure_id}>
              <Card className="cursor-pointer transition hover:bg-accent/40">
                <CardContent
                  className="flex items-center justify-between p-4"
                  onClick={() => void pick(m.procedure_id)}
                >
                  <div>
                    <p className="font-medium">{m.title}</p>
                    <p className="text-xs text-muted-foreground">
                      Potrivire: {(m.score * 100).toFixed(0)}%
                    </p>
                  </div>
                  <Button>{t("common.continue")}</Button>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      ) : null}

      {matches && matches.length === 0 && !redirectCandidate ? (
        <p className="text-sm text-muted-foreground">
          Nu am găsit o procedură potrivită. Încearcă alte cuvinte.
        </p>
      ) : null}

      {redirectCandidate ? (
        <Card className="border-amber-500">
          <CardContent className="space-y-2 p-4">
            <p className="font-medium">
              {t("req.redirect_external", { target: redirectCandidate })}
            </p>
            <p className="text-sm text-muted-foreground">
              Pe roadmap avem integrarea directă. Momentan, vă rugăm vizitați site-ul
              instituției.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </main>
  );
}
