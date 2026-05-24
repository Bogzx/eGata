"use client";

import { useSessionStore } from "@/lib/sessionStore";
import { DonePane } from "@/components/right-pane/DonePane";
import { FillingPane } from "@/components/right-pane/FillingPane";
import { MatchesPane } from "@/components/right-pane/MatchesPane";
import { PlanPane } from "@/components/right-pane/PlanPane";
import { ReviewPane } from "@/components/right-pane/ReviewPane";
import { WelcomePane } from "@/components/right-pane/WelcomePane";
import type { SessionStateName } from "@/lib/types";

/**
 * Right pane is a pure function of the backend session state.
 *
 *   exploring         → WelcomePane
 *   confirming_match  → MatchesPane | PlanPane  (PlanPane when a scenario
 *                       plan was returned by the latest lookup)
 *   filling           → FillingPane
 *   reviewing         → ReviewPane
 *   delivered         → DonePane
 *   redirected        → WelcomePane (the redirect itself is a chat bubble)
 *
 * No internal state, no self-transitions, no rightPane.kind anywhere
 * else in the codebase — those went away in the cleanup pass.
 */
function paneForSessionState(
  state: SessionStateName,
  hasScenarioPlan: boolean,
): React.ReactNode {
  switch (state) {
    case "exploring":
      return <WelcomePane />;
    case "confirming_match":
      return hasScenarioPlan ? <PlanPane /> : <MatchesPane />;
    case "filling":
      return <FillingPane />;
    case "reviewing":
      return <ReviewPane />;
    case "delivered":
      return <DonePane />;
    case "redirected":
      return <WelcomePane />;
  }
}

export function RightPane() {
  const session = useSessionStore((s) => s.session);
  const scenarioPlan = useSessionStore((s) => s.scenarioPlan);
  const document = useSessionStore((s) => s.document);
  const sending = useSessionStore((s) => s.sending);

  // No session yet (initial paint, fresh visit). If we have a document
  // already loaded — which happens on direct /r/<id> URLs — assume the
  // user is still filling. Otherwise show the welcome lane.
  if (!session) {
    if (document) return <FillingPane />;
    return <WelcomePane />;
  }

  // Keep FillingPane visible while the agent is still streaming, even if
  // the backend has already flipped to REVIEWING. The last set_field in a
  // batch (e.g. optional `email`) often arrives AFTER the transition, so
  // swapping mid-stream both flashes the panel ("refresh mid completare")
  // and risks the new ReviewPane mounting before the trailing field_updated
  // has been applied. Wait until the turn settles, then show ReviewPane.
  if (session.state === "reviewing" && sending) {
    return <FillingPane />;
  }

  return paneForSessionState(session.state, scenarioPlan !== null);
}
