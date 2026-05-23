# CivicAI Multi-Procedure RAG — Design

**Status:** Draft for implementation
**Date:** 2026-05-23
**Owners:** Bogdan + team
**Builds on:** `docs/superpowers/specs/2026-05-23-civicai-design.md`, `docs/superpowers/specs/2026-05-23-chat-first-redesign-design.md`

---

## 1. Goal

Let a citizen describe a real-life situation in natural Romanian (e.g., *"am cumpărat un apartament"*) and have the agent return a coherent plan that distinguishes:

- **In-scope steps** — procedures CivicAI can autocomplete (linked to existing `backend/procedures/*.json`).
- **External steps** — documents/actions the citizen must obtain from third parties (notar, OCPI, auditor energetic, DRPCIV, …) that CivicAI cannot complete due to institutional boundaries.

The existing single-procedure RAG keeps working unchanged for atomic queries. This adds a parallel **scenario** layer on top, plus a missing **external-institutions catalog** that is already referenced by `ActNecesar.emitent_id` but has no backing data.

## 2. Constraints

- One embedding per logical unit (procedure or scenario). No chunking — chunking degrades retrieval for short procedural texts.
- Authored summaries, not auto-extracted from PDFs. We never store PDF binaries.
- Backward compatible: the existing `lookup_procedure` tool keeps its signature; the agent's six-tool surface and the chat-first right-pane state machine are extended, not replaced.
- Honest refusal: if neither a scenario nor a procedure scores above the threshold, return empty matches and let the agent say *"nu am o procedură pentru asta"*. Drop the keyword-guess `redirect_candidate` from the lookup response — the agent can still invoke `find_redirect` deliberately.
- Hackathon-scoped: scenarios are hand-authored JSONs in the repo; ~5 to start. No admin UI.

## 3. Data model

### 3.1 Vector store

Rename and extend the existing table:

```sql
-- backend/migrations/007_rag_entries.sql
alter table procedures_embeddings rename to rag_entries;
alter table rag_entries rename column procedure_id to id;
alter table rag_entries add column kind text not null default 'procedure'
  check (kind in ('procedure', 'scenario'));
create index idx_rag_entries_kind on rag_entries(kind);
```

Schema after migration:

```
rag_entries
-----------
 id            text PK             (e.g. "schimbare-domiciliu", "sc-cumparare-apartament")
 kind          text not null       ('procedure' | 'scenario')
 embedding     vector(768)
 source_text   text not null       (authored summary; one row, never chunked)
 updated_at    timestamptz
```

Embedding pipeline (`backend/app/embeddings.py`) is unchanged — same Gemini `gemini-embedding-001` at 768 dims. A new `scenario_source_text(scenario)` helper mirrors the existing `procedure_source_text(proc)`.

### 3.2 Scenario JSON

Lives at `backend/scenarios/<id>.json`. Loader follows the same lru_cache pattern as `procedures.get_registry()`.

```json
{
  "id": "sc-cumparare-apartament",
  "title": "Cumpărare apartament",
  "description": "Plan complet după cumpărarea unui apartament: declarare clădire, schimbare CI, abonament parcare.",
  "summary_for_rag": "Plan pentru cetățeanul care a cumpărat sau urmează să cumpere un apartament. Acoperă declararea clădirii pentru impozit, schimbarea cărții de identitate cu noua adresă, abonamentul de parcare în cartier. Include pașii externi: notar contract vânzare-cumpărare, OCPI extras carte funciară, auditor energetic certificat de performanță.",
  "synonyms": ["cumpărare apartament", "achiziție locuință", "am cumpărat o casă", "am cumpărat un apartament"],
  "sample_queries": [
    "am cumpărat un apartament",
    "ce trebuie să fac după ce iau o locuință",
    "ce hârtii îmi trebuie pentru apartament nou"
  ],
  "complexitate": "complex",
  "termen_total": "2-3 luni",
  "in_scope_steps": [
    { "ordine": 1, "procedure_id": "declarare-cladire",        "deadline_days": 30, "note": "ITL-001 — în 30 zile de la dobândire." },
    { "ordine": 2, "procedure_id": "schimbare-domiciliu",      "deadline_days": 15 },
    { "ordine": 3, "procedure_id": "abonament-parcare-strada", "note": "După emiterea noului CI." }
  ],
  "external_steps": [
    { "ordine": 0, "institutie_id": "notariat-public",   "obligatoriu": true, "note": "Primul pas. Contract V-C autentificat." },
    { "ordine": 0, "institutie_id": "ocpi-ancpi",        "obligatoriu": true, "note": "Extras CF max 30 zile." },
    { "ordine": 0, "institutie_id": "auditor-energetic", "obligatoriu": true, "note": "De obicei vânzătorul îl furnizează." }
  ]
}
```

The `summary_for_rag` field is the **only** text embedded into `rag_entries.source_text`. `synonyms` and `sample_queries` are appended to it at embedding time (same pattern as `procedure_source_text`).

Pydantic model added to `backend/app/models.py`:

```python
class ScenarioInScopeStep(BaseModel):
    ordine: int
    procedure_id: str
    deadline_days: int | None = None
    note: str | None = None

class ScenarioExternalStep(BaseModel):
    ordine: int
    institutie_id: str
    obligatoriu: bool = True
    note: str | None = None

class Scenario(BaseModel):
    id: str
    title: str
    description: str
    summary_for_rag: str
    synonyms: list[str] = Field(default_factory=list)
    sample_queries: list[str] = Field(default_factory=list)
    complexitate: str | None = None
    termen_total: str | None = None
    applies_if: str | None = None        # same expression syntax as next_steps.applies_if
    in_scope_steps: list[ScenarioInScopeStep] = Field(default_factory=list)
    external_steps: list[ScenarioExternalStep] = Field(default_factory=list)
```

Initial five scenarios drawn from `primarii-app-data/scenarii/` (already authored as markdown there):

| Scenario ID | Source folder |
|---|---|
| `sc-certificat-fiscal` | `scenarii/scenariu-1-certificat-atestare-fiscala/` |
| `sc-cumparare-apartament` | `scenarii/scenariu-2-cumparare-apartament/` |
| `sc-autorizatie-construire` | `scenarii/scenariu-3-autorizatie-construire-casa/` |
| `sc-vanzare-apartament` | `scenarii/scenariu-4-vanzare-apartament/` |
| `sc-persoana-dizabilitati` | `scenarii/scenariu-5-persoana-dizabilitati/` |

Translation from markdown to scenario JSON is a one-time hand-author task per scenario; not automated.

### 3.3 Institution JSON

Lives at `backend/institutions/<id>.json`. Loader mirrors procedures.

```json
{
  "id": "ocpi-ancpi",
  "nume_scurt": "OCPI",
  "nume_complet": "Oficiul de Cadastru și Publicitate Imobiliară",
  "scope": "Cadastru, extras carte funciară, plan situație.",
  "url": "https://www.ancpi.ro",
  "phone": "021 317 7339",
  "online_disponibil": true,
  "note_ai_cannot_complete": "Extras CF se obține direct la OCPI sau online pe ePay. CivicAI nu poate emite acest document — instituție diferită."
}
```

Pydantic model:

```python
class Institutie(BaseModel):
    id: str
    nume_scurt: str
    nume_complet: str
    scope: str
    url: str | None = None
    phone: str | None = None
    online_disponibil: bool = False
    note_ai_cannot_complete: str | None = None
```

Initial set (~7 institutions) covers everything referenced by existing procedure `emitent_id` fields plus the scenarios' `institutie_id`s:

- `notariat-public`
- `ocpi-ancpi`
- `auditor-energetic`
- `drpciv`
- `anaf`
- `cnas`
- `spclep-mai`

A loader-time integrity check raises if any procedure's `acte_necesare[].emitent_id` or any scenario's `external_steps[].institutie_id` references an unknown institution.

## 4. Tool surface

### 4.1 `lookup_procedure` — extended response

The tool **name and arguments are unchanged** so the agent's Gemini function declaration in `agent.py` does not break.

```python
# backend/app/tools/lookup_procedure.py

class ExternalStep(BaseModel):
    institutie_id: str
    institutie_nume: str                  # resolved from institutions catalog
    scope: str | None = None
    url: str | None = None
    phone: str | None = None
    obligatoriu: bool = True
    note: str | None = None
    note_ai_cannot_complete: str | None = None

class InScopeStep(BaseModel):
    ordine: int
    procedure_id: str
    procedure_title: str                  # resolved from procedures registry
    deadline_days: int | None = None
    note: str | None = None
    acte_necesare: list[ActeNecesareItem] # surfaced from the procedure JSON

class ScenarioPlan(BaseModel):
    scenario_id: str
    title: str
    summary: str                           # = scenario.description
    complexitate: str | None = None
    termen_total: str | None = None
    in_scope_steps: list[InScopeStep]
    external_steps: list[ExternalStep]

class LookupResult(BaseModel):
    matches: list[ProcedureMatch] = Field(default_factory=list)
    scenario_plan: ScenarioPlan | None = None
    # NOTE: redirect_candidate is removed. The agent uses find_redirect deliberately.
```

### 4.2 Lookup algorithm

**Top-1 wins.** If the highest-scoring entry is a scenario above threshold, `scenario_plan` is populated. If the highest-scoring entry is a procedure (even when a lower-ranked scenario exists in the top-5), `scenario_plan` stays null. This avoids surfacing a multi-step plan when the citizen's query is clearly atomic.

```python
@register("lookup_procedure")
async def lookup_procedure(ctx: ToolContext, query: str) -> LookupResult:
    if not query.strip():
        raise ValueError("query cannot be empty")

    embedding = embed_text(query)
    raw = search_top_k_rag(embedding, k=5)   # NEW search across rag_entries (kind-agnostic)

    procedure_matches: list[ProcedureMatch] = []
    scenario_plan: ScenarioPlan | None = None

    # Top-1 dispatch: only fire scenario_plan if THE top hit is a scenario.
    if raw and raw[0]["score"] >= SCENARIO_THRESHOLD and raw[0]["kind"] == "scenario":
        scenario_plan = _build_scenario_plan(raw[0]["id"])

    # Procedure matches are always populated from the procedure rows in top-K
    # so the agent has fallback options even when a scenario fires.
    procedures_registry = get_registry()
    for row in raw:
        if row["kind"] != "procedure":
            continue
        proc = procedures_registry.get(row["id"])
        if proc is None:
            continue
        procedure_matches.append(
            ProcedureMatch(
                procedure_id=row["id"],
                title=proc.title,
                score=float(row["score"]),
                description=proc.description,
                acte_necesare=[_resolve_act(a) for a in proc.acte_necesare],
            )
        )
        if len(procedure_matches) >= 3:
            break

    return LookupResult(matches=procedure_matches, scenario_plan=scenario_plan)
```

`SCENARIO_THRESHOLD = 0.55` (same as existing `REDIRECT_THRESHOLD`). If no entry — scenario or procedure — clears 0.55, both fields return empty and the agent refuses honestly.

`_build_scenario_plan(scenario_id)` resolves all `procedure_id` and `institutie_id` references at lookup time so the agent gets one fully-hydrated payload. `_resolve_act(a)` enriches `ActeNecesareItem.emitent_id` with `institutie_nume` and `note_ai_cannot_complete` when applicable.

### 4.3 New DB helper

```python
# backend/app/embeddings.py

def search_top_k_rag(query_embedding: list[float], k: int = 5) -> list[dict[str, Any]]:
    vec_literal = "[" + ",".join(f"{x:.7f}" for x in query_embedding) + "]"
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, kind, 1 - (embedding <=> %s::vector) as score "
            "from rag_entries "
            "order by embedding <=> %s::vector asc limit %s;",
            (vec_literal, vec_literal, k),
        )
        return [dict(r) for r in cur.fetchall()]
```

The existing `search_top_k` is kept as a thin wrapper filtered to `kind='procedure'` for any callers that explicitly want procedures only — but the lookup tool uses the new kind-agnostic version.

### 4.4 Indexing script

`backend/scripts/index_rag.py` (extends the existing procedure indexer):

```
for proc in procedures_registry:
    text = procedure_source_text(proc)
    upsert_rag_entry(id=proc.id, kind="procedure", source_text=text, embedding=embed_text(text))

for scenario in scenarios_registry:
    text = scenario_source_text(scenario)
    upsert_rag_entry(id=scenario.id, kind="scenario", source_text=text, embedding=embed_text(text))
```

Idempotent. Run at deploy time and whenever a scenario or procedure JSON changes. ~26 embedding requests total today.

## 5. Frontend changes

### 5.1 Right-pane state machine — new `plan` substate

In `frontend/lib/sessionStore.ts` `RightPaneState` union, add:

```ts
| { kind: "plan"; scenarioId: string }
```

Transition rules added to `frontend/lib/rightPaneState.ts`:

| From → To | Trigger |
|---|---|
| `welcome` → `plan` | `lookup_procedure` tool result has `scenario_plan` and store is not already engaged with a doc. |
| `plan` → `guide` | User clicks "Începe acum" on one of the in-scope steps. Standard `startProcedure(procedure_id)`. |
| `plan` → `plan` | Returning from a finished procedure via `popstate` to `/r/plan/<scenario_id>` (see 5.3). |

`computeInitialRightPaneFrom(doc, procedure)` is unchanged — it only handles single-doc resume. Plans are not persisted to a doc; they live in the session store and a separate URL slot.

### 5.2 `PlanPane` component

New `frontend/components/right-pane/PlanPane.tsx`. Reads `scenario_plan` from the session store (cached from the most recent `lookup_procedure` result).

```
┌─ Plan: Cumpărare apartament ─────────────────────┐
│  Sumar: Plan complet după cumpărarea unui...     │
│  Complexitate: complex · Termen total: 2-3 luni  │
│                                                   │
│  ✅ Ce pot completa eu pentru tine                │
│  ① Declarare clădire                             │
│      Termen: 30 zile             [Începe acum]   │
│  ② Schimbare CI                                   │
│      Termen: 15 zile             [Începe acum]   │
│  ③ Abonament parcare                              │
│      După CI nou                 [Începe acum]   │
│                                                   │
│  ↗ Ce trebuie să faci tu (extern)                │
│  • Notar — contract V-C autentificat              │
│      📞 (nr) · 🌐 notar.ro                        │
│      CivicAI nu poate emite — instituție diferită.│
│  • OCPI — extras carte funciară                  │
│  • Auditor energetic — certificat                │
└───────────────────────────────────────────────────┘
```

"Începe acum" wires to the existing `startProcedure(procedure_id)` store action and the standard flow takes over (create doc → push `/r/<doc-id>` → right pane becomes `guide`). After the procedure finishes (`done` state), the user can press the browser back button to return to the plan; we push `/p/<scenario_id>` when the plan first opens so the browser history is clean.

### 5.3 URL slot for plans

Add a third route family alongside `/` and `/r/[id]`:

- `/p/<scenario_id>` — plan view for a scenario, no active doc.

`ChatSurface` accepts an optional `activeScenarioId` prop the same way it accepts `activeDocId`. When set, on mount it calls `loadScenarioPlan(scenarioId)` instead of `loadDocument(docId)`. `popstate` is extended:

```
"/"               → reset()
"/r/<id>"         → loadDocument(id)
"/p/<id>"         → loadScenarioPlan(id)
```

`loadScenarioPlan(id)` either reuses a cached `scenario_plan` from the most recent lookup or re-fetches via a new convenience endpoint (see 5.4).

### 5.4 New endpoint — `GET /scenarios/{id}`

Resolves a scenario by id with all references hydrated (same shape as `ScenarioPlan`). Used by:
- `loadScenarioPlan(id)` on direct URL access / refresh
- The agent if needed (added to allowlist later; not in scope for first cut)

Implementation lives in `backend/app/scenarios.py` (new module mirroring `procedures.py`):

```python
@router.get("/{scenario_id}", response_model=ScenarioPlan)
def get_scenario_plan(scenario_id: str) -> ScenarioPlan:
    plan = _build_scenario_plan(scenario_id)  # shared with lookup_procedure
    if plan is None:
        raise HTTPException(status_code=404, detail="Unknown scenario")
    return plan
```

Mounted in `main.py` next to `procedures_router`.

### 5.5 `WelcomePane` chips

Mix scenarios into the suggestion pool. New shape of suggestions: top 2 scenarios + top 2 procedures, filtered by citizen attributes. Scenario filter uses the new `Scenario.applies_if` field (same expression syntax as `NextStep.applies_if`; same evaluator in `applies_if.py`). Procedures keep their existing hand-coded category filter (`owns_vehicle === false` etc.) until a future refactor unifies both.

Clicking a scenario chip calls a new store action `openScenarioPlan(scenarioId)` that fetches via the new API client method:

```ts
// frontend/lib/api.ts (new method)
getScenarioPlan: (id: string) => request<ScenarioPlan>(`/scenarios/${id}`),

// frontend/lib/sessionStore.ts (new action)
openScenarioPlan(id) :
  plan = await api.getScenarioPlan(id)
  store.scenarioPlan = plan
  store.rightPane = { kind: "plan", scenarioId: id }
  history.pushState(null, "", `/p/${id}`)
```

Scenario chips render with a distinct visual (📋 prefix instead of 💡) so the user knows they're picking a multi-step plan rather than a single procedure.

### 5.6 `GuidePane` shows external acte enrichment

`GuidePane` reads `procedure` from the session store, which is hydrated by `api.getProcedure(id)`. We extend `GET /procedures/{id}` server-side to resolve each `acte_necesare[].emitent_id` against the institutions catalog and return the enriched shape (`institutie_nume`, `url`, `phone`, `note_ai_cannot_complete`). GuidePane then renders an "↗ <Institutie>" badge on every act with a resolved `emitent_id`, keeping the existing layout for `emitent: "primarie" | "user"` items.

This mirrors the resolution already done at lookup time by `_resolve_act`, so the same Pydantic shape is returned from both endpoints.

## 6. Agent prompt patch

Append to `CONVERSATIONAL_SYSTEM` in `backend/app/prompts.py`:

```
10. Dacă tool-ul `lookup_procedure` returnează un câmp `scenario_plan` (situație
    cu mai multe proceduri), nu enumera procedurile sau actele în chat. Spune
    în 1-2 propoziții ce acoperă planul ("Plan pentru cumpărare apartament:
    3 cereri la primărie și 3 pași externi.") și menționează că detaliile
    sunt în panoul din dreapta. Cetățeanul alege de unde începe.

11. Dacă cetățeanul nu specifică de unde începe într-un scenariu, nu inițializa
    automat o procedură. Așteaptă alegerea explicită prin click în plan.
```

`PHONE_TOOL_ALLOWLIST` (phone-only) is updated to surface scenario plans verbally:

```
12. Pe telefon, dacă `scenario_plan` apare, citește pe scurt: numărul de pași
    interni și externi, primul pas recomandat. Apoi invită cetățeanul pe
    civicai.ro pentru execuție.
```

## 7. Failure mode

| Case | Response shape | Agent behavior |
|---|---|---|
| Top score < 0.55 (no match) | `{matches: [], scenario_plan: null}` | Says "Nu am o procedură pentru asta. Spune-mi altfel?" |
| Top is scenario, score ≥ 0.55 | `{matches: [procedure fallbacks], scenario_plan: <plan>}` | Surfaces plan in chat (1-2 sentences) + right pane shows `PlanPane` |
| Top is procedure, score ≥ 0.55 | `{matches: [procedure, …], scenario_plan: null}` | Existing single-procedure flow (GuidePane) |
| Mixed: top scenario but agent thinks user wants atomic | `propose_widget(choice)` between scenario plan and individual procedures | Agent's judgment; system prompt directive does not force scenario presentation |

The keyword-guessing `redirect_candidate` is removed. The agent calls `find_redirect` deliberately when the LLM judges the query is out-of-scope.

## 8. Migration plan

Ordered checklist for a single deploy:

1. Author scenario JSONs in `backend/scenarios/`.
2. Author institution JSONs in `backend/institutions/`.
3. Add Pydantic models (`Scenario`, `Institutie`) to `backend/app/models.py`.
4. Add `backend/app/scenarios.py` (registry loader + `GET /scenarios/{id}`) and `backend/app/institutions.py` (registry loader, no router).
5. Apply migration `007_rag_entries.sql` (rename + add `kind` column).
6. Run indexer `backend/scripts/index_rag.py` against the renamed table.
7. Extend `lookup_procedure` tool with `scenario_plan` field + new `search_top_k_rag` query.
8. Add prompt directives (`prompts.py`).
9. Add `PlanPane` + `/p/[id]` route + store actions + `WelcomePane` scenario chips.
10. Optional: add `lookup_procedure` MSW handler scenario fixture for `am cumpărat un apartament`.

Each step is independently deployable except 5+6 which must ship together.

## 9. Testing

### 9.1 Backend

| Layer | What | How |
|---|---|---|
| `Scenario` Pydantic model | All fields validate; references to procedures/institutions resolve | pytest unit + integrity test that walks all scenario JSONs |
| `Institutie` registry | All `emitent_id` values referenced by procedures exist; all `institutie_id` values in scenarios exist | pytest integrity test |
| `lookup_procedure` extended | Scenario hit returns `scenario_plan`; procedure hit returns matches; sub-threshold returns empty | pytest with a mocked `search_top_k_rag` |
| `_build_scenario_plan` | Resolves all in-scope and external refs; raises on missing refs | pytest unit |
| `GET /scenarios/{id}` | 200 for known, 404 for unknown | pytest with FastAPI TestClient |
| Indexer script | Idempotent upsert | pytest with a stub `upsert_rag_entry` |

### 9.2 Frontend

| Layer | What | How |
|---|---|---|
| `sessionStore.openScenarioPlan` | Sets store state; pushes URL | vitest unit |
| `rightPaneState` | `welcome` → `plan` transition table extended | vitest unit |
| `PlanPane` | Renders in_scope_steps + external_steps; "Începe acum" calls startProcedure | RTL |
| `WelcomePane` chips | Mixes 2 scenarios + 2 procedures; scenario chip opens plan | RTL + MSW |
| MSW handler | Returns a stub scenario_plan for "am cumpărat un apartament" | MSW setup |

### 9.3 Manual demo

Cover the new flow at the end of the existing demo checklist:

- Idle → type "am cumpărat un apartament" → 1-2 sentence agent reply + right pane shows plan with 3 in-scope + 3 external steps.
- Click "Începe acum" on Declarare clădire → standard guide pane appears for that procedure.
- Browser back → returns to plan.
- Direct visit to `/p/sc-cumparare-apartament` (refresh) → plan re-hydrates from `GET /scenarios/{id}`.

## 10. Out of scope

- Admin UI for authoring scenarios. JSON-on-disk only.
- Cross-procedure prefill (e.g., copying `adresa_noua` from one doc to the next). Each procedure remains an independent doc; orchestration is by the citizen.
- Auto-decomposing free-text queries into multi-scenario plans. One scenario per match.
- Translating `primarii-app-data/scenarii/` markdown automatically; hand-authored.
- A `set_field_across_documents` tool. Reminders already cover the "you should also do X next" case.
- Re-embedding old procedures with richer summaries that include acte_necesare. Possible follow-up, not required for this design.

## 11. Open questions

None at the time of writing. Update if implementation reveals gaps.
