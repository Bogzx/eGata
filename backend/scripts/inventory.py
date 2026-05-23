"""Build a complete inventory: per PDF, decide
  - barcode code (or None)
  - has_stema  (True/False)

Stema heuristic:
  - Image-only scanned PDF with 'PRIMĂRIA' visible at top-left → YES
  - Embedded small image (<50pt wide) at top-left → YES (Cluj forms)
  - Embedded image bigger but with 'PRIMĂRIA' nearby → YES (some Cluj forms)
  - No images on page 1 → NO (Anexa-1 et al.)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import fitz

ROOT = Path(r"C:\Users\Oricum\OneDrive\Desktop\HACKATON CLUJ 2026\ClujHackathon\primarii-app-data\scenarii")

RE_PLAIN = re.compile(r"\*\s*([0-9]{4,9})\s*\*")
RE_PUA = re.compile(r"([][-]{4,9}[])")

def decode_pua(s: str) -> str:
    return "".join(chr(ord(c) - 0xF000) for c in s)

def find_barcode(text: str) -> str | None:
    from collections import Counter
    matches: list[str] = RE_PLAIN.findall(text)
    for pua in RE_PUA.findall(text):
        matches.append(decode_pua(pua[1:-1]))  # strip surrounding *
    if not matches:
        return None
    return Counter(matches).most_common(1)[0][0]

# Manual overrides for image-only PDFs (verified visually earlier)
MANUAL_BARCODE: dict[str, str] = {
    "scenariu-6-taiere-arbore-curte-privata/Cerere-aviz-doborare-arbori-curte-privata-source.pdf": "460007",
}

def detect_stema(doc: fitz.Document) -> bool:
    page = doc[0]
    text = page.get_text()
    imgs = page.get_images(full=True)
    has_primaria_text = "PRIMĂRIA" in text or "PRIM" in text

    if not imgs:
        # No images → no stema (national MAI text-only forms)
        return False

    # Check for Cluj branding text + at least one image → stema
    if has_primaria_text:
        return True

    # Image-only scanned PDF (no text). Check if first image is full-page → likely a scan that includes stema
    img = imgs[0]
    info = doc.extract_image(img[0])
    w, h = info["width"], info["height"]
    if w > 1000 and h > 1500:  # Full-page raster scan
        return True

    return False


results: dict[str, dict] = {}

for pdf_path in sorted(ROOT.rglob("*-source.pdf")):
    rel = pdf_path.relative_to(ROOT).as_posix()
    if "Consimtamant" in pdf_path.name:
        results[rel] = {"barcode": None, "has_stema": False, "skip_reason": "consimtamant"}
        continue

    doc = fitz.open(pdf_path)
    page = doc[0]
    text = page.get_text()
    barcode = find_barcode(text) or MANUAL_BARCODE.get(rel)

    results[rel] = {
        "barcode": barcode,
        "has_stema": detect_stema(doc),
        "page_count": doc.page_count,
        "image_only": len(text.strip()) == 0,
    }
    doc.close()

print(json.dumps(results, indent=2, ensure_ascii=False))

out = Path(__file__).parent / "form_inventory.json"
out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n=> Saved: {out}")

print("\n=== SUMMARY ===")
print(f"Total forms (excl. consimtamant): {sum(1 for k in results if 'Consimtamant' not in k)}")
print(f"  with barcode:  {sum(1 for v in results.values() if v.get('barcode'))}")
print(f"  with stema:    {sum(1 for v in results.values() if v.get('has_stema'))}")
print(f"  without either: {sum(1 for v in results.values() if not v.get('barcode') and not v.get('has_stema') and 'skip_reason' not in v)}")

unique = sorted({v["barcode"] for v in results.values() if v.get("barcode")})
print(f"\nUnique codes ({len(unique)}): {unique}")

no_stema = [k for k, v in results.items() if 'skip_reason' not in v and not v.get('has_stema')]
print(f"\nForms WITHOUT stema ({len(no_stema)}):")
for k in no_stema:
    print(f"  - {k}")
