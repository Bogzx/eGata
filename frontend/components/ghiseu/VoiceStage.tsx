"use client";

import type { GhiseuState } from "@/lib/ghiseuStore";
import { CaptionStrip } from "./CaptionStrip";
import { AlertIcon, MicSlashIcon } from "./icons";

const STATUS_COPY: Record<GhiseuState, { title: string; hint: string }> = {
  idle: { title: "Bună. Apasă microfonul pentru ajutor.", hint: "" },
  listening: {
    title: "Te ascult…",
    hint: "Vorbește natural. Te ascult până faci o pauză.",
  },
  thinking: {
    title: "Mă gândesc…",
    hint: "Verific datele tale și caut cererea potrivită.",
  },
  speaking: {
    title: "Vorbesc…",
    hint: "Apasă Întrerupe dacă vrei să spui altceva.",
  },
  review: {
    title: "E corect totul?",
    hint: "Aruncă o privire peste actul completat. Spune-mi sau apasă mai jos.",
  },
  export: {
    title: "Cum trimitem actul?",
    hint: "Alege o opțiune. Pot să-l trimit eu sau să-l înregistrez direct la primărie.",
  },
  submitting: {
    title: "Trimit cererea…",
    hint: "Durează câteva secunde. Te rog să aștepți confirmarea.",
  },
  done: {
    title: "Gata. Cererea a fost trimisă.",
    hint: "Vei primi confirmarea pe email. Mulțumesc!",
  },
  error: {
    title: "S-a pierdut conexiunea",
    hint: "Verificăm legătura cu serverul. Va dura câteva secunde.",
  },
  "mic-denied": {
    title: "Microfonul este blocat",
    hint: "Permite accesul la microfon în setările browserului ca să poți vorbi.",
  },
};

type Props = { state: GhiseuState };

export function VoiceStage({ state }: Props) {
  const copy = STATUS_COPY[state];
  const isError = state === "error" || state === "mic-denied";

  if (isError) {
    return (
      <div className="gh-stage">
        <div className="gh-status">
          <h2 className="gh-status-text">{copy.title}</h2>
          <p className="gh-status-hint">{copy.hint}</p>
        </div>
        <div className="gh-viz-wrap">
          <div className="gh-error-icon">
            {state === "mic-denied" ? (
              <MicSlashIcon size={44} />
            ) : (
              <AlertIcon size={44} />
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="gh-stage">
      <div className="gh-status">
        <h2 className="gh-status-text">{copy.title}</h2>
      </div>
      <CaptionStrip state={state} />
    </div>
  );
}
