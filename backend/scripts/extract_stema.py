"""Extract the Cluj-Napoca coat-of-arms (stema) by clip-rendering a region
of the source PDF at high DPI, then auto-cropping whitespace.
"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz  # pymupdf
from PIL import Image, ImageChops

SRC_PDF = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    r"C:\Users\Oricum\OneDrive\Desktop\HACKATON CLUJ 2026\ClujHackathon\primarii-app-data\scenarii\scenariu-6-taiere-arbore-curte-privata\Cerere-aviz-doborare-arbori-curte-privata-source.pdf"
)
OUT_PATHS = [
    Path(r"C:\Users\Oricum\OneDrive\Desktop\HACKATON CLUJ 2026\ClujHackathon\primarii-app-data\scenarii\assets\stema-cluj.png"),
    Path(r"C:\Users\Oricum\OneDrive\Desktop\HACKATON CLUJ 2026\ClujHackathon\backend\templates\assets\stema-cluj.png"),
]

DPI = 400
ZOOM = DPI / 72

doc = fitz.open(SRC_PDF)
page = doc[0]
page_rect = page.rect
print(f"Page rect: {page_rect}")

# Stema is in the top-left ~10% × ~10% of the page in PDF point space (1pt = 1/72in).
# A4 page is 595 x 842 pt. Stema area roughly: x=20..90, y=20..100 pt.
clip = fitz.Rect(20, 22, 72, 102)
mat = fitz.Matrix(ZOOM, ZOOM)
pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
tmp_png = Path(__file__).parent / "_stema_raw.png"
pix.save(tmp_png)
print(f"Rendered raw clip -> {tmp_png} ({pix.width}x{pix.height})")

# Auto-crop white-ish borders (threshold-based to ignore JPEG noise).
img = Image.open(tmp_png).convert("L")  # grayscale
from PIL import ImageOps
inverted = ImageOps.invert(img)
# Binarize: anything darker than 240 in original (i.e. > 15 inverted) is "content"
mask = inverted.point(lambda p: 255 if p > 15 else 0)
bbox = mask.getbbox()
img_rgb = Image.open(tmp_png).convert("RGB")
if bbox:
    # Add small padding around the content
    pad = 10
    bbox = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
            min(img_rgb.width, bbox[2] + pad), min(img_rgb.height, bbox[3] + pad))
    cropped = img_rgb.crop(bbox)
    print(f"Threshold-cropped to {cropped.size} (from bbox {bbox})")
else:
    cropped = img_rgb
    print("No content found, keeping full clip")

for out in OUT_PATHS:
    out.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(out, "PNG")
    print(f"  -> {out} ({out.stat().st_size} bytes)")

tmp_png.unlink()
