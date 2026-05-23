"""Quick regex test - find out why RE_3MP_HEADER isn't matching scenariu-1 CAF."""
import re
from pathlib import Path

text = Path(r"C:\Users\Oricum\OneDrive\Desktop\HACKATON CLUJ 2026\ClujHackathon\primarii-app-data\scenarii\scenariu-1-certificat-atestare-fiscala\491002-Cerere-CAF-fillable.tex").read_text(encoding="utf-8")

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

m = RE_3MP_HEADER.search(text)
print("Full match?", bool(m))

# Bisect to find where it stops matching
patterns = [
    (r"\\begin\{minipage\}\[t\]\{0\.35\\textwidth\}\s*", "minipage open"),
    (r"\\textbf\{PRIMĂRIA\}\\\\\s*", "PRIMĂRIA"),
    (r"\\textbf\{CLUJ-NAPOCA\}\s*", "CLUJ-NAPOCA"),
    (r"\\end\{minipage\}%\s*", "minipage end"),
    (r"\\begin\{minipage\}\[t\]\{0\.30\\textwidth\}\s*", "second minipage"),
    (r"\\centering\s*", "centering"),
    (r"\\vspace\{0pt\}\s*", "vspace 0"),
    (r"\$\*\\,[\d\\,\s]+\\,\*\$\s*", "barcode"),
    (r"\\end\{minipage\}%\s*", "minipage end 2"),
    (r"\\begin\{minipage\}\[t\]\{0\.35\\textwidth\}\s*", "third minipage"),
    (r"\\raggedleft\s*", "raggedleft"),
    (r"Nr\. \\fillline\[3\.5cm\] / \\fillline\[1\.5cm\]\s*", "Nr. line"),
    (r"\\end\{minipage\}", "final minipage end"),
]

cumulative = ""
for p, name in patterns:
    cumulative += p
    try:
        rec = re.compile(cumulative, re.DOTALL)
        m = rec.search(text)
        print(f"  {'OK' if m else 'FAIL'}: cumulative through {name}")
        if not m:
            # Find where in text we got
            # Try matching just the previous combo
            print("    (last working segment failed at: " + name + ")")
            break
    except re.error as e:
        print(f"  REGEX ERROR at {name}: {e}")
        break
