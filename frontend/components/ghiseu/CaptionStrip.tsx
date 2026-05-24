"use client";

import { type GhiseuState, useGhiseuStore } from "@/lib/ghiseuStore";

type Line = { text: string; final?: boolean } | null;

type Transcript = Record<GhiseuState, { user: Line; agent: Line }>;

// Design-copy fallback shown when no live caption exists yet (e.g., the
// agent's greeting placeholder before the user has spoken).
const TRANSCRIPT: Transcript = {
  idle: {
    user: null,
    agent: { text: "Bună! Spune-mi cu ce te pot ajuta astăzi.", final: true },
  },
  listening: {
    user: null,
    agent: { text: "Te ascult.", final: true },
  },
  thinking: { user: null, agent: null },
  speaking: { user: null, agent: null },
  review: {
    user: null,
    agent: {
      text: "Am pregătit cererea. Verifică datele înainte să o trimitem.",
      final: true,
    },
  },
  export: { user: null, agent: null },
  submitting: { user: null, agent: null },
  done: { user: null, agent: null },
  error: { user: null, agent: null },
  "mic-denied": { user: null, agent: null },
};

type Props = { state: GhiseuState };

export function CaptionStrip({ state }: Props) {
  const liveCaption = useGhiseuStore((s) => s.caption);
  const fallback = TRANSCRIPT[state];

  const user: Line = liveCaption.user
    ? { text: liveCaption.user.text, final: !liveCaption.user.live }
    : fallback.user;
  const agent: Line = liveCaption.agent
    ? { text: liveCaption.agent.text, final: !liveCaption.agent.live }
    : fallback.agent;

  if (!user && !agent) return null;
  return (
    <div className="gh-caption" aria-live="polite">
      {user ? (
        <div className="gh-cap-line" data-role="user">
          <span className="gh-cap-tag">Tu</span>
          <span className="gh-cap-text">
            {user.final ? (
              user.text
            ) : (
              <span className="partial">{user.text}</span>
            )}
          </span>
        </div>
      ) : null}
      {agent ? (
        <div className="gh-cap-line" data-role="agent">
          <span className="gh-cap-tag">eGata</span>
          <span className="gh-cap-text">{agent.text}</span>
        </div>
      ) : null}
    </div>
  );
}
