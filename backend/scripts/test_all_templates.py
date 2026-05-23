"""Smoke-test ALL backend templates by rendering them with sample data via the
real render_and_compile() code path. Outputs PDFs to smoke_pdfs/.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pdf import render_and_compile

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
OUT_DIR = Path(__file__).resolve().parent / "smoke_pdfs"

# Generic sample data - covers most field names across all templates
SAMPLE: dict[str, str] = {
    "nume_complet": "Maria Ionescu",
    "nume_titular": "Maria Ionescu",
    "cnp": "2851014120010",
    "cnp_titular": "2851014120010",
    "adresa": "Str. Avram Iancu nr. 5, Cluj-Napoca",
    "adresa_curenta": "Str. Avram Iancu nr. 5, Cluj-Napoca",
    "adresa_noua": "Str. Plopilor nr. 22, Cluj-Napoca",
    "telefon": "0744-123-456",
    "email": "maria.ionescu@example.com",
    "localitate": "Cluj-Napoca",
    "judet": "Cluj",
    "strada": "Str. Avram Iancu",
    "strada_domiciliu": "Str. Avram Iancu",
    "strada_arbori": "Str. Avram Iancu",
    "strada_placuta": "Str. Avram Iancu",
    "numar": "5",
    "numar_imobil": "5",
    "nr_arbori": "5",
    "nr_domiciliu": "5",
    "nr_placuta": "5",
    "ap_domiciliu": "3",
    "apartament": "3",
    "bloc": "",
    "scara": "",
    "etaj": "2",
    "ci_seria": "KX",
    "ci_numar": "123456",
    "ci_data_emitere": "15.03.2020",
    "ci_emitent": "SPCLEP Cluj-Napoca",
    "data_nasterii": "10 mai 1985",
    "loc_nastere": "Cluj-Napoca",
    "judet_nastere": "Cluj",
    "contact_nume": "Ana Vasilescu",
    "contact_telefon": "0721-555-000",
    "contact_email": "ana@example.com",
    "scop": "Vânzare apartament",
    "motiv": "Pierdere",
    "numar_arbori": "2",
    "categoria_eligibilitate": "pensionar_invalid_veteran",
    "document_1": "Cupon de pensie",
    "document_2": "Certificat fiscal local",
    "document_3": "Adeverință ANAF",
    "zona_descriere": "Str. Bună Ziua intersecție cu Becaș",
    "numar_tufe": "30",
    "suprafata_mp": "200",
    "proprietar_teren": "Necunoscut",
    "alte_informatii": "Vizibil de pe stradă",
    "tip_proprietate": "proprietar",
    "motivul": "Schimbare loc de muncă",
    "data_propusa": "15 iunie 2026",
    "nume_partener": "Andrei Popescu",
    "componenta_familie": "Soț + 2 copii",
    "venit_familie": "4500",
    "marca_model": "VW Golf 7",
    "nr_inmatriculare": "CJ-12-ABC",
    "zona_solicitata": "Str. Avram Iancu",
    "grad_handicap": "GRAV",
    "modalitate_plata": "virament bancar",
    "iban": "RO12 BTRL 0000 1111 2222 3333",
    "tip_cerere": "construire",
    "adresa_imobil": "Str. Memorandumului 22, Cluj-Napoca",
    "scop_lucrari": "Construire locuință individuală",
    "valoare_estimata": "350000",
    "destinatie": "Locuință",
    "nr_certificat_urbanism": "CU-2025-1234",
    "nr_autorizatie": "AC-2025-5678",
    "data_emitere": "10.01.2025",
    "termen_finalizare": "10.01.2027",
    "ref_doc": "Doc-2026-001",
    "suma": "5000",
    "data_cerere": "23.05.2026",
    "adresa_corespondenta": "Str. Avram Iancu nr. 5, Cluj-Napoca",
    "cod_postal": "400089",
    "sector": "",
    "fax": "",
}

OUT_DIR.mkdir(exist_ok=True)
failures: list[str] = []
for tex in sorted(TEMPLATES_DIR.glob("*.tex")):
    if tex.name == "base.tex":
        continue
    try:
        pdf = render_and_compile(tex.name, SAMPLE)
    except Exception as exc:
        msg = str(exc).splitlines()[0][:120]
        failures.append(f"{tex.name}: {msg}")
        print(f"  FAIL  {tex.name}  {msg}")
        continue
    out = OUT_DIR / tex.name.replace(".tex", ".pdf")
    out.write_bytes(pdf)
    print(f"  OK    {tex.name}  ({len(pdf):,} bytes)")

print()
print(f"Result: {len(failures)} failures out of {len(list(TEMPLATES_DIR.glob('*.tex'))) - 1} templates.")
if failures:
    print("Failures:")
    for f in failures:
        print(f"  - {f}")
