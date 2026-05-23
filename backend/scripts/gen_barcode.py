"""Generate Code 39 barcodes for primărie form codes, with the
human-readable `* X X X X X X *` caption underneath that matches the
official Cluj-Napoca form layout.

Usage:
    python gen_barcode.py                       # regenerates the full inventory
    python gen_barcode.py 491001 460006 ...     # specific codes only
"""
from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont

OUT_DIRS = [
    Path(r"C:\Users\Oricum\OneDrive\Desktop\HACKATON CLUJ 2026\ClujHackathon\primarii-app-data\scenarii\assets"),
    Path(r"C:\Users\Oricum\OneDrive\Desktop\HACKATON CLUJ 2026\ClujHackathon\backend\templates\assets"),
]
INVENTORY = Path(__file__).parent / "barcode_inventory.json"

CODE39 = barcode.get_barcode_class("code39")

BAR_OPTIONS = {
    "module_width": 0.40,
    "module_height": 12.0,
    "quiet_zone": 2.0,
    "write_text": False,
    "background": "white",
    "foreground": "black",
}

CAPTION_FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\consolab.ttf"),
    Path(r"C:\Windows\Fonts\courbd.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
    Path("/Library/Fonts/Courier New Bold.ttf"),
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in CAPTION_FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _render_bars(code: str) -> Image.Image:
    bc = CODE39(code, writer=ImageWriter(), add_checksum=False)
    buf = BytesIO()
    bc.write(buf, options=BAR_OPTIONS)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def _compose(code: str) -> Image.Image:
    bars = _render_bars(code)
    bw, bh = bars.size

    caption = "* " + " ".join(code) + " *"
    font_size = max(28, int(bh * 0.28))
    font = _load_font(font_size)

    # Measure caption width.
    dummy = Image.new("RGB", (1, 1))
    tw, th = dummy.getbbox()[:2] if False else (0, 0)
    bbox = ImageDraw.Draw(dummy).textbbox((0, 0), caption, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    gap = max(6, int(bh * 0.05))
    pad_bottom = max(8, int(bh * 0.08))
    final_w = max(bw, tw + 20)
    final_h = bh + gap + th + pad_bottom

    out = Image.new("RGB", (final_w, final_h), "white")
    out.paste(bars, ((final_w - bw) // 2, 0))
    draw = ImageDraw.Draw(out)
    draw.text(
        ((final_w - tw) // 2 - bbox[0], bh + gap - bbox[1]),
        caption,
        fill="black",
        font=font,
    )
    return out


def gen(code: str) -> None:
    img = _compose(code)
    for out_dir in OUT_DIRS:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"barcode-{code}.png"
        img.save(out_path, "PNG", optimize=True)
        print(f"  -> {out_path}  ({img.size[0]}x{img.size[1]}, {out_path.stat().st_size:,} B)")


def _codes_from_inventory() -> list[str]:
    data = json.loads(INVENTORY.read_text(encoding="utf-8"))
    seen: set[str] = set()
    for meta in data.values():
        code = meta.get("barcode")
        if code:
            seen.add(code)
    return sorted(seen)


def main() -> None:
    codes = sys.argv[1:]
    if not codes:
        codes = _codes_from_inventory()
        # Backend templates also reference 460007 (tăiere arbore) which has
        # no entry in the inventory because the source PDF is image-only.
        if "460007" not in codes:
            codes.append("460007")
    for c in codes:
        print(f"Code 39: {c}")
        gen(c)


if __name__ == "__main__":
    main()
