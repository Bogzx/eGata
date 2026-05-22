import { createWorker } from "tesseract.js";
import { parse as parseMrz } from "mrz";

export type MrzResult = {
  cnp: string;
  nume: string;
  prenume: string;
  data_nasterii?: string;
  valid: boolean;
};

function titleCase(s: string): string {
  return s
    .toLowerCase()
    .split(/\s+/)
    .map((p) => (p.length > 0 ? p[0]!.toUpperCase() + p.slice(1) : p))
    .join(" ");
}

function isoFromMrzDate(yy_mm_dd: string | undefined): string | undefined {
  if (!yy_mm_dd || yy_mm_dd.length !== 6) return undefined;
  const yy = Number(yy_mm_dd.slice(0, 2));
  const mm = yy_mm_dd.slice(2, 4);
  const dd = yy_mm_dd.slice(4, 6);
  const century = yy <= new Date().getFullYear() % 100 ? 2000 : 1900;
  return `${century + yy}-${mm}-${dd}`;
}

export async function parseMrzFromImage(image: Blob): Promise<MrzResult> {
  const worker = await createWorker("ron+eng");
  try {
    const { data } = await worker.recognize(image);
    const lines = data.text
      .split(/\r?\n/)
      .map((l) => l.replace(/\s+/g, "").toUpperCase())
      .filter((l) => l.length >= 30 && /[<A-Z0-9]/.test(l));

    for (let size = 3; size >= 2; size -= 1) {
      for (let i = 0; i + size <= lines.length; i += 1) {
        const candidate = lines.slice(i, i + size);
        try {
          const parsed = parseMrz(candidate);
          if (parsed.valid && parsed.fields.personalNumber) {
            return {
              cnp: String(parsed.fields.personalNumber),
              nume: titleCase(String(parsed.fields.lastName ?? "")),
              prenume: titleCase(String(parsed.fields.firstName ?? "")),
              data_nasterii: isoFromMrzDate(
                parsed.fields.birthDate as string | undefined,
              ),
              valid: true,
            };
          }
        } catch {
          continue;
        }
      }
    }

    return { cnp: "", nume: "", prenume: "", valid: false };
  } finally {
    await worker.terminate();
  }
}
