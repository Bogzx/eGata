"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { GhiseuShell } from "@/components/ghiseu/GhiseuShell";
import { getSession } from "@/lib/session";
import "./ghiseu.css";

export default function GhiseuPage() {
  const router = useRouter();

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!getSession()) router.replace("/login");
  }, [router]);

  return <GhiseuShell />;
}
