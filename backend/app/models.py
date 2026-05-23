"""Shared Pydantic v2 request/response models."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginROeIDRequest(BaseModel):
    persona_id: str | None = None


class LoginMRZRequest(BaseModel):
    cnp: str = Field(min_length=13, max_length=13)
    nume: str = Field(min_length=1)
    prenume: str = Field(min_length=1)


class ChallengeResponse(BaseModel):
    challenge_id: str
    phone_hint: str


class OTPRequest(BaseModel):
    challenge_id: str
    code: str = Field(min_length=4, max_length=10)


class OTPResponse(BaseModel):
    access_token: str
    citizen_id: UUID


class CitizenAttributes(BaseModel):
    model_config = ConfigDict(extra="allow")
    owns_vehicle: bool | None = None
    marital_status: Literal["necăsătorit", "căsătorit", "divorțat", "văduv"] | None = None
    has_children: bool | None = None
    employer: str | None = None
    medic_familie: str | None = None
    preferred_language: Literal["ro", "en"] | None = None
    current_address: str | None = None
    accessibility: dict[str, Any] | None = None


class CitizenResponse(BaseModel):
    id: UUID
    cnp: str
    nume: str
    prenume: str
    data_nasterii: date
    email: str | None
    phone: str
    attributes: dict[str, Any]


class ProcedureField(BaseModel):
    name: str
    label: str
    source: str
    required: bool
    options: list[str] | None = None
    suggest_default: str | None = None
    redact_in_voice: bool | None = None


class NextStep(BaseModel):
    kind: Literal["in_scope_procedure", "external_redirect"]
    procedure_id: str | None = None
    redirect_target: str | None = None
    deadline_days: int | None = None
    title: str
    applies_if: str | None = None


class ActNecesar(BaseModel):
    """A required document for a procedure.

    emitent values used in JSON catalog:
      - "primarie"  → generated/issued by city hall (or filled in this app)
      - "user"      → citizen already has it (CI, old certificates, etc.)
      - "extern"    → third party not in institution catalog (e.g. payment receipt)
      - <omitted>   → use emitent_id to reference institutii-externe.json
    """
    denumire: str
    emitent: str | None = None
    emitent_id: str | None = None
    format: str | None = None
    observatie: str | None = None
    obligatoriu: bool = True
    alternative: list[str] = Field(default_factory=list)


class Procedure(BaseModel):
    id: str
    title: str
    description: str
    scope: Literal["primarie", "external"]
    category: str
    synonyms: list[str]
    sample_queries: list[str]
    acte_necesare: list[ActNecesar] = Field(default_factory=list)
    fields: list[ProcedureField]
    template: str
    next_steps: list[NextStep] = Field(default_factory=list)


class ProcedureLookupRequest(BaseModel):
    query: str = Field(min_length=1)


class ProcedureMatch(BaseModel):
    procedure_id: str
    title: str
    score: float


class ProcedureLookupResponse(BaseModel):
    matches: list[ProcedureMatch]
    redirect_candidate: str | None = None


class CreateDocumentRequest(BaseModel):
    procedure_id: str


class DocumentResponse(BaseModel):
    id: UUID
    citizen_id: UUID
    procedure_id: str
    status: Literal["draft", "finalized"]
    fields: dict[str, Any]
    pdf_url: str | None = None
    delivery: Literal["save", "send", "print"] | None = None
    ref_number: str | None = None
    created_at: datetime
    delivered_at: datetime | None = None


class PatchFieldsRequest(BaseModel):
    fields: dict[str, Any]


class GeneratePDFResponse(BaseModel):
    pdf_url: str


class DeliverRequest(BaseModel):
    delivery: Literal["save", "send", "print"]


class LedgerEntry(BaseModel):
    id: int
    event_type: Literal[
        "doc_created", "completed_draft", "pdf_generated",
        "delivered", "redirected", "reminder_created",
    ]
    payload_hash: str
    prev_hash: str
    row_hash: str
    created_at: datetime


class LedgerResponse(BaseModel):
    entries: list[LedgerEntry]
    verified: bool


class ChatToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]


class ChatPreferences(BaseModel):
    simple_language: bool = False
    voice_only: bool = False


class AgentChatRequest(BaseModel):
    conversation_id: str | None = None
    document_id: UUID | None = None
    message: str
    preferences: ChatPreferences | None = None


class AgentChatResponse(BaseModel):
    conversation_id: str
    message: str
    tool_calls: list[ChatToolCall] = Field(default_factory=list)


class ReminderResponse(BaseModel):
    id: UUID
    citizen_id: UUID
    trigger_doc_id: UUID | None = None
    kind: Literal["in_scope_procedure", "external_redirect"]
    procedure_id: str | None = None
    redirect_target: str | None = None
    title: str
    due_date: date | None = None
    status: Literal["pending", "started", "done", "dismissed"]
    created_at: datetime


class PatchAttributesRequest(BaseModel):
    attributes: dict[str, Any]


# ---- Multi-procedure RAG: institutions, scenarios, resolved shapes ----


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
