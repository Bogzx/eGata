# LaTeX Templates — Index global

Pentru fiecare formular al primăriei (34 total, în 10 scenarii) ai **2 fișiere**:

| Fișier | Conținut |
|--------|----------|
| `<name>-source.pdf` | PDF-ul **ORIGINAL** al primăriei (descărcat de pe files.primariaclujnapoca.ro) |
| `<name>-fillable.tex` | Variantă **LaTeX-nativă** cu fielduri marcate explicit (`\fillline`, `\fillbox`, `\checkboxempty`) — pentru auto-fill |

**Restaurate / generate:** 2026-05-23 (scenariile 1-5); 2026-05-23 (scenariile 6-10 adăugate)
**Total fișiere:** 34 surse PDF + 34 templates fillable .tex

---

## Convenții comune fillable

**Preamble standard:**
```latex
\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[romanian]{babel}
\usepackage[margin=2cm]{geometry}
\usepackage{array,tabularx,enumitem,graphicx,setspace,xcolor,hyperref}
\usepackage{amssymb}       % \square pentru \checkboxempty
\usepackage{multirow}      % doar la ITL-001 + Anexa-1
\setlength{\parindent}{0pt}
\newcommand{\fillline}[1][6cm]{\underline{\hspace{#1}}}
\newcommand{\fillbox}[1][0.4cm]{\framebox[#1]{\rule{0pt}{#1}}}
\newcommand{\checkboxempty}{$\square$}
```

**Mapare câmpuri:**

| Tip câmp PDF | Comandă LaTeX |
|--------------|---------------|
| Text scurt | `\fillline[Xcm]` |
| CNP (13 caractere) | `\fillbox` × 13 |
| Serie+Nr CI (8) | `\fillbox` × 8 |
| IBAN (24) | `\fillbox` × 24 |
| Text liber multi-rând | `\hrulefill` × N |
| Bifă | `\checkboxempty Label` |
| Tabel | `\begin{tabularx}{...}` |
| Semnătură + data | `Data: \fillline[3cm] \hfill Semnătura: \fillline[4cm]` |

---

## Scenariile

### Scenariul 1 — CAF (Certificat Atestare Fiscală) PF 🟢
`scenariu-1-certificat-atestare-fiscala/`
- `491002-Cerere-CAF` (Cod 491.002 / Model 2016-ITL-010)
- `Consimtamant-OUG-41-2016` (universal)

### Scenariul 2 — Cumpărare apartament + Mutare + Parcare 🔵
`scenariu-2-cumparare-apartament/`
- `ITL-001-Declaratie-impozit-cladiri-PF` (OMFP 1985/2016, național, landscape A4)
- `Anexa-1-Cerere-eliberare-CI` (DEP)
- `Anexa-5-Declaratie-gazduitor`
- `700.001-Cerere-abonament-parcare-strada-PF`
- `Consimtamant-OUG-41-2016`

### Scenariul 3 — Autorizație Construire casă 🔵🔵
`scenariu-3-autorizatie-construire-casa/`
**⚠️ F.8/F.9 (cerere AC propriu-zisă) — OMDRT 839/2009, doar la ghișeu.**
- `431.001-Cerere-emitere-certificat-urbanism`
- `Cerere-prelungire-certificat-urbanism` (Cod 431.002)
- `432.002-Cerere-prelungire-AC-AD`
- `432.008-Cerere-atestare-edificare-extindere`
- `460.006-Aviz-principiu-constructii`
- `Consimtamant-OUG-41-2016`

### Scenariul 4 — Vânzare apartament 🔵
`scenariu-4-vanzare-apartament/`
- `491002-Cerere-CAF`
- `491004-Cerere-situatie-debite`
- `491001-Cerere-actualizare-date`
- `ITL-001-Declaratie-impozit-cladiri-PF` (mod scoatere/radiere)
- `DITL-001-Cerere-compensare` (PJ)
- `DITL-002-Cerere-restituire` (PJ, include IBAN grid)
- `Consimtamant-OUG-41-2016`

### Scenariul 5 — Persoană cu Dizabilități 🔵🔵
`scenariu-5-persoana-dizabilitati/`
**Submisii la DASM Cluj (str. Venus FN), nu sediul central.**
- `802.013-Cerere-indemnizatie-dizabilitati`
- `802.012-Cerere-card-parcare-dizabilitati`
- `802.014-Cerere-transport-urban-dizabilitati`
- `Consimtamant-OUG-41-2016`

### Scenariul 6 — Tăiere arbore curte privată 🟢
`scenariu-6-taiere-arbore-curte-privata/`
**Direcția Ecologie Urbană și Spații Verzi (cod barcode 460.007). Legea 24/2007.**
- `Cerere-aviz-doborare-arbori-curte-privata`
- `Consimtamant-OUG-41-2016`

### Scenariul 7 — Eliberare plăcuță număr poștal 🟢
`scenariu-7-placuta-numar-postal/`
**Serviciul Siguranța Circulației (cod 446.011).**
- `446011-Cerere-eliberare-placuta-numar-postal`
- `Consimtamant-OUG-41-2016`

### Scenariul 8 — Premiu 100 ani de viață 🟢
`scenariu-8-premiu-100-ani/`
**DEP – Premii (cod 310.001, barcode 313001). Adresat Domnului Primar. Premiu 2.000 RON net + diplomă.**
- `310001-Cerere-premiere-100-ani`
- `Consimtamant-OUG-41-2016`

### Scenariul 9 — Tichete sociale „Alimente" 🟢
`scenariu-9-tichete-alimente/`
**DASM — Protecție Socială (cod 801.001). 500 lei/an pe tichete electronice. Termen limită: 27 noiembrie.**
- `801001-Cerere-tichete-alimente`
- `Consimtamant-OUG-41-2016`

### Scenariul 10 — Sesizare teren cu ambrozia 🟢
`scenariu-10-sesizare-ambrozia/`
**Fond Funciar / Ecologie Urbană (cod 304.001). Legea 62/2018. Sesizare civică, gratuită.**
- `304001-Sesizare-ambrozia`
- `Consimtamant-OUG-41-2016`

---

## Setup compilare LaTeX (opțional)

**MiKTeX 25.12 instalat user-scope** (pentru rulare locală):
```powershell
winget install MiKTeX.MiKTeX --scope user --silent
$env:Path += ";$env:LOCALAPPDATA\Programs\MiKTeX\miktex\bin\x64"
initexmf --set-config-value=[MPM]AutoInstall=1
```

**Compile o variantă fillable:**
```bash
cd scenariu-1-certificat-atestare-fiscala
pdflatex -interaction=nonstopmode 491002-Cerere-CAF-fillable.tex
# -> produce 491002-Cerere-CAF-fillable.pdf
```

În Overleaf: urcă doar `<name>-fillable.tex`. Nu are dependențe externe.

---

## Cum se folosește în aplicația AI Coach (auto-fill server-side)

```python
# Server-side: ai un endpoint care primește datele user-ului
# și trimite înapoi un PDF completat

import subprocess, tempfile, os, re

def fill_template(tex_path, user_data):
    with open(tex_path, 'r', encoding='utf-8') as f:
        template = f.read()

    # Înlocuiește placeholders:
    # \fillline[6cm] -> \underline{\textit{valoare}}
    # \fillbox grupuri de 13 -> cifrele CNP-ului
    # \checkboxempty -> $\boxtimes$ (pentru bifa dorită)

    out = template
    out = out.replace(r'\fillline[10cm]', r'\underline{\textit{' + user_data['nume'] + '}}', 1)
    # ... mai multe substitutii contextual

    with tempfile.NamedTemporaryFile(suffix='.tex', delete=False) as tmp:
        tmp.write(out.encode('utf-8'))
        tmp_path = tmp.name

    subprocess.run(['pdflatex', '-interaction=nonstopmode', tmp_path],
                   cwd=os.path.dirname(tmp_path))
    return tmp_path.replace('.tex', '.pdf')
```

**Server stack recomandat:**
- Docker image: `texlive/texlive:latest` (vine cu pdflatex + toate pachetele LaTeX)
- Backend: Python/Node care invocă pdflatex pe template-uri populate

---

## Surse PDF originale

Toate URL-urile complete în `../formulare.json` (cheia `formulare[].url_pdf`).
**⚠️ URL-urile sunt volatile** — re-scrape lunar pe `https://primariaclujnapoca.ro/informatii-publice/cereri-tip/`.
