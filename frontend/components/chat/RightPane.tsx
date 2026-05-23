"use client";

import { useSessionStore } from "@/lib/sessionStore";
import { DeliveryPane } from "@/components/right-pane/DeliveryPane";
import { DonePane } from "@/components/right-pane/DonePane";
import { FillingPane } from "@/components/right-pane/FillingPane";
import { GuidePane } from "@/components/right-pane/GuidePane";
import { MatchesPane } from "@/components/right-pane/MatchesPane";
import { PdfPane } from "@/components/right-pane/PdfPane";
import { PlanPane } from "@/components/right-pane/PlanPane";
import { ReviewPane } from "@/components/right-pane/ReviewPane";
import { WelcomePane } from "@/components/right-pane/WelcomePane";
import type { SessionStateName } from "@/lib/types";

/**
 * Pick a pane component purely from the backend session state.
 *
 * confirming_match → MatchesPane unless the session was launched against
 * a scenario plan (scenario_id set), in which case PlanPane.
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
      // The redirect was already surfaced as a system bubble in chat;
      // show the welcome lane so the user can pivot to a new request.
      return <WelcomePane />;
  }
}

export function RightPane() {
  const session = useSessionStore((s) => s.session);
  const scenarioPlan = useSessionStore((s) => s.scenarioPlan);
  const legacyKind = useSessionStore((s) => s.rightPane.kind);

  // Preferred path: dispatch on the backend's session state. The session
  // snapshot is the single source of truth post-rewrite. When the
  // snapshot hasn't arrived yet (e.g. first paint, or a flow that hasn't
  // yet exercised the new agent), fall back to the legacy rightPane.kind
  // so DocsPane / Pdf / Delivery transitions still work.
  if (session) {
    return paneForSessionState(session.state, scenarioPlan !== null);
  }

  switch (legacyKind) {
    case "welcome":
      return <WelcomePane />;
    case "guide":
      return <GuidePane />;
    case "filling":
      return <FillingPane />;
    case "review":
      return <ReviewPane />;
    case "pdf":
      return <PdfPane />;
    case "delivery":
      return <DeliveryPane />;
    case "done":
      return <DonePane />;
    case "plan":
      return <PlanPane />;
    case "matches":
      return <MatchesPane />;
  }
}
