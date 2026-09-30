"""Auto-patch backend/templates/*.tex (excluding base.tex and the 5 new ones
already image-upgraded) to use real stema + Code 39 barcode images.

Differences from patch_fillables.py:
1. Image paths are `assets/...` (no `../`), because pdf.py copies the
   `templates/assets/` directory into the tempdir at runtime.
2. Backend templates have Jinja2 `{{...}}` placeholders interleaved.
3. Multiple header layouts found in existing templates:
     - single-line: `\textbf{PRIMĂRIA CLUJ-NAPOCA} \hfill Cod: ... \hfill Nr. ...`
     - 3-col tabular: \textbf{PRIMĂRIA} & \textbf{*XXX*} & Nr. ... \\
                       \textbf{CLUJ-NAPOCA} & & \\
     - 3-minipage Cluj (new templates) -- already patched, skip
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

TPL_DIR = Path(r"C:\Users\Oricum\OneDrive\Desktop\HACKATON CLUJ 2026\ClujHackathon\backend\templates")

# Map: template filename -> (barcode_code, has_stema)
MAPPING: dict[str, tuple[str | None, bool]] = {
    "abonament-parcare-strada.tex":          ("700001", True),
    "actualizare-date-contribuabil.tex":     ("491001", True),
    "atestare-edificare.tex":                ("432008", True),
    "aviz-principiu-constructii.tex":        ("460006", True),
    "card-parcare-dizabilitati.tex":         ("802012", True),
    "cerere-certificat-urbanism.tex":        ("431001", True),
    "certificat-fiscal.tex":                 ("491002", True),
    "compensare-creante-fiscale.tex":        ("492006", False),
    "declarare-cladire.tex":                 ("491007", True),
    "indemnizatie-dizabilitati.tex":         ("802013", True),
    "prelungire-autorizatie-construire.tex": ("432002", True),
    "prelungire-certificat-urbanism.tex":    ("431002", True),
    "preschimbare-ci.tex":                   (None, False),  # Anexa-1, national, no stema/barcode
    "restituire-sume-fiscale.tex":           ("492007", False),
    "situatie-debite.tex":                   ("491004", True),
    "transport-urban-dizabilitati.tex":      ("802014", True),
}

# Already-image patterns (from new templates) - idempotency guard
RE_ALREADY_UPGRADED = re.compile(r"\\includegraphics\[height=1\.5cm\]\{assets/stema-cluj\.png\}")

# Barcode patterns
RE_PLAIN_BARCODE = re.compile(r"\*([0-9]{4,9})\*(?!\$)")           # *492006*
RE_SPACED_BARCODE = re.compile(r"\$\*\\,([\d\\,\s]+)\\,\*\$")        # $*\,4\,9\,1\,0\,0\,2\,*$

# Header patterns
# Single-line: \begin{flushleft} \textbf{PRIMĂRIA CLUJ-NAPOCA} ... \end{flushleft}
RE_SINGLELINE_HEADER = re.compile(
    r"\\begin\{flushleft\}\s*"
    r"\\textbf\{PRIMĂRIA CLUJ-NAPOCA\}\s*\\hfill\s*"
    r"(?:Cod:[^\n]*?\\hfill\s*)?"
    r"Nr\. \\fillline\[\d+cm\] / \\fillline\[\d+cm\]\s*"
    r"\\end\{flushleft\}",
    re.DOTALL,
)

# 3-column tabular: \begin{tabular}{p{5cm} p{5cm} p{5cm}}
#                   \textbf{PRIMĂRIA} & \textbf{*X*} & Nr. ... \\
#                   \textbf{CLUJ-NAPOCA} & & \\
#                   \end{tabular}
RE_TABULAR_HEADER = re.compile(
    r"\\begin\{tabular\}\{[^}]*\}\s*"
    r"\\textbf\{PRIMĂRIA\}\s*&\s*\\textbf\{\*[0-9]+\*\}\s*&\s*Nr\.[^\\]*\\\\\s*"
    r"\\textbf\{CLUJ-NAPOCA\}\s*&\s*&\s*\\\\\s*"
    r"\\end\{tabular\}",
    re.DOTALL,
)

# 3-minipage Cluj header (same as fillable, used by certificat-fiscal et al.):
RE_3MP_HEADER = re.compile(
    r"\\begin\{minipage\}\[t\]\{0\.35\\textwidth\}\s*"
    r"\\textbf\{PRIMĂRIA\}\\\\\s*"
    r"\\textbf\{CLUJ-NAPOCA\}\s*"
    r"\\end\{minipage\}%\s*"
    r"\\begin\{minipage\}\[t\]\{0\.30\\textwidth\}\s*"
    r"\\centering\s*"
    r"\\vspace\{0pt\}\s*"
    r"(?:\$\*\\,[\d\\,\s]+\\,\*\$|\\includegraphics\[[^\]]*\]\{assets/barcode-[0-9]+\.png\})\s*"
    r"\\end\{minipage\}%\s*"
    r"\\begin\{minipage\}\[t\]\{0\.35\\textwidth\}\s*"
    r"\\raggedleft\s*"
    r"Nr\. \\fillline\[3\.5cm\] / \\fillline\[1\.5cm\]\s*"
    r"\\end\{minipage\}",
    re.DOTALL,
)

# Variant 1: 0.45/0.25/0.25 layout with \hfill separators (actualizare-date, situatie-debite)
RE_3MP_VARIANT_HFILL = re.compile(
    r"\\begin\{minipage\}\[t\]\{0\.45\\textwidth\}\s*"
    r"\\textbf\{PRIMĂRIA\}\\\\\s*"
    r"\\textbf\{CLUJ-NAPOCA\}\s*"
    r"\\end\{minipage\}\s*"
    r"\\hfill\s*"
    r"\\begin\{minipage\}\[t\]\{0\.25\\textwidth\}\s*"
    r"\\centering\s*"
    r"\\includegraphics\[[^\]]*\]\{assets/barcode-[0-9]+\.png\}\s*"
    r"\\end\{minipage\}\s*"
    r"\\hfill\s*"
    r"\\begin\{minipage\}\[t\]\{0\.25\\textwidth\}\s*"
    r"Nr\. \\fillline\[\d+cm\] / \\fillline\[\d+(?:\.\d+)?cm\]\s*"
    r"\\end\{minipage\}",
    re.DOTALL,
)

# Variant 2: 0.3/0.4/0.3 layout with % separators
# (atestare-edificare, aviz-principiu, cerere-certificat-urbanism, prelungire-*)
RE_3MP_VARIANT_PERCENT = re.compile(
    r"\\begin\{minipage\}\{0\.3\\textwidth\}\s*"
    r"\\textbf\{PRIMĂRIA\}\\\\\s*"
    r"\\textbf\{CLUJ-NAPOCA\}\s*"
    r"\\end\{minipage\}%\s*"
    r"\\begin\{minipage\}\{0\.4\\textwidth\}\s*"
    r"\\centering\s*"
    r"\\textbf\{\\includegraphics\[[^\]]*\]\{assets/barcode-[0-9]+\.png\}\}\s*"
    r"\\end\{minipage\}%\s*"
    r"\\begin\{minipage\}\{0\.3\\textwidth\}\s*"
    r"\\raggedleft\s*"
    r"Nr\. \\fillline\[\d+cm\] / \\fillline\[\d+(?:\.\d+)?cm\]\s*"
    r"\\end\{minipage\}",
    re.DOTALL,
)

# Variant 3: 3-column tabular with image inside textbf
RE_TABULAR_VARIANT = re.compile(
    r"\\begin\{tabular\}\{[^\n]*\}\s*"
    r"\\textbf\{PRIMĂRIA\}\s*&\s*"
    r"\\textbf\{\\includegraphics\[[^\]]*\]\{assets/barcode-[0-9]+\.png\}\}\s*&\s*"
    r"Nr\..*?\\\\\s*"
    r"\\textbf\{CLUJ-NAPOCA\}\s*&\s*&\s*\\\\\s*"
    r"\\end\{tabular\}",
    re.DOTALL,
)

# Footer trailing minipage with barcode image already in place (from earlier round)
# or with spaced asterisks. We replace either to the standardised image.
RE_FOOTER_BARCODE = re.compile(
    r"(\\begin\{minipage\}\[t\]\{0\.35\\textwidth\}\s*\\raggedleft\s*)"
    r"(?:\$\*\\,[\d\\,\s]+\\,\*\$|\\includegraphics\[[^\]]*\]\{assets/barcode-[0-9]+\.png\})"
    r"(\s*\\end\{minipage\})",
    re.DOTALL,
)

# Two-line PRIMĂRIA + CLUJ-NAPOCA in minipage style (existing scenariu-1..5 backend ones)
# (Skip - new templates already use \includegraphics)


def make_header(barcode: str | None, has_stema: bool) -> str:
    if has_stema and barcode:
        return (
            "\\noindent\n"
            "\\begin{minipage}[t]{0.40\\textwidth}\n"
            "\\vspace{0pt}\n"
            "\\includegraphics[height=1.5cm]{assets/stema-cluj.png}%\n"
            "\\hspace{0.2cm}%\n"
            "\\raisebox{0.5cm}{\\parbox[t]{3.5cm}{\\textbf{PRIMĂRIA}\\\\\\textbf{CLUJ-NAPOCA}}}\n"
            "\\end{minipage}%\n"
            "\\begin{minipage}[t]{0.30\\textwidth}\n"
            "\\centering\n"
            "\\vspace{0.4cm}\n"
            f"\\includegraphics[width=3.5cm,height=0.9cm]{{assets/barcode-{barcode}.png}}\n"
            "\\end{minipage}%\n"
            "\\begin{minipage}[t]{0.30\\textwidth}\n"
            "\\raggedleft\n"
            "\\vspace{0.6cm}\n"
            "Nr. \\fillline[3cm] / \\fillline[1cm]\n"
            "\\end{minipage}"
        )
    if has_stema and not barcode:
        return (
            "\\noindent\n"
            "\\begin{minipage}[t]{0.40\\textwidth}\n"
            "\\vspace{0pt}\n"
            "\\includegraphics[height=1.5cm]{assets/stema-cluj.png}%\n"
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
    if barcode and not has_stema:
        # No stema (DITL forms): just barcode + Nr., no Cluj branding
        return (
            "\\noindent\n"
            "\\hfill\n"
            "\\begin{minipage}[t]{0.40\\textwidth}\n"
            "\\centering\n"
            f"\\includegraphics[width=4cm,height=0.9cm]{{assets/barcode-{barcode}.png}}\n"
            "\\end{minipage}\n"
            "\\hfill\n"
            "\\begin{minipage}[t]{0.30\\textwidth}\n"
            "\\raggedleft\n"
            "Nr. \\fillline[3cm] / \\fillline[1cm]\n"
            "\\end{minipage}"
        )
    return ""


def patch_file(tex_path: Path, barcode: str | None, has_stema: bool, dry_run: bool = False) -> tuple[bool, list[str]]:
    text = tex_path.read_text(encoding="utf-8")
    orig = text
    log: list[str] = []

    new_header = make_header(barcode, has_stema)

    # Try 3MP Cluj header (most common in existing templates)
    if new_header:
        text, n = RE_3MP_HEADER.subn(lambda m: new_header, text)
        if n:
            log.append(f"3MP header replaced (n={n})")

    # Try variants
    if new_header:
        text, n = RE_3MP_VARIANT_HFILL.subn(lambda m: new_header, text)
        if n:
            log.append(f"3MP variant hfill replaced (n={n})")
        text, n = RE_3MP_VARIANT_PERCENT.subn(lambda m: new_header, text)
        if n:
            log.append(f"3MP variant percent replaced (n={n})")
        text, n = RE_TABULAR_VARIANT.subn(lambda m: new_header, text)
        if n:
            log.append(f"tabular variant replaced (n={n})")

    # Try tabular header (3-col layout - older pattern)
    if new_header:
        text, n = RE_TABULAR_HEADER.subn(lambda m: new_header, text)
        if n:
            log.append(f"tabular header replaced (n={n})")

    # Try single-line header
    if new_header:
        text, n = RE_SINGLELINE_HEADER.subn(lambda m: new_header, text)
        if n:
            log.append(f"single-line header replaced (n={n})")

    # Footer barcode (in trailing minipage)
    if barcode:
        footer_img = f"\\includegraphics[width=3cm,height=0.7cm]{{assets/barcode-{barcode}.png}}"
        def _footer(m):
            return m.group(1) + footer_img + m.group(2)
        text, n = RE_FOOTER_BARCODE.subn(_footer, text)
        if n:
            log.append(f"footer barcode replaced (n={n})")

    # Replace all remaining barcode text/sequences with image
    if barcode:
        img_inline = f"\\includegraphics[width=3cm,height=0.7cm]{{assets/barcode-{barcode}.png}}"
        img_centered = f"\\includegraphics[width=3.5cm,height=0.9cm]{{assets/barcode-{barcode}.png}}"

        # Spaced: $*\,4\,9\,1\,0\,0\,2\,*$
        text, n = RE_SPACED_BARCODE.subn(lambda m: img_centered, text)
        if n:
            log.append(f"spaced barcode replaced (n={n})")

        # Plain: *492006*  (also handles \textbf{*492006*})
        text, n = RE_PLAIN_BARCODE.subn(lambda m: img_inline, text)
        if n:
            log.append(f"plain barcode replaced (n={n})")

    if text == orig:
        return False, ["no changes (pattern not found)"]
    if not dry_run:
        tex_path.write_text(text, encoding="utf-8")
    return True, log


def main(dry_run: bool = False) -> int:
    total = changed = 0
    for fname, (barcode, has_stema) in MAPPING.items():
        path = TPL_DIR / fname
        if not path.exists():
            print(f"  [MISSING] {fname}")
            continue
        total += 1
        did, log = patch_file(path, barcode, has_stema, dry_run=dry_run)
        if did:
            changed += 1
        prefix = "CHANGED" if did else "skip"
        print(f"  [{prefix}] {fname}  (barcode={barcode}, stema={has_stema})")
        for ln in log:
            print(f"      - {ln}")
    print()
    print(f"Summary: {changed}/{total} backend templates changed{' (dry run)' if dry_run else ''}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
