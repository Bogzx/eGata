"use client";

import { useParams } from "next/navigation";
import { ChatSurface } from "@/components/chat/ChatSurface";

export default function DocChatPage() {
  const params = useParams<{ id: string }>();
  return <ChatSurface activeDocId={params.id ?? null} />;
}
