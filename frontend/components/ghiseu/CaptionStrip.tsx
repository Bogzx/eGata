"use client";

import type { GhiseuState } from "@/lib/ghiseuStore";

type Line = { text: string; final?: boolean } | null;

type Transcript = Record<GhiseuState, { user: Line; agent: Line }>;

const TRANSCRIPT: Transcript = {
  idle: {
    user: null,
    agent: { text: "Bună! Spune-mi cu ce te pot ajuta astăzi.", final: true },
  },
  listening: {
    user: {
      text: "Vreau o adeverință de venit pentru bancă, pe ultimele 6 luni…",
      final: false,
    },
    agent: { text: "Sigur, te ajut cu adeverința de venit.", final: true },
  },
  thinking: {
    user: {
      text: "Vreau o adeverință de venit pentru bancă, pe ultimele 6 luni.",
      final: true,
    },
    agent: null,
  },
  speaking: {
    user: {
      text: "Vreau o adeverință de venit pentru bancă, pe ultimele 6 luni.",
      final: true,
    },
    agent: {
      text:
        "Bine. Am completat datele tale din ROeID. Verifică perioada și instituția destinatară…",
      final: true,
    },
  },
  review: {
    user: { text: "Da, e ok perioada.", final: true },
    agent: {
      text: "Am pregătit cererea. Te rog verifică datele înainte să o trimitem.",
      final: true,
    },
  },
  export: {
    user: { text: "Trimite-o pe email.", final: true },
    agent: { text: "Perfect. Pe ce email să o trimit — ana.popescu@…?", final: true },
  },
  done: {
    user: null,
    agent: {
      text: "Am trimis cererea către Direcția de Taxe. O să primești o copie pe email.",
      final: true,
    },
  },
  error: { user: null, agent: null },
  "mic-denied": { user: null, agent: null },
};

type Props = { state: GhiseuState };

export function CaptionStrip({ state }: Props) {
  const data = TRANSCRIPT[state];
  if (!data.user && !data.agent) return null;
  return (
    <div className="gh-caption" aria-live="polite">
      {data.user ? (
        <div className="gh-cap-line" data-role="user">
          <span className="gh-cap-tag">Tu</span>
          <span className="gh-cap-text">
            {data.user.final ? (
              data.user.text
            ) : (
              <span className="partial">{data.user.text}</span>
            )}
          </span>
        </div>
      ) : null}
      {data.agent ? (
        <div className="gh-cap-line" data-role="agent">
          <span className="gh-cap-tag">eGata</span>
          <span className="gh-cap-text">{data.agent.text}</span>
        </div>
      ) : null}
    </div>
  );
}
