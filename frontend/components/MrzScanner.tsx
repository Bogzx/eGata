"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { t } from "@/lib/i18n";
import { parseMrzFromImage, type MrzResult } from "@/lib/mrz";

type Props = {
  onParsed: (r: MrzResult) => void;
};

type Mode = "camera" | "upload" | "manual";

export function MrzScanner({ onParsed }: Props) {
  const [mode, setMode] = useState<Mode>("camera");
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    if (mode !== "camera") {
      streamRef.current?.getTracks().forEach((tr) => tr.stop());
      streamRef.current = null;
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
        });
        if (cancelled) {
          stream.getTracks().forEach((tr) => tr.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => undefined);
        }
      } catch {
        setMode("upload");
      }
    })();
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((tr) => tr.stop());
      streamRef.current = null;
    };
  }, [mode]);

  async function captureFrame(): Promise<Blob | null> {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0) return null;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0);
    return await new Promise((resolve) =>
      canvas.toBlob((b) => resolve(b), "image/jpeg", 0.9),
    );
  }

  async function runParse(blob: Blob) {
    // Tesseract runs OCR on the main thread — a 30MB kiosk-camera image
    // can lock the UI for 30+ seconds. Cap at 5 MB; users get a clear
    // error and can crop/retake instead of staring at a frozen page.
    const MAX_BYTES = 5 * 1024 * 1024;
    if (blob.size > MAX_BYTES) {
      setError(
        "Imaginea este prea mare (max 5 MB). Te rog redimensioneaz-o sau folosește camera.",
      );
      return;
    }
    setScanning(true);
    setError(null);
    try {
      const r = await parseMrzFromImage(blob);
      if (!r.valid) {
        setError(t("mrz.failed"));
        return;
      }
      onParsed(r);
    } catch {
      setError(t("mrz.failed"));
    } finally {
      setScanning(false);
    }
  }

  if (mode === "manual") {
    return (
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          const data = new FormData(e.currentTarget);
          onParsed({
            cnp: String(data.get("cnp") ?? ""),
            nume: String(data.get("nume") ?? ""),
            prenume: String(data.get("prenume") ?? ""),
            valid: true,
          });
        }}
      >
        <h2 className="text-xl font-semibold">{t("mrz.manual_fallback")}</h2>
        <div>
          <Label htmlFor="cnp">CNP</Label>
          <Input id="cnp" name="cnp" required pattern="\d{13}" inputMode="numeric" />
        </div>
        <div>
          <Label htmlFor="nume">Nume</Label>
          <Input id="nume" name="nume" required />
        </div>
        <div>
          <Label htmlFor="prenume">Prenume</Label>
          <Input id="prenume" name="prenume" required />
        </div>
        <Button type="submit">{t("common.continue")}</Button>
      </form>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">{t("mrz.title")}</h2>
      <p className="text-sm text-muted-foreground">{t("mrz.instruction")}</p>

      {mode === "camera" ? (
        <div className="relative overflow-hidden rounded-lg border bg-black">
          <video
            ref={videoRef}
            className="aspect-video w-full"
            playsInline
            muted
            aria-label="Camera preview"
          />
          <div className="pointer-events-none absolute inset-x-8 bottom-12 h-16 rounded border-2 border-yellow-300/80" />
        </div>
      ) : (
        <label
          htmlFor="mrz-upload-input"
          className="flex aspect-video w-full cursor-pointer items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/30 text-sm text-muted-foreground"
        >
          Apasă pentru a încărca o poză cu buletinul
        </label>
      )}

      <input
        id="mrz-upload-input"
        data-testid="mrz-upload"
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void runParse(f);
        }}
      />

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          disabled={scanning || mode !== "camera"}
          onClick={async () => {
            const blob = await captureFrame();
            if (blob) void runParse(blob);
          }}
        >
          {scanning ? t("mrz.scanning") : "Capturează"}
        </Button>
        <Button type="button" variant="outline" onClick={() => setMode("upload")}>
          Încarcă o poză
        </Button>
        <Button type="button" variant="ghost" onClick={() => setMode("manual")}>
          {t("login.manual_cnp_button")}
        </Button>
      </div>

      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}
