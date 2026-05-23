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

export function RightPane() {
  const kind = useSessionStore((s) => s.rightPane.kind);
  switch (kind) {
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
