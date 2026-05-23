---
type: component
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Pydantic Models

All HTTP contract shapes live in [[models]]. The FE's `frontend/lib/types.ts` is hand-aligned to this. Worth reading [[models]] first.

## Categories

- **Auth**: `LoginROeIDRequest`, `LoginMRZRequest`, `ChallengeResponse`, `OTPRequest`, `OTPResponse`
- **Citizen**: `CitizenAttributes`, `CitizenResponse`, `PatchAttributesRequest`
- **Procedure**: `Procedure`, `ProcedureField`, `NextStep`, `ActNecesar`, `ResolvedProcedure`, `ResolvedActeNecesareItem`
- **Document**: `CreateDocumentRequest`, `DocumentResponse`, `PatchFieldsRequest`, `GeneratePDFResponse`, `DeliverRequest`
- **Ledger**: `LedgerEntry`, `LedgerResponse`
- **Agent**: `AgentChatRequest`, `AgentChatResponse`, `ChatPreferences`, `ChatToolCall`, `WidgetResultRequest`, `WidgetResultResponse`, `WidgetResultEvent`
- **Reminders**: `ReminderResponse`
- **Scenario / Institutions**: `Institutie`, `Scenario`, `ScenarioPlan`, `ScenarioInScopeStep`, `ScenarioExternalStep`, `ResolvedInScopeStep`, `ResolvedExternalStep`

## Two conventions

1. **`ConfigDict(extra="allow")`** on `CitizenAttributes` — citizens can have arbitrary attribute keys; we don't want to reject unknowns.
2. **`Literal[...]`** for discriminated unions (`scope`, `kind`, `delivery`, `event_type`) — Pydantic validates AND the FE's TypeScript narrowing works.

## Pitfalls

- `WidgetResultRequest.value` is typed as `Any` because confirm widgets return bool, date pickers return string, choice widgets return string. The agent's `_coerce_widget_value` handles the bool case before dispatch.
- `Procedure.template` is a filename (`.tex`), not a Python module. [[pdf]] resolves it relative to `backend/templates/`.

## See also

- [[models]]
- frontend/lib/types.ts
