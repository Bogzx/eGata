import type { Citizen, Document, LedgerResponse, Procedure, Reminder } from "@/lib/types";

export const maria: Citizen = {
  id: "00000000-0000-0000-0000-000000000001",
  cnp: "2851014123456",
  nume: "Ionescu",
  prenume: "Maria",
  data_nasterii: "1985-03-14",
  email: "maria@example.com",
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

export const ion: Citizen = {
  id: "00000000-0000-0000-0000-000000000002",
  cnp: "1700212123456",
  nume: "Pop",
  prenume: "Ion",
  data_nasterii: "1970-02-12",
  email: "ion@example.com",
  phone: "+40722334455",
  attributes: {
    owns_vehicle: false,
    marital_status: "căsătorit",
    has_children: true,
    employer: "Pensionar",
    medic_familie: "Dr. Marin, Cluj",
    preferred_language: "ro",
    current_address: "Str. Memorandumului 12, Cluj-Napoca",
    accessibility: { voice_only: true, simple_language: true, large_text: true },
  },
};

export const elena: Citizen = {
  id: "00000000-0000-0000-0000-000000000003",
  cnp: "2950820123456",
  nume: "Mureșan",
  prenume: "Elena",
  data_nasterii: "1995-08-20",
  email: "elena@example.com",
  phone: "+40733998877",
  attributes: {
    owns_vehicle: true,
    marital_status: "căsătorit",
    has_children: true,
    employer: "SC Tech SRL",
    medic_familie: "Dr. Antoniu, Cluj",
    preferred_language: "ro",
    current_address: "Str. Horea 28, Cluj-Napoca",
    accessibility: { voice_only: false, simple_language: false, large_text: false },
  },
};

export const personas = [
  { id: "maria-ionescu", citizen: maria, label: "Maria Ionescu (35, mută adresa)" },
  { id: "ion-pop", citizen: ion, label: "Ion Pop (55, voice-only, simplu)" },
  { id: "elena-muresan", citizen: elena, label: "Elena Mureșan (30, familie)" },
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

export const knownProcedures: Procedure[] = [
  schimbareDomiciliu,
  {
    id: "adeverinta-venit",
    title: "Adeverință de venit",
    description: "Adeverință de venit pentru bancă",
    scope: "primarie",
    category: "evidenta-persoanelor",
    synonyms: ["adeverinta venit", "venit pentru banca"],
    sample_queries: ["am nevoie de adeverință de venit"],
    fields: [
      { name: "nume_complet", label: "Nume complet", source: "profile", required: true },
      { name: "cnp", label: "CNP", source: "profile", required: true, redact_in_voice: true },
      { name: "scopul", label: "Scopul adeverinței", source: "ask", required: true },
    ],
    template: "adeverinta-venit.tex",
    next_steps: [],
  },
  {
    id: "preschimbare-ci",
    title: "Preschimbare carte de identitate",
    description: "Preschimbarea cărții de identitate",
    scope: "primarie",
    category: "evidenta-persoanelor",
    synonyms: ["buletin nou", "schimb buletin"],
    sample_queries: ["vreau să-mi schimb buletinul"],
    fields: [
      { name: "nume_complet", label: "Nume complet", source: "profile", required: true },
      { name: "cnp", label: "CNP", source: "profile", required: true },
    ],
    template: "preschimbare-ci.tex",
    next_steps: [],
  },
  {
    id: "certificat-nastere",
    title: "Copie certificat de naștere",
    description: "Eliberare duplicat certificat de naștere",
    scope: "primarie",
    category: "stare-civila",
    synonyms: ["copie nastere", "duplicat nastere"],
    sample_queries: ["vreau o copie a certificatului de naștere"],
    fields: [
      { name: "nume_complet", label: "Nume complet", source: "profile", required: true },
      { name: "cnp", label: "CNP", source: "profile", required: true },
      { name: "scopul", label: "Scopul", source: "ask", required: false },
    ],
    template: "certificat-nastere.tex",
    next_steps: [],
  },
];

const now = new Date().toISOString();

export const draftDoc: Document = {
  id: "11111111-1111-1111-1111-111111111111",
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

export const deliveredDoc: Document = {
  id: "22222222-2222-2222-2222-222222222222",
  citizen_id: maria.id,
  procedure_id: "adeverinta-venit",
  status: "finalized",
  fields: { nume_complet: "Maria Ionescu", scopul: "credit bancar" },
  delivery: "send",
  ref_number: "CV-A4B7",
  pdf_url: "https://example.com/doc-2222.pdf",
  created_at: now,
  delivered_at: now,
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

export const seededReminders: Reminder[] = [
  {
    id: "r1",
    citizen_id: maria.id,
    kind: "in_scope_procedure",
    procedure_id: "preschimbare-ci",
    title: "Cartea de identitate expiră în 23 de zile",
    due_date: "2026-06-15",
    status: "pending",
    created_at: now,
  },
  {
    id: "r2",
    citizen_id: maria.id,
    kind: "external_redirect",
    redirect_target: "DRPCIV",
    title: "Actualizare certificat înmatriculare auto",
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
