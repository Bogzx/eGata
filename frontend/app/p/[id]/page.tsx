"use client";

import { use } from "react";
import { ChatSurface } from "@/components/chat/ChatSurface";

type Props = { params: Promise<{ id: string }> };

export default function ScenarioPlanPage({ params }: Props) {
  const { id } = use(params);
  return <ChatSurface activeDocId={null} activeScenarioId={id} />;
}
