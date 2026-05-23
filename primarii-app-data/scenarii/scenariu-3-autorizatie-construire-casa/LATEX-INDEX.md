# LaTeX Templates Index — Scenariu 3: Autorizație Construire Casă

LaTeX mirror templates for Primăria Cluj-Napoca PDF forms used in the building-permit (autorizație de construire) flow. Each `.tex` mirrors the layout of its source PDF with all fillable fields left BLANK, ready to be auto-filled by the AI Coach app.

## Files

| File | Form code | Description |
|------|-----------|-------------|
| `431.001-Cerere-emitere-certificat-urbanism.tex` | Cod 431.001 | Cerere pentru emiterea Certificatului de Urbanism (CU) — first step before AC; includes 4-page form with scop, tipuri lucrări (a-i), operațiuni notariale, imobil identification (CF, nr. cadastral, suprafață), and precizări complete. |
| `Cerere-prelungire-certificat-urbanism.tex` | Cod 431.002 | Cerere pentru prelungirea valabilității Certificatului de Urbanism — used when CU is about to expire before AC is obtained. Includes nr. CU, perioada de prelungire, anexe (taxa 30%). |
| `432.002-Cerere-prelungire-AC-AD.tex` | Cod 432.002 | Cerere pentru prelungirea valabilității Autorizației de Construire/Desființare — extends an existing AC/AD; includes nr. autorizație, lucrări rămase de executat, memoriu justificativ și documentație tehnică derivată D.A.T.C./D.A.T.D. |
| `432.008-Cerere-atestare-edificare-extindere.tex` | Cod 432.008 | Cerere pentru eliberarea Certificatului de Atestare a Edificării/Extinderii Construcției — emis după finalizarea lucrărilor; include 18 acte anexe (extras CF, proces-verbal recepție, certificat performanță energetică, adeverință ISC, etc.). |
| `460.006-Aviz-principiu-constructii.tex` | Cod 460.006 | Cerere pentru eliberarea Avizului de Principiu pentru lucrări de construcții — emis de Direcția Ecologie Urbană și Spații Verzi (Serviciul Spații Verzi); piese scrise + piese desenate. |
| `Consimtamant-OUG-41-2016.tex` | OUG 41/2016 | Consimțământ ca Primăria Cluj-Napoca să solicite în numele cetățeanului copii de pe avize/documente de la alte instituții publice (simplificare administrativă). |

## Notă importantă — formulare AC propriu-zise

Formularele pentru cererea de **Autorizație de Construire propriu-zisă** (F.8 — cerere emitere AC, F.9 — anunț începere lucrări, plus modelele de comunicare) sunt **formulare naționale** reglementate prin **Ordinul M.D.R.T. nr. 839/2009** pentru aprobarea Normelor Metodologice de aplicare a Legii 50/1991. Aceste formulare se obțin și se depun **doar la ghișeu** la Primăria Cluj-Napoca (Calea Moților nr. 3-7) și **nu sunt disponibile** ca PDF descărcabil pe portalul online local — drept urmare nu există template `.tex` echivalent în acest set.

Pentru fluxul complet al unei autorizații de construire casă în Cluj-Napoca, cetățeanul parcurge:
1. **431.001** Cerere CU → primește Certificatul de Urbanism
2. (eventual) **431.002** prelungire CU
3. **460.006** Aviz de principiu spații verzi + alte avize prevăzute în CU
4. **F.8 OMDRT 839/2009** Cerere AC (la ghișeu) → primește Autorizația de Construire
5. **F.9 OMDRT 839/2009** Anunț începere lucrări (la ghișeu)
6. (eventual) **432.002** prelungire AC
7. **432.008** Cerere atestare edificare după finalizarea lucrărilor
8. **Consimțământ OUG 41/2016** se atașează la oricare dintre cererile de mai sus

## Compilare

```bash
pdflatex <fișier>.tex
```

Pachete necesare: `inputenc`, `fontenc`, `babel` (romanian), `geometry`, `array`, `tabularx`, `enumitem`, `graphicx`, `setspace`, `xcolor`, `hyperref`.
