export const GHISEU_PREF_KEY = "egata.ghiseu";

export function getGhiseuPref(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(GHISEU_PREF_KEY) === "1";
  } catch {
    return false;
  }
}

export function setGhiseuPref(value: boolean): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(GHISEU_PREF_KEY, value ? "1" : "0");
  } catch {
    // private browsing / quota — swallow
  }
}
