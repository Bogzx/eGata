"use client";

import { useState } from "react";
import {
  CheckCircle2,
  Mail,
  Building2,
  Printer,
  Calendar,
  MapPin,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSessionStore } from "@/lib/sessionStore";
// Note: "Conversație nouă" button lives in the topbar (TopBar.tsx) so it's
// always reachable. Don't duplicate it here.

function nextWorkdayAt(daysAhead: number, hour: number, minute: number): Date {
  const d = new Date();
  let added = 0;
  while (added < daysAhead) {
    d.setDate(d.getDate() + 1);
    const dow = d.getDay();
    if (dow !== 0 && dow !== 6) added++;
  }
  d.setHours(hour, minute, 0, 0);
  return d;
}

function formatRoDate(d: Date): string {
  const weekdays = [
    "Duminică",
    "Luni",
    "Marți",
    "Miercuri",
    "Joi",
    "Vineri",
    "Sâmbătă",
  ];
  const months = [
    "ianuarie",
    "februarie",
    "martie",
    "aprilie",
    "mai",
    "iunie",
    "iulie",
    "august",
    "septembrie",
    "octombrie",
    "noiembrie",
    "decembrie",
  ];
  return `${weekdays[d.getDay()]}, ${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
}

function formatRoTime(d: Date): string {
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

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
  const citizen = useSessionStore((s) => s.citizen);
  const [appointmentBooked, setAppointmentBooked] = useState(false);

  const delivery = document?.delivery;
  const ghiseu = ghiseuForProcedure(document?.procedure_id);
  const appointment = nextWorkdayAt(3, 10, 30);

  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 p-10 text-center">
      <CheckCircle2 className="text-green-600" size={48} aria-hidden />

      {delivery === "save" ? (
        <>
          <h2 className="flex items-center gap-2 text-3xl font-semibold">
            <Mail size={32} /> PDF trimis pe email
          </h2>
          <p className="text-lg">
            Verifică inbox-ul tău:
            <br />
            <strong className="text-xl">{citizen?.email ?? "adresa ta de email"}</strong>
          </p>
        </>
      ) : delivery === "send" ? (
        <>
          <h2 className="flex items-center gap-2 text-3xl font-semibold">
            <Building2 size={32} /> Cererea a fost trimisă la primărie
          </h2>
          <p className="text-lg">
            Cererea ta a ajuns la Primăria Cluj-Napoca.
            <br />
            Vei primi un răspuns în câteva zile lucrătoare.
          </p>

          {!appointmentBooked ? (
            <Button
              variant="outline"
              onClick={() => setAppointmentBooked(true)}
              className="mt-2"
            >
              <Calendar size={16} className="mr-2" />
              Vrei și o programare pentru ridicare?
            </Button>
          ) : (
            <div
              className="mt-2 w-full rounded-lg border p-4 text-left"
              style={{
                borderColor: "var(--c-line)",
                background: "rgba(47, 160, 132, 0.08)",
              }}
            >
              <p className="mb-2 flex items-center gap-2 font-semibold">
                <CheckCircle2 size={18} className="text-green-600" />
                Programare confirmată
              </p>
              <p className="text-sm">
                <Calendar size={14} className="mr-1 inline" />
                <strong>{formatRoDate(appointment)}</strong>, ora{" "}
                <strong>{formatRoTime(appointment)}</strong>
              </p>
              <p className="mt-1 text-sm">
                <MapPin size={14} className="mr-1 inline" />
                {ghiseu.nume}
              </p>
              <p className="text-xs" style={{ color: "var(--c-ink-soft)" }}>
                {ghiseu.adresa}
                {ghiseu.observatie ? ` — ${ghiseu.observatie}` : ""}
              </p>
            </div>
          )}
        </>
      ) : delivery === "print" ? (
        <>
          <h2 className="flex items-center gap-2 text-3xl font-semibold">
            <Printer size={32} /> PDF trimis la imprimantă
          </h2>
          <p className="text-lg">
            După printare, semnează pe linia de Semnătură și completează data cu
            pixul, apoi depune-l la ghișeu:
          </p>
          <div
            className="w-full rounded-lg border p-3 text-left text-base"
            style={{
              borderColor: "var(--c-line)",
              background: "var(--c-bg)",
            }}
          >
            <p className="flex items-center gap-2 font-semibold">
              <MapPin size={16} /> {ghiseu.nume}
            </p>
            <p className="text-sm" style={{ color: "var(--c-ink-soft)" }}>
              {ghiseu.adresa}
            </p>
          </div>
        </>
      ) : (
        <h2 className="text-3xl font-semibold">Gata.</h2>
      )}

    </div>
  );
}
