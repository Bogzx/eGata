# Multi-Procedure RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scenarios layer + external-institutions catalog to the existing procedure RAG, so a natural-language query like *"am cumpărat un apartament"* returns a structured multi-step plan distinguishing in-scope procedures from external steps.

**Architecture:** Unified `rag_entries` table holds one embedding per logical unit (procedure OR scenario) with a `kind` column. The existing `lookup_procedure` tool keeps its signature but its `LookupResult` gains an optional `scenario_plan` field populated only when the top-1 hit is a scenario above threshold. A new `PlanPane` right-pane state renders the plan. A new institutions catalog fills the dangling `emitent_id` references already present in procedure JSONs.

**Tech Stack:** FastAPI + Pydantic v2, Postgres pgvector, Gemini `gemini-embedding-001` (768-dim, unchanged), Next.js 15 App Router, Zustand session store, framer-motion.

**Spec:** `docs/superpowers/specs/2026-05-23-multi-procedure-rag-design.md`

**Branching:** Work on a new branch `feat/multi-procedure-rag` off `main`. Frequent commits per task.

---

## Task 1: Branch + author institution JSONs

**Files:**
- Create: `backend/institutions/notariat-public.json`
- Create: `backend/institutions/ocpi-ancpi.json`
- Create: `backend/institutions/auditor-energetic.json`
- Create: `backend/institutions/drpciv.json`
- Create: `backend/institutions/anaf.json`
- Create: `backend/institutions/cnas.json`
- Create: `backend/institutions/spclep-mai.json`

- [ ] **Step 1: Create branch**

```bash
git checkout main
git pull
git checkout -b feat/multi-procedure-rag
```

- [ ] **Step 2: Create `backend/institutions/notariat-public.json`**

```json
{
  "id": "notariat-public",
  "nume_scurt": "Notariat public",
  "nume_complet": "Notariat public (oricare birou notarial)",
  "scope": "Autentificare contracte (vânzare-cumpărare, donație), împuterniciri, declarații notariale.",
  "url": "https://www.uniuneanotarilor.ro",
  "phone": null,
  "online_disponibil": false,
  "note_ai_cannot_complete": "Contractul autentificat se semnează în prezența notarului. CivicAI nu poate emite contracte notariale."
}
```

- [ ] **Step 3: Create `backend/institutions/ocpi-ancpi.json`**

```json
{
  "id": "ocpi-ancpi",
  "nume_scurt": "OCPI",
  "nume_complet": "Oficiul de Cadastru și Publicitate Imobiliară (ANCPI)",
  "scope": "Cadastru, extras carte funciară, plan situație.",
  "url": "https://www.ancpi.ro",
  "phone": "021 317 7339",
  "online_disponibil": true,
  "note_ai_cannot_complete": "Extras carte funciară se obține direct la OCPI sau online pe ePay. CivicAI nu poate emite acest document — instituție diferită."
}
```

- [ ] **Step 4: Create `backend/institutions/auditor-energetic.json`**

```json
{
  "id": "auditor-energetic",
  "nume_scurt": "Auditor energetic",
  "nume_complet": "Auditor energetic atestat MDRT",
  "scope": "Certificat de performanță energetică a clădirilor.",
  "url": "https://www.mdrt.gov.ro",
  "phone": null,
  "online_disponibil": false,
  "note_ai_cannot_complete": "Certificatul energetic se eliberează de un auditor atestat după inspecție. CivicAI nu îl poate emite."
}
```

- [ ] **Step 5: Create `backend/institutions/drpciv.json`**

```json
{
  "id": "drpciv",
  "nume_scurt": "DRPCIV",
  "nume_complet": "Direcția Regim Permise de Conducere și Înmatriculare a Vehiculelor",
  "scope": "Talon auto, permis de conducere, înmatriculare.",
  "url": "https://www.drpciv.ro",
  "phone": "021 9665",
  "online_disponibil": true,
  "note_ai_cannot_complete": "Actualizarea talonului auto se face la DRPCIV după schimbarea CI. CivicAI nu poate emite documente DRPCIV."
}
```

- [ ] **Step 6: Create `backend/institutions/anaf.json`**

```json
{
  "id": "anaf",
  "nume_scurt": "ANAF",
  "nume_complet": "Agenția Națională de Administrare Fiscală",
  "scope": "Impozite, taxe, fiscalitate, domiciliu fiscal.",
  "url": "https://www.anaf.ro",
  "phone": "031 403 9160",
  "online_disponibil": true,
  "note_ai_cannot_complete": "Notificările fiscale se depun la ANAF. CivicAI nu poate emite documente ANAF."
}
```

- [ ] **Step 7: Create `backend/institutions/cnas.json`**

```json
{
  "id": "cnas",
  "nume_scurt": "CNAS",
  "nume_complet": "Casa Națională de Asigurări de Sănătate",
  "scope": "Medic de familie, asigurare medicală, card de sănătate.",
  "url": "https://www.cnas.ro",
  "phone": "0800 800 950",
  "online_disponibil": true,
  "note_ai_cannot_complete": "Schimbarea medicului de familie se face la CNAS. CivicAI nu poate emite documente CNAS."
}
```

- [ ] **Step 8: Create `backend/institutions/spclep-mai.json`**

```json
{
  "id": "spclep-mai",
  "nume_scurt": "SPCLEP",
  "nume_complet": "Serviciul Public Comunitar Local de Evidență a Persoanelor (MAI)",
  "scope": "Eliberare carte de identitate, evidența persoanelor.",
  "url": "https://depabd.mai.gov.ro",
  "phone": null,
  "online_disponibil": false,
  "note_ai_cannot_complete": "CI nou se predă fizic la SPCLEP/Primărie. Cererea (Anexa 1) se completează în CivicAI dar prezentarea fizică este necesară."
}
```

- [ ] **Step 9: Commit**

```bash
git add backend/institutions
git commit -m "feat(rag): institutions catalog (7 institutions)"
```

---

## Task 2: Author scenario JSONs (5 scenarios)

**Files:**
- Create: `backend/scenarios/sc-cumparare-apartament.json`
- Create: `backend/scenarios/sc-vanzare-apartament.json`
- Create: `backend/scenarios/sc-certificat-fiscal.json`
- Create: `backend/scenarios/sc-autorizatie-construire.json`
- Create: `backend/scenarios/sc-persoana-dizabilitati.json`

Each scenario JSON references existing procedure IDs and institution IDs. Source markdown lives in `primarii-app-data/scenarii/` (already authored); we extract structured fields manually.

- [ ] **Step 1: Create `backend/scenarios/sc-cumparare-apartament.json`**

```json
{
  "id": "sc-cumparare-apartament",
  "title": "Cumpărare apartament",
  "description": "Plan complet după cumpărarea unui apartament: declarare clădire pentru impozit, schimbare CI cu noua adresă, abonament parcare în cartier.",
  "summary_for_rag": "Plan pentru cetățeanul care a cumpărat sau urmează să cumpere un apartament. Acoperă declararea clădirii pentru impozit la primărie (DITL), schimbarea cărții de identitate cu noua adresă (DEP), abonamentul de parcare riveran în cartier. Include pașii externi: notar contract vânzare-cumpărare autentificat, OCPI extras carte funciară, auditor energetic certificat de performanță.",
  "synonyms": ["cumpărare apartament", "achiziție locuință", "am cumpărat o casă", "am cumpărat un apartament", "mutat în apartament nou"],
  "sample_queries": [
    "am cumpărat un apartament",
    "ce trebuie să fac după ce iau o locuință",
    "ce hârtii îmi trebuie pentru apartament nou",
    "mut domiciliul în apartamentul nou"
  ],
  "complexitate": "complex",
  "termen_total": "2-3 luni",
  "applies_if": null,
  "in_scope_steps": [
    { "ordine": 1, "procedure_id": "declarare-cladire",        "deadline_days": 30, "note": "ITL-001 — în 30 zile de la dobândire." },
    { "ordine": 2, "procedure_id": "schimbare-domiciliu",      "deadline_days": 15, "note": "Anexa 1 — necesită contract V-C + extras CF." },
    { "ordine": 3, "procedure_id": "abonament-parcare-strada", "deadline_days": null, "note": "După emiterea noului CI." }
  ],
  "external_steps": [
    { "ordine": 0, "institutie_id": "notariat-public",   "obligatoriu": true, "note": "Primul pas. Contract V-C autentificat." },
    { "ordine": 0, "institutie_id": "ocpi-ancpi",        "obligatoriu": true, "note": "Extras carte funciară max 30 zile." },
    { "ordine": 0, "institutie_id": "auditor-energetic", "obligatoriu": true, "note": "De obicei vânzătorul îl furnizează." }
  ]
}
```

- [ ] **Step 2: Create `backend/scenarios/sc-vanzare-apartament.json`**

```json
{
  "id": "sc-vanzare-apartament",
  "title": "Vânzare apartament",
  "description": "Plan complet pentru vânzarea unui apartament: certificat fiscal, certificat de urbanism (dacă e cazul), pași externi la notar.",
  "summary_for_rag": "Plan pentru cetățeanul care vinde un apartament. La primărie: certificat fiscal pentru atestare lipsă datorii, eventual certificat de urbanism. Pași externi: notar pentru contractul autentificat, OCPI pentru extras carte funciară, auditor energetic pentru certificat de performanță, ANAF pentru declarare venit din vânzare.",
  "synonyms": ["vânzare apartament", "vând locuință", "vând casă", "vânzare imobil"],
  "sample_queries": [
    "vând apartamentul",
    "vreau să-mi vând locuința",
    "ce acte îmi trebuie ca să vând un apartament",
    "vânzare casă acte"
  ],
  "complexitate": "complex",
  "termen_total": "1-2 luni",
  "applies_if": null,
  "in_scope_steps": [
    { "ordine": 1, "procedure_id": "certificat-fiscal", "deadline_days": null, "note": "Certificat de atestare fiscală — confirmă că nu există restanțe la impozite." }
  ],
  "external_steps": [
    { "ordine": 0, "institutie_id": "ocpi-ancpi",        "obligatoriu": true, "note": "Extras carte funciară actualizat (max 30 zile)." },
    { "ordine": 0, "institutie_id": "auditor-energetic", "obligatoriu": true, "note": "Certificat de performanță energetică (vânzătorul furnizează)." },
    { "ordine": 0, "institutie_id": "notariat-public",   "obligatoriu": true, "note": "Autentificarea contractului V-C." },
    { "ordine": 0, "institutie_id": "anaf",              "obligatoriu": false, "note": "Declarare venit din vânzare imobil (dacă deținut sub 3 ani)." }
  ]
}
```

- [ ] **Step 3: Create `backend/scenarios/sc-certificat-fiscal.json`**

```json
{
  "id": "sc-certificat-fiscal",
  "title": "Obținere certificat de atestare fiscală",
  "description": "Plan pentru obținerea unui certificat de atestare fiscală — necesar pentru notar, instanță, sau alte instituții.",
  "summary_for_rag": "Cetățeanul are nevoie de un certificat de atestare fiscală care confirmă lipsa restanțelor la impozite locale. Este o procedură în întregime la primărie (DITL). Documentul este apoi folosit la notar pentru tranzacții imobiliare, în procese, sau pentru alte instituții.",
  "synonyms": ["certificat fiscal", "atestare fiscală", "lipsă datorii primărie", "adeverință fiscală"],
  "sample_queries": [
    "am nevoie de certificat fiscal",
    "vreau atestare fiscală pentru notar",
    "îmi trebuie adeverință că nu am datorii la primărie"
  ],
  "complexitate": "simplu",
  "termen_total": "1-3 zile lucrătoare",
  "applies_if": null,
  "in_scope_steps": [
    { "ordine": 1, "procedure_id": "certificat-fiscal", "deadline_days": null, "note": "Cerere standard la DITL." }
  ],
  "external_steps": []
}
```

- [ ] **Step 4: Create `backend/scenarios/sc-autorizatie-construire.json`**

```json
{
  "id": "sc-autorizatie-construire",
  "title": "Autorizație de construire casă",
  "description": "Plan complet pentru autorizarea construirii unei case: certificat de urbanism, aviz de principiu, autorizație de construire.",
  "summary_for_rag": "Cetățeanul vrea să construiască o casă. La primărie: certificat de urbanism (obligatoriu primul pas), aviz de principiu pentru construcție, apoi autorizația de construire propriu-zisă. Pașii externi includ proiectantul autorizat pentru proiectul tehnic, OCPI pentru cadastru și extrase, eventual avize ANAF/ISC.",
  "synonyms": ["autorizație construire", "vreau să construiesc casă", "autorizație de construcție", "ridicare casă"],
  "sample_queries": [
    "vreau să-mi construiesc o casă",
    "autorizație de construire",
    "ce acte îmi trebuie ca să construiesc",
    "vreau să ridic o casă pe un teren"
  ],
  "complexitate": "foarte complex",
  "termen_total": "3-6 luni",
  "applies_if": null,
  "in_scope_steps": [
    { "ordine": 1, "procedure_id": "cerere-certificat-urbanism",  "deadline_days": null, "note": "Primul pas obligatoriu. Termen primărie: 30 zile." },
    { "ordine": 2, "procedure_id": "aviz-principiu-constructii",  "deadline_days": null, "note": "După obținerea CU. Termen primărie: 15 zile." }
  ],
  "external_steps": [
    { "ordine": 0, "institutie_id": "ocpi-ancpi", "obligatoriu": true, "note": "Plan de situație + extras CF pentru terenul pe care construiești." }
  ]
}
```

- [ ] **Step 5: Create `backend/scenarios/sc-persoana-dizabilitati.json`**

```json
{
  "id": "sc-persoana-dizabilitati",
  "title": "Persoană cu dizabilități — drepturi și facilități",
  "description": "Plan pentru o persoană cu dizabilități încadrată într-un grad: card de parcare, transport urban gratuit, indemnizație.",
  "summary_for_rag": "Cetățeanul (sau aparținătorul) este o persoană cu dizabilități cu certificat de încadrare. La primărie poate cere: cardul european de parcare, gratuitate transport urban, indemnizație lunară (dacă nu o primește de la altă sursă). Pașii externi: comisia de evaluare medicală pentru reînnoirea certificatului (DGASPC).",
  "synonyms": ["persoană dizabilități", "handicap", "facilități dizabilități", "card parcare handicap"],
  "sample_queries": [
    "am certificat de handicap, ce drepturi am la primărie",
    "card de parcare pentru dizabilități",
    "vreau gratuitate transport pentru handicap",
    "indemnizație persoană cu dizabilități"
  ],
  "complexitate": "mediu",
  "termen_total": "2-4 săptămâni",
  "applies_if": null,
  "in_scope_steps": [
    { "ordine": 1, "procedure_id": "card-parcare-dizabilitati",    "deadline_days": null, "note": "Card european de parcare." },
    { "ordine": 2, "procedure_id": "transport-urban-dizabilitati", "deadline_days": null, "note": "Gratuitate transport urban (CTP)." },
    { "ordine": 3, "procedure_id": "indemnizatie-dizabilitati",    "deadline_days": null, "note": "Indemnizație lunară — verifică eligibilitatea." }
  ],
  "external_steps": []
}
```

- [ ] **Step 6: Commit**

```bash
git add backend/scenarios
git commit -m "feat(rag): 5 hand-authored scenario JSONs"
```

---

## Task 3: Add Pydantic models for Scenario + Institutie

**Files:**
- Modify: `backend/app/models.py`

- [ ] **Step 1: Append models to `backend/app/models.py`**

Find the end of the file (after `PatchAttributesRequest`) and append:

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
    applies_if: str | None = None
    in_scope_steps: list[ScenarioInScopeStep] = Field(default_factory=list)
    external_steps: list[ScenarioExternalStep] = Field(default_factory=list)


# Response shapes returned by lookup_procedure / GET /scenarios/{id}.

class ResolvedExternalStep(BaseModel):
    institutie_id: str
    institutie_nume: str
    scope: str | None = None
    url: str | None = None
    phone: str | None = None
    obligatoriu: bool = True
    note: str | None = None
    note_ai_cannot_complete: str | None = None


class ResolvedActeNecesareItem(BaseModel):
    denumire: str
    emitent: str | None = None
    emitent_id: str | None = None
    institutie_nume: str | None = None
    note_ai_cannot_complete: str | None = None
    format: str | None = None
    observatie: str | None = None
    obligatoriu: bool = True
    alternative: list[str] = Field(default_factory=list)


class ResolvedInScopeStep(BaseModel):
    ordine: int
    procedure_id: str
    procedure_title: str
    deadline_days: int | None = None
    note: str | None = None
    acte_necesare: list[ResolvedActeNecesareItem] = Field(default_factory=list)


class ScenarioPlan(BaseModel):
    scenario_id: str
    title: str
    summary: str
    complexitate: str | None = None
    termen_total: str | None = None
    in_scope_steps: list[ResolvedInScopeStep]
    external_steps: list[ResolvedExternalStep]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/models.py
git commit -m "feat(rag): Pydantic models for Scenario + Institutie + ScenarioPlan"
```

---

## Task 4: Institutions registry + integrity test

**Files:**
- Create: `backend/app/institutions.py`
- Create: `backend/tests/test_institutions.py`

- [ ] **Step 1: Write failing integrity test first**

Create `backend/tests/test_institutions.py`:

```python
"""Institutions catalog loads, all expected IDs present."""
from app.institutions import get_institutions_registry


EXPECTED_IDS = {
    "notariat-public",
    "ocpi-ancpi",
    "auditor-energetic",
    "drpciv",
    "anaf",
    "cnas",
    "spclep-mai",
}


def test_registry_loads_all_institutions():
    reg = get_institutions_registry()
    assert set(reg.keys()) == EXPECTED_IDS


def test_each_institution_has_required_fields():
    reg = get_institutions_registry()
    for inst_id, inst in reg.items():
        assert inst.id == inst_id, f"{inst_id} id mismatch"
        assert inst.nume_scurt, f"{inst_id} missing nume_scurt"
        assert inst.nume_complet, f"{inst_id} missing nume_complet"
        assert inst.scope, f"{inst_id} missing scope"


def test_procedure_emitent_ids_all_resolve():
    """Every emitent_id in any procedure JSON must exist in the registry."""
    from app.procedures import get_registry as get_procedure_registry
    reg = get_institutions_registry()
    procs = get_procedure_registry()
    unresolved: list[str] = []
    for proc in procs.values():
        for act in proc.acte_necesare:
            if act.emitent_id and act.emitent_id not in reg:
                unresolved.append(f"{proc.id}::{act.emitent_id}")
    assert unresolved == [], f"Unresolved emitent_id references: {unresolved}"
```

- [ ] **Step 2: Run; verify test fails (module not found)**

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_institutions.py -v
```

Expected: collection error — `from app.institutions import get_institutions_registry` raises ImportError.

- [ ] **Step 3: Implement `backend/app/institutions.py`**

```python
"""Institutions catalog — loads JSON files from backend/institutions/."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.models import Institutie

INSTITUTIONS_DIR = Path(__file__).resolve().parent.parent / "institutions"


@lru_cache(maxsize=1)
def get_institutions_registry() -> dict[str, Institutie]:
    out: dict[str, Institutie] = {}
    for path in sorted(INSTITUTIONS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        inst = Institutie.model_validate(data)
        if inst.id != path.stem:
            raise ValueError(f"Institution id {inst.id!r} does not match filename {path.stem!r}")
        out[inst.id] = inst
    if not out:
        raise RuntimeError(f"No institutions found in {INSTITUTIONS_DIR}")
    return out


def get_institution(institutie_id: str) -> Institutie | None:
    return get_institutions_registry().get(institutie_id)
```

- [ ] **Step 4: Run tests; verify all pass**

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_institutions.py -v
```

Expected: 3/3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/institutions.py backend/tests/test_institutions.py
git commit -m "feat(rag): institutions registry + integrity test"
```

---

## Task 5: Scenarios registry + plan builder + GET /scenarios/{id}

**Files:**
- Create: `backend/app/scenarios.py`
- Create: `backend/tests/test_scenarios.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_scenarios.py`:

```python
"""Scenarios catalog + plan resolution + endpoint."""
import pytest
from fastapi.testclient import TestClient

from app.scenarios import build_scenario_plan, get_scenarios_registry


EXPECTED_SCENARIO_IDS = {
    "sc-cumparare-apartament",
    "sc-vanzare-apartament",
    "sc-certificat-fiscal",
    "sc-autorizatie-construire",
    "sc-persoana-dizabilitati",
}


def test_registry_loads_all_scenarios():
    reg = get_scenarios_registry()
    assert set(reg.keys()) == EXPECTED_SCENARIO_IDS


def test_scenario_in_scope_procedure_ids_all_resolve():
    """Every in_scope_steps[].procedure_id must exist in the procedure registry."""
    from app.procedures import get_registry as get_procedures
    procs = get_procedures()
    unresolved: list[str] = []
    for sc in get_scenarios_registry().values():
        for step in sc.in_scope_steps:
            if step.procedure_id not in procs:
                unresolved.append(f"{sc.id}::{step.procedure_id}")
    assert unresolved == []


def test_scenario_institutie_ids_all_resolve():
    """Every external_steps[].institutie_id must exist in the institutions registry."""
    from app.institutions import get_institutions_registry
    insts = get_institutions_registry()
    unresolved: list[str] = []
    for sc in get_scenarios_registry().values():
        for step in sc.external_steps:
            if step.institutie_id not in insts:
                unresolved.append(f"{sc.id}::{step.institutie_id}")
    assert unresolved == []


def test_build_scenario_plan_resolves_all_refs():
    plan = build_scenario_plan("sc-cumparare-apartament")
    assert plan is not None
    assert plan.scenario_id == "sc-cumparare-apartament"
    assert plan.title == "Cumpărare apartament"
    # 3 in-scope procedures
    assert len(plan.in_scope_steps) == 3
    # Each in-scope step carries resolved procedure_title
    for step in plan.in_scope_steps:
        assert step.procedure_title, f"missing procedure_title for {step.procedure_id}"
    # External steps resolved to institution names
    titles = {s.institutie_nume for s in plan.external_steps}
    assert "Notariat public (oricare birou notarial)" in titles
    assert "Oficiul de Cadastru și Publicitate Imobiliară (ANCPI)" in titles


def test_build_scenario_plan_returns_none_for_unknown():
    assert build_scenario_plan("sc-does-not-exist") is None


def test_scenario_with_no_external_steps():
    plan = build_scenario_plan("sc-certificat-fiscal")
    assert plan is not None
    assert plan.external_steps == []
    assert len(plan.in_scope_steps) == 1


def test_endpoint_returns_plan(monkeypatch):
    from app.main import app
    # Bypass auth (the /scenarios route is public for the agent + frontend)
    client = TestClient(app)
    res = client.get("/scenarios/sc-cumparare-apartament")
    assert res.status_code == 200
    body = res.json()
    assert body["scenario_id"] == "sc-cumparare-apartament"
    assert len(body["in_scope_steps"]) == 3


def test_endpoint_404_unknown():
    from app.main import app
    client = TestClient(app)
    res = client.get("/scenarios/sc-does-not-exist")
    assert res.status_code == 404
```

- [ ] **Step 2: Run; verify collection error or all-fail**

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_scenarios.py -v
```

Expected: ImportError on `from app.scenarios import ...`.

- [ ] **Step 3: Implement `backend/app/scenarios.py`**

```python
"""Scenarios catalog + plan builder + GET /scenarios/{id}.

A scenario links several existing procedures (in-scope) and external institution
steps (CivicAI cannot complete) into a coherent multi-step plan for a real-life
situation like "buying an apartment".
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.institutions import get_institutions_registry
from app.models import (
    ResolvedActeNecesareItem,
    ResolvedExternalStep,
    ResolvedInScopeStep,
    Scenario,
    ScenarioPlan,
)

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@lru_cache(maxsize=1)
def get_scenarios_registry() -> dict[str, Scenario]:
    out: dict[str, Scenario] = {}
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        sc = Scenario.model_validate(data)
        if sc.id != path.stem:
            raise ValueError(f"Scenario id {sc.id!r} does not match filename {path.stem!r}")
        out[sc.id] = sc
    if not out:
        raise RuntimeError(f"No scenarios found in {SCENARIOS_DIR}")
    return out


def resolve_act(act) -> ResolvedActeNecesareItem:
    """Enrich an ActNecesar with institution name + ai-cannot-complete note when applicable."""
    institutie_nume: str | None = None
    note_ai: str | None = None
    if act.emitent_id:
        inst = get_institutions_registry().get(act.emitent_id)
        if inst is not None:
            institutie_nume = inst.nume_complet
            note_ai = inst.note_ai_cannot_complete
    return ResolvedActeNecesareItem(
        denumire=act.denumire,
        emitent=act.emitent,
        emitent_id=act.emitent_id,
        institutie_nume=institutie_nume,
        note_ai_cannot_complete=note_ai,
        format=act.format,
        observatie=act.observatie,
        obligatoriu=act.obligatoriu,
        alternative=list(act.alternative),
    )


def build_scenario_plan(scenario_id: str) -> ScenarioPlan | None:
    from app.procedures import get_registry as get_procedures_registry

    sc = get_scenarios_registry().get(scenario_id)
    if sc is None:
        return None

    procs = get_procedures_registry()
    insts = get_institutions_registry()

    resolved_in_scope: list[ResolvedInScopeStep] = []
    for step in sc.in_scope_steps:
        proc = procs.get(step.procedure_id)
        if proc is None:
            # Skip dangling — integrity test catches this in CI; tolerate at runtime.
            continue
        resolved_in_scope.append(
            ResolvedInScopeStep(
                ordine=step.ordine,
                procedure_id=step.procedure_id,
                procedure_title=proc.title,
                deadline_days=step.deadline_days,
                note=step.note,
                acte_necesare=[resolve_act(a) for a in proc.acte_necesare],
            )
        )

    resolved_external: list[ResolvedExternalStep] = []
    for step in sc.external_steps:
        inst = insts.get(step.institutie_id)
        if inst is None:
            continue
        resolved_external.append(
            ResolvedExternalStep(
                institutie_id=inst.id,
                institutie_nume=inst.nume_complet,
                scope=inst.scope,
                url=inst.url,
                phone=inst.phone,
                obligatoriu=step.obligatoriu,
                note=step.note,
                note_ai_cannot_complete=inst.note_ai_cannot_complete,
            )
        )

    return ScenarioPlan(
        scenario_id=sc.id,
        title=sc.title,
        summary=sc.description,
        complexitate=sc.complexitate,
        termen_total=sc.termen_total,
        in_scope_steps=resolved_in_scope,
        external_steps=resolved_external,
    )


@router.get("/{scenario_id}", response_model=ScenarioPlan)
def get_scenario_plan_endpoint(scenario_id: str) -> ScenarioPlan:
    plan = build_scenario_plan(scenario_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id!r} not found")
    return plan
```

- [ ] **Step 4: Mount the router in `backend/app/main.py`**

Open `backend/app/main.py`. Find the existing `from app.procedures import router as procedures_router` import line and add right after it:

```python
from app.scenarios import router as scenarios_router
```

Then find the existing `app.include_router(procedures_router)` line and add right after it:

```python
app.include_router(scenarios_router)
```

- [ ] **Step 5: Run tests; verify all pass**

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_scenarios.py -v
```

Expected: 8/8 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/scenarios.py backend/app/main.py backend/tests/test_scenarios.py
git commit -m "feat(rag): scenarios registry + plan builder + GET /scenarios/{id}"
```

---

## Task 6: Migration 007 — rename procedures_embeddings → rag_entries + add kind

**Files:**
- Create: `backend/migrations/007_rag_entries.sql`

- [ ] **Step 1: Write migration**

```sql
-- 007_rag_entries.sql (Multi-procedure RAG)
-- Rename procedures_embeddings to rag_entries and add a kind column so we can
-- hold both procedure and scenario embeddings in one table.

alter table procedures_embeddings rename to rag_entries;
alter table rag_entries rename column procedure_id to id;
alter table rag_entries add column if not exists kind text not null default 'procedure'
  check (kind in ('procedure', 'scenario'));

create index if not exists idx_rag_entries_kind on rag_entries(kind);
```

- [ ] **Step 2: Apply migration to Supabase**

Via Supabase SQL editor (Dashboard → SQL Editor → New query → paste contents → Run), OR via psql if `SUPABASE_DB_URL` is set:

```bash
psql "$SUPABASE_DB_URL" -f backend/migrations/007_rag_entries.sql
```

Expected output: `ALTER TABLE` x3, `CREATE INDEX` x1.

- [ ] **Step 3: Verify the rename**

```sql
\d rag_entries
-- Should show: id, kind, embedding (vector(768)), source_text, updated_at.
```

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/007_rag_entries.sql
git commit -m "feat(rag): migration 007 — rag_entries table with kind column"
```

---

## Task 7: Update `embeddings.py` for the new table + add search_top_k_rag

**Files:**
- Modify: `backend/app/embeddings.py`

- [ ] **Step 1: Replace upsert + add search_top_k_rag**

In `backend/app/embeddings.py`, replace the `upsert_procedure_embedding` and `search_top_k` functions with the following block:

```python
def upsert_rag_entry(
    *,
    entry_id: str,
    kind: str,
    source_text: str,
    embedding: list[float],
) -> None:
    if len(embedding) != EMBEDDING_DIM:
        raise ValueError(f"Embedding must be {EMBEDDING_DIM}-dim, got {len(embedding)}")
    if kind not in {"procedure", "scenario"}:
        raise ValueError(f"Invalid kind {kind!r}; must be 'procedure' or 'scenario'")
    vec_literal = "[" + ",".join(f"{x:.7f}" for x in embedding) + "]"
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "insert into rag_entries (id, kind, embedding, source_text) "
            "values (%s, %s, %s::vector, %s) "
            "on conflict (id) do update set "
            "kind = excluded.kind, embedding = excluded.embedding, "
            "source_text = excluded.source_text, updated_at = now();",
            (entry_id, kind, vec_literal, source_text),
        )
        conn.commit()


# Back-compat shim — existing callers use this name + signature.
def upsert_procedure_embedding(procedure_id: str, source_text: str, embedding: list[float]) -> None:
    upsert_rag_entry(entry_id=procedure_id, kind="procedure", source_text=source_text, embedding=embedding)


def search_top_k_rag(query_embedding: list[float], k: int = 5) -> list[dict[str, Any]]:
    """Top-K across rag_entries regardless of kind. Each row: {id, kind, score}."""
    vec_literal = "[" + ",".join(f"{x:.7f}" for x in query_embedding) + "]"
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, kind, 1 - (embedding <=> %s::vector) as score "
            "from rag_entries "
            "order by embedding <=> %s::vector asc limit %s;",
            (vec_literal, vec_literal, k),
        )
        return [dict(r) for r in cur.fetchall()]


# Back-compat wrapper for code paths that only want procedure matches.
def search_top_k(query_embedding: list[float], k: int = 3) -> list[dict[str, Any]]:
    vec_literal = "[" + ",".join(f"{x:.7f}" for x in query_embedding) + "]"
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id as procedure_id, 1 - (embedding <=> %s::vector) as score "
            "from rag_entries where kind = 'procedure' "
            "order by embedding <=> %s::vector asc limit %s;",
            (vec_literal, vec_literal, k),
        )
        return [dict(r) for r in cur.fetchall()]
```

- [ ] **Step 2: Add scenario_source_text helper**

In `backend/app/embeddings.py`, after the existing `procedure_source_text` function, add:

```python
def scenario_source_text(sc) -> str:
    """Authored summary + synonyms + sample queries — never chunked."""
    parts = [sc.summary_for_rag, " ".join(sc.synonyms), " ".join(sc.sample_queries)]
    return "\n".join(p for p in parts if p)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/embeddings.py
git commit -m "feat(rag): rag_entries upsert + kind-agnostic search_top_k_rag"
```

---

## Task 8: Indexer script `backend/scripts/index_rag.py`

**Files:**
- Create: `backend/scripts/index_rag.py`

- [ ] **Step 1: Create the indexer**

```python
"""Re-index all procedures + scenarios into rag_entries.

Idempotent. Safe to run after every JSON change. Requires Supabase DB env vars
and a working GEMINI_API_KEY.
"""
from __future__ import annotations

import logging

from app.embeddings import (
    embed_text,
    procedure_source_text,
    scenario_source_text,
    upsert_rag_entry,
)
from app.institutions import get_institutions_registry
from app.procedures import get_registry as get_procedures_registry
from app.scenarios import get_scenarios_registry

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("index_rag")


def main() -> None:
    # Touch institutions registry once to trigger integrity checks.
    insts = get_institutions_registry()
    log.info("Institutions loaded: %d", len(insts))

    procs = get_procedures_registry()
    log.info("Procedures loaded: %d — indexing...", len(procs))
    for proc in procs.values():
        text = procedure_source_text(proc)
        embedding = embed_text(text)
        upsert_rag_entry(entry_id=proc.id, kind="procedure", source_text=text, embedding=embedding)
        log.info("  ✓ %s", proc.id)

    scs = get_scenarios_registry()
    log.info("Scenarios loaded: %d — indexing...", len(scs))
    for sc in scs.values():
        text = scenario_source_text(sc)
        embedding = embed_text(text)
        upsert_rag_entry(entry_id=sc.id, kind="scenario", source_text=text, embedding=embedding)
        log.info("  ✓ %s", sc.id)

    log.info("Done. Total entries indexed: %d", len(procs) + len(scs))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the indexer against the deployed DB**

From the backend dir with env vars sourced:

```bash
cd backend && .venv/Scripts/python.exe -m scripts.index_rag
```

Expected: log lines for each procedure + each scenario, then `Total entries indexed: 26` (21 procedures + 5 scenarios).

If it fails on missing `Scenario.applies_if`-evaluator-on-frontend path, ignore — that's the frontend task; the indexer doesn't evaluate `applies_if`.

- [ ] **Step 3: Verify in SQL**

```sql
select kind, count(*) from rag_entries group by kind;
```

Expected: `procedure | 21`, `scenario | 5`.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/index_rag.py
git commit -m "feat(rag): index_rag.py — populates rag_entries with procedures + scenarios"
```

---

## Task 9: Extend `lookup_procedure` tool with `scenario_plan`

**Files:**
- Modify: `backend/app/tools/lookup_procedure.py`
- Modify: `backend/tests/test_plan3_smoke.py` (add new test cases)

- [ ] **Step 1: Write failing tests in `backend/tests/test_plan3_smoke.py`**

Append to the existing file (find the end of test functions and add):

```python
def test_lookup_returns_scenario_plan_when_top_is_scenario(monkeypatch):
    """When the top-1 RAG hit is a scenario above threshold, scenario_plan is populated."""
    from app.tools import lookup_procedure as lp_module
    from app.tools.lookup_procedure import LookupResult, lookup_procedure
    import asyncio

    fake_rows = [
        {"id": "sc-cumparare-apartament", "kind": "scenario", "score": 0.78},
        {"id": "declarare-cladire", "kind": "procedure", "score": 0.62},
    ]

    def fake_embed(_text):
        return [0.0] * 768

    def fake_search(_emb, k=5):
        return fake_rows

    monkeypatch.setattr(lp_module, "embed_text", fake_embed)
    monkeypatch.setattr(lp_module, "search_top_k_rag", fake_search)

    result: LookupResult = asyncio.run(
        lookup_procedure(ctx=None, query="am cumpărat un apartament")
    )

    assert result.scenario_plan is not None
    assert result.scenario_plan.scenario_id == "sc-cumparare-apartament"
    assert len(result.scenario_plan.in_scope_steps) == 3


def test_lookup_returns_no_scenario_when_top_is_procedure(monkeypatch):
    """Procedure wins even if a scenario is in the top-K but lower-ranked."""
    from app.tools import lookup_procedure as lp_module
    from app.tools.lookup_procedure import lookup_procedure
    import asyncio

    fake_rows = [
        {"id": "schimbare-domiciliu", "kind": "procedure", "score": 0.81},
        {"id": "sc-cumparare-apartament", "kind": "scenario", "score": 0.66},
    ]

    monkeypatch.setattr(lp_module, "embed_text", lambda _t: [0.0] * 768)
    monkeypatch.setattr(lp_module, "search_top_k_rag", lambda _e, k=5: fake_rows)

    result = asyncio.run(lookup_procedure(ctx=None, query="vreau să-mi schimb domiciliul"))

    assert result.scenario_plan is None
    assert len(result.matches) >= 1
    assert result.matches[0].procedure_id == "schimbare-domiciliu"


def test_lookup_below_threshold_returns_empty(monkeypatch):
    """Sub-threshold hits return empty matches and no scenario_plan."""
    from app.tools import lookup_procedure as lp_module
    from app.tools.lookup_procedure import lookup_procedure
    import asyncio

    fake_rows = [
        {"id": "schimbare-domiciliu", "kind": "procedure", "score": 0.30},
    ]

    monkeypatch.setattr(lp_module, "embed_text", lambda _t: [0.0] * 768)
    monkeypatch.setattr(lp_module, "search_top_k_rag", lambda _e, k=5: fake_rows)

    result = asyncio.run(lookup_procedure(ctx=None, query="ceva ciudat care nu există"))

    # Procedure matches list still includes the row (agent uses scores to judge),
    # but no scenario plan was triggered.
    assert result.scenario_plan is None
```

- [ ] **Step 2: Run tests; verify they fail**

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_plan3_smoke.py -v -k "lookup_returns" -k "lookup_below"
```

Expected: 3 failures — `scenario_plan` field doesn't exist on LookupResult.

- [ ] **Step 3: Rewrite `backend/app/tools/lookup_procedure.py`**

Replace the entire file contents:

```python
"""lookup_procedure — kind-agnostic RAG search; returns procedure matches + optional scenario plan."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.embeddings import embed_text, search_top_k_rag
from app.models import (
    ResolvedActeNecesareItem,
    ScenarioPlan,
)
from app.procedures import get_registry
from app.scenarios import build_scenario_plan, resolve_act
from app.tools import ToolContext, register

SCENARIO_THRESHOLD = 0.55


class ProcedureMatch(BaseModel):
    procedure_id: str
    title: str
    score: float
    description: str | None = None
    acte_necesare: list[ResolvedActeNecesareItem] = Field(default_factory=list)


class LookupResult(BaseModel):
    matches: list[ProcedureMatch] = Field(default_factory=list)
    scenario_plan: ScenarioPlan | None = None


@register("lookup_procedure")
async def lookup_procedure(ctx: ToolContext, query: str) -> LookupResult:
    """Find the best primărie unit (procedure or scenario) for a free-text Romanian query.

    Top-1 wins: scenario_plan is populated only when the highest-scoring hit is a
    scenario above SCENARIO_THRESHOLD. Procedure matches are always populated from
    procedure rows in top-K so the agent has fallback options.
    """
    query = (query or "").strip()
    if not query:
        raise ValueError("query cannot be empty")

    embedding = embed_text(query)
    raw = search_top_k_rag(embedding, k=5)

    scenario_plan: ScenarioPlan | None = None
    if raw and raw[0]["score"] >= SCENARIO_THRESHOLD and raw[0]["kind"] == "scenario":
        scenario_plan = build_scenario_plan(raw[0]["id"])

    reg = get_registry()
    matches: list[ProcedureMatch] = []
    for row in raw:
        if row["kind"] != "procedure":
            continue
        proc = reg.get(row["id"])
        if proc is None:
            continue
        matches.append(
            ProcedureMatch(
                procedure_id=row["id"],
                title=proc.title,
                score=float(row["score"]),
                description=proc.description,
                acte_necesare=[resolve_act(a) for a in proc.acte_necesare],
            )
        )
        if len(matches) >= 3:
            break

    return LookupResult(matches=matches, scenario_plan=scenario_plan)
```

- [ ] **Step 4: Run tests; verify they pass**

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_plan3_smoke.py -v -k "lookup"
```

Expected: 3 PASS (plus whatever existing `lookup`-tagged tests there were).

- [ ] **Step 5: Commit**

```bash
git add backend/app/tools/lookup_procedure.py backend/tests/test_plan3_smoke.py
git commit -m "feat(rag): lookup_procedure returns scenario_plan when top hit is scenario"
```

---

## Task 10: Extend `GET /procedures/{id}` to resolve `emitent_id`

**Files:**
- Modify: `backend/app/procedures.py`
- Modify: `backend/app/models.py`

- [ ] **Step 1: Add a `ResolvedProcedure` response model in `backend/app/models.py`**

Find the existing `Procedure` class. Right after it, add:

```python
class ResolvedProcedure(BaseModel):
    """Same shape as Procedure, but acte_necesare items are enriched with
    institution name + AI-cannot-complete note when an emitent_id is present.
    """
    id: str
    title: str
    description: str
    scope: Literal["primarie", "external"]
    category: str
    synonyms: list[str]
    sample_queries: list[str]
    acte_necesare: list[ResolvedActeNecesareItem] = Field(default_factory=list)
    fields: list[ProcedureField]
    template: str
    next_steps: list[NextStep] = Field(default_factory=list)
```

- [ ] **Step 2: Update `GET /procedures/{id}` to return the resolved shape**

In `backend/app/procedures.py`, find the existing `get_procedure` endpoint and replace it with:

```python
@router.get("/{procedure_id}", response_model=ResolvedProcedure)
def get_procedure(procedure_id: str) -> ResolvedProcedure:
    from app.scenarios import resolve_act  # lazy: avoid cyclic imports at module load

    reg = get_registry()
    proc = reg.get(procedure_id)
    if proc is None:
        raise HTTPException(status_code=404, detail=f"Procedure '{procedure_id}' not found")

    return ResolvedProcedure(
        id=proc.id,
        title=proc.title,
        description=proc.description,
        scope=proc.scope,
        category=proc.category,
        synonyms=list(proc.synonyms),
        sample_queries=list(proc.sample_queries),
        acte_necesare=[resolve_act(a) for a in proc.acte_necesare],
        fields=list(proc.fields),
        template=proc.template,
        next_steps=list(proc.next_steps),
    )
```

Update the import line at the top of `backend/app/procedures.py` to include the new model:

```python
from app.models import (
    Procedure,
    ProcedureLookupRequest,
    ProcedureLookupResponse,
    ProcedureMatch,
    ResolvedProcedure,
)
```

- [ ] **Step 3: Smoke-test the endpoint locally**

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/test_scenarios.py::test_endpoint_returns_plan -v
```

(reuses existing TestClient setup; this step just confirms nothing broke from import changes)

- [ ] **Step 4: Commit**

```bash
git add backend/app/procedures.py backend/app/models.py
git commit -m "feat(rag): GET /procedures/{id} resolves emitent_id to institution info"
```

---

## Task 11: Agent prompt directives

**Files:**
- Modify: `backend/app/prompts.py`

- [ ] **Step 1: Append directives to `CONVERSATIONAL_SYSTEM`**

In `backend/app/prompts.py`, find the `CONVERSATIONAL_SYSTEM` string. Inside the triple-quoted string, before the closing `"""`, append (preserving formatting and numbering):

```
10. Dacă tool-ul `lookup_procedure` returnează un câmp `scenario_plan` (situație
    cu mai multe proceduri), nu enumera procedurile sau actele în chat. Spune
    în 1-2 propoziții ce acoperă planul ("Plan pentru cumpărare apartament:
    3 cereri la primărie și 3 pași externi.") și menționează că detaliile
    sunt în panoul din dreapta. Cetățeanul alege de unde începe.
11. Dacă cetățeanul nu specifică de unde începe într-un scenariu, nu inițializa
    automat o procedură. Așteaptă alegerea explicită prin click în plan sau o
    cerere explicită ("începe cu schimbarea CI").
```

- [ ] **Step 2: Append to `PHONE_SYSTEM`**

Same file, find `PHONE_SYSTEM`. Append before the closing `"""`:

```
7. Dacă `lookup_procedure` returnează un `scenario_plan`, citește pe scurt:
   "Acest plan are X cereri la primărie și Y pași externi. Primul pas: <titlu>."
   Apoi invită cetățeanul pe civicai.ro pentru execuție. Nu enumera vocal toate
   procedurile sau actele — fragmentează în mai multe replici dacă cetățeanul cere detalii.
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/prompts.py
git commit -m "feat(rag): agent prompt directives for scenario_plan handling"
```

---

## Task 12: Frontend types + API client method

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add TypeScript types for ScenarioPlan + resolved shapes**

In `frontend/lib/types.ts`, append at the end:

```typescript
export type ResolvedActeNecesareItem = {
  denumire: string;
  emitent?: string;
  emitent_id?: string;
  institutie_nume?: string;
  note_ai_cannot_complete?: string;
  format?: string;
  observatie?: string;
  obligatoriu: boolean;
  alternative: string[];
};

export type ResolvedInScopeStep = {
  ordine: number;
  procedure_id: string;
  procedure_title: string;
  deadline_days?: number;
  note?: string;
  acte_necesare: ResolvedActeNecesareItem[];
};

export type ResolvedExternalStep = {
  institutie_id: string;
  institutie_nume: string;
  scope?: string;
  url?: string;
  phone?: string;
  obligatoriu: boolean;
  note?: string;
  note_ai_cannot_complete?: string;
};

export type ScenarioPlan = {
  scenario_id: string;
  title: string;
  summary: string;
  complexitate?: string;
  termen_total?: string;
  in_scope_steps: ResolvedInScopeStep[];
  external_steps: ResolvedExternalStep[];
};
```

- [ ] **Step 2: Add `getScenarioPlan` to `frontend/lib/api.ts`**

Open `frontend/lib/api.ts`. In the imports block at the top, add `ScenarioPlan`:

```typescript
import { getSession } from "./session";
import type {
  AuthSession,
  Citizen,
  ChatResponse,
  Document,
  LedgerResponse,
  LoginChallenge,
  Procedure,
  ProcedureLookupResponse,
  Reminder,
  ScenarioPlan,
  VoicePreferences,
} from "./types";
```

In the `export const api = { ... }` object, after `getProcedure`, add:

```typescript
  getScenarioPlan: (id: string) => request<ScenarioPlan>(`/scenarios/${id}`),
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat(rag): frontend types for ScenarioPlan + api.getScenarioPlan"
```

---

## Task 13: Session store + right-pane `plan` state

**Files:**
- Modify: `frontend/lib/sessionStore.ts`
- Modify: `frontend/lib/rightPaneState.ts`

- [ ] **Step 1: Extend RightPaneState union**

In `frontend/lib/sessionStore.ts` (or wherever `RightPaneState` is defined — check `rightPaneState.ts` if needed), find the existing union and add:

```typescript
| { kind: "plan"; scenarioId: string }
```

Example diff:

```typescript
export type RightPaneState =
  | { kind: "welcome" }
  | { kind: "guide"; procedureId: string }
  | { kind: "filling"; activeField?: string }
  | { kind: "review" }
  | { kind: "pdf"; url: string }
  | { kind: "delivery" }
  | { kind: "done"; refNumber: string }
  | { kind: "plan"; scenarioId: string };  // NEW
```

- [ ] **Step 2: Add `scenarioPlan` to SessionState + `openScenarioPlan` action**

In `frontend/lib/sessionStore.ts`, find the `SessionState` interface. Add:

```typescript
  scenarioPlan: ScenarioPlan | null;

  openScenarioPlan(scenarioId: string): Promise<void>;
```

(Import `ScenarioPlan` from `./types` at the top of the file.)

In the store implementation, initialize `scenarioPlan: null` in the initial state, and add the action:

```typescript
async openScenarioPlan(scenarioId: string) {
  try {
    const plan = await api.getScenarioPlan(scenarioId);
    set({
      scenarioPlan: plan,
      rightPane: { kind: "plan", scenarioId },
    });
    if (typeof window !== "undefined") {
      history.pushState(null, "", `/p/${scenarioId}`);
    }
  } catch (e) {
    // best-effort; agent can still surface plan via lookup_procedure
    console.error("openScenarioPlan failed", e);
  }
},
```

Also ensure `reset()` clears `scenarioPlan: null`.

- [ ] **Step 3: Add `applyToolResult` branch for scenario_plan in lookup_procedure**

In the same store file, find the existing `applyToolResult(toolName, args, result)` action. Add a case for `lookup_procedure` (or extend the existing one):

```typescript
if (toolName === "lookup_procedure") {
  const res = result as { scenario_plan?: ScenarioPlan | null } | undefined;
  const sp = res?.scenario_plan ?? null;
  if (sp) {
    // Only set plan state when not currently engaged with a document.
    const { activeDocId } = get();
    if (!activeDocId) {
      set({
        scenarioPlan: sp,
        rightPane: { kind: "plan", scenarioId: sp.scenario_id },
      });
      if (typeof window !== "undefined") {
        history.pushState(null, "", `/p/${sp.scenario_id}`);
      }
    }
  }
  return;
}
```

- [ ] **Step 4: Add transition rules to `rightPaneState.ts`**

Open `frontend/lib/rightPaneState.ts`. In the table-driven transitions module, add an explicit list of legal transitions involving `plan`:

```typescript
// welcome → plan: scenario_plan returned by lookup_procedure OR explicit chip click.
// plan    → guide: user clicks "Începe acum" on an in_scope_step (uses startProcedure).
// any     → plan via popstate to /p/<id>: handled in ChatSurface popstate listener.
```

If the file exposes a `nextState(current, event)` function, add cases:

```typescript
case "OPEN_PLAN":   // { type: "OPEN_PLAN", scenarioId }
  return { kind: "plan", scenarioId: event.scenarioId };
```

(If your store dispatches state directly via `set`, the union extension in step 1 is enough — no additional reducer changes needed.)

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/sessionStore.ts frontend/lib/rightPaneState.ts
git commit -m "feat(rag): right-pane plan state + openScenarioPlan action"
```

---

## Task 14: `/p/[id]` route

**Files:**
- Create: `frontend/app/p/[id]/page.tsx`
- Modify: `frontend/components/chat/ChatSurface.tsx`

- [ ] **Step 1: Create the route file**

Create `frontend/app/p/[id]/page.tsx`:

```tsx
"use client";

import { use } from "react";
import { ChatSurface } from "@/components/chat/ChatSurface";

type Props = { params: Promise<{ id: string }> };

export default function ScenarioPlanPage({ params }: Props) {
  const { id } = use(params);
  return <ChatSurface activeDocId={null} activeScenarioId={id} />;
}
```

- [ ] **Step 2: Extend `ChatSurface` to accept `activeScenarioId`**

Open `frontend/components/chat/ChatSurface.tsx`. Modify the `Props` type:

```typescript
type Props = {
  activeDocId: string | null;
  activeScenarioId?: string | null;
};
```

Update the component signature:

```typescript
export function ChatSurface({ activeDocId, activeScenarioId = null }: Props) {
```

Find the existing `useEffect` that calls `loadDocument(activeDocId)`. Right after it, add:

```typescript
const openScenarioPlan = useSessionStore((s) => s.openScenarioPlan);

useEffect(() => {
  if (!activeScenarioId) return;
  void openScenarioPlan(activeScenarioId).catch(() => {});
}, [activeScenarioId, openScenarioPlan]);
```

Find the existing `popstate` handler. Extend it:

```typescript
function onPop() {
  const path = window.location.pathname;
  if (path === "/") {
    reset();
  } else if (path.startsWith("/r/")) {
    void loadDocument(path.slice(3));
  } else if (path.startsWith("/p/")) {
    void openScenarioPlan(path.slice(3));
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/p frontend/components/chat/ChatSurface.tsx
git commit -m "feat(rag): /p/[id] route renders ChatSurface with scenario plan"
```

---

## Task 15: `PlanPane` component

**Files:**
- Create: `frontend/components/right-pane/PlanPane.tsx`
- Modify: `frontend/components/chat/RightPane.tsx`

- [ ] **Step 1: Create `PlanPane`**

```tsx
"use client";

import { Button } from "@/components/ui/button";
import { useSessionStore } from "@/lib/sessionStore";

export function PlanPane() {
  const plan = useSessionStore((s) => s.scenarioPlan);
  const startProcedure = useSessionStore((s) => s.startProcedure);

  if (!plan) {
    return (
      <p className="p-6 text-sm text-muted-foreground">Se încarcă planul…</p>
    );
  }

  return (
    <article className="mx-auto max-w-2xl space-y-6 p-6">
      <header>
        <p className="text-xs uppercase tracking-wider text-muted-foreground">
          Plan multi-pas
        </p>
        <h2 className="mt-1 text-2xl font-semibold">{plan.title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{plan.summary}</p>
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
          {plan.complexitate ? <span>Complexitate: {plan.complexitate}</span> : null}
          {plan.termen_total ? <span>Termen total: {plan.termen_total}</span> : null}
        </div>
      </header>

      <section>
        <h3 className="mb-2 text-sm font-medium">
          ✅ Ce pot completa eu pentru tine
        </h3>
        <ol className="space-y-3">
          {plan.in_scope_steps.map((step) => (
            <li
              key={step.procedure_id}
              className="flex items-start justify-between gap-3 rounded-lg border p-3"
            >
              <div>
                <p className="font-medium">
                  {step.ordine}. {step.procedure_title}
                </p>
                {step.deadline_days ? (
                  <p className="text-xs text-muted-foreground">
                    Termen: {step.deadline_days} zile
                  </p>
                ) : null}
                {step.note ? (
                  <p className="text-xs text-muted-foreground">{step.note}</p>
                ) : null}
              </div>
              <Button
                size="sm"
                onClick={() => void startProcedure(step.procedure_id)}
              >
                Începe acum
              </Button>
            </li>
          ))}
        </ol>
      </section>

      {plan.external_steps.length > 0 ? (
        <section>
          <h3 className="mb-2 text-sm font-medium">
            ↗ Ce trebuie să faci tu (extern)
          </h3>
          <ul className="space-y-3">
            {plan.external_steps.map((step) => (
              <li
                key={step.institutie_id}
                className="rounded-lg border border-dashed p-3"
              >
                <p className="font-medium">{step.institutie_nume}</p>
                {step.note ? (
                  <p className="text-xs text-muted-foreground">{step.note}</p>
                ) : null}
                <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
                  {step.phone ? <span>📞 {step.phone}</span> : null}
                  {step.url ? (
                    <a
                      href={step.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline"
                    >
                      🌐 {step.url}
                    </a>
                  ) : null}
                </div>
                {step.note_ai_cannot_complete ? (
                  <p className="mt-2 text-xs italic text-muted-foreground">
                    {step.note_ai_cannot_complete}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}
```

- [ ] **Step 2: Mount `PlanPane` in `RightPane`**

Open `frontend/components/chat/RightPane.tsx`. Find the switch on `rightPane.kind`. Add a case:

```tsx
import { PlanPane } from "@/components/right-pane/PlanPane";

// inside the switch:
case "plan":
  return <PlanPane />;
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/right-pane/PlanPane.tsx frontend/components/chat/RightPane.tsx
git commit -m "feat(rag): PlanPane renders scenario plan with start-now per in-scope step"
```

---

## Task 16: `WelcomePane` scenario chips

**Files:**
- Modify: `frontend/components/right-pane/WelcomePane.tsx`
- Modify: `frontend/lib/api.ts` (add `listScenarios` if not present)

- [ ] **Step 1: Add `listScenarios` to api**

In `frontend/lib/api.ts`, add a new endpoint method (if not present). First add a return type in `lib/types.ts`:

```typescript
// frontend/lib/types.ts — append
export type ScenarioSummary = {
  id: string;
  title: string;
  description: string;
  complexitate?: string;
  applies_if?: string;
};
```

Then in `lib/api.ts`, in the imports add `ScenarioSummary`, and in the api object after `getScenarioPlan`:

```typescript
listScenarios: () => request<ScenarioSummary[]>("/scenarios"),
```

- [ ] **Step 2: Add a `GET /scenarios` endpoint in the backend**

Open `backend/app/scenarios.py`. After the `get_scenario_plan_endpoint` function, add:

```python
from app.models import Scenario as ScenarioModel  # alias to keep imports tidy

class ScenarioSummary(BaseModel):
    id: str
    title: str
    description: str
    complexitate: str | None = None
    applies_if: str | None = None


@router.get("", response_model=list[ScenarioSummary])
def list_scenarios() -> list[ScenarioSummary]:
    return [
        ScenarioSummary(
            id=sc.id,
            title=sc.title,
            description=sc.description,
            complexitate=sc.complexitate,
            applies_if=sc.applies_if,
        )
        for sc in get_scenarios_registry().values()
    ]
```

Add at the top of `backend/app/scenarios.py`:

```python
from pydantic import BaseModel
```

- [ ] **Step 3: Modify `WelcomePane` to mix scenario chips**

Open `frontend/components/right-pane/WelcomePane.tsx`. Replace the imports + body to also fetch scenarios:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";
import type {
  CitizenAttributes,
  Procedure,
  Reminder,
  ScenarioSummary,
} from "@/lib/types";

function filterProcedures(procs: Procedure[], attrs: CitizenAttributes): Procedure[] {
  const out: Procedure[] = [];
  const seenCategories = new Set<string>();
  for (const p of procs) {
    if (p.category.includes("vehicul") && attrs.owns_vehicle === false) continue;
    if (p.category.includes("copii") && attrs.has_children === false) continue;
    if (seenCategories.has(p.category)) continue;
    seenCategories.add(p.category);
    out.push(p);
    if (out.length >= 2) break;
  }
  return out;
}

function filterScenarios(scenarios: ScenarioSummary[], attrs: CitizenAttributes): ScenarioSummary[] {
  // Evaluate applies_if client-side using the same simple syntax as backend.
  // For hackathon scope, accept all scenarios that either have no applies_if or
  // pass a trivial check; full applies_if evaluation lives on the backend.
  return scenarios
    .filter((s) => {
      if (!s.applies_if) return true;
      // Minimal client check: "owns_vehicle == true" / "has_children == true" only.
      const m = /^(\w+)\s*==\s*(true|false)$/.exec(s.applies_if.trim());
      if (!m) return true;
      const [, key, val] = m;
      const expected = val === "true";
      const actual = (attrs as Record<string, unknown>)[key];
      return actual === expected;
    })
    .slice(0, 2);
}

export function WelcomePane() {
  const citizen = useSessionStore((s) => s.citizen);
  const startProcedure = useSessionStore((s) => s.startProcedure);
  const openScenarioPlan = useSessionStore((s) => s.openScenarioPlan);
  const openDrawer = useSessionStore((s) => s.openDrawer);
  const [procedures, setProcedures] = useState<Procedure[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void Promise.all([
      api.listProcedures().catch(() => [] as Procedure[]),
      api.listScenarios().catch(() => [] as ScenarioSummary[]),
      api.listReminders().catch(() => [] as Reminder[]),
    ]).then(([p, s, r]) => {
      setProcedures(p);
      setScenarios(s);
      setReminders(r);
      setLoading(false);
    });
  }, []);

  const pendingReminders = reminders.filter((r) => r.status === "pending");
  const attrs = citizen?.attributes ?? {};
  const procSuggestions = filterProcedures(procedures, attrs);
  const scenarioSuggestions = filterScenarios(scenarios, attrs);

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center gap-5 p-6 text-center">
      <Sparkles className="text-primary" size={36} aria-hidden />
      <h2 className="text-2xl font-semibold">
        Bună{citizen?.prenume ? `, ${citizen.prenume}` : ""}. Cu ce te pot ajuta?
      </h2>
      <p className="text-sm text-muted-foreground">
        Spune-mi în cuvinte simple ce ai nevoie — eu mă ocup de hârtii.
      </p>

      <div className="flex flex-wrap justify-center gap-2 pt-2">
        {pendingReminders.length > 0 ? (
          <Button variant="secondary" size="sm" onClick={() => openDrawer()}>
            🔔 Ai {pendingReminders.length}{" "}
            {pendingReminders.length === 1 ? "amintire activă" : "amintiri active"}
          </Button>
        ) : null}
        {scenarioSuggestions.map((s) => (
          <Button
            key={s.id}
            variant="secondary"
            size="sm"
            onClick={() => void openScenarioPlan(s.id)}
          >
            📋 {s.title}
          </Button>
        ))}
        {procSuggestions.map((p) => (
          <Button
            key={p.id}
            variant="outline"
            size="sm"
            onClick={() => void startProcedure(p.id)}
          >
            💡 {p.title}
          </Button>
        ))}
      </div>

      {loading && procedures.length === 0 && scenarios.length === 0 ? (
        <Card className="mt-4">
          <CardContent className="p-4 text-sm text-muted-foreground">
            Se încarcă procedurile…
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components/right-pane/WelcomePane.tsx \
        frontend/lib/api.ts frontend/lib/types.ts \
        backend/app/scenarios.py
git commit -m "feat(rag): WelcomePane mixes scenario + procedure chips; GET /scenarios"
```

---

## Task 17: `GuidePane` external act enrichment

**Files:**
- Modify: `frontend/components/right-pane/GuidePane.tsx`
- Modify: `frontend/lib/types.ts`

- [ ] **Step 1: Update the procedure type to allow resolved acte_necesare**

In `frontend/lib/types.ts`, modify the existing `Procedure` type to optionally carry resolved acte_necesare fields:

```typescript
// Update existing ActeNecesareItem (or add this type)
export type ActeNecesareItem = {
  denumire: string;
  emitent?: string;
  emitent_id?: string;
  institutie_nume?: string;          // NEW — populated by backend
  note_ai_cannot_complete?: string;  // NEW — populated by backend
  format?: string;
  observatie?: string;
  obligatoriu: boolean;
  alternative: string[];
};
```

Ensure `Procedure.acte_necesare` is typed as `ActeNecesareItem[]` (it likely already is — just confirm both fields are optional so existing call sites that consume the un-resolved shape still compile).

- [ ] **Step 2: Render the resolved badge in `GuidePane`**

Open `frontend/components/right-pane/GuidePane.tsx`. Replace the existing acte_necesare list with:

```tsx
{procedure.acte_necesare && procedure.acte_necesare.length > 0 ? (
  <section>
    <h3 className="mb-2 text-sm font-medium">
      Acte pe care să le ai la îndemână
    </h3>
    <ul className="list-disc space-y-2 pl-5 text-sm">
      {procedure.acte_necesare.map((a, i) => (
        <li key={i}>
          {a.denumire}
          {a.obligatoriu === false ? (
            <span className="text-muted-foreground"> (opțional)</span>
          ) : null}
          {a.institutie_nume ? (
            <span className="ml-1 rounded bg-muted px-1 py-0.5 text-xs">
              ↗ {a.institutie_nume}
            </span>
          ) : null}
          {a.observatie ? (
            <span className="block text-xs text-muted-foreground">
              {a.observatie}
            </span>
          ) : null}
          {a.note_ai_cannot_complete ? (
            <span className="block text-xs italic text-muted-foreground">
              {a.note_ai_cannot_complete}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  </section>
) : (
  <p className="text-sm text-muted-foreground">
    Nu sunt acte fizice obligatorii pentru această procedură.
  </p>
)}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/right-pane/GuidePane.tsx frontend/lib/types.ts
git commit -m "feat(rag): GuidePane renders institution badge + ai-cannot-complete note"
```

---

## Task 18: Final acceptance + manual smoke test + commit

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

```bash
cd backend && .venv/Scripts/python.exe -m pytest -v
```

Expected: all tests pass, including the new `test_institutions.py`, `test_scenarios.py`, and the three new scenarios in `test_plan3_smoke.py`. If the existing test suite already had unrelated failures, document them but don't gate this task on them.

- [ ] **Step 2: Run the indexer one more time to ensure DB is current**

```bash
cd backend && .venv/Scripts/python.exe -m scripts.index_rag
```

- [ ] **Step 3: Manual smoke test — idle → scenario plan**

Run backend + frontend locally with env vars set. In the browser:

1. Log in as Maria.
2. On idle (`/`), confirm scenario chips are visible (e.g., `📋 Cumpărare apartament`).
3. Click `📋 Cumpărare apartament` → URL becomes `/p/sc-cumparare-apartament`, right pane shows PlanPane with 3 in-scope steps + 3 external steps.
4. Click `Începe acum` on Declarare clădire → URL becomes `/r/<doc-id>`, right pane becomes GuidePane.
5. Click browser back → URL returns to `/p/sc-cumparare-apartament`, right pane restores PlanPane.

- [ ] **Step 4: Manual smoke test — natural language → scenario plan**

1. Open `/` (reset state if needed).
2. Type `am cumpărat un apartament` in the composer; submit.
3. Agent should reply in 1-2 sentences referring to the plan (not enumerate the procedures in chat).
4. Right pane should show PlanPane for `sc-cumparare-apartament`.

- [ ] **Step 5: Manual smoke test — atomic query stays atomic**

1. Open `/`.
2. Type `vreau să-mi schimb domiciliul`; submit.
3. Agent goes through the existing single-procedure flow — GuidePane (not PlanPane).

- [ ] **Step 6: Manual smoke test — external act badge**

1. Start a procedure that has acte_necesare with `emitent_id` (e.g., `schimbare-domiciliu` references `ocpi-ancpi`).
2. In GuidePane, confirm the "↗ Oficiul de Cadastru …" badge appears next to "Extras carte funciară".

- [ ] **Step 7: Push branch + open PR**

```bash
git push -u origin feat/multi-procedure-rag
gh pr create --title "Multi-procedure RAG: scenarios + institutions catalog" --body "$(cat <<'EOF'
## Summary
- Unified rag_entries table holds one embedding per procedure or scenario; no chunking.
- 5 hand-authored scenario JSONs in backend/scenarios/ drawn from primarii-app-data/scenarii/.
- 7 external-institutions JSONs in backend/institutions/ — fills the dangling emitent_id references.
- lookup_procedure tool extended with scenario_plan field; top-1 dispatch (scenario wins only when it's the top hit).
- GET /procedures/{id} now resolves emitent_id to institution name + AI-cannot-complete note.
- New PlanPane right-pane state; /p/[id] route; openScenarioPlan store action; WelcomePane mixes 2 scenarios + 2 procedures.

Closes spec docs/superpowers/specs/2026-05-23-multi-procedure-rag-design.md.

## Test plan
- [ ] backend pytest passes
- [ ] indexer populates 26 rag_entries (21 + 5)
- [ ] manual: idle → scenario chip → plan → start step → guide → back → plan
- [ ] manual: natural language "am cumpărat un apartament" → plan
- [ ] manual: atomic "vreau să-mi schimb domiciliul" → guide, not plan
- [ ] manual: GuidePane shows institution badge for external acte

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Task summary

| # | Task | Tests added | Verification |
|---|---|---|---|
| 1 | Institution JSONs | none | integrity test (Task 4) |
| 2 | Scenario JSONs | none | integrity test (Task 5) |
| 3 | Pydantic models | — | imports + tests downstream |
| 4 | Institutions registry | 3 tests | pytest |
| 5 | Scenarios registry + endpoint | 8 tests | pytest |
| 6 | Migration 007 | — | SQL `\d rag_entries` |
| 7 | embeddings.py for rag_entries | — | indexer succeeds |
| 8 | Indexer script | — | row count check |
| 9 | lookup_procedure scenario_plan | 3 tests | pytest |
| 10 | GET /procedures/{id} resolution | — | reuses test 5 endpoint |
| 11 | Prompt directives | — | manual demo |
| 12 | Frontend types + api method | — | typecheck |
| 13 | Session store + plan state | — | manual demo |
| 14 | /p/[id] route | — | manual demo |
| 15 | PlanPane component | — | manual demo |
| 16 | WelcomePane scenario chips | — | manual demo |
| 17 | GuidePane external badge | — | manual demo |
| 18 | Acceptance + PR | — | all 6 smoke tests pass |

Total: 14 backend unit tests + 6 manual smoke tests.
