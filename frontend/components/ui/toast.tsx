"use client";
import * as React from "react";
import { cn } from "@/lib/utils";

type ToastVariant = "default" | "success" | "destructive";

export interface ToastMessage {
  id: string;
  title: string;
  description?: string;
  variant?: ToastVariant;
}

interface ToastContextValue {
  toasts: ToastMessage[];
  toast: (msg: Omit<ToastMessage, "id">) => void;
  dismiss: (id: string) => void;
}

const ToastContext = React.createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastMessage[]>([]);

  const dismiss = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = React.useCallback(
    (msg: Omit<ToastMessage, "id">) => {
      const id = Math.random().toString(36).slice(2);
      setToasts((prev) => [...prev, { ...msg, id }]);
      setTimeout(() => dismiss(id), 5000);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ toasts, toast, dismiss }}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={cn(
              "pointer-events-auto rounded-md border bg-background px-4 py-3 shadow-lg",
              t.variant === "success" && "border-green-500/40 bg-green-50 text-green-900",
              t.variant === "destructive" &&
                "border-destructive bg-destructive text-destructive-foreground",
            )}
          >
            <div className="font-medium">{t.title}</div>
            {t.description && <div className="text-sm opacity-90">{t.description}</div>}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = React.useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
