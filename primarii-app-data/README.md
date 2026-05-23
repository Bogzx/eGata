# Dataset Primării — Cluj-Napoca (seed)

Date scrappate de pe **primariaclujnapoca.ro** și sub-domenii (e-primariaclujnapoca.ro, dasmclujnapoca.ro) pentru aplicația ta de AI coach care generează automat dosarele necesare la primărie.

**Data extragere:** 2026-05-23

---

## Conținut

### Fișiere JSON (gata pentru ingestion în aplicație)

| Fișier | Conținut | Folosit pentru |
|--------|----------|----------------|
| `catalog.json` | ~50 servicii principale cu acte necesare și emitent pentru fiecare document | Cheia primară a aplicației — match user-problem → service → documents |
| `institutii-externe.json` | ~70 instituții externe (ANAF, ONRC, OCPI, notariat, DGASPC, AJPIS, AJOFM, ITM, RAR, ARR, DSP, ISU, APM, DJC, instanță, parchet, școli, spitale, asociații, furnizori utilități etc.) cu lista documentelor pe care le emit | Resolve `emitent_id` → instituție → instrucțiuni utilizator („mergi la X pentru documentul Y") |
| `formulare.json` | ~165 formulare codificate (cu URL PDF + departament + beneficiar PF/PJ + cod național/local) | Pentru auto-fill formulare cu datele utilizatorului |

### Rapoarte detaliate per departament (markdown)

| Fișier | Departament | Servicii |
|--------|-------------|----------|
| `raport-per-departament/01-evidenta-persoanelor-si-stare-civila.md` | DEP + Stare Civilă | CI/CEI, naștere, căsătorie, deces, divorț, transcriere, schimbare nume, transcrieri |
| `raport-per-departament/02-taxe-si-impozite.md` | DITL | Impozit clădiri/teren/auto, certificat fiscal (CAF), restituiri, scutiri, ITL 001-017 |
| `raport-per-departament/03-urbanism-si-autorizari-constructii.md` | Urbanism + AC | Certificate urbanism, AC, AD, PUZ, PUD, avize CTATU/estetică, branșamente, intrare în legalitate |
| `raport-per-departament/04-asistenta-sociala-si-locuire.md` | DASM + Fond Locativ | Alocații, ICC, stimulent inserție, VMI, ajutor încălzire/chirie, locuință socială/ANL, dizabilități, vârstnici |
| `raport-per-departament/05-comert-mediu-mobilitate.md` | Comerț + Mediu + Mobilitate | Acorduri funcționare, publicitate, salubritate, spații verzi, parcare, taxi, cimitire, animale |
| `raport-per-departament/06-master-catalog-registratura.md` | Toate | Catalog master cu toate cele ~165 formulare codificate |

### Scenarii test (cu PDF-uri descărcate, gata pentru demo)

5 scenarii reale pentru AI Coach app, fiecare cu PDF-urile primăriei descărcate și lista instituțiilor externe. Vezi `scenarii/README.md` pentru detalii.

| Folder | Scenariu | Complexitate | PDF-uri | Instituții externe |
|--------|----------|-------------|---------|---------------------|
| `scenarii/scenariu-1-certificat-atestare-fiscala/` | CAF (Certificat Atestare Fiscală) PF | 🟢 Simplu | 2 | 1 |
| `scenarii/scenariu-2-cumparare-apartament/` | Cumpărare apt + mutare + parcare | 🔵 Complex | 5 | 7 |
| `scenariu-3-autorizatie-construire-casa/` | Autorizație Construire casă | 🔵🔵 Foarte complex | 6 | 13+ |
| `scenarii/scenariu-4-vanzare-apartament/` | Vânzare apartament + radiere + restituire | 🔵 Complex | 7 | 8 |
| `scenarii/scenariu-5-persoana-dizabilitati/` | Indemnizație + Card parcare + Transport | 🔵🔵 Complex social | 4 | 7 |

**Total: 24 PDF-uri descărcate**, toate de la primariaclujnapoca.ro. Vezi `scenarii/README.md` pentru index global și fiecare folder pentru detalii complete.

---

## Cum se folosește în aplicație

### Schema dezirabilă pentru engine-ul AI coach:

1. **User input** → „Vreau să declar o clădire cumpărată"
2. **Match** → `catalog.json` → `tax-cladire-pf-dobandire`
3. **Lista documente** → iterează prin `acte_necesare`
4. **Resolve emitent** → fiecare `emitent_id` → `institutii-externe.json` → instrucțiuni pas-cu-pas
5. **Generează dosar** → găsește formularele tip (`ITL-001` etc.) în `formulare.json` → descarcă PDF + auto-completează cu datele utilizatorului
6. **Output utilizator:**
   - „📋 Dosar generat:"
   - „✅ Documente de la primărie (descărcate și pre-completate)"
   - „⚠️ Documente de obținut de la alte instituții:"
     - „1. **Notariat** — actul de dobândire (contract V-C / certificat moștenitor)"
     - „2. **OCPI Cluj** — extras de carte funciară (max 30 zile)"
     - „3. **ANEVAR** — raport de evaluare (dacă e clădire nerezidențială)"

---

## Observații importante pentru implementare

### 1. URL-uri PDF volatile
Numele de fișier PDF se schimbă cu fiecare revizuire (datate `2023/07/`, `2024/06/`, `2026/05/`). Recomandare: **scrape periodic** pagina-pivot `https://primariaclujnapoca.ro/informatii-publice/cereri-tip/` și menține un mapping `cod → URL curent`.

### 2. Stare Civilă — excepție
Majoritatea formularelor de stare civilă (naștere, căsătorie, deces, divorț, transcrieri, schimbare nume) **NU au PDF descărcabil** — completare la ghișeu (str. Moților 5). Aplicația ar trebui să gestioneze această clasă separat: „intervievează cetățeanul → produce un PDF letric local."

### 3. Documente universale
**Consimțământul OUG 41/2016** (`Consimtamant-solicitare-acte.pdf`) este atașabil la majoritatea cererilor — propune-l automat în UX.

### 4. Coduri ITL naționale
Formularele `ITL-001` → `ITL-017` sunt **naționale** (OMFP 94/2016) — pot fi mapate către orice altă primărie din România. Bun pentru extensibilitate.

### 5. Coduri lipsă în secvențe
Coduri lipsă în secvențele numerice (ex. `491.007+` sau `802.003-007`) — direcția a retras unele formulare. NU presupune secvențialitate.

### 6. Documente străine
Necesită OBLIGATORIU:
- **Apostilă Haga** (state semnatare ale Convenției Haga 1961) SAU
- **Supralegalizare** (state non-Haga, prin MAE)
- **Traducere autentificată notarială**

### 7. Comerț, cimitire, publicitate
Quasi-toate disponibile pe **eDirect / PCUe** (https://edirect.e-guvernare.ro) — listate pe `/proceduri-online/`.

### 8. Cuantumuri taxe
Stabilite anual prin **HCL** (Hotărâri Consiliu Local). Cuantumurile din `catalog.json` sunt valabile pentru 2026 — necesită actualizare anuală.

### 9. Beneficiar
- ~110 servicii PF-only sau cu variantă PJ dedicată
- ~35 servicii PJ-only (comerț, transport, declarații PJ)
- ~20 servicii ambele

---

## Departamente principale & contacte

| Direcție | Adresă | Email | Tel |
|----------|--------|-------|-----|
| Sediu central | str. Moților 3 | registratura@primariaclujnapoca.ro | 0264-596-030 |
| Registratură | str. Moților 7 | registratura@primariaclujnapoca.ro | — |
| Stare Civilă | str. Moților 5 | starecivila@primariaclujnapoca.ro | — |
| DITL — Impozite PF | Piața Unirii 1 cam. 1, 3, 4A, 4B, 5, 11 | persoanefizice@primariaclujnapoca.ro | 0264 434 921 |
| DITL — Impozite PJ | Piața Unirii 1 cam. 13A-C | persoanejuridice@primariaclujnapoca.ro | 0264 424 901 |
| DASM | str. Venus fn | contact@dasmclujnapoca.ro | 0264-599316 |
| Direcția Urbanism | str. Moților 3, cam. 58A, 65 | — | 0264 596 030 int. 4330, 4331 |
| Autorizări Comerț | str. Regele Ferdinand 31 | autorizaricomert@primariaclujnapoca.ro | 0264 439 334 |
| Cimitire | str. Avram Iancu 26-28 | cimitire@primariaclujnapoca.ro | 0264 454 421 |
| Parcări | str. Moților 7 | — | — |
| Taxi | str. Moților 3, cam. 26 | — | — |

---

## Surse de date originale

- https://primariaclujnapoca.ro
- https://www.e-primariaclujnapoca.ro/registratura/cereri/
- https://www.e-primariaclujnapoca.ro/taxe/ITL.php
- https://primariaclujnapoca.ro/informatii-publice/cereri-tip/
- https://primariaclujnapoca.ro/proceduri-online/
- https://dasmclujnapoca.ro/en/formulare/
- https://portal.dasmclujnapoca.ro/servicii
- https://primariaclujnapoca.ro/social/
- https://primariaclujnapoca.ro/locuinte/
- https://primariaclujnapoca.ro/taxe-si-impozite-locale/
- https://primariaclujnapoca.ro/urbanism/
- https://primariaclujnapoca.ro/autorizari-constructii/
- https://primariaclujnapoca.ro/parcari/
- https://primariaclujnapoca.ro/taximetrie/
- https://primariaclujnapoca.ro/salubritate/

---

## Următorii pași sugerați

1. **Validare cu un caz real** — alege un scenariu (ex. „cumpăr apartament" sau „mă mut și vreau abonament parcare") și verifică că dosarul generat e complet.
2. **Auto-completare cu datele utilizatorului** — implementează un layer care preia CNP, nume, adresă, IBAN etc. și le inserează în PDF-urile descărcate (use `pdf-lib` sau `PyPDF2`).
3. **Refresh periodic** — scrape lunar `/informatii-publice/cereri-tip/` pentru a verifica URL-urile PDF.
4. **Extindere la alte primării** — formularele ITL sunt naționale; portează la Cluj-Napoca, Sibiu, Brașov ușor. Formularele locale (DITL-XXX, codurile cu prefix 100-815) sunt specifice Cluj — necesită scrape per primărie.
5. **Tracking modificări HCL** — cuantumurile se schimbă anual prin HCL. Watch `/informatii-publice/hcl/` pentru actualizări.
