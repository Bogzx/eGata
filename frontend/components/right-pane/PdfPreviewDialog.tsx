"use client";

import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";

type Props = {
  procedureId: string | null;
  title: string;
  onClose: () => void;
};

export function PdfPreviewDialog({ procedureId, title, onClose }: Props) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!procedureId) return;
    let cancelled = false;
    let createdUrl: string | null = null;
    setPdfUrl(null);
    setError(null);
    api
      .previewProcedurePdf(procedureId)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        createdUrl = url;
        setPdfUrl(url);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(
            "Nu am putut genera previzualizarea. Încearcă din nou peste câteva clipe."
          );
          console.error("[egata] preview-pdf failed", e);
        }
      });
    return () => {
      cancelled = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [procedureId]);

  return (
    <Dialog open={!!procedureId} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="h-[90vh] max-w-4xl">
        <DialogTitle>{title}</DialogTitle>
        <div className="flex-1 overflow-hidden rounded border" style={{ borderColor: "var(--c-line)" }}>
          {pdfUrl ? (
            <iframe
              src={pdfUrl}
              className="h-full w-full"
              title={`Previzualizare PDF — ${title}`}
            />
          ) : error ? (
            <div className="flex h-full items-center justify-center p-6 text-center text-sm">
              {error}
            </div>
          ) : (
            <div className="flex h-full items-center justify-center p-6 text-center text-sm" style={{ color: "var(--c-ink-soft)" }}>
              Se generează previzualizarea PDF…
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
