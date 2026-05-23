import type { Metadata } from "next";
import { Onest, JetBrains_Mono } from "next/font/google";
import { AccessGate } from "@/components/AccessGate";
import { DemoResetButton } from "@/components/DemoResetButton";
import { MockProvider } from "@/components/MockProvider";
import { VoiceProvider } from "@/lib/voiceContext";
import "./globals.css";

const onest = Onest({
  subsets: ["latin", "latin-ext"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
  variable: "--font-civic-loaded",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
  variable: "--font-mono-loaded",
});

export const metadata: Metadata = {
  title: "eGata — Asistentul tău pentru primărie",
  description:
    "Spune-i ce ai nevoie. Îți spune ce acte îți trebuie. Le și completează cu tine.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="ro"
      suppressHydrationWarning
      className={`${onest.variable} ${jetbrainsMono.variable}`}
    >
      <body className="bg-background text-foreground antialiased">
        <MockProvider>
          <AccessGate>
            <VoiceProvider>{children}</VoiceProvider>
          </AccessGate>
          <DemoResetButton />
        </MockProvider>
      </body>
    </html>
  );
}
