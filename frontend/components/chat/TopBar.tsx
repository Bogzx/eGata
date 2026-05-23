"use client";

import { ChevronDown, FolderOpen, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSessionStore } from "@/lib/sessionStore";
import { useKioskMode } from "@/lib/kioskMode";

export function TopBar() {
  const citizen = useSessionStore((s) => s.citizen);
  const openDrawer = useSessionStore((s) => s.openDrawer);
  const toggleProfile = useSessionStore((s) => s.toggleProfileMenu);
  const isKiosk = useKioskMode();

  return (
    <header className="flex items-center justify-between border-b bg-background px-4 py-2">
      <Button
        variant="outline"
        size="sm"
        onClick={openDrawer}
        aria-label="Documentele mele"
      >
        <FolderOpen className="mr-2" size={16} aria-hidden />
        Documentele mele
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={toggleProfile}
        aria-label={isKiosk ? "Accesibilitate" : "Profil"}
        aria-haspopup="menu"
      >
        <User className="mr-2" size={16} aria-hidden />
        {isKiosk ? "Accesibilitate" : (citizen?.prenume ?? "Profil")}
        <ChevronDown className="ml-1" size={14} aria-hidden />
      </Button>
    </header>
  );
}
