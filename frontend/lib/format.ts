/**
 * Format an arbitrary field value into a human-readable Romanian string for
 * display in the kiosk review screen and other surfaces.
 *
 * - null / undefined / empty string → "—" (em dash placeholder)
 * - boolean → "Da" / "Nu"
 * - ISO date string (YYYY-MM-DD) → "DD.MM.YYYY"
 * - everything else → String(value)
 */
export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") {
    if (value === "") return "—";
    const isoMatch = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
    if (isoMatch) return `${isoMatch[3]}.${isoMatch[2]}.${isoMatch[1]}`;
    return value;
  }
  if (typeof value === "boolean") return value ? "Da" : "Nu";
  return String(value);
}
