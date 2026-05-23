"use client";

import { useEffect, useRef } from "react";

export type MeshPalette = {
  dark: string;
  mid: string;
  light: string;
  bg: string;
};

const GREEN: MeshPalette = {
  dark: "#1F6F5F",
  mid: "#2FA084",
  light: "#6FCF97",
  bg: "#EEEEEE",
};

type Props = {
  palette?: MeshPalette;
  dark?: boolean;
};

export function AnimatedMesh({ palette = GREEN, dark = false }: Props) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const cvs = ref.current;
    if (!cvs) return;
    const ctx = cvs.getContext("2d");
    if (!ctx) return;

    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let w = 0;
    let h = 0;
    let raf = 0;
    let t = 0;

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

    const pal: [string, string, string, string] = [
      palette.dark,
      palette.mid,
      palette.light,
      dark ? "#06120F" : palette.bg,
    ];

    function blob(cx: number, cy: number, r: number, color: string, alpha: number) {
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

    const orbs = [
      { c: pal[0], rx: 0.45, ry: 0.55, sx: 0.00045, sy: 0.00037, size: 0.55, a: dark ? 0.55 : 0.85 },
      { c: pal[1], rx: 0.30, ry: 0.40, sx: 0.00062, sy: 0.00051, size: 0.50, a: dark ? 0.50 : 0.80 },
      { c: pal[2], rx: 0.35, ry: 0.30, sx: 0.00073, sy: 0.00043, size: 0.45, a: dark ? 0.42 : 0.75 },
      { c: pal[1], rx: 0.25, ry: 0.50, sx: 0.00038, sy: 0.00060, size: 0.40, a: dark ? 0.40 : 0.70 },
      { c: pal[0], rx: 0.40, ry: 0.45, sx: 0.00029, sy: 0.00047, size: 0.50, a: dark ? 0.35 : 0.55 },
    ];

    function paint() {
      if (!ctx) return;
      ctx.fillStyle = pal[3];
      ctx.fillRect(0, 0, w, h);
      const cx = w / 2;
      const cy = h / 2;
      const R = Math.max(w, h);
      orbs.forEach((o, i) => {
        const px = cx + Math.cos(t * o.sx + i * 1.7) * (w * o.rx);
        const py = cy + Math.sin(t * o.sy + i * 2.3) * (h * o.ry);
        blob(px, py, R * o.size, o.c, o.a);
      });
    }

    if (reduced) {
      paint();
    } else {
      const frame = () => {
        t += 16;
        paint();
        raf = requestAnimationFrame(frame);
      };
      raf = requestAnimationFrame(frame);
    }

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [palette, dark]);

  return (
    <div className="gh-bg" aria-hidden="true">
      <canvas ref={ref} />
      <div className="gh-grain" />
      <div className="gh-vignette" />
    </div>
  );
}
