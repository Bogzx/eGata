export type Citizen = {
  id: string;
  cnp: string;
  nume: string;
  prenume: string;
  data_nasterii: string;
  email: string;
  phone: string;
  attributes: CitizenAttributes;
};

export type CitizenAttributes = {
  owns_vehicle?: boolean;
  marital_status?: "necăsătorit" | "căsătorit" | "divorțat" | "văduv";
  has_children?: boolean;
  employer?: string;
  medic_familie?: string;
  preferred_language?: "ro" | "en";
  current_address?: string;
  accessibility?: {
    voice_only?: boolean;
    simple_language?: boolean;
    large_text?: boolean;
  };
};

export type ActNecesar = {
  denumire: string;
  emitent?: string;
  emitent_id?: string;
  institutie_nume?: string;
  note_ai_cannot_complete?: string;
  format?: string;
  observatie?: string;
  obligatoriu?: boolean;
  alternative?: string[];
};

export type Procedure = {
  id: string;
  title: string;
  description: string;
  scope: "primarie" | "external";
  category: string;
  synonyms: string[];
  sample_queries: string[];
  acte_necesare?: ActNecesar[];
  fields: ProcedureField[];
  template: string;
  next_steps: NextStep[];
};

export type ProcedureField = {
  name: string;
  label: string;
  source: string;
  required: boolean;
  options?: string[];
  suggest_default?: string;
  redact_in_voice?: boolean;
};

export type NextStep = {
  kind: "in_scope_procedure" | "external_redirect";
  procedure_id?: string;
  redirect_target?: string;
  deadline_days?: number;
  title: string;
  applies_if?: string;
};

export type Document = {
  id: string;
  citizen_id: string;
  procedure_id: string;
  status: "draft" | "finalized";
  fields: Record<string, unknown>;
  pdf_url?: string;
  delivery?: "save" | "send" | "print" | "download";
  ref_number?: string;
  created_at: string;
  delivered_at?: string;
};

export type LedgerEntry = {
  id: number;
  event_type:
    | "doc_created"
    | "completed_draft"
    | "pdf_generated"
    | "delivered"
    | "redirected"
    | "reminder_created";
  payload_hash: string;
  prev_hash: string;
  row_hash: string;
  created_at: string;
  /** The hashed payload and the exact timestamp string in row_hash — enough
   * to recompute the chain client-side (backend/scripts/verify_ledger.py). */
  payload?: Record<string, unknown>;
  hashed_at?: string | null;
  /** Ed25519 signature over this row's head statement (null: not yet signed). */
  key_id?: string | null;
  signature?: string | null;
};

export type LedgerResponse = {
  entries: LedgerEntry[];
  verified: boolean;
  genesis_hash?: string;
  citizen_id?: string;
  document_id?: string;
  signing_keys?: { key_id: string; algorithm: string; public_key: string; status: string }[];
};

export type Reminder = {
  id: string;
  citizen_id: string;
  trigger_doc_id?: string;
  kind: "in_scope_procedure" | "external_redirect";
  procedure_id?: string;
  redirect_target?: string;
  title: string;
  due_date?: string;
  status: "pending" | "started" | "done" | "dismissed";
  created_at: string;
};

export type ChatToolCall = {
  name: string;
  arguments: Record<string, unknown>;
};

export type VoicePreferences = {
  simple_language?: boolean;
  voice_only?: boolean;
};

export type LoginChallenge = {
  challenge_id: string;
  phone_hint: string;
};

export type AuthSession = {
  access_token: string;
  citizen_id: string;
};

export type ProcedureLookupMatch = {
  procedure_id: string;
  title: string;
  score: number;
};

export type ProcedureLookupResponse = {
  matches: ProcedureLookupMatch[];
  redirect_candidate: string | null;
};

export type ChatMessage = {
  role: "user" | "agent";
  text: string;
  tool_calls?: ChatToolCall[];
};

export type ChatResponse = {
  conversation_id: string;
  message: string;
  tool_calls: ChatToolCall[];
};

// ---- Multi-procedure RAG types ----

export type ScenarioSummary = {
  id: string;
  title: string;
  description: string;
  complexitate?: string;
  applies_if?: string;
};

export type ResolvedActeNecesareItem = {
  denumire: string;
  emitent?: string;
  emitent_id?: string;
  institutie_nume?: string;
  note_ai_cannot_complete?: string;
  format?: string;
  observatie?: string;
  obligatoriu?: boolean;
  alternative?: string[];
  linked_procedure_id?: string;
};

export type ResolvedInScopeStep = {
  ordine: number;
  procedure_id: string;
  procedure_title: string;
  deadline_days?: number;
  note?: string;
  acte_necesare?: ResolvedActeNecesareItem[];
};

export type ResolvedExternalStep = {
  institutie_id: string;
  institutie_nume: string;
  scope?: string;
  url?: string;
  phone?: string;
  obligatoriu?: boolean;
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

export type LookupMatch = {
  procedure_id: string;
  title: string;
  score: number;
  description?: string;
  acte_necesare: ResolvedActeNecesareItem[];
};

// ---- Chat-first redesign types ----

export type WidgetSpec =
  | {
      type: "choice";
      question: string;
      options: string[];
      targetField: string;
      widgetId: string;
      // Set by the store when the user submits. Persisted in localStorage
      // so reloads don't re-arm the widget for a second submission.
      submittedValue?: string | null;
    }
  | {
      type: "confirm";
      question: string;
      onConfirmTool?: string;
      widgetId: string;
      submittedValue?: string | null;
    }
  | {
      type: "date";
      question: string;
      targetField: string;
      widgetId: string;
      submittedValue?: string | null;
    };

export type Message =
  | { id: string; role: "user"; text: string; via: "text" | "voice"; live?: boolean }
  | { id: string; role: "agent"; text: string; widgets?: WidgetSpec[]; live?: boolean }
  | { id: string; role: "system"; text: string };

// ---- Session snapshot pushed by the backend (state-machine rewrite) ----

export type SessionStateName =
  | "exploring"
  | "confirming_match"
  | "filling"
  | "reviewing"
  | "delivered"
  | "redirected";

export type PendingWidget = {
  widget_id: string;
  type: "choice" | "confirm" | "date";
  question: string;
  target_field?: string | null;
  options: string[];
};

export type SessionSnapshot = {
  id: string;
  citizen_id: string;
  state: SessionStateName;
  active_document_id: string | null;
  scenario_id: string | null;
  step_index: number | null;
  pending_widgets: PendingWidget[];
  /** Monotonic per-process counter from the backend. The store drops
   * any snapshot whose seq is lower than the last applied one. */
  seq?: number;
};

// Frontend events pushed by tools. The store reacts to these directly
// (e.g. document_opened → navigate to /r/<id>; widget_proposed → render
// inline widget; redirect → show redirect card).
export type FrontendEvent =
  | { type: "document_opened"; document_id: string; procedure_id: string }
  | {
      type: "widget_proposed";
      widget_id: string;
      widget_type: "choice" | "confirm" | "date";
      question: string;
      options: string[];
      target_field: string | null;
    }
  | { type: "field_updated"; document_id: string; name: string; value: unknown }
  | {
      type: "document_delivered";
      document_id: string;
      pdf_url: string;
      delivery: "save" | "send" | "print" | "download";
      ref_number: string;
    }
  | { type: "redirect"; target: string; name: string; url: string }
  | {
      type: "lookup_returned";
      matches: LookupMatch[];
      scenario_plan: ScenarioPlan | null;
    };

export type VoiceStatus =
  | "idle"
  | "connecting"
  | "listening"
  | "speaking"
  | "error";
