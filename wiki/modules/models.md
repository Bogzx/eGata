---
type: module
path: "backend/app/models.py"
status: active
language: python
purpose: "Pydantic v2 request/response shapes — the source of truth for the HTTP contract."
depends_on: []
used_by: [auth, citizens, procedures, scenarios, documents, ledger, agent, agent_voice, reminders]
created: 2026-05-23
updated: 2026-05-23
---

# models

Every Pydantic model the API uses lives here. Whenever a FastAPI route declares `response_model=`, it points at a class in this file. This is also the contract: the frontend's `lib/types.ts` is a hand-aligned mirror.

## What's inside

| Section | Models |
|---|---|
| Auth | `LoginROeIDRequest`, `LoginMRZRequest`, `ChallengeResponse`, `OTPRequest`, `OTPResponse` |
| Citizen | `CitizenAttributes`, `CitizenResponse`, `PatchAttributesRequest` |
| Procedure | `ProcedureField`, `NextStep`, `ActNecesar`, `Procedure`, `ProcedureLookupRequest`, `ProcedureMatch`, `ProcedureLookupResponse`, `ResolvedProcedure`, `ResolvedActeNecesareItem` |
| Document | `CreateDocumentRequest`, `DocumentResponse`, `PatchFieldsRequest`, `GeneratePDFResponse`, `DeliverRequest` |
| Ledger | `LedgerEntry`, `LedgerResponse` |
| Agent | `ChatToolCall`, `ChatPreferences`, `AgentChatRequest`, `AgentChatResponse`, `WidgetResultRequest`, `WidgetResultEvent`, `WidgetResultResponse` |
| Reminders | `ReminderResponse` |
| Scenario | `Institutie`, `Scenario`, `ScenarioInScopeStep`, `ScenarioExternalStep`, `ResolvedInScopeStep`, `ResolvedExternalStep`, `ScenarioPlan` |

## Key contracts

### `Procedure` (procedure JSON ⇄ Python)

```python
class Procedure(BaseModel):
    id: str
    title: str
    description: str
    scope: Literal["primarie", "external"]
    category: str
    synonyms: list[str]
    sample_queries: list[str]
    acte_necesare: list[ActNecesar]
    fields: list[ProcedureField]
    template: str          # LaTeX filename
    next_steps: list[NextStep]
```

`ProcedureField.applies_if` is the first-class conditional ([[applies_if]]). When non-null, the field is only "required" if the expression is true against `{**citizen.attrs, **doc.fields}`.

### `AgentChatRequest` (the agent door)

```python
class AgentChatRequest(BaseModel):
    conversation_id: str | None = None
    document_id: UUID | None = None
    message: str
    preferences: ChatPreferences | None = None   # simple_language, voice_only
```

`document_id` is the **legacy injection** path: when the frontend POSTs `/documents` then chats with an active doc, [[agent]] folds it into the session and transitions to FILLING. New flows use `start_procedure` ([[start_procedure]]) instead.

### `WidgetResultResponse`

When the user clicks a widget, two paths:

- `target_field` set → `set_field` runs server-side, the snapshot reflects the field, `requires_chat_followup: false`.
- No `target_field` (typical confirm-match widget) → `requires_chat_followup: true` and the FE follows up via `/agent/chat/stream` to let the agent decide what to do.

See [[Flow Widget Round-Trip]] for the full diagram.

## See also

- [[Pydantic Models]] — extracted as a component view
- [[HTTP API Surface]]
- frontend/lib/types.ts — must stay aligned by hand (see README §"Regenerating the OpenAPI contract")
