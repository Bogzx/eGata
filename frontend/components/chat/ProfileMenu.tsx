"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AccessibilityToggles } from "@/components/AccessibilityToggles";
import { Button } from "@/components/ui/button";
import { useKioskMode } from "@/lib/kioskMode";
import { clearSession } from "@/lib/session";
import { useSessionStore } from "@/lib/sessionStore";

export function ProfileMenu() {
  const open = useSessionStore((s) => s.profileMenuOpen);
  const close = useSessionStore((s) => s.closeProfileMenu);
  const reset = useSessionStore((s) => s.reset);
  const isKiosk = useKioskMode();
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) close();
    }
    if (open) document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open, close]);

  function signOut() {
    clearSession();
    window.location.href = "/login";
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          ref={ref}
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.15 }}
          role="menu"
          className="fixed right-3 top-12 z-50 w-[300px] rounded-lg border bg-background p-3 shadow-lg"
        >
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Accesibilitate
          </p>
          <AccessibilityToggles />
          {!isKiosk ? (
            <div className="mt-3 flex flex-col gap-1 border-t pt-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  reset();
                  close();
                }}
                className="justify-start"
              >
                ↻ Conversație nouă
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={signOut}
                className="justify-start"
              >
                ⎋ Ieșire din cont
              </Button>
            </div>
          ) : null}
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
