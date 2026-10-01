import type { CitizenAttributes } from "./types";

type Variant = "standard" | "simple";

type Entry = { standard: string; simple?: string };

const strings = {
  "app.title": { standard: "eGata" },
  "app.tagline": {
    standard: "Spune-i ce ai nevoie. Îți spune ce acte îți trebuie.",
    simple: "Spune ce vrei. Te ajutăm cu actele.",
  },
  "login.title": { standard: "Conectare cu ROeID" },
  "login.subtitle": {
    standard: "Confirmă identitatea ca să continuăm.",
    simple: "Spune cine ești ca să mergem mai departe.",
  },
  "login.roeid_button": { standard: "Login cu ROeID" },
  "login.persona_label": { standard: "Persona demo (dev)" },
  "login.scan_id_button": { standard: "Scanează buletinul" },
  "login.manual_cnp_button": { standard: "Introdu CNP manual" },
  "otp.title": {
    standard: "Introdu codul primit prin SMS",
    simple: "Scrie codul primit pe telefon",
  },
  "otp.phone_hint": { standard: "Cod trimis la {{phone_hint}}" },
  "otp.submit": { standard: "Confirmă" },
  "otp.error": { standard: "Cod incorect. Mai încearcă o dată." },
  "home.greeting": {
    standard: "Bună ziua, {{prenume}}.",
    simple: "Salut, {{prenume}}!",
  },
  "home.recommended_title": {
    standard: "Următoarele acțiuni recomandate",
    simple: "Ce-ar fi bine să faci mai departe",
  },
  "home.documents_title": { standard: "Documente recente" },
  "home.start_new": { standard: "Începe o cerere nouă" },
  "home.empty_documents": {
    standard: "Nu ai documente încă. Apasă mai sus ca să începi.",
    simple: "Nu ai acte salvate încă. Apasă butonul de sus.",
  },
  "home.empty_reminders": {
    standard: "Nu ai pași următori sugerați momentan.",
    simple: "Nu mai ai nimic de făcut acum.",
  },
  "req.title": { standard: "Cerere: {{title}}" },
  "req.auto_filled_intro": {
    standard: "Am completat din profilul tău:",
    simple: "Am pus aici lucrurile pe care le știam deja despre tine:",
  },
  "req.more_needed": {
    standard: "Mai am nevoie de {{count}} lucruri. Cum vrei să le completăm?",
    simple: "Mai trebuie să-mi spui {{count}} lucruri. Cum vrei să-mi spui?",
  },
  "req.preview_title": { standard: "Previzualizare cerere" },
  "req.search_title": {
    standard: "Ce ai nevoie să rezolvi?",
    simple: "Ce vrei să facem?",
  },
  "req.search_placeholder": {
    standard: "Ex: vreau să-mi schimb adresa",
    simple: "Ex: vreau să schimb unde stau",
  },
  "req.search_button": { standard: "Caută" },
  "req.redirect_external": {
    standard: "Aceasta nu e o procedură a primăriei. Te trimitem la {{target}}.",
    simple: "Asta nu e la primărie. Du-te la {{target}}.",
  },
  "mode.manual": { standard: "Manual" },
  "mode.guided": { standard: "Pe ecran" },
  "mode.voice": { standard: "Vocal" },
  "mode.switch": { standard: "Schimbă modul" },
  "chat.input_placeholder": {
    standard: "Scrie aici ce ai nevoie...",
    simple: "Spune cu cuvintele tale...",
  },
  "chat.send": { standard: "Trimite" },
  "delivery.title": { standard: "Cum vrei să primești cererea?" },
  "delivery.save": { standard: "Salvează ca PDF" },
  "delivery.send": { standard: "Confirmare pe SMS" },
  "delivery.print": { standard: "Tipărește" },
  "delivery.confirmation": {
    standard: "Cererea ta e completată. Referință: {{ref}}",
    simple: "Gata! Numărul cererii tale este {{ref}}.",
  },
  "doc.audit_title": { standard: "Istoric integritate" },
  "doc.audit_verified": { standard: "Chain verificat" },
  "doc.audit_unverified": { standard: "Atenție: lanț de verificare deteriorat" },
  "doc.download_pdf": { standard: "Descarcă PDF" },
  "doc.ref_number": { standard: "Referință eGata: {{ref}}" },
  "doc.fields_title": { standard: "Date din cerere" },
  "kiosk.accessibility_corner": { standard: "Pentru persoane cu nevoi speciale" },
  "a11y.voice_only": { standard: "Mod vocal" },
  "a11y.simple_language": { standard: "Explică-mi mai simplu" },
  "a11y.large_text": { standard: "Text mai mare" },
  "mrz.title": { standard: "Scanează buletinul" },
  "mrz.instruction": {
    standard: "Poziționează partea de jos a buletinului în chenar.",
    simple: "Pune actul cu fața în jos, în chenar.",
  },
  "mrz.manual_fallback": { standard: "Introdu CNP manual" },
  "mrz.scanning": { standard: "Se citește..." },
  "mrz.failed": { standard: "Nu am reușit să citesc buletinul. Mai încearcă." },
  "common.continue": { standard: "Continuă" },
  "common.cancel": { standard: "Anulează" },
  "common.back": { standard: "Înapoi" },
  "common.loading": { standard: "Se încarcă..." },
  "common.error": { standard: "A apărut o eroare. Încearcă din nou." },
  "common.server_unreachable": {
    standard: "Serverul eGata nu răspunde. Încearcă mai târziu sau rulează aplicația local.",
  },
  "common.save": { standard: "Salvează" },
  "common.next": { standard: "Următor" },
} as const satisfies Record<string, Entry>;

export type StringKey = keyof typeof strings;

function interpolate(template: string, params: Record<string, string | number>): string {
  return template.replace(/\{\{(\w+)\}\}/g, (_, k: string) => {
    const v = params[k];
    return v === undefined ? `{{${k}}}` : String(v);
  });
}

export function t(
  key: StringKey,
  params: Record<string, string | number> = {},
  variant: Variant = "standard",
): string {
  const entry = strings[key] as Entry | undefined;
  if (!entry) {
    throw new Error(`i18n: missing key "${key}"`);
  }
  const tmpl = variant === "simple" && entry.simple ? entry.simple : entry.standard;
  return interpolate(tmpl, params);
}

export function getVariant(attrs: CitizenAttributes | undefined): Variant {
  return attrs?.accessibility?.simple_language ? "simple" : "standard";
}
