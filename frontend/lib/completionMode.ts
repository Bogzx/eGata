export type CompletionMode = "manual" | "guided" | "voice";

export type CompletionModeState = {
  mode: CompletionMode | null;
};

export type CompletionModeAction =
  | { type: "CHOOSE"; mode: CompletionMode }
  | { type: "SWITCH"; mode: CompletionMode }
  | { type: "RESET" }
  | { type: "noop" };

export function reduceCompletionMode(
  state: CompletionModeState,
  action: CompletionModeAction,
): CompletionModeState {
  switch (action.type) {
    case "CHOOSE":
    case "SWITCH":
      return { mode: action.mode };
    case "RESET":
      return { mode: null };
    case "noop":
    default:
      return state;
  }
}

const KEY = (docId: string) => `civicai.mode.${docId}`;

export function loadPersistedMode(docId: string): CompletionMode | null {
  if (typeof window === "undefined") return null;
  const v = window.localStorage.getItem(KEY(docId));
  return v === "manual" || v === "guided" || v === "voice" ? v : null;
}

export function persistMode(docId: string, mode: CompletionMode | null): void {
  if (typeof window === "undefined") return;
  if (mode === null) window.localStorage.removeItem(KEY(docId));
  else window.localStorage.setItem(KEY(docId), mode);
}
