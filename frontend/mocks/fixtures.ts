import type { Citizen, Document, LedgerResponse, Procedure, Reminder } from "@/lib/types";

// Personas and UUIDs match backend/migrations/002_seed_data.sql.
// Keep these in sync when adding personas on either side.
export const maria: Citizen = {
  id: "11111111-1111-1111-1111-111111111111",
  cnp: "2851014123456",
  nume: "Ionescu",
  prenume: "Maria",
  data_nasterii: "1985-03-14",
  email: "maria.ionescu@example.com",
  phone: "+40712345678",
  attributes: {
    owns_vehicle: true,
    marital_status: "necăsătorit",
    has_children: false,
    employer: "SC Acme SRL",
    medic_familie: "Dr. Popescu, Cluj",
    preferred_language: "ro",
    current_address: "Str. Avram Iancu 5, Cluj-Napoca",
    accessibility: { voice_only: false, simple_language: false, large_text: false },
  },
};

export const andrei: Citizen = {
  id: "22222222-2222-2222-2222-222222222222",
  cnp: "1900512123456",
  nume: "Popa",
  prenume: "Andrei",
  data_nasterii: "1990-05-12",
  email: "andrei.popa@example.com",
  phone: "+40722345678",
  attributes: {
    owns_vehicle: false,
    marital_status: "căsătorit",
    has_children: true,
    employer: "Bosch Cluj",
    medic_familie: "Dr. Vasilescu, Cluj",
    preferred_language: "ro",
    current_address: "Str. Memorandumului 12, Cluj-Napoca",
    accessibility: { voice_only: false, simple_language: true, large_text: false },
  },
};

export const elena: Citizen = {
  id: "33333333-3333-3333-3333-333333333333",
  cnp: "2620908123456",
  nume: "Dumitru",
  prenume: "Elena",
  data_nasterii: "1962-09-08",
  email: "elena.dumitru@example.com",
  phone: "+40732345678",
  attributes: {
    owns_vehicle: true,
    marital_status: "văduv",
    has_children: true,
    medic_familie: "Dr. Munteanu, Cluj",
    preferred_language: "ro",
    current_address: "Str. Horea 8, Cluj-Napoca",
    accessibility: { voice_only: true, simple_language: true, large_text: true },
  },
};

export const personas = [
  { id: "maria-ionescu", citizen: maria, label: "Maria Ionescu (40, schimbă domiciliul)" },
  { id: "andrei-popa", citizen: andrei, label: "Andrei Popa (36, simplu)" },
  { id: "elena-dumitru", citizen: elena, label: "Elena Dumitru (63, vocal+simplu+text mare)" },
] as const;

export const schimbareDomiciliu: Procedure = {
  id: "schimbare-domiciliu",
  title: "Schimbare domiciliu",
  description: "Înscrierea mențiunii de stabilire a domiciliului",
  scope: "primarie",
  category: "evidenta-persoanelor",
  synonyms: ["mutare", "schimbat adresa", "domiciliu nou"],
  sample_queries: [
    "vreau să-mi schimb domiciliul",
    "m-am mutat la altă adresă",
    "trebuie să schimb adresa pe buletin",
  ],
  fields: [
    { name: "nume_complet", label: "Nume complet", source: "id_scan|profile", required: true },
    {
      name: "cnp",
      label: "CNP",
      source: "id_scan|profile",
      required: true,
      redact_in_voice: true,
    },
    { name: "adresa_curenta", label: "Adresă curentă", source: "id_scan|profile", required: true },
    { name: "adresa_noua", label: "Adresă nouă", source: "ask", required: true },
    {
      name: "tip_proprietate",
      label: "Tip proprietate",
      source: "ask",
      options: ["proprietar", "chiriaș", "găzduit"],
      required: true,
    },
    {
      name: "motivul",
      label: "Motivul cererii",
      source: "ask",
      suggest_default: "Schimbare loc de muncă",
      required: false,
    },
  ],
  template: "schimbare-domiciliu.tex",
  next_steps: [
    {
      kind: "in_scope_procedure",
      procedure_id: "preschimbare-ci",
      deadline_days: 15,
      title: "Preschimbare carte de identitate",
    },
    {
      kind: "external_redirect",
      redirect_target: "DRPCIV",
      deadline_days: 30,
      title: "Actualizare certificat înmatriculare auto",
      applies_if: "owns_vehicle == true",
    },
    {
      kind: "external_redirect",
      redirect_target: "CNAS",
      title: "Actualizare medic de familie",
    },
    {
      kind: "external_redirect",
      redirect_target: "ANAF",
      title: "Notificare schimbare domiciliu fiscal",
    },
  ],
};

// Mirrors backend/procedures/*.json — IDs and required fields stay in sync.
export const knownProcedures: Procedure[] = [
  schimbareDomiciliu,
  {
    id: "preschimbare-ci",
    title: "Preschimbare carte de identitate",
    description: "Eliberare carte de identitate nouă.",
    scope: "primarie",
    category: "evidenta-persoanelor",
    synonyms: ["buletin nou", "schimb buletin", "ci nouă", "expiră buletinul"],
    sample_queries: ["vreau să-mi schimb buletinul"],
    fields: [
      { name: "nume_complet", label: "Nume complet", source: "profile", required: true },
      { name: "cnp", label: "CNP", source: "profile", required: true },
      { name: "motivul", label: "Motivul preschimbării", source: "ask", required: true },
    ],
    template: "preschimbare-ci.tex",
    next_steps: [],
  },
  {
    id: "certificat-fiscal",
    title: "Certificat fiscal",
    description: "Atestare lipsă datorii la bugetul local.",
    scope: "primarie",
    category: "taxe-locale",
    synonyms: ["certificat fiscal", "atestare fiscală", "lipsa datorii"],
    sample_queries: ["am nevoie de un certificat fiscal"],
    fields: [
      { name: "nume_complet", label: "Nume complet", source: "profile", required: true },
      { name: "cnp", label: "CNP", source: "profile", required: true },
      { name: "scopul", label: "Scopul", source: "ask", required: true },
    ],
    template: "certificat-fiscal.tex",
    next_steps: [],
  },
];

const now = new Date().toISOString();

// Document UUIDs match backend seed (002_seed_data.sql).
export const draftDoc: Document = {
  id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  citizen_id: maria.id,
  procedure_id: "schimbare-domiciliu",
  status: "draft",
  fields: {
    nume_complet: "Maria Ionescu",
    cnp: "2851014123456",
    adresa_curenta: "Str. Avram Iancu 5, Cluj-Napoca",
  },
  created_at: now,
};

export const ledgerFor = (docId: string): LedgerResponse => ({
  entries: [
    {
      id: 1,
      event_type: "doc_created",
      payload_hash: "0xpayloaddoc",
      prev_hash: "0x0000000000000000000000000000000000000000000000000000000000000000",
      row_hash: "0xrow1",
      created_at: now,
    },
    {
      id: 2,
      event_type: "completed_draft",
      payload_hash: "0xpayloadcompleted",
      prev_hash: "0xrow1",
      row_hash: "0xrow2",
      created_at: now,
    },
    {
      id: 3,
      event_type: "pdf_generated",
      payload_hash: "0xpayloadpdf",
      prev_hash: "0xrow2",
      row_hash: "0xrow3",
      created_at: now,
    },
    {
      id: 4,
      event_type: "delivered",
      payload_hash: "0xpayloaddelivered",
      prev_hash: "0xrow3",
      row_hash: "0xrow4",
      created_at: now,
    },
  ],
  verified: true,
});

// Reminder UUIDs match backend seed (002_seed_data.sql).
export const seededReminders: Reminder[] = [
  {
    id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
    citizen_id: maria.id,
    kind: "in_scope_procedure",
    procedure_id: "preschimbare-ci",
    title: "Cartea de identitate expiră în 23 de zile — programează preschimbarea",
    due_date: "2026-06-15",
    status: "pending",
    created_at: now,
  },
  {
    id: "dddddddd-dddd-dddd-dddd-dddddddddddd",
    citizen_id: maria.id,
    trigger_doc_id: draftDoc.id,
    kind: "external_redirect",
    redirect_target: "DRPCIV",
    title:
      "După schimbarea domiciliului trebuie să-ți actualizezi certificatul de înmatriculare la DRPCIV",
    due_date: "2026-06-22",
    status: "pending",
    created_at: now,
  },
];

export function pickAgentReply(
  message: string,
): { text: string; tool_calls: { name: string; arguments: Record<string, unknown> }[] } {
  const m = message.toLowerCase();
  if (m.includes("domic") || m.includes("mutare") || m.includes("adresa")) {
    return {
      text: "Înțeleg că vrei să-ți schimbi domiciliul. Continuăm?",
      tool_calls: [{ name: "lookup_procedure", arguments: { query: message } }],
    };
  }
  if (m.includes("anaf") || m.includes("taxa") || m.includes("impozit")) {
    return {
      text: "Asta nu e treaba primăriei — vă rog vizitați ghiseul.ro pentru ANAF.",
      tool_calls: [{ name: "find_redirect", arguments: { query: message } }],
    };
  }
  if (m.includes("adres") && m.includes("nou")) {
    return {
      text: "Am notat noua adresă. Care e tipul de proprietate: proprietar, chiriaș sau găzduit?",
      tool_calls: [{ name: "set_field", arguments: { field: "adresa_noua", value: message } }],
    };
  }
  return {
    text: "Spune-mi te rog mai multe despre ce ai nevoie de la primărie.",
    tool_calls: [],
  };
}
