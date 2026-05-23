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
    </div>
  );
}
