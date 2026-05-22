"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { t } from "@/lib/i18n";
import type { Document, Procedure } from "@/lib/types";

type Props = {
  documents: Document[];
  procedures: Procedure[];
};

export function DocumentList({ documents, procedures }: Props) {
  if (documents.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("home.empty_documents")}</p>;
  }
  const titleOf = (id: string) =>
    procedures.find((p) => p.id === id)?.title ?? id;

  return (
    <ul className="space-y-3">
      {documents.map((d) => (
        <li key={d.id}>
          <Link href={`/doc/${d.id}`} className="block">
            <Card className="transition hover:bg-accent/40 focus-within:ring-2">
              <CardContent className="flex items-center justify-between p-4">
                <div>
                  <p className="font-medium">{titleOf(d.procedure_id)}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(d.created_at).toLocaleDateString("ro-RO")}
                  </p>
                  {d.ref_number ? (
                    <p className="text-xs text-muted-foreground">
                      {t("doc.ref_number", { ref: d.ref_number })}
                    </p>
                  ) : null}
                </div>
                {d.status === "finalized" ? (
                  <Badge variant="default">Trimisă</Badge>
                ) : (
                  <Badge variant="secondary">În lucru</Badge>
                )}
              </CardContent>
            </Card>
          </Link>
        </li>
      ))}
    </ul>
  );
}
