# LaTeX Templates Index — Scenariu 4: Vânzare apartament

Empty LaTeX templates mirroring Primăria Cluj-Napoca PDF forms. Used by the AI Coach app to auto-fill citizen data for the apartment-sale scenario.

| File | Form code | Description |
|------|-----------|-------------|
| `491001-Cerere-actualizare-date.tex` | 491.001 / Model 2016-ITL | Cerere actualizare date cu caracter personal — persoană fizică (update contribuabil personal data with DITL Cluj-Napoca). |
| `491002-Cerere-CAF.tex` | 491.002 / Model 2016-ITL-010 | Cerere eliberare certificat de atestare fiscală PF — necesar pentru înstrăinare bunuri (vânzare apartament). |
| `491004-Cerere-situatie-debite.tex` | 491.004 | Cerere comunicare situație debite/plăți persoană fizică pentru clădiri, terenuri, auto. |
| `ITL-001-Declaratie-impozit-cladiri-PF.tex` | ITL-001 / Model 2016 | Declarație fiscală pentru stabilirea impozitului/taxei pe clădirile rezidențiale/nerezidențiale/mixte ale PF. **Folosit aici în mod SCOATERE / RADIERE după vânzarea apartamentului** — același template, intenție diferită (se completează datele clădirii înstrăinate + nr. act vânzare). |
| `DITL-001-Cerere-compensare.tex` | DITL 001 / *492006* | Cerere de compensare creanțe fiscale (art. 167 alin. 7 Cod proc. fiscală). |
| `DITL-002-Cerere-restituire.tex` | DITL 002 / *492007* | Cerere de restituire sume nedatorate (art. 168 Cod proc. fiscală). Conține grila IBAN 24 căsuțe pentru contul de restituire. |
| `Consimtamant-OUG-41-2016.tex` | OUG 41/2016 art. 2^1 alin. 2 | Consimțământ pentru ca Primăria Cluj-Napoca să obțină în numele solicitantului copii de pe avize / documente emise de alte instituții publice. |

## Câmpuri-cheie per formular (auto-fill targets)

- **491001 / 491004**: Nume/Prenume, CNP (13 căsuțe), Act ID + Serie + Nr, Domiciliu (Localitate, Str, Nr, Bl, Ap, Jud/Sect), Telefon, E-mail, Adresă corespondență, Data, Semnătura.
- **491002 (CAF)**: + rol nominal unic, listă imobile/mijloace transport, scop (Înstrăinare/Alte), descriere bunuri.
- **ITL-001**: până la 3 coproprietari, CNP/CIF, cotă proprietate, date împuternicit, datele clădirii (rezidențial / nerezidențial / mixt), suprafețe utilă & construită desfășurată, an construire, scutire DA/NU, valoare achiziție, nr. act dobândire, tip evaluare (raport / nou construit / dobândit), spațiu organ fiscal.
- **DITL 001/002**: Subscrisa, CUI/CIF, sediu+domiciliu reprezentant, sumă (lei), reprezentând, achitare prin chitanță/mandat/ordin de plată; pentru DITL-002 + motivul restituirii + IBAN 24 căsuțe.
- **Consimtamant-OUG**: Nume, CI/BI serie+nr, CNP, domiciliu, nr/data cerere principală.

## Convenții folosite
- `\fillline[Xcm]` — câmp text single-line.
- `\fillbox` — căsuță individuală (CNP 13×, IBAN 24×).
- `\hrulefill` — linii libere pentru text multi-rând.
- `\checkboxempty` — bifă goală (`$\square$`).
- `tabularx` — matricea de clădiri din ITL-001 (cat. A-F).
