"use client";

import { useEffect, useRef } from "react";

export type BackgroundVariant =
  | "mesh"
  | "waves"
  | "aurora"
  | "dots"
  | "field"
  | "static";

type Props = {
  variant?: BackgroundVariant;
  /** [dark, mid, light, bg] hex tuple — used to colour blobs/stripes/dots. */
  palette?: [string, string, string, string];
};

const DEFAULT_PALETTE: [string, string, string, string] = [
  "#1F6F5F",
  "#2FA084",
  "#6FCF97",
  "#EEEEEE",
];

/**
 * Recreates the spirit of Plain Bread Studio's Animated Backgrounds V1.
 * Five live variants + a static fallback. Honors prefers-reduced-motion.
 */
export function AnimatedBackground({
  variant = "mesh",
  palette = DEFAULT_PALETTE,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rafRef = useRef(0);
  const tRef = useRef(0);

  useEffect(() => {
    const cvs = canvasRef.current;
    if (!cvs) return;
    const ctx = cvs.getContext("2d");
    if (!ctx) return;

    let w = 0;
    let h = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    const reduceMotion = mql.matches;
    const effectiveVariant = reduceMotion ? "static" : variant;

    function resize() {
      if (!cvs || !ctx) return;
      w = cvs.clientWidth;
      h = cvs.clientHeight;
      cvs.width = w * dpr;
      cvs.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(cvs);

    const pal = palette;

    function blob(cx: number, cy: number, r: number, color: string, alpha = 1) {
      if (!ctx) return;
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
      g.addColorStop(0, color + "ff");
      g.addColorStop(0.55, color + "aa");
      g.addColorStop(1, color + "00");
      ctx.globalAlpha = alpha;
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    function drawMesh(t: number) {
      if (!ctx) return;
      ctx.fillStyle = pal[3];
      ctx.fillRect(0, 0, w, h);
      const cx = w / 2;
      const cy = h / 2;
      const R = Math.max(w, h);
      const orbs = [
        { c: pal[0], rx: 0.45, ry: 0.55, sx: 0.00045, sy: 0.00037, size: 0.55, a: 0.85 },
        { c: pal[1], rx: 0.30, ry: 0.40, sx: 0.00062, sy: 0.00051, size: 0.50, a: 0.80 },
        { c: pal[2], rx: 0.35, ry: 0.30, sx: 0.00073, sy: 0.00043, size: 0.45, a: 0.75 },
        { c: pal[1], rx: 0.25, ry: 0.50, sx: 0.00038, sy: 0.00060, size: 0.40, a: 0.70 },
        { c: pal[0], rx: 0.40, ry: 0.45, sx: 0.00029, sy: 0.00047, size: 0.50, a: 0.55 },
      ];
      ctx.globalCompositeOperation = "source-over";
      orbs.forEach((o, i) => {
        const px = cx + Math.cos(t * o.sx + i * 1.7) * (w * o.rx);
        const py = cy + Math.sin(t * o.sy + i * 2.3) * (h * o.ry);
        blob(px, py, R * o.size, o.c, o.a);
      });
    }

    function drawWaves(t: number) {
      if (!ctx) return;
      ctx.fillStyle = pal[3];
      ctx.fillRect(0, 0, w, h);
      const bands = [
        { c: pal[2], y: 0.30, amp: 70, freq: 0.0017, speed: 0.00045, alpha: 0.55 },
        { c: pal[1], y: 0.55, amp: 95, freq: 0.0013, speed: 0.00032, alpha: 0.65 },
        { c: pal[0], y: 0.78, amp: 80, freq: 0.0019, speed: -0.00038, alpha: 0.75 },
      ];
      bands.forEach((b, i) => {
        ctx.fillStyle = b.c;
        ctx.globalAlpha = b.alpha;
        ctx.beginPath();
        ctx.moveTo(0, h);
        for (let x = 0; x <= w; x += 4) {
          const y =
            h * b.y +
            Math.sin(x * b.freq + t * b.speed + i) * b.amp +
            Math.sin(x * b.freq * 0.4 + t * b.speed * 1.6) * (b.amp * 0.4);
          ctx.lineTo(x, y);
        }
        ctx.lineTo(w, h);
        ctx.closePath();
        ctx.fill();
      });
      ctx.globalAlpha = 1;
    }

    function drawAurora(t: number) {
      if (!ctx) return;
      ctx.fillStyle = pal[3];
      ctx.fillRect(0, 0, w, h);
      ctx.save();
      ctx.translate(w / 2, h / 2);
      ctx.rotate(-0.35);
      const stripes = 9;
      for (let i = 0; i < stripes; i++) {
        const sway = Math.sin(t * 0.00035 + i * 0.7) * (w * 0.05);
        const x = -w + (i / stripes) * w * 2.4 + sway;
        const grad = ctx.createLinearGradient(x, -h, x + 200, h);
        const col = pal[i % 3];
        grad.addColorStop(0, col + "00");
        grad.addColorStop(0.5, col + "cc");
        grad.addColorStop(1, col + "00");
        ctx.fillStyle = grad;
        ctx.globalAlpha = 0.55;
        ctx.fillRect(x, -h * 1.5, 220, h * 3);
      }
      ctx.restore();
      ctx.globalAlpha = 1;
    }

    function drawDots(t: number) {
      if (!ctx) return;
      ctx.fillStyle = pal[3];
      ctx.fillRect(0, 0, w, h);
      const cols = 22;
      const gx = w / cols;
      const rows = Math.ceil(h / gx) + 2;
      for (let i = 0; i < cols; i++) {
        for (let j = 0; j < rows; j++) {
          const cx = i * gx + gx / 2;
          const cy = j * gx + gx / 2;
          const d = Math.hypot(cx - w * 0.3, cy - h * 0.4);
          const wave = Math.sin(d * 0.011 - t * 0.0018) * 0.5 + 0.5;
          const r = 1.5 + wave * (gx * 0.18);
          const colorIdx = wave > 0.6 ? 0 : wave > 0.3 ? 1 : 2;
          ctx.fillStyle = pal[colorIdx];
          ctx.globalAlpha = 0.25 + wave * 0.55;
          ctx.beginPath();
          ctx.arc(cx, cy, r, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
    }

    function drawField(t: number) {
      if (!ctx) return;
      const g = ctx.createLinearGradient(0, 0, w, h);
      g.addColorStop(0, pal[3]);
      g.addColorStop(0.5, pal[2] + "80");
      g.addColorStop(1, pal[1] + "40");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
      const N = 7;
      for (let i = 0; i < N; i++) {
        const px = w * (0.1 + 0.13 * i) + Math.cos(t * 0.0004 + i) * w * 0.08;
        const py = h * (0.7 - 0.07 * i) + Math.sin(t * 0.0005 + i * 1.4) * h * 0.12;
        const size = (w + h) * 0.12;
        ctx.save();
        ctx.translate(px, py);
        ctx.rotate(t * 0.00012 + i);
        const grd = ctx.createRadialGradient(0, 0, 0, 0, 0, size);
        grd.addColorStop(0, pal[i % 3] + "cc");
        grd.addColorStop(1, pal[i % 3] + "00");
        ctx.fillStyle = grd;
        ctx.fillRect(-size, -size, size * 2, size * 2);
        ctx.restore();
      }
    }

    function drawStatic() {
      if (!ctx) return;
      const g = ctx.createLinearGradient(0, 0, w, h);
      g.addColorStop(0, pal[3]);
      g.addColorStop(0.55, pal[2] + "55");
      g.addColorStop(1, pal[1] + "33");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
      blob(w * 0.15, h * 0.20, Math.max(w, h) * 0.45, pal[2], 0.35);
      blob(w * 0.85, h * 0.85, Math.max(w, h) * 0.50, pal[1], 0.30);
      blob(w * 0.70, h * 0.10, Math.max(w, h) * 0.30, pal[0], 0.22);
    }

    function frame() {
      tRef.current += 16;
      const t = tRef.current;
      switch (effectiveVariant) {
        case "waves":
          drawWaves(t);
          break;
        case "aurora":
          drawAurora(t);
          break;
        case "dots":
          drawDots(t);
          break;
        case "field":
          drawField(t);
          break;
        case "mesh":
        default:
          drawMesh(t);
          break;
      }
      rafRef.current = requestAnimationFrame(frame);
    }

    if (effectiveVariant === "static") {
      drawStatic();
      const ro2 = new ResizeObserver(() => {
        resize();
        drawStatic();
      });
      ro2.observe(cvs);
      return () => {
        ro.disconnect();
        ro2.disconnect();
      };
    }

    rafRef.current = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, [variant, palette]);

  return (
    <div className="bg-root" aria-hidden="true">
      <canvas ref={canvasRef} className="bg-canvas" />
      <div className="bg-grain" />
      <div className="bg-vignette" />
    </div>
  );
}
