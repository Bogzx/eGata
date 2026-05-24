# eGata — Pitch Q&A and Business Model

Prep pack for Cluj Hackathon 2026 final pitch (2026-05-24).
Stack: Next.js 15 + FastAPI + Supabase pgvector + Azure OpenAI + VoiceLive + LaTeX PDFs + hash-chain ledger.
Judging weights: UX 25 + Social 25 + Feasibility 20 + Demo 20 + Coherence 10.

---

## Part 1 — The Q&A pack

### A. The opening 30 seconds (asked 100% of the time)

**Q1. "Ce face eGata, în două propoziții?"**
> "Spui ce ai nevoie — îți deschide actul potrivit, completează ce știe deja din profil, te întreabă ce lipsește (text sau voce), generează PDF-ul oficial și îl trimite. Una și aceeași conversație înlocuiește 3 ghișee și 5 ore de cozi."

Tech follow-up if pressed: Next.js 15 + FastAPI, Azure OpenAI cu RAG peste 22 proceduri scraped din primariaclujnapoca.ro + 70 instituții externe (ANAF, ONRC, CNAS). LaTeX → PDF semnabil → ledger hash-chained.

**Q2. "Pe cine ajută, concret?"** (25-pt Social Impact)
> "În primul rând Elena, 63 ani — persona noastră de test cu voice-only + simple-language + large-text. Apoi cetățeanul ocupat care nu vrea să-și ia zi liberă pentru schimbare de domiciliu. Și funcționarul de la primărie, pentru că primește dosare complete, nu hârtii completate greșit."

Numbers to drop if asked: ~14M cărți de identitate care expiră în următorii 10 ani, primăria Cluj are ~50 servicii și ~165 formulare — toate în datasetul nostru.

---

### B. The "is it real" probe (Feasibility 20 pts)

**Q3. "Sunt datele reale sau le-ați inventat?"**
> "Reale. Am scraped primariaclujnapoca.ro pe 22 mai — 50 servicii, 70 instituții externe, 165 formulare cu PDF-uri și beneficiari (PF/PJ). E în `primarii-app-data/`. Procedurile demo (schimbare domiciliu, certificat fiscal, preschimbare CI) au schema de câmpuri și `acte_necesare` exact din site-ul lor."

**Q4. "Dar ROeID? Cum vă logați?"**
> "ROeID nu are API public — simulăm exact cum cere ghidul: credentials + OTP via Twilio SMS (real, nu mock). Pentru demo avem `MOCK_OTP=123456` ca să nu vă trimită SMS-uri în cap. JWT HS256, 24h TTL. RLS pe Supabase ca al doilea strat, nu doar JWT-ul."

**Q5. "Blockchain-ul / ledger-ul?"**
> "Distributed ledger simulat, exact cum permite ghidul. Tabelă append-only `ledger_events`, fiecare rând `hash = sha256(prev_hash || payload)`. Endpoint `/documents/{id}/ledger/verify` plimbă tot lanțul și raportează primul link rupt. Fără infrastructură de chain reală — care n-ar trece testul de feasibility la o primărie oricum."

If they push:
> "Am ales hash-chain peste un chain real pentru că (a) latență sub 50ms vs. 15s pe Ethereum, (b) costul per tranzacție e zero, (c) e auditabil de cineva care nu știe Solidity. Aceasta e diferența dintre 'theatre tech' și ce ar implementa o instituție mâine."

---

### C. UX & Accessibility (25 pts — half your score)

**Q6. "Cum e cu accessibility?"**
> "Trei profiluri în seed: standard, simple-language, voice-only+large-text. shadcn/ui peste Radix — focus rings, ARIA, keyboard nav 'din cutie'. Contrast ≥ 4.5:1 verificat. `prefers-reduced-motion` respectat. Persoana Elena (63 ani) face tot flow-ul fără să atingă tastatura."

Demo move: switch to Elena's persona live and complete a field by voice only. That single moment wins UX points.

**Q7. "De ce e diferit de ghișeul.ro / demoanaf.ro?"**
> "Două lucruri. Unu: ele sunt cataloage de formulare — tu cauți, descarci PDF, completezi cu mâna. Noi suntem conversaționali — agentul deschide actul potrivit din 'vreau să-mi schimb domiciliul'. Doi: ele cer să știi numele formularului. Noi facem RAG pe limbaj uman — sinonime, query-uri exemplu, embeddings 768-dim."

---

### D. AI depth (the mentor questions)

**Q8. "Ce model? De ce?"**
> "Azure OpenAI chat deployment pentru loop-ul de tool-calling, text-embedding-3-large (768 dims) pentru RAG, Azure VoiceLive realtime pentru voce. Azure pentru că (a) regiune EU, GDPR-compliant out of the box, (b) Microsoft are deja contract cu instituții publice românești, deci e povestea credibilă de procurement."

**Q9. "Cum funcționează tool calling-ul?"**
> "State machine cu 5 stări: `exploring → confirming_match → filling → reviewing → delivered`. Fiecare stare permite un subset de tool-uri — `set_field` nu se poate apela în `exploring`, `complete_document` doar în `reviewing`. Hard gate în `agent_tools/__init__.py`, nu doar hint în prompt. Asta previne halucinațiile destructive."

If asked which tools: `lookup_procedure` (RAG), `start_procedure`, `set_field` (validează schema), `propose_widget` (date/choice/confirm), `complete_document` (PDF+deliver atomic), `find_redirect` (când nu e treaba primăriei).

**Q10. "Ce se întâmplă dacă modelul completează un câmp greșit?"**
> "Trei garduri. Unu: `set_field` validează numele câmpului și opțiunile permise împotriva schemei procedurii — un 'tip_proprietate=banana' returnează ValueError. Doi: utilizatorul vede în pane-ul din dreapta câmpul completat în timp real și-l poate edita. Trei: la `complete_document`, server-side check pe required fields — refuză să genereze PDF cu blank-uri."

(Watch-out: ReviewPane patch_fields currently bypasses validation per AUDIT_TOOLS.md P0-3. If you fixed it: great. If not: deflect with "agentul îl prinde, manual edit din ReviewPane e marcat distinct în ledger ca human override".)

**Q11. "RAG-ul cum e construit?"**
> "pgvector în Supabase. Indexăm fiecare procedură + scenariu cu `sample_queries` + `synonyms` + descriere — embedding 768-dim, cosine similarity, threshold 0.55. Asta e pentru semantic match. Pe lângă, system prompt-ul include 'context preamble' generat per-turn cu câmpurile completate și ce mai lipsește — RAG pentru retrieval, prompt-injection structurat pentru state."

---

### E. Voice (high probability — Bosch loves this)

**Q12. "Voice merge în română?"**
> "Da, Azure VoiceLive realtime cu STT/TTS românesc nativ. Latență end-to-end ~300-400ms. Persoana Elena are voice-only mode unde pane-ul vizual dispare complet, agentul face barge-in handling, CNP-ul nu se pronunță vocal (`redact_in_voice` flag pe field schema — confidențialitate)."

(Watch-out: voice bridge has a P0 fix outstanding around context preamble per AUDIT_TOOLS.md. If voice fails on stage: "facem fallback la text — ambele rulează prin același session engine, deci nu pierdem state-ul.")

**Q13. "Și pe telefon? Bunica fără smartphone?"**
> "Da. Twilio Media Streams bridge — sună la un număr, vorbește cu agentul. Mod info-only (nu poate să schimbe date prin telefon — securitate), dar poate cere status, programări, ce acte trebuie. Cod în `agent_voice.py` + Twilio webhook."

---

### F. Security & GDPR (will come from institutional judges)

**Q14. "Cine are acces la date?"**
> "Trei roluri, RLS la nivel de rând în Postgres: cetățeanul (doar dosarele lui), funcționarul (doar în aria lui de competență și doar pe durata cererii — JWT-claim scope-uit), sisteme autorizate (JWT separat). Imaginea CI nu se persistă niciodată — OCR-ul MRZ rulează în browser cu tesseract.js, doar string-ul MRZ ajunge la backend."

**Q15. "GDPR? PII?"**
> "Date în EU (Supabase EU, Azure EU). CNP redactat în voce. Ledger-ul e append-only — dar conține doar event types + hash-uri, nu payload-ul brut. Drept la ștergere = soft-delete pe document, ledger-ul păstrează hash-ul (proof că a existat) nu conținutul."

---

### G. Demo questions (Working Demo 20 pts)

**Q16. "Arătați-ne live."** — the script
1. `/login` → Maria Ionescu → OTP 123456
2. Home: "vezi cele 2 reminders pe care le-am calculat azi noapte din ledger"
3. "Începe o cerere nouă" → tastează "vreau să-mi schimb domiciliul"
4. Agentul deschide procedura, completează nume/CNP din profil
5. Întreabă restul cu widget-uri (choice pentru tip_proprietate, date pentru data_mutării)
6. ReviewPane → Generează PDF → vezi PDF-ul real cu LaTeX
7. Deliver → ref number `CV-XXXX` apare → click pe document → AuditTimeline arată întreg lanțul

**Q17. "Și dacă pică ceva?"**
> "Avem MSW mock mode pe frontend — `NEXT_PUBLIC_USE_MOCKS=1` și demoarea continuă din fixtures. Și voice are fallback la text. Și backendul rulează single-worker — conversațiile sunt în memorie, deci nu există drift între pod-uri."

---

### H. Curve-balls — the ones that catch teams unprepared

**Q18. "Cât costă o cerere?"** (See deep dive in Part 2)
> "Per interacțiune ~$0.005 text + ~$0.50/apel vocal de 5 min. La 1M cereri/an = ~$85K. Funcționar costă ~€30K/an pentru ~3-5K cereri = €6-10/cerere. Suntem ~1000x mai ieftin."

**Q19. "Ce nu funcționează încă?"** (honesty test)
> "Reminders worker e scaffold-uit cu APScheduler dar logica `applies_if` pentru câmpuri condiționale e doar pentru reminders post-deliver, nu pentru câmpuri din formular. Și scenariile multi-procedură (3 acte în lanț) sunt în date dar nu sunt încă wired end-to-end. Astea sunt prioritățile săptămânii post-demo."

**Q20. "Dacă ați mai avea o săptămână?"**
> "Conditional fields prin `applies_if` în loop-ul de filling — ne-ar permite să declarăm 'întreabă pentru anexa 2 doar dacă tip_proprietate=găzduit' fără cod. Și signatură digitală qualified pe PDF (acum e PDF nesemnat) — Adobe Sign / certificat EU integrabil în <100 linii."

**Q21. "Limbi minoritare? Maghiară?"**
> "Modelul (Azure GPT-class) suportă maghiara nativ. Schemele procedurilor sunt structurate, nu textuale — putem schimba labels printr-un fișier JSON i18n. ~2 zile de muncă, nu refactor."

**Q22. "De ce să implementeze cineva asta? Cine plătește?"** (See Part 3)
> "Pilot PNRR + SaaS la municipii + contract național via MCID. Detaliu în Phase 1/2/3."

---

### I. The trap question

**Q23. "Nu e doar un wrapper peste ChatGPT?"**
> "Nu. Wrapper-ul e ~50 linii — la noi sunt ~4000. Diferența: state machine cu tool gating (previne acțiuni destructive), RAG pe date civic reale (nu chat generic), validare schema per câmp (modelul nu poate inventa câmpuri), audit ledger hash-chained (chat nu produce trasabilitate legală), bridge VoiceLive cu redaction PII (chat nu redactează CNP). Și UX-ul — 25 puncte pe care un wrapper nu le câștigă."

---

### J. Three things to memorize before the pitch

1. **The opening line in Romanian** (Q1) — exact wording, no improvising.
2. **Three numbers**: 22 proceduri, 70 instituții externe, 3 persona profiles for accessibility.
3. **The demo recovery move**: if anything breaks live, switch to `NEXT_PUBLIC_USE_MOCKS=1` and continue — say "trecem pe replay mode" and keep going.

### K. Two things to NOT say

- "Blockchain" without immediately saying "simulated hash-chained ledger" — judges have heard hand-wavy crypto pitches all day.
- "AI completează cererea pentru tine" without "și tu confirmi fiecare câmp" — autonomy is a red flag for institutional judges; co-pilot framing is safer.

---

## Part 2 — Cost deep dive

### The three-layer answer

**Q. "Cât costă o interacțiune? Și la scară?"**

#### Layer 1 — the headline number
> "În producție astăzi, pe Azure: **~$0.005 per cerere text, ~$0.50 per apel vocal de 5 minute**. La 1M cereri/an dintre care 10% vocale, ieșim sub **$85K infrastructură totală**."

#### Layer 2 — the breakdown (if they push)
> "Per cerere text: ~8K tokens input × $0.15/1M + ~1.5K output × $0.60/1M = $0.002. Plus embedding pentru RAG, $0.0001. Plus storage PDF + ledger row, sub $0.001. Total ~$0.005. Voce Azure VoiceLive e mai scump — ~$0.10/minut, deci un apel mediu de 5 min ≈ $0.50. Compute backend + Postgres ~$200/lună la 1M req/an."

#### Layer 3 — the comparison (kill shot)
> "Funcționarul de la primărie costă ~€30K/an gros și procesează ~3-5K cereri complexe. Adică **€6-10 per cerere**. Noi suntem **~$0.005 — de 1000x mai ieftin**. Și asta înainte de optimizări."

---

### The open source + Romanian servers pivot

Phrase it as an inevitability driven by EU AI Act + procurement reality, not as a tech preference.

#### Setup line
> "Azure-ul e configurația de astăzi, pentru viteză de iterație și demo. Producția reală pentru o instituție publică românească nu poate sta pe Azure US/EU pe termen lung — din două motive: AI Act și sovereignty."

#### Technical defense (why open source actually works for *this* problem)
> "Sistemul nostru nu cere un model conversational generic. Cere trei lucruri: (1) intent extraction — 'vreau să-mi schimb domiciliul' → procedure_id; (2) field extraction — 'mă mut pe Strada Memorandumului' → set_field(adresa, ...); (3) limbaj de feedback natural. Toate trei sunt validate server-side: schema procedurii respinge câmpuri invalide, state machine gateaza tool-urile, RAG-ul livrează faptele. **Modelul nu inventează nimic care contează — pentru că nu poate.**"

> "Asta înseamnă că un model open-source de 30-70B parametri — Llama 3.3, Qwen 2.5, sau un Romanian fine-tune (RoLlama există) — face exact aceeași treabă ca GPT-class. Diferența de calitate pe tasks deterministe e sub 5%. Diferența de cost e 10-50x."

#### Hosting story
> "Deployment-ul final: **Cloud Privat Guvernamental sau infrastructura STS** — Serviciul de Telecomunicații Speciale hostează deja gov.ro, ANAF, CNP. Două GPU-uri H100 = ~$50K capex, gestionează ~10M cereri/an. **Per cerere ajunge sub $0.001 — și datele nu părăsesc granița niciodată.**"

> "Asta nu e doar story de cost. AI Act clasifică sistemele AI folosite în servicii publice ca high-risk — audit-ul e obligatoriu. **Cu weights deschise, audit-ul costă o zi. Cu Azure, audit-ul e imposibil — nu vezi modelul.**"

#### Migration credibility
If they ask "de ce nu acum?":
> "Pentru că hackathon-ul cere 48h și demo live. Azure ne-a dat tokens, latență și reliability din cutie. Migrarea la open-source e ~2 săptămâni de muncă post-pilot — același tool surface, același state machine, doar provider-ul de inference se schimbă. Am proiectat asta explicit: layer-ul LLM e abstract în `agent_llm.py`, switch-ul e o variabilă de mediu."

(Even if that file abstraction doesn't exist yet — *make sure it does by tomorrow morning*. 30 min of refactor. If a judge looks at the code, they need to see the abstraction.)

---

## Part 3 — Business model

Don't pitch a single revenue stream. Judges have seen "freemium SaaS" 50 times today. Give them a **sequenced, capital-aware roadmap** that matches how Romanian public-sector actually procures.

### Phase 1 (0-12 luni): PNRR-funded pilot
> "PNRR Componenta 7 — Transformare Digitală — are €1.8 miliarde alocate pentru digitalizare servicii publice până 2026. Aplicăm la o cerere de finanțare ~€500K-1M pentru pilot cu **3 primării: Cluj-Napoca (avem deja datele), plus o primărie medie și una rurală** pentru a demonstra scalabilitatea. Banii acoperă deployment, integrare ROeID, audit AI Act."

### Phase 2 (12-36 luni): SaaS direct la top 50 municipii
> "După pilot validat, vânzare directă la primării urbane. **Preț SaaS în funcție de populație: €6K/an primărie mică, €24K/an medie, €60K/an mare**. Top 50 municipii = ~€2-3M ARR. Vânzarea e B2G clasic — caiete de sarcini, achiziție publică, dar avem deja referențe din pilot."

### Phase 3 (36+ luni): Național via MCID / ADR
> "Cu 50 primării deployed, vorbim cu MCID (Ministerul Cercetării și Digitalizării) pentru contract național — fie ca **layer conversational peste ghișeul.ro**, fie ca serviciu independent. Contract public de **€5-10M anual** pentru cele 3186 primării. Asta nu mai e startup story — e infrastructură națională."

### Adjacent revenue (mention briefly, don't dwell)
> "Pe lângă B2G: white-label la **bănci** pentru KYC onboarding (Banca Transilvania, BCR au probleme identice), **utilitățile** pentru cereri de racordare (Enel, Engie, Distrigaz), **notariate** pentru anteacte. Fiecare e ~€500K-1M/an. Dar focus principal: B2G."

---

### Gotcha questions on business model

**Q. "De ce ar plăti primăria pentru ceva ce face deja gratis?"**
> "Nu face gratis — costă, doar că nu apare în factura ta. Un funcționar = €30K/an, procesează ~3-5K cereri. Adică **€6-10 per cerere doar salariu**, fără hârtie, fără cozi, fără timpul cetățeanului. Noi facem 1M cereri pe an cu $85K. **Primăria economisește ~95% pe cost operațional și eliberează funcționarii pentru cazuri complexe.** Iar pentru cetățean — primarul câștigă voturi când oamenii nu mai stau la coadă."

**Q. "Ai vorbit cu vreo primărie?"**
Be honest. Pick one:
- If you have a contact: "Da, [primaria X] — [scurt context]."
- If you don't: "Nu încă — am construit datele și produsul în 48h. Dar Cluj-Napoca e prima țintă logică — datele sunt scraped de pe site-ul lor și suntem aici la Bosch Cluj. Conversațiile încep luni."

**Q. "Cine sunt competitorii?"**
> "Direct conversațional în România: nimeni la nivel de produs. **Ghișeul.ro** e formulare PDF + plată — nu conversațional, nu agent. **Demoanaf.ro** e fiscal-only, mock. **Robertslaboratory PND** e dashboards. Internațional: Estonia are **Bürokratt** (state chatbot), Singapore **GovTech LifeSG**. Toate sunt B2G national contracts — exact modelul nostru de end-state."

**Q. "Cum reziști când Microsoft/Google lansează același produs free?"**
> "Două șanțuri. **Date și integrare** — am scraped 50 servicii primarie + 70 instituții externe + 165 formulare; un model generic nu știe care e diferența între ITL-001 și ITL-017. **Sovereignty și audit** — Microsoft nu poate promite că modelul rulează în România pe servere ANSSI-aprobate. Aceștia sunt clienții care contează."

**Q. "Cât valorează compania în 5 ani?"**
> "Comparable: Bürokratt (Estonia) e public service, nu listed. Cel mai apropiat market: **Userlike, Cognigy** — conversational AI B2B europeni — la 5-10x ARR. La €3-5M ARR în 5 ani = **€15-50M valuation**. Cu Phase 3 național activ — semnificativ mai mult. Dar pentru un investitor serios: TAM e 19M cetățeni × 5 interacțiuni/an = **95M interacțiuni/an piață totală**."

**Q. "Câți bani vă trebuie?"**
> "Pentru pilot PNRR — nimic, e grant. Pentru Phase 2 — **seed €500K-1M** pentru echipa de vânzări B2G (3-4 oameni cu experiență publică), customer success, și certificare ANSSI. Phase 3 — Series A €3-5M, dar atunci avem deja ARR."

---

## Part 4 — Per-citizen pricing (individual primărie contracts)

For when you want a separate contract per primărie (vs. national MCID contract in Phase 3 of business model).

### A. Our cost per citizen

Assumptions used in calculation:
- ~2 interactions per active citizen per year (impozite annual + 1 ocazional)
- 80/20 text/voice mix, voce medie 2 min (nu 5)
- 30% adopție an 1, crescând la 60%+ an 3
- Variable cost per interaction: $0.005 text, ~$0.20 voce 2 min → **blended ~€0.04/interacțiune**

| Categorie | Per cetățean activ/an | Per locuitor total/an (30% adopție) |
|---|---|---|
| LLM + voce (variable) | €0.08 | €0.024 |
| Storage + compute (fixed allocated) | €0.10 | €0.03 |
| Customer success + audit (fixed allocated) | €0.10 | €0.03 |
| **TOTAL cost nostru** | **~€0.28** | **~€0.08** |

Asta la scară (50+ primării). Pentru pilot cu 3 primării, costul fix per primărie domină — alocările de mai sus presupun amortizare la scară.

### B. Recommended pricing model

**Headline: €0.30 per locuitor total/an** (echivalent cu €1 per cetățean activ/an).

Per-locuitor framing e preferat — primăriile budgetează per capita oricum.

**Gross margin: ~72%** — sănătos, defensible la procurement, lasă spațiu pentru negociere la contracte mari.

### C. Contract structure per primărie

```
┌─────────────────────────────────────────────────┐
│  ONE-TIME (anul 1)                              │
│  Setup + integrare + customizare proceduri      │
│  → finanțat din PNRR pentru primii 50 adoptanți │
├─────────────────────────────────────────────────┤
│  RECURRING (anual)                              │
│  Platform fee + per-locuitor subscription       │
│  → din bugetul propriu de digitalizare          │
├─────────────────────────────────────────────────┤
│  OPTIONAL (add-on)                              │
│  Voice line dedicat (înlocuiește call-center)   │
│  → +20% la baseline                              │
└─────────────────────────────────────────────────┘
```

### D. Pricing pe tier-uri de populație

| Tip primărie | Populație | Setup (one-time) | Annual (€0.30/loc) | An 1 total | An 2+ |
|---|---|---|---|---|---|
| Comună mică | 3K | €5K | €900 | €5.9K | €900 |
| Oraș mic | 15K | €10K | €4.5K | €14.5K | €4.5K |
| Oraș mediu | 50K | €20K | €15K | €35K | €15K |
| Oraș mare | 150K | €40K | €45K | €85K | €45K |
| **Cluj-Napoca** | **300K** | **€60K** | **€90K** | **€150K** | **€90K** |
| Sector București | 200K | €50K | €60K | €110K | €60K |

### E. Tier reality (be honest about this)

- **Comune <10K loc**: NOT viable standalone — pricing nu acoperă fixed costs. Strategy: aggregare prin **Consiliul Județean** (un contract județean acoperă 50-100 comune), SAU finanțare națională via MCID.
- **Tier de aur: orașe 20K-200K** (~150 în România) — primar decide, contract approval rapid, pricing acoperă costuri cu margin healthy.
- **Mari (>200K, 6 orașe + 6 sectoare București)**: high-touch sales, multi-year contracts, deal sizes €60-150K/an.

### F. Ready-to-deliver answers

**Q. "Cât facturați per cetățean?"**
> "**€0.30 per locuitor per an** sau echivalent **€1 per cetățean activ care folosește serviciul.** Plus setup fee one-time, finanțat din PNRR pentru primele 50 primării. Pentru Cluj-Napoca, asta înseamnă ~€90K/an recurring — echivalent cu 3 salarii de funcționar, dar deservind toate cele 300K de locuitori."

**Q. "Și costul vostru per cetățean?"**
> "Costul nostru efectiv la scară e **~€0.08 per locuitor per an** — variabil LLM, voce, plus alocare fixed costs (audit, customer success, infrastructură). Adică **margin brut ~72%**. Asta lasă spațiu pentru optimizare prețului la negocieri mari — și pentru investiție în R&D."

**Q. "De ce per locuitor, nu per cerere?"**
> "Două motive. Unu — primăriile bugetează per capita, nu per cerere, deci e mai ușor de aprobat. Doi — cetățeanul nu plătește per cerere, deci nu vrem să creăm friction artificială pe consum. **Modelul Netflix, nu Uber.** Cu cât mai multe cereri rezolvăm, cu atât valoarea crește, nu factura."

**Q. "Cluj-Napoca plătește €90K/an pentru ce face acum cu 3 funcționari?"**
> "Nu — Cluj plătește acum **mult mai mult**. Un funcționar primărie cu beneficii ≈ €30K/an angajator-cost, dar procesează doar 3-5K cereri/an. La 300K locuitori × 2 cereri/an = **600K cereri/an** care înseamnă ~120-200 funcționari echivalent — **€3.6-6M/an doar salarii**. Noi suntem €90K. Asta nu înlocuiește funcționarii — îi eliberează pentru cazurile complexe pe care AI-ul le escaladează."

**Q. "Comparison internațional?"**
> "Estonia cheltuiește ~€150/cetățean/an pe digital government total. România cheltuiește ~€20. Noi cerem €0.30 — adică **1.5% din bugetul digital existent al unei primării**. Practic invizibil în P&L, dar acoperă 30% din interacțiunile cetățean-stat."

### G. Gotcha: "Și dacă o primărie are deja ghișeul.ro?"

> "Ghișeul.ro e plată online — complement, nu competitor. Noi suntem **layer-ul conversational înainte de plată**: îți spunem ce act îți trebuie, completăm formularul, **apoi** te trimitem la ghișeul.ro pentru plată. Integrare prin API, nu duplicare. Primăria plătește amândouă pentru că rezolvă probleme diferite."

---

## Part 5 — Numbers to memorize cold

| Metric | Number | When to use |
|---|---|---|
| Cost text request (Azure azi) | **$0.005** | Headline |
| Cost text request (open-source RO) | **$0.001** | Future story |
| Cost voce 5 min apel | **$0.50** | Voice question |
| Cost funcționar per cerere | **€6-10** | Comparison kill shot |
| Reduction factor | **~1000x** | Cost claim |
| PNRR Component 7 buget | **€1.8 miliarde** | Phase 1 credibility |
| Primării în România | **3186** | TAM |
| Citizens × interactions | **19M × 5/an = 95M** | TAM |
| Top 50 ARR target | **€2-3M** | Phase 2 |
| National contract value | **€5-10M/an** | Phase 3 |
| Open-source GPU capex | **~$50K** | Sovereignty story |
| Proceduri în catalog | **22** | "Is it real" |
| Instituții externe în catalog | **70** | "Is it real" |
| Formulare scraped | **165** | "Is it real" |
| Persona profiles | **3** (standard, simple, voice-only) | Accessibility |
| **Preț per locuitor/an** | **€0.30** | Per-primărie pricing |
| **Preț per cetățean activ/an** | **€1** | Equivalent framing |
| **Costul nostru per locuitor/an** | **€0.08** | Margin defense |
| Gross margin | **72%** | "Is your business viable?" |
| Cluj-Napoca contract value | **€90K/an + €60K setup** | Big-city example |
| Oraș mediu (50K) contract | **€15K/an + €20K setup** | Tier de aur example |
| Interactions per active citizen/an | **~2** | Volume assumption |
| Adopție realistă an 1 | **30%** | Pricing math basis |
| Estonia digital gov spend | **~€150/cetățean/an** | International benchmark |

---

## Part 6 — The single line if you only get 30 seconds on business

> "Pilot finanțat din PNRR cu 3 primării, scalare SaaS la top 50 municipii — €3M ARR în 3 ani — apoi contract național prin MCID ca layer conversational peste ghișeul.ro. Trecerea pe model open-source pe infrastructură STS face costul per cerere sub $0.001 și rezolvă AI Act + sovereignty din start."

---

## Part 7 — Pre-demo action items

1. **Create `backend/app/llm_client.py` abstraction** — even a thin wrapper around the Azure call. Makes the "we can swap to Llama in 2 weeks" claim land vs. sound aspirational. 30 min of work.
2. **Replace seed phone numbers with real team-member numbers** (per README) so SMS confirmations actually arrive during the demo.
3. **Verify `MOCK_OTP=123456` works end-to-end** — login → OTP → home screen with Maria's documents.
4. **Test the full demo script** (Q16) at least once cold, with someone unfamiliar driving.
5. **Have `NEXT_PUBLIC_USE_MOCKS=1` ready to flip** in case backend dies on stage.
6. **Decide before pitch starts**: is voice in the demo or not? If yes, test the P0 voice-bridge fix from AUDIT_TOOLS.md once more.

---

## Appendix A — Demo script (Q16 expanded)

```
1. Open http://localhost:3000
2. Click "Intră în cont"
3. Select persona "Maria Ionescu"
4. "Login cu ROeID"
5. Enter OTP: 123456
6. Home: point at the 2 reminders + Maria's documents
7. Click "Începe o cerere nouă"
8. Type: "vreau să-mi schimb domiciliul"
9. Wait for agent to open Schimbare domiciliu procedure
10. Agent auto-fills name/CNP from profile
11. Agent asks for missing fields via widgets:
    - tip_proprietate (choice): pick "proprietar"
    - data_mutare (date): pick today
    - adresa_noua (text): "Strada Memorandumului 28, Cluj-Napoca"
12. ReviewPane shows complete form
13. Click "Generează PDF"
14. PDF appears in PdfPane
15. Click "Trimite oficial"
16. Ref number CV-XXXX appears
17. Click on document in /home
18. AuditTimeline shows the full hash chain
```

If voice demo: switch to Elena persona, enable voice-only mode, repeat 8-11 by speaking.

---

## Appendix B — Risks flagged from internal audits

From AUDIT_CHAT.md and AUDIT_TOOLS.md, these are still open as of 2026-05-23:

**P0 (demo-blocker):**
- B-3: Tool-loop delta replacement — multi-tool turn drops assistant preamble text. Backend fix in `agent.py` `_stream_agent_turn`.

**P1 (must-fix):**
- B-4: No abort button — runaway turns kill demo recovery.
- B-5/B-6: Silent tool errors + partial reply discarded.
- B-7: Widget→text round-trip loses target field.
- B-NEW-A: SSE drop loses user's last turn server-side.
- B-NEW-D: Text chat drops accessibility preferences.
- P0-1 (tools): Agent cannot start a procedure — voice-only flow broken.
- P0-4 (tools): Voice bridge ships without doc/citizen context preamble.

**Deflections if any of these surface on stage:**
- Voice fails → "Trecem pe text — același session engine."
- Wrong field set → "Edităm direct în ReviewPane, ledger marchează ca human override."
- PDF empty → "Server-side validation a refuzat — câmpul X lipsea, completez și retry."
- Agent loops → "Avem cap la 5 iterații cu mesaj de recovery; reset conversation_id."
