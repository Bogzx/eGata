"""Generate Code 39 barcodes for primărie form codes.

Usage:
    python gen_barcode.py 460007 446011 313001 801001 304001
"""
from __future__ import annotations

import sys
from pathlib import Path

import barcode
from barcode.writer import ImageWriter

OUT_DIRS = [
    Path(r"C:\Users\Oricum\OneDrive\Desktop\HACKATON CLUJ 2026\ClujHackathon\primarii-app-data\scenarii\assets"),
    Path(r"C:\Users\Oricum\OneDrive\Desktop\HACKATON CLUJ 2026\ClujHackathon\backend\templates\assets"),
]

CODE39 = barcode.get_barcode_class("code39")

OPTIONS = {
    "module_width": 0.30,
    "module_height": 8.0,
    "quiet_zone": 2.0,
    "font_size": 0,         # no human-readable digits under (the official PDFs have them)
    "write_text": False,
    "background": "white",
    "foreground": "black",
}

def gen(code: str) -> None:
    bc = CODE39(code, writer=ImageWriter(), add_checksum=False)
    for out_dir in OUT_DIRS:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_base = out_dir / f"barcode-{code}"
        # python-barcode appends ".png" automatically
        bc.save(str(out_base), options=OPTIONS)
        print(f"  -> {out_base}.png")

if __name__ == "__main__":
    codes = sys.argv[1:] or ["460007"]
    for c in codes:
        print(f"Code 39: {c}")
        gen(c)
