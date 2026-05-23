"use client";

import { useSessionStore } from "@/lib/sessionStore";

export function WelcomePane() {
  const citizen = useSessionStore((s) => s.citizen);
  const prenume = citizen?.prenume ?? "";

  return (
    <div className="welcome">
      <h2 className="hello">
        Bună{prenume ? `, ${prenume}` : ""}.
        <br />
        <span className="hello-soft">Cu ce te pot ajuta astăzi?</span>
      </h2>
      <p className="welcome-sub">
        Spune-mi în cuvinte simple ce ai nevoie. Eu îți spun ce acte îți trebuie
        — și le completez cu tine.
      </p>
    </div>
  );
}
