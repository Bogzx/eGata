"""Smoke-test the 5 new templates: render with sample fields, write PDF to disk.

Run from repo root:
    python backend/scripts/test_new_templates.py

Output PDFs land next to this script.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pdf import render_and_compile

SAMPLES: dict[str, dict[str, object]] = {
    "taiere-arbore-curte-privata.tex": {
        "nume_complet": "Maria Ionescu",
        "adresa": "Str. Avram Iancu nr. 5, Cluj-Napoca",
        "telefon": "0744-123-456",
        "numar_arbori": "2",
        "strada_arbori": "Str. Avram Iancu",
        "nr_arbori": "5",
        "email": "maria.ionescu@example.com",
    },
    "placuta-numar-postal.tex": {
        "nume_complet": "Alexandru Popescu",
        "localitate": "Cluj-Napoca",
        "strada_domiciliu": "Str. Plopilor",
        "nr_domiciliu": "15",
        "ap_domiciliu": "3",
        "telefon": "0755-987-654",
        "strada_placuta": "Str. Plopilor",
        "nr_placuta": "15",
        "email": "alex.popescu@example.com",
    },
    "premiu-100-ani.tex": {
        "nume_complet": "Elena Vasilescu",
        "strada": "Str. Memorandumului",
        "numar_imobil": "22",
        "apartament": "4",
        "data_nasterii": "10 mai 1926",
        "loc_nastere": "Turda",
        "judet_nastere": "Cluj",
        "ci_seria": "KX",
        "ci_numar": "123456",
        "cnp": "2260510120010",
        "contact_nume": "Ana Vasilescu (fiica)",
        "contact_telefon": "0721-555-000",
        "contact_email": "ana.vasilescu@example.com",
        "telefon": "0264-111-222",
    },
    "tichete-alimente.tex": {
        "nume_complet": "Ileana Stoica",
        "cnp": "2480815120020",
        "strada": "Str. Mărăşti",
        "numar": "8",
        "apartament": "12",
        "telefon": "0723-444-555",
        "categoria_eligibilitate": "pensionar_invalid_veteran",
        "document_1": "Cupon de pensie luna mai 2026",
        "document_2": "Certificat fiscal local",
        "document_3": "Adeverință ANAF",
    },
    "sesizare-ambrozia.tex": {
        "nume_complet": "Andrei Mureșan",
        "cnp": "1980225120030",
        "localitate": "Cluj-Napoca",
        "strada": "Str. Bună Ziua",
        "numar": "44",
        "bloc": "",
        "scara": "",
        "etaj": "",
        "apartament": "",
        "judet": "Cluj",
        "ci_seria": "KX",
        "ci_numar": "456789",
        "ci_data_emitere": "15.03.2020",
        "ci_emitent": "SPCLEP Cluj-Napoca",
        "zona_descriere": "Teren liber la intersecția Bună Ziua cu Becaș, 46.74° N, 23.61° E",
        "numar_tufe": "30-40",
        "suprafata_mp": "200",
        "proprietar_teren": "Necunoscut",
        "alte_informatii": "Zona se extinde pe marginea drumului",
        "telefon": "0744-333-222",
        "email": "andrei.muresan@example.com",
    },
}

OUT_DIR = Path(__file__).resolve().parent / "smoke_pdfs"


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    failures: list[str] = []
    for template, fields in SAMPLES.items():
        try:
            pdf = render_and_compile(template, fields)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{template}: {exc}")
            print(f"  FAIL  {template}: {exc}")
            continue
        out_path = OUT_DIR / template.replace(".tex", ".pdf")
        out_path.write_bytes(pdf)
        print(f"  OK    {template} -> {out_path.relative_to(Path.cwd()) if str(out_path).startswith(str(Path.cwd())) else out_path} ({len(pdf)} bytes)")
    print()
    if failures:
        print(f"{len(failures)} failure(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All 5 templates rendered + compiled cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
