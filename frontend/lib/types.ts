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
  delivery?: "save" | "send" | "print";
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
};

export type LedgerResponse = {
  entries: LedgerEntry[];
  verified: boolean;
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
