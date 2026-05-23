import { http, HttpResponse } from "msw";
import {
  andrei,
  deliveredDoc,
  draftDoc,
  elena,
  knownProcedures,
  ledgerFor,
  maria,
  pickAgentReply,
  schimbareDomiciliu,
  seededReminders,
} from "./fixtures";
import type { Citizen, Document, Reminder } from "@/lib/types";

const BASE =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL) ||
  "http://localhost:8000";

const citizensByToken = new Map<string, Citizen>([
  ["mock-token-maria", maria],
  ["mock-token-andrei", andrei],
  ["mock-token-elena", elena],
]);

const tokenByPersona: Record<string, string> = {
  "maria-ionescu": "mock-token-maria",
  "andrei-popa": "mock-token-andrei",
  "elena-dumitru": "mock-token-elena",
};

const tokenByCnp: Record<string, string> = {
  [maria.cnp]: "mock-token-maria",
  [andrei.cnp]: "mock-token-andrei",
  [elena.cnp]: "mock-token-elena",
};

const challengeTokenStore = new Map<string, string>();

const documents = new Map<string, Document>();
documents.set(draftDoc.id, { ...draftDoc });
documents.set(deliveredDoc.id, { ...deliveredDoc });

const reminders = new Map<string, Reminder>();
seededReminders.forEach((r) => reminders.set(r.id, { ...r }));

let docCounter = 100;

function authedCitizen(request: Request): Citizen | null {
  const auth = request.headers.get("Authorization");
  if (!auth) return null;
  const token = auth.replace(/^Bearer\s+/i, "");
  return citizensByToken.get(token) ?? null;
}

export const handlers = [
  http.post(`${BASE}/auth/login-roeid`, async ({ request }) => {
    const body = (await request.json()) as { persona_id?: string };
    const persona = body.persona_id ?? "maria-ionescu";
    const token = tokenByPersona[persona] ?? "mock-token-maria";
    const challengeId = `ch_roeid_${persona}`;
    challengeTokenStore.set(challengeId, token);
    return HttpResponse.json({ challenge_id: challengeId, phone_hint: "***5678" });
  }),

  http.post(`${BASE}/auth/login-mrz`, async ({ request }) => {
    const body = (await request.json()) as { cnp: string };
    const token = tokenByCnp[body.cnp] ?? "mock-token-maria";
    const challengeId = `ch_mrz_${body.cnp.slice(-4)}`;
    challengeTokenStore.set(challengeId, token);
    return HttpResponse.json({ challenge_id: challengeId, phone_hint: "***5678" });
  }),

  http.post(`${BASE}/auth/otp`, async ({ request }) => {
    const body = (await request.json()) as { challenge_id: string; code: string };
    if (body.code !== "123456") {
      return HttpResponse.json({ detail: "Cod OTP incorect" }, { status: 401 });
    }
    const token = challengeTokenStore.get(body.challenge_id) ?? "mock-token-maria";
    const citizen = citizensByToken.get(token) ?? maria;
    return HttpResponse.json({ access_token: token, citizen_id: citizen.id });
  }),

  http.get(`${BASE}/citizens/me`, ({ request }) => {
    const c = authedCitizen(request) ?? maria;
    return HttpResponse.json(c);
  }),

  http.patch(`${BASE}/citizens/me/attributes`, async ({ request }) => {
    const c = authedCitizen(request) ?? maria;
    const body = (await request.json()) as { attributes: Partial<Citizen["attributes"]> };
    const updated = { ...c, attributes: { ...c.attributes, ...body.attributes } };
    return HttpResponse.json(updated);
  }),

  http.post(`${BASE}/procedures/lookup`, async ({ request }) => {
    const body = (await request.json()) as { query: string };
    const q = body.query.toLowerCase();
    if (q.includes("anaf") || q.includes("taxa") || q.includes("impozit")) {
      return HttpResponse.json({ matches: [], redirect_candidate: "ANAF" });
    }
    if (q.includes("cnas") || q.includes("medic de familie") || q.includes("asigurare sănătate")) {
      return HttpResponse.json({ matches: [], redirect_candidate: "CNAS" });
    }
    if (q.includes("permis") || q.includes("înmatricul") || q.includes("talon")) {
      return HttpResponse.json({ matches: [], redirect_candidate: "DRPCIV" });
    }
    if (q.includes("buletin") || q.includes("carte de identitate") || q.includes("ci nouă")) {
      return HttpResponse.json({
        matches: [
          { procedure_id: "preschimbare-ci", title: "Preschimbare carte de identitate", score: 0.88 },
        ],
        redirect_candidate: null,
      });
    }
    if (q.includes("venit") || q.includes("adeverin")) {
      return HttpResponse.json({
        matches: [{ procedure_id: "adeverinta-venit", title: "Adeverință de venit", score: 0.9 }],
        redirect_candidate: null,
      });
    }
    if (q.includes("certificat fiscal") || q.includes("atestare fiscal") || q.includes("datorii")) {
      return HttpResponse.json({
        matches: [{ procedure_id: "certificat-fiscal", title: "Certificat fiscal", score: 0.86 }],
        redirect_candidate: null,
      });
    }
    if (q.includes("naster") || q.includes("certificat de nast")) {
      return HttpResponse.json({
        matches: [
          {
            procedure_id: "certificat-nastere-copie",
            title: "Copie certificat de naștere",
            score: 0.85,
          },
        ],
        redirect_candidate: null,
      });
    }
    if (q.includes("căsător") || q.includes("casator")) {
      return HttpResponse.json({
        matches: [
          {
            procedure_id: "inregistrare-casatorie",
            title: "Înregistrare căsătorie",
            score: 0.87,
          },
        ],
        redirect_candidate: null,
      });
    }
    if (q.includes("ajutor social") || q.includes("venit minim")) {
      return HttpResponse.json({
        matches: [{ procedure_id: "ajutor-social", title: "Ajutor social", score: 0.84 }],
        redirect_candidate: null,
      });
    }
    const matchesDomic =
      q.includes("domic") || q.includes("mutare") || q.includes("adres");
    if (matchesDomic) {
      return HttpResponse.json({
        matches: [
          { procedure_id: "schimbare-domiciliu", title: "Schimbare domiciliu", score: 0.92 },
          { procedure_id: "preschimbare-ci", title: "Preschimbare CI", score: 0.41 },
        ],
        redirect_candidate: null,
      });
    }
    return HttpResponse.json({ matches: [], redirect_candidate: null });
  }),

  http.get(`${BASE}/procedures`, () => HttpResponse.json(knownProcedures)),

  http.get(`${BASE}/procedures/:id`, ({ params }) => {
    const p = knownProcedures.find((x) => x.id === params.id);
    if (!p) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    return HttpResponse.json(p);
  }),

  http.post(`${BASE}/documents`, async ({ request }) => {
    const citizen = authedCitizen(request) ?? maria;
    const body = (await request.json()) as { procedure_id: string };
    docCounter += 1;
    const id = `33333333-3333-3333-3333-${String(docCounter).padStart(12, "0")}`;
    const doc: Document = {
      id,
      citizen_id: citizen.id,
      procedure_id: body.procedure_id,
      status: "draft",
      fields:
        body.procedure_id === schimbareDomiciliu.id
          ? {
              nume_complet: `${citizen.prenume} ${citizen.nume}`,
              cnp: citizen.cnp,
              adresa_curenta: citizen.attributes.current_address ?? "",
            }
          : {
              nume_complet: `${citizen.prenume} ${citizen.nume}`,
              cnp: citizen.cnp,
            },
      created_at: new Date().toISOString(),
    };
    documents.set(id, doc);
    return HttpResponse.json(doc, { status: 201 });
  }),

  http.get(`${BASE}/documents`, ({ request }) => {
    const citizen = authedCitizen(request) ?? maria;
    return HttpResponse.json(
      Array.from(documents.values()).filter((d) => d.citizen_id === citizen.id),
    );
  }),

  http.get(`${BASE}/documents/:id`, ({ params }) => {
    const d = documents.get(String(params.id));
    if (!d) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    return HttpResponse.json(d);
  }),

  http.patch(`${BASE}/documents/:id/fields`, async ({ params, request }) => {
    const d = documents.get(String(params.id));
    if (!d) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const body = (await request.json()) as { fields: Record<string, unknown> };
    const updated: Document = { ...d, fields: { ...d.fields, ...body.fields } };
    documents.set(updated.id, updated);
    return HttpResponse.json(updated);
  }),

  http.post(`${BASE}/documents/:id/generate-pdf`, ({ params }) => {
    const d = documents.get(String(params.id));
    if (!d) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const url = `https://example.com/doc-${d.id}.pdf`;
    documents.set(d.id, { ...d, pdf_url: url });
    return HttpResponse.json({ pdf_url: url });
  }),

  http.post(`${BASE}/documents/:id/deliver`, async ({ params, request }) => {
    const d = documents.get(String(params.id));
    if (!d) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const body = (await request.json()) as { delivery: "save" | "send" | "print" };
    const refSuffix = d.id.replace(/-/g, "").slice(0, 4).toUpperCase();
    const updated: Document = {
      ...d,
      status: "finalized",
      delivery: body.delivery,
      ref_number: `CV-${refSuffix}`,
      delivered_at: new Date().toISOString(),
    };
    documents.set(d.id, updated);
    return HttpResponse.json(updated);
  }),

  http.get(`${BASE}/documents/:id/ledger`, ({ params }) =>
    HttpResponse.json(ledgerFor(String(params.id))),
  ),

  http.post(`${BASE}/agent/chat`, async ({ request }) => {
    const body = (await request.json()) as {
      conversation_id?: string | null;
      message: string;
    };
    const reply = pickAgentReply(body.message);
    return HttpResponse.json({
      conversation_id: body.conversation_id ?? "conv_mock_1",
      message: reply.text,
      tool_calls: reply.tool_calls,
    });
  }),

  http.get(`${BASE}/reminders`, ({ request }) => {
    const citizen = authedCitizen(request) ?? maria;
    return HttpResponse.json(
      Array.from(reminders.values()).filter((r) => r.citizen_id === citizen.id),
    );
  }),

  http.patch(`${BASE}/reminders/:id`, async ({ params, request }) => {
    const r = reminders.get(String(params.id));
    if (!r) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const body = (await request.json()) as { status: Reminder["status"] };
    const updated = { ...r, status: body.status };
    reminders.set(updated.id, updated);
    return HttpResponse.json(updated);
  }),

  // ---- Plan 4: start a reminder (creates a draft document from it) ----
  http.post(`${BASE}/reminders/:id/start`, ({ params, request }) => {
    const citizen = authedCitizen(request) ?? maria;
    const r = reminders.get(String(params.id));
    if (!r) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    if (r.kind !== "in_scope_procedure" || !r.procedure_id) {
      return HttpResponse.json(
        { detail: "Reminder is not an in-scope procedure" },
        { status: 400 },
      );
    }
    docCounter += 1;
    const id = `44444444-4444-4444-4444-${String(docCounter).padStart(12, "0")}`;
    const doc: Document = {
      id,
      citizen_id: citizen.id,
      procedure_id: r.procedure_id,
      status: "draft",
      fields: {
        nume_complet: `${citizen.prenume} ${citizen.nume}`,
        cnp: citizen.cnp,
      },
      created_at: new Date().toISOString(),
    };
    documents.set(id, doc);
    reminders.set(r.id, { ...r, status: "started" });
    return HttpResponse.json({
      id: r.id,
      status: "started",
      document_id: id,
      procedure_id: r.procedure_id,
    });
  }),

  // ---- Plan 4: dismiss a reminder ----
  http.post(`${BASE}/reminders/:id/dismiss`, ({ params }) => {
    const r = reminders.get(String(params.id));
    if (!r) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const updated: Reminder = { ...r, status: "dismissed" };
    reminders.set(updated.id, updated);
    return HttpResponse.json(updated);
  }),

  // ---- Plan 4: demo reset (clears + reseeds for the citizen) ----
  http.post(`${BASE}/demo/reset`, async ({ request }) => {
    const citizen = authedCitizen(request) ?? maria;
    for (const [id, doc] of documents.entries()) {
      if (doc.citizen_id === citizen.id) documents.delete(id);
    }
    for (const [id, rem] of reminders.entries()) {
      if (rem.citizen_id === citizen.id) reminders.delete(id);
    }
    // Reseed the demo reminders that belong to this citizen
    seededReminders
      .filter((r) => r.citizen_id === citizen.id)
      .forEach((r) => reminders.set(r.id, { ...r }));
    return HttpResponse.json({ ok: true, citizen_id: citizen.id });
  }),

  // ---- Plan 3: voice session bootstrap (mock — no real Gemini WS) ----
  http.post(`${BASE}/voice/session`, async ({ request }) => {
    const citizen = authedCitizen(request) ?? maria;
    const body = (await request.json().catch(() => ({}))) as {
      document_id?: string;
      preferences?: { simple_language?: boolean; voice_only?: boolean };
    };
    let documentContext: Record<string, unknown> | null = null;
    if (body.document_id) {
      const doc = documents.get(body.document_id);
      if (doc) {
        const proc = knownProcedures.find((p) => p.id === doc.procedure_id);
        documentContext = {
          id: doc.id,
          procedure_id: doc.procedure_id,
          procedure_title: proc?.title ?? doc.procedure_id,
          fields: doc.fields,
        };
      }
    }
    return HttpResponse.json({
      session_id: `mock_session_${Date.now()}`,
      gemini_api_key: "mock-api-key",
      gemini_model: "gemini-mock-voice",
      gemini_voice: "Aoede",
      system_prompt: "MOCK system prompt (MSW)",
      tool_jwt: "mock.jwt.token",
      tool_base_url: `${BASE}/tools`,
      tool_names: [
        "lookup_procedure",
        "set_field",
        "generate_pdf",
        "deliver",
        "find_redirect",
        "set_reminder",
      ],
      citizen_context: {
        id: citizen.id,
        nume: citizen.nume,
        prenume: citizen.prenume,
        attributes: citizen.attributes,
      },
      document_context: documentContext,
      _mock_note:
        "MSW does not implement Gemini Live WS — UI shows connecting state only. Use a real backend (Mode A/B) to exercise voice.",
    });
  }),

  // ---- Plan 3: tool dispatch (mock — no JWT verification, just round-trip) ----
  http.post(`${BASE}/tools/:name`, async ({ params, request }) => {
    const name = String(params.name);
    const args = (await request.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    if (name === "lookup_procedure") {
      const q = String(args.query || "").toLowerCase();
      if (q.includes("domic") || q.includes("mutare")) {
        const proc = knownProcedures.find((p) => p.id === "schimbare-domiciliu");
        return HttpResponse.json({
          matches: [
            {
              procedure_id: "schimbare-domiciliu",
              title: "Schimbare domiciliu",
              score: 0.92,
              description: proc?.description,
              acte_necesare: proc?.acte_necesare ?? [],
            },
          ],
          redirect_candidate: null,
        });
      }
      return HttpResponse.json({ matches: [], redirect_candidate: null });
    }
    if (name === "find_redirect") {
      const q = String(args.query || "").toLowerCase();
      if (q.includes("impozit") || q.includes("anaf")) {
        return HttpResponse.json({
          target: "ANAF",
          name: "ANAF",
          url: "https://www.anaf.ro",
          phone: "031 403 9160",
          explanation: "Impozite, taxe, fiscalitate.",
        });
      }
      return HttpResponse.json({ target: null });
    }
    return HttpResponse.json({ ok: true, _mock_tool: name, _args: args });
  }),
];
