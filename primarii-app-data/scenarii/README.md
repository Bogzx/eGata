# Scenarii Test pentru AI Coach — PDF-uri + Instituții Externe

**5 scenarii reale**, fiecare cu **TOATE formularele primăriei descărcate ca PDF** (sau notă explicită pentru cele national-only) și lista detaliată a instituțiilor externe.

Optimizate pentru ClujHackathon 2026 (challenge **Your City** / **AI Civic Agents**).

---

## Structură

```
scenarii/
├── README.md  (acest fișier)
├── scenariu-1-certificat-atestare-fiscala/        [2 PDF-uri]   🟢 Simplu
├── scenariu-2-cumparare-apartament/               [5 PDF-uri]   🔵 Complex
├── scenariu-3-autorizatie-construire-casa/        [6 PDF-uri]   🔵🔵 Foarte complex
├── scenariu-4-vanzare-apartament/                 [7 PDF-uri]   🔵 Complex
└── scenariu-5-persoana-dizabilitati/              [4 PDF-uri]   🔵🔵 Complex social
```

**Total: 24 PDF-uri descărcate** din primariaclujnapoca.ro.

Fiecare folder conține:
- **README.md** — descrierea scenariului + lista actelor + instituții externe (cine, unde, ce emite, cost)
- **PDF-uri tipizate** — formularele primăriei

---

## Tabel comparativ scenarii

| # | Scenariu | Complexitate | PDF-uri | Inst. externe | Termen | Cost |
|---|----------|-------------|---------|----------------|--------|------|
| 1 | Certificat atestare fiscală (CAF) | 🟢 Simplu | 2 | 1 (MAI) | 2-5 zile | <50 RON |
| 2 | Cumpărare apartament + mutare + parcare | 🔵 Complex | 5 | 7 | 2-3 luni | 3.000-5.000 RON |
| 3 | Autorizație construire casă | 🔵🔵 Foarte complex | 6 | 13+ | 4-8 luni | 30.000-50.000 RON |
| 4 | Vânzare apartament (radiere + restituire) | 🔵 Complex | 7 | 8 | 30-45 zile | 5.000-8.000 RON |
| 5 | Dizabilități (indemnizație + parcare + transport) | 🔵🔵 Complex social | 4 | 7 | 30-60 zile | Gratuit, +1.500 RON/lună |

---

## 🟢 Scenariul 1 — CAF (Certificat Atestare Fiscală) PF
**Folder:** `scenariu-1-certificat-atestare-fiscala/`
**PDF-uri primărie ✅:** `491002-Cerere-CAF.pdf`, `Consimtamant-OUG-41-2016.pdf`
**Instituții externe:** 1 (SPCLEP/MAI pentru CI)
**Folosit pentru:** vânzare imobil, succesiune, credit bancar, angajare

## 🔵 Scenariul 2 — Cumpărare apartament + Mutare + Parcare
**Folder:** `scenariu-2-cumparare-apartament/`
**PDF-uri primărie ✅:** `ITL-001-Declaratie-impozit-cladiri-PF.pdf`, `Anexa-1-Cerere-eliberare-CI.pdf`, `Anexa-5-Declaratie-gazduitor.pdf`, `700.001-Cerere-abonament-parcare-strada-PF.pdf`, `Consimtamant-OUG-41-2016.pdf`
**Instituții externe:** 7 — Notariat, OCPI, Auditor energetic MDRT, SPCLEP, DRPCIV, RAR, Bancă

## 🔵🔵 Scenariul 3 — Autorizație Construire casă
**Folder:** `scenariu-3-autorizatie-construire-casa/`
**PDF-uri primărie ✅:** `431.001-Cerere-emitere-certificat-urbanism.pdf`, `Cerere-prelungire-certificat-urbanism.pdf`, `432.002-Cerere-prelungire-AC-AD.pdf`, `432.008-Cerere-atestare-edificare-extindere.pdf`, `460.006-Aviz-principiu-constructii.pdf`, `Consimtamant-OUG-41-2016.pdf`
**⚠️ Notă:** F.8 + F.9 (cerere AC propriu-zisă) sunt formulare naționale OMDRT 839/2009 — la ghișeu primărie.
**Instituții externe:** 13+ (Notariat, OCPI, OAR, geotehnician, verificator, expert tehnic, auditor energetic, 4 furnizori utilități, ISU, APM, DSP, ISC, Casa Constructorilor; condițional DJC, Apele Române)

## 🔵 Scenariul 4 — Vânzare apartament (radiere + CAF + restituire)
**Folder:** `scenariu-4-vanzare-apartament/`
**PDF-uri primărie ✅:** `491002-Cerere-CAF.pdf`, `491004-Cerere-situatie-debite.pdf`, `ITL-001-Declaratie-impozit-cladiri-PF.pdf` (varianta scoatere), `DITL-002-Cerere-restituire.pdf`, `DITL-001-Cerere-compensare.pdf`, `491001-Cerere-actualizare-date.pdf`, `Consimtamant-OUG-41-2016.pdf`
**Instituții externe:** 8 — Notariat (pivot), OCPI, Auditor energetic, ANAF, Bancă, SPCLEP, RAR, DRPCIV (opțional dacă include și auto)

## 🔵🔵 Scenariul 5 — Persoană cu Dizabilități
**Folder:** `scenariu-5-persoana-dizabilitati/`
**PDF-uri primărie ✅:** `802.013-Cerere-indemnizatie-dizabilitati.pdf`, `802.012-Cerere-card-parcare-dizabilitati.pdf`, `802.014-Cerere-transport-urban-dizabilitati.pdf`, `Consimtamant-OUG-41-2016.pdf`
**Instituții externe:** 7 — DGASPC (pivot), SPCLEP, Casa de Pensii, Bancă, (opțional) Instanță/Notariat (tutelă), Primărie anterioară, Fotostudio

---

## Acoperire taxonomică

| Categorie primărie | Scenarii care o testează |
|--------------------|--------------------------|
| Taxe și Impozite (CAF, ITL, restituiri) | S1, S2, S4 |
| Evidența Persoanelor (CI) | S2 |
| Urbanism + Autorizări Construire | S3 |
| Parcare | S2 |
| Asistență Socială — Dizabilități | S5 |
| Transport public | S5 |
| Restituiri / Compensări | S4 |
| Actualizare date contribuabil | S4 |

## Acoperire instituții externe (29 în catalog; testate prin scenarii: 19)

✅ ANAF, OCPI/ANCPI, Notariat, MAI/SPCLEP, RAR, DRPCIV, IPJ (cazier la S3), OAR, MDRT (verificator/expert/auditor energetic), ISU, APM, DSP, ISC, Compania Apă Someș, Delgaz Grid, Electrica, Telekom/RCS/Orange, Casa Socială Constructorilor, Casa de Pensii, Bancă, DGASPC, AJPIS (plătitor), CTP Cluj, Primării alte UAT-uri, Instanță, Fotostudio, DJC (condițional), Apele Române (condițional), Brantner/RADP

---

## Folosire în AI Coach app

Pentru fiecare scenariu, app-ul ar trebui să:

1. **Citească `README.md`** din folderul respectiv → cunoaște lista completă acte + instituții
2. **Pre-completeze PDF-urile** din folder cu datele utilizatorului (CNP, nume, adresă, IBAN, etc.) — folosind `pdf-lib` (JS) sau `PyPDF2` (Python)
3. **Generează checklist** „cumpărături instituții externe" — fiecare cu adresă, telefon, cost estimat
4. **Avertizează despre termene critice:**
   - S2: 30 zile pentru ITL-001 după achiziție
   - S4: 30 zile pentru ITL-001 (scoatere) după vânzare
   - S5: cer reînnoire anuală transport gratuit
   - S3: 24 luni valabilitate AC
5. **Detectează reciclarea** documentelor între cereri (S4: CI + extras CF folosit în 3 cereri; S5: certificat handicap + CI folosit în toate 3 cereri)
6. **Calculează costuri totale** și **beneficii** pentru utilizator
7. **Sugerează metoda optimă de depunere** (online/email/ghișeu)

---

## Decizii de design pentru hackathon

- **De ce 5 scenarii?** Acoperă spectrul: simplu (1 doc) → foarte complex (13+ doc + 8+ avize)
- **De ce toate PDF-uri descărcabile?** Demonstrează valoarea AI coach end-to-end (download → fill → submit) fără handoff la "ghișeu"
- **De ce S2 + S4 (cumpărare + vânzare)?** Demonstrează ciclul complet de proprietate
- **De ce S5?** **Impact social major** — populație vulnerabilă, criteriu hackathon (25 pts social impact)
- **De ce S3 inclus deși F.8/F.9 sunt la ghișeu?** Restul stack-ului urbanism (CU + atestare + aviz principiu + prelungire) sunt downloadable; CU este cel care listează avizele — flow-ul principal e demonstrabil

---

## Surse PDF-uri

Toate fișierele descărcate de pe **files.primariaclujnapoca.ro**. URL-urile complete sunt în `../formulare.json`.

**⚠️ URL-urile sunt volatile** — numele fișierelor se schimbă cu fiecare revizuire. Re-scrape periodic pentru menținerea sincronizării.
