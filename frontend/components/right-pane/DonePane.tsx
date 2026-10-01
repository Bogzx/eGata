"use client";

import {
  CheckCircle2,
  Download,
  FileCheck2,
  MapPin,
  MessageSquare,
  Printer,
} from "lucide-react";
import { useSessionStore } from "@/lib/sessionStore";
// Note: "Conversație nouă" button lives in the topbar (TopBar.tsx) so it's
// always reachable. Don't duplicate it here.

// What this pane may claim, and what it may not. eGata fills the form,
// renders the PDF, stores it and records every step in the ledger. It does
// not file the request with the primărie, e-mail it, print it or book an
// appointment, so nothing here says it did: the citizen still signs the PDF
// and takes it to the ghișeu below.

type GhiseuInfo = {
  nume: string;
  adresa: string;
  observatie?: string;
};

function ghiseuForProcedure(procedureId: string | undefined): GhiseuInfo {
  if (procedureId === "placuta-numar-postal") {
    return {
      nume: "Ghișeul CIC — Centrul de Informare Cetățeni",
      adresa: "str. Moților nr. 3, parter, Cluj-Napoca",
      observatie: "Pentru Serviciul Siguranța Circulației",
    };
  }
  if (procedureId === "certificat-nomenclatura-stradala") {
    return {
      nume: "Ghișeul CIC — Centrul de Informare Cetățeni",
      adresa: "str. Moților nr. 3, parter, Cluj-Napoca",
      observatie: "Pentru Serviciul Urbanism",
    };
  }
  if (procedureId === "taiere-arbore-curte-privata") {
    return {
      nume: "Ghișeul Spații Verzi",
      adresa: "Calea Moților nr. 1-3, et. 2, Cluj-Napoca",
      observatie: "Direcția Ecologie Urbană — tel. 0264 336 234",
    };
  }
  return {
    nume: "Ghișeul CIC — Centrul de Informare Cetățeni",
    adresa: "str. Moților nr. 3, parter, Cluj-Napoca",
  };
}

export function DonePane() {
  const document = useSessionStore((s) => s.document);
  const smsSent = useSessionStore((s) => s.smsSent);

  const delivery = document?.delivery;
  const ghiseu = ghiseuForProcedure(document?.procedure_id);

  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 p-10 text-center">
      <CheckCircle2 className="text-green-600" size={48} aria-hidden />

      <h2 className="text-3xl font-semibold">Cererea e completată</h2>
      {document?.ref_number ? (
        <p className="text-lg">
          Referință eGata: <strong>{document.ref_number}</strong>
        </p>
      ) : null}

      {delivery === "print" ? (
        <p className="flex items-center gap-2 text-lg">
          <Printer size={20} aria-hidden /> Deschide PDF-ul și tipărește-l.
        </p>
      ) : delivery === "send" ? (
        <p className="flex items-center gap-2 text-lg">
          <MessageSquare size={20} aria-hidden />
          {smsSent === true
            ? "Ți-am trimis referința pe SMS."
            : smsSent === false
              ? "SMS-ul nu e configurat pe acest server, așa că nu a plecat niciun mesaj."
              : "Ai cerut confirmarea pe SMS."}
        </p>
      ) : (
        <p className="flex items-center gap-2 text-lg">
          <FileCheck2 size={20} aria-hidden /> PDF-ul e salvat în „Documentele mele”.
        </p>
      )}

      {document?.pdf_url ? (
        <a
          className="civic-btn civic-btn-secondary"
          href={document.pdf_url}
          target="_blank"
          rel="noreferrer"
        >
          <Download size={16} className="mr-2 inline" aria-hidden />
          Descarcă PDF
        </a>
      ) : null}

      <div
        className="w-full rounded-lg border p-4 text-left"
        style={{ borderColor: "var(--c-line)", background: "var(--c-bg)" }}
      >
        <p className="mb-1 font-semibold">Ce urmează</p>
        <p className="text-sm">
          eGata nu depune cererea pentru tine. Semnează PDF-ul și depune-l la:
        </p>
        <p className="mt-2 flex items-center gap-2 font-semibold">
          <MapPin size={16} aria-hidden /> {ghiseu.nume}
        </p>
        <p className="text-sm" style={{ color: "var(--c-ink-soft)" }}>
          {ghiseu.adresa}
          {ghiseu.observatie ? ` — ${ghiseu.observatie}` : ""}
        </p>
      </div>
    </div>
  );
}
