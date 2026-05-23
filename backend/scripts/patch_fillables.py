"""Auto-patch every -fillable.tex in scenarii/ to use real stema + Code 39 barcode
images, based on form_inventory.json.

Three substitution rules:

A. 3-minipage Cluj header (most forms):
       \begin{minipage}[t]{0.35\textwidth} \textbf{PRIMARIA}\\ \textbf{CLUJ-NAPOCA} \end{minipage}%
       \begin{minipage}[t]{0.30\textwidth} ... $*\,X\,X\,X\,*$ ... \end{minipage}%
       \begin{minipage}[t]{0.35\textwidth} \raggedleft Nr. ... \end{minipage}
   -> stema image + barcode image + Nr.

B. Plain barcode text  *492006*  (DITL forms, no stema)
   -> \includegraphics[barcode]

C. Spaced barcode  $*\,4\,9\,1\,0\,0\,7\,*$  embedded in non-3-minipage layouts (e.g. ITL-001)
   -> \includegraphics[barcode]

D. Footer barcode (in trailing minipage)
   -> \includegraphics[smaller barcode]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Oricum\OneDrive\Desktop\HACKATON CLUJ 2026\ClujHackathon\primarii-app-data\scenarii")
INV_PATH = Path(__file__).parent / "form_inventory.json"

inventory = json.loads(INV_PATH.read_text(encoding="utf-8"))

# ----- regex patterns -----

# Pattern A: full 3-minipage header (matches my own pattern as well as scenariu-1..5)
RE_3MP_HEADER = re.compile(
    r"\\begin\{minipage\}\[t\]\{0\.35\\textwidth\}\s*"
    r"\\textbf\{PRIMĂRIA\}\\\\\s*"
    r"\\textbf\{CLUJ-NAPOCA\}\s*"
    r"\\end\{minipage\}%\s*"
    r"\\begin\{minipage\}\[t\]\{0\.30\\textwidth\}\s*"
    r"\\centering\s*"
    r"\\vspace\{0pt\}\s*"
    r"\$\*\\,[\d\\,\s]+\\,\*\$\s*"
    r"\\end\{minipage\}%\s*"
    r"\\begin\{minipage\}\[t\]\{0\.35\\textwidth\}\s*"
    r"\\raggedleft\s*"
    r"Nr\. \\fillline\[3\.5cm\] / \\fillline\[1\.5cm\]\s*"
    r"\\end\{minipage\}",
    re.DOTALL,
)

# Pattern A (after upgrade): with images. Used for re-runs / idempotency.
RE_3MP_HEADER_UPGRADED = re.compile(
    r"\\noindent\s*\\begin\{minipage\}\[t\]\{0\.40\\textwidth\}\s*"
    r"\\vspace\{0pt\}\s*"
    r"\\includegraphics\[height=1\.5cm\]\{\.\.\/assets\/stema-cluj\.png\}",
    re.DOTALL,
)

# Pattern D: footer trailing minipage with spaced barcode
RE_FOOTER_BARCODE = re.compile(
    r"(\\begin\{minipage\}\[t\]\{0\.35\\textwidth\}\s*\\raggedleft\s*)"
    r"\$\*\\,[\d\\,\s]+\\,\*\$"
    r"(\s*\\end\{minipage\})",
    re.DOTALL,
)

# Pattern B: plain *123456* (centered or inline) - DITL style
RE_PLAIN_BARCODE = re.compile(r"\*([0-9]{4,9})\*(?!\$)")

# Pattern C: spaced barcode  $*\,4\,9\,1\,0\,0\,7\,*$  in non-3MP layout
RE_SPACED_BARCODE = re.compile(r"\$\*\\,([\d\\,\s]+)\\,\*\$")

# Pattern E: single-line PRIMĂRIA header (700.001, Anexa-5 style)
#   \begin{flushleft} \textbf{PRIMĂRIA CLUJ-NAPOCA} \hfill [Cod: ... \hfill] Nr. ... \end{flushleft}
RE_SINGLELINE_HEADER = re.compile(
    r"\\begin\{flushleft\}\s*"
    r"\\textbf\{PRIMĂRIA CLUJ-NAPOCA\}\s*\\hfill\s*"
    r"(?:Cod:[^\n]*?\\hfill\s*)?"
    r"Nr\. \\fillline\[\d+cm\] / \\fillline\[\d+cm\]\s*"
    r"\\end\{flushleft\}",
    re.DOTALL,
)


def make_3mp_header(barcode_code: str | None, has_stema: bool) -> str:
    """Build the 3-minipage header. Caller decides if/how to use it."""
    if has_stema and barcode_code:
        return (
            "\\noindent\n"
            "\\begin{minipage}[t]{0.40\\textwidth}\n"
            "\\vspace{0pt}\n"
            f"\\includegraphics[height=1.5cm]{{../assets/stema-cluj.png}}%\n"
            "\\hspace{0.2cm}%\n"
            "\\raisebox{0.5cm}{\\parbox[t]{3.5cm}{\\textbf{PRIMĂRIA}\\\\\\textbf{CLUJ-NAPOCA}}}\n"
            "\\end{minipage}%\n"
            "\\begin{minipage}[t]{0.30\\textwidth}\n"
            "\\centering\n"
            "\\vspace{0.4cm}\n"
            f"\\includegraphics[width=3.5cm,height=0.9cm]{{../assets/barcode-{barcode_code}.png}}\n"
            "\\end{minipage}%\n"
            "\\begin{minipage}[t]{0.30\\textwidth}\n"
            "\\raggedleft\n"
            "\\vspace{0.6cm}\n"
            "Nr. \\fillline[3cm] / \\fillline[1cm]\n"
            "\\end{minipage}"
        )
    if has_stema and not barcode_code:
        return (
            "\\noindent\n"
            "\\begin{minipage}[t]{0.40\\textwidth}\n"
            "\\vspace{0pt}\n"
            f"\\includegraphics[height=1.5cm]{{../assets/stema-cluj.png}}%\n"
            "\\hspace{0.2cm}%\n"
            "\\raisebox{0.5cm}{\\parbox[t]{3.5cm}{\\textbf{PRIMĂRIA}\\\\\\textbf{CLUJ-NAPOCA}}}\n"
            "\\end{minipage}%\n"
            "\\hfill\n"
            "\\begin{minipage}[t]{0.30\\textwidth}\n"
            "\\raggedleft\n"
            "\\vspace{0.6cm}\n"
            "Nr. \\fillline[3cm] / \\fillline[1cm]\n"
            "\\end{minipage}"
        )
    # no stema + barcode (unusual) - shouldn't hit in 3MP context
    if barcode_code and not has_stema:
        return (
            "\\noindent\n"
            "\\hfill\n"
            "\\begin{minipage}[t]{0.30\\textwidth}\n"
            "\\centering\n"
            f"\\includegraphics[width=3.5cm,height=0.9cm]{{../assets/barcode-{barcode_code}.png}}\n"
            "\\end{minipage}%\n"
            "\\hfill\n"
            "\\begin{minipage}[t]{0.30\\textwidth}\n"
            "\\raggedleft\n"
            "Nr. \\fillline[3cm] / \\fillline[1cm]\n"
            "\\end{minipage}"
        )
    return ""  # shouldn't be reached


def patch_file(tex_path: Path, info: dict, dry_run: bool = False) -> tuple[bool, list[str]]:
    """Returns (changed, log_lines)."""
    text = tex_path.read_text(encoding="utf-8")
    orig = text
    log: list[str] = []
    barcode = info.get("barcode")
    has_stema = info.get("has_stema", False)

    # If already upgraded, skip.
    if RE_3MP_HEADER_UPGRADED.search(text):
        log.append("already upgraded (idempotent skip)")
        return False, log

    # Rule A: replace standard 3-minipage Cluj header
    new_header = make_3mp_header(barcode, has_stema)
    text_a, count_a = RE_3MP_HEADER.subn(lambda m: new_header, text)
    if count_a:
        log.append(f"3MP header replaced (n={count_a})")
        text = text_a

    # Rule E: replace single-line PRIMĂRIA header
    if has_stema and (count_a == 0):
        text_e, count_e = RE_SINGLELINE_HEADER.subn(lambda m: new_header, text)
        if count_e:
            log.append(f"single-line header upgraded to 3MP (n={count_e})")
            text = text_e

    # Rule D: replace footer barcode with image (if barcode known)
    if barcode:
        footer_img = f"\\includegraphics[width=3cm,height=0.7cm]{{../assets/barcode-{barcode}.png}}"
        def _footer(m):
            return m.group(1) + footer_img + m.group(2)
        text, count_d = RE_FOOTER_BARCODE.subn(_footer, text)
        if count_d:
            log.append(f"footer barcode replaced (n={count_d})")

    # Rule C: replace any remaining spaced-asterisk barcodes (ITL-001 style)
    if barcode:
        spaced_img = f"\\includegraphics[width=3.5cm,height=0.9cm]{{../assets/barcode-{barcode}.png}}"
        text, count_c = RE_SPACED_BARCODE.subn(lambda m: spaced_img, text)
        if count_c:
            log.append(f"spaced barcode replaced (n={count_c})")

    # Rule B: replace plain *XXXXX* text (DITL style)
    if barcode:
        plain_img = f"\\includegraphics[width=3cm,height=0.7cm]{{../assets/barcode-{barcode}.png}}"
        text, count_b = RE_PLAIN_BARCODE.subn(lambda m: plain_img, text)
        if count_b:
            log.append(f"plain barcode replaced (n={count_b})")

    if text == orig:
        log.append("no changes (pattern not found)")
        return False, log

    if not dry_run:
        tex_path.write_text(text, encoding="utf-8")
    return True, log


def main(dry_run: bool = False) -> int:
    failures = 0
    total = 0
    changed = 0
    for source_pdf_key, info in inventory.items():
        if "skip_reason" in info:
            continue
        # Each -source.pdf has a matching -fillable.tex (replace suffix)
        fillable = source_pdf_key.replace("-source.pdf", "-fillable.tex")
        tex_path = ROOT / fillable
        if not tex_path.exists():
            print(f"  [MISSING] {fillable}")
            failures += 1
            continue
        total += 1
        did_change, log = patch_file(tex_path, info, dry_run=dry_run)
        if did_change:
            changed += 1
        prefix = "CHANGED" if did_change else "skip"
        print(f"  [{prefix}] {fillable}")
        for ln in log:
            print(f"      - {ln}")
    print()
    print(f"Summary: {changed}/{total} fillables changed{' (dry run)' if dry_run else ''}.")
    return failures


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
