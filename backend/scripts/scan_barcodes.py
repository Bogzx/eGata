"""Scan every -source.pdf in scenarii/ and extract the actual barcode code.

Handles 3 PDF flavors:
1. Plain text `*123456*` (e.g. scenariu-10)
2. Barcode font with Private Use Area chars ( + digits-in--) -
   typical for fonts like Free3of9 / IDAutomationHC39M that map ASCII to PUA.
3. Image-only scanned PDFs - falls back to pymupdf's built-in OCR.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import fitz  # pymupdf

ROOT = Path(r"C:\Users\Oricum\OneDrive\Desktop\HACKATON CLUJ 2026\ClujHackathon\primarii-app-data\scenarii")

# 1. Plain text: *123456*
RE_PLAIN = re.compile(r"\*\s*([0-9]{4,9})\s*\*")
# 2. PUA:  + [-]+ + 
RE_PUA = re.compile(r"([-]{4,9})")

def decode_pua(s: str) -> str:
    """Map - -> '0'-'9'."""
    return "".join(chr(ord(c) - 0xF000) for c in s)


def find_barcode(text: str) -> str | None:
    from collections import Counter
    matches: list[str] = []
    matches.extend(RE_PLAIN.findall(text))
    for pua_match in RE_PUA.findall(text):
        matches.append(decode_pua(pua_match))
    if not matches:
        return None
    return Counter(matches).most_common(1)[0][0]


def is_image_only(page: fitz.Page) -> bool:
    return len(page.get_text().strip()) == 0


results: dict[str, dict] = {}

for pdf_path in sorted(ROOT.rglob("*-source.pdf")):
    rel = pdf_path.relative_to(ROOT).as_posix()
    if "Consimtamant" in pdf_path.name:
        results[rel] = {"barcode": None, "skip_reason": "consimtamant (pdfpages wrapper)"}
        continue

    doc = fitz.open(pdf_path)
    page = doc[0]
    text = page.get_text()
    code = find_barcode(text)

    notes = []
    if code is None and is_image_only(page):
        # Try OCR via tesseract (if installed). pymupdf's get_textpage_ocr()
        # needs tessdata. Try a simpler path: render page top region and OCR.
        try:
            # Render top ~15% of page at high DPI
            page_rect = page.rect
            top_clip = fitz.Rect(0, 0, page_rect.width, page_rect.height * 0.15)
            mat = fitz.Matrix(3, 3)  # 216 DPI-ish for an A4 ~ 72 DPI baseline
            pix = page.get_pixmap(matrix=mat, clip=top_clip)
            tp = page.get_textpage_ocr(flags=0, full=False, language="eng", dpi=300)
            ocr_text = tp.extractText()
            code = find_barcode(ocr_text)
            if code:
                notes.append("via OCR")
        except Exception as exc:
            notes.append(f"OCR failed: {type(exc).__name__}: {str(exc)[:80]}")

    results[rel] = {
        "barcode": code,
        "page_count": doc.page_count,
        "image_only": is_image_only(page),
        "notes": notes,
    }
    doc.close()

print(json.dumps(results, indent=2, ensure_ascii=False))

out = Path(__file__).parent / "barcode_inventory.json"
out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n=> Saved: {out}")

unique = sorted({v["barcode"] for v in results.values() if v.get("barcode")})
print(f"\nUnique barcode codes ({len(unique)}): {unique}")
null_pdfs = [k for k, v in results.items() if v.get("barcode") is None and "Consimtamant" not in k]
print(f"\nPDFs without detected barcode ({len(null_pdfs)}):")
for p in null_pdfs:
    print(f"  - {p}  image_only={results[p].get('image_only')}")
