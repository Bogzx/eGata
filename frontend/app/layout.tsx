import type { Metadata } from "next";
import { DemoResetButton } from "@/components/DemoResetButton";
import "./globals.css";

export const metadata: Metadata = {
  title: "CivicAI — Asistentul tău pentru primărie",
  description:
    "Spune-i ce ai nevoie. Îți spune ce acte îți trebuie. Le și completează cu tine.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ro" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        {children}
        <DemoResetButton />
      </body>
    </html>
  );
}
