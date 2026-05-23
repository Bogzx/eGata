"use client";

export type MobileView = "chat" | "doc";

type Props = {
  value: MobileView;
  onChange: (next: MobileView) => void;
  /** When true, the inactive "Document" segment briefly pulses. */
  hinted?: boolean;
};

export function MobileViewToggle({ value, onChange, hinted = false }: Props) {
  return (
    <div
      className="mobile-toggle"
      role="group"
      aria-label="Comută între chat și document"
    >
      <button
        type="button"
        className={
          "mobile-toggle-seg " + (value === "chat" ? "is-active" : "")
        }
        aria-pressed={value === "chat"}
        onClick={() => {
          if (value !== "chat") onChange("chat");
        }}
      >
        Chat
      </button>
      <button
        type="button"
        className={
          "mobile-toggle-seg " +
          (value === "doc" ? "is-active" : "") +
          (hinted && value !== "doc" ? " is-hinted" : "")
        }
        aria-pressed={value === "doc"}
        onClick={() => {
          if (value !== "doc") onChange("doc");
        }}
      >
        Document
      </button>
    </div>
  );
}
