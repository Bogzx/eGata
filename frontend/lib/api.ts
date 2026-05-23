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
  ScenarioSummary,
  VoicePreferences,
} from "./types";

const BASE_URL =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL) ||
  "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

type ReqOpts = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean;
};

async function request<T>(path: string, opts: ReqOpts = {}): Promise<T> {
  const { method = "GET", body, auth = true } = opts;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    const s = getSession();
    if (s) headers["Authorization"] = `Bearer ${s.access_token}`;
  }
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  const parsed = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new ApiError(res.status, parsed, `${method} ${path} → ${res.status}`);
  }
  return parsed as T;
}

export const api = {
  loginRoeid: (b: { persona_id?: string }) =>
    request<LoginChallenge>("/auth/login-roeid", { method: "POST", body: b, auth: false }),

  loginMrz: (b: { cnp: string; nume: string; prenume: string }) =>
    request<LoginChallenge>("/auth/login-mrz", { method: "POST", body: b, auth: false }),

  otp: (b: { challenge_id: string; code: string }) =>
    request<AuthSession>("/auth/otp", { method: "POST", body: b, auth: false }),

  getCitizenMe: () => request<Citizen>("/citizens/me"),

  patchCitizenAttributes: (attrs: Partial<Citizen["attributes"]>) =>
    request<Citizen>("/citizens/me/attributes", { method: "PATCH", body: { attributes: attrs } }),

  lookupProcedure: (b: { query: string }) =>
    request<ProcedureLookupResponse>("/procedures/lookup", { method: "POST", body: b }),

  listProcedures: () => request<Procedure[]>("/procedures"),

  getProcedure: (id: string) => request<Procedure>(`/procedures/${id}`),

  listScenarios: () => request<ScenarioSummary[]>("/scenarios"),

  getScenarioPlan: (id: string) => request<ScenarioPlan>(`/scenarios/${id}`),

  createDocument: (b: { procedure_id: string }) =>
    request<Document>("/documents", { method: "POST", body: b }),

  getDocument: (id: string) => request<Document>(`/documents/${id}`),

  listDocuments: () => request<Document[]>("/documents"),

  patchDocumentFields: (id: string, fields: Record<string, unknown>) =>
    request<Document>(`/documents/${id}/fields`, { method: "PATCH", body: { fields } }),

  generatePdf: (id: string) =>
    request<{ pdf_url: string }>(`/documents/${id}/generate-pdf`, { method: "POST" }),

  deliverDocument: (id: string, delivery: "save" | "send" | "print") =>
    request<Document>(`/documents/${id}/deliver`, { method: "POST", body: { delivery } }),

  getDocumentLedger: (id: string) =>
    request<LedgerResponse>(`/documents/${id}/ledger`),

  listReminders: () => request<Reminder[]>("/reminders"),

  patchReminderStatus: (id: string, status: Reminder["status"]) =>
    request<Reminder>(`/reminders/${id}`, { method: "PATCH", body: { status } }),

  startReminder: (id: string) =>
    request<{ id: string; status: string; document_id: string; procedure_id: string }>(
      `/reminders/${id}/start`,
      { method: "POST" },
    ),

  dismissReminder: (id: string) =>
    request<Reminder>(`/reminders/${id}/dismiss`, { method: "POST" }),

  resetDemo: (citizenId?: string) => {
    const token =
      (typeof process !== "undefined" && process.env.NEXT_PUBLIC_DEMO_TOKEN) || "";
    return fetch(`${BASE_URL}/demo/reset`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Demo-Token": token,
      },
      body: JSON.stringify({ citizen_id: citizenId ?? null }),
    }).then(async (res) => {
      const text = await res.text();
      const parsed = text ? JSON.parse(text) : null;
      if (!res.ok) {
        throw new ApiError(res.status, parsed, `POST /demo/reset → ${res.status}`);
      }
      return parsed as { ok: boolean; citizen_id: string };
    });
  },

  chat: (b: {
    conversation_id?: string | null;
    document_id?: string;
    message: string;
    preferences?: VoicePreferences;
  }) => request<ChatResponse>("/agent/chat", { method: "POST", body: b }),

  /** Resolve a pending widget without round-tripping through the model.
   *
   * Returns `requires_chat_followup=true` when the widget had no
   * target_field — the answer is a signal the agent must react to, so
   * the caller is expected to follow up with /agent/chat/stream. */
  submitWidget: (b: {
    conversation_id: string;
    widget_id: string;
    value: unknown;
  }) =>
    request<{
      conversation_id: string;
      snapshot: import("./types").SessionSnapshot;
      user_message: string;
      events: Array<{
        kind: "tool_result" | "frontend_event";
        name?: string | null;
        output?: Record<string, unknown> | null;
        error?: string | null;
        event?: Record<string, unknown> | null;
      }>;
      requires_chat_followup: boolean;
    }>("/agent/widget-result", { method: "POST", body: b }),
};
