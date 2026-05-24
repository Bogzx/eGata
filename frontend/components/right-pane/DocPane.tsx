"use client";

import type { ReactNode } from "react";

type Props = {
  /** Small label above title. Pass empty string to hide. */
  eyebrow?: string;
  title: string;
  /** When true, the title renders at a larger size (used for the
   * procedure-match pane where the title IS the focal point). */
  titleEmphasis?: boolean;
  refNumber?: string;
  /** Main paper / form body. */
  children: ReactNode;
  /** Optional action buttons rendered in the footer. */
  actions?: ReactNode;
};

/**
 * Right-column document preview shell. Wraps any pane's content with the
 * eGata eyebrow + title + ref + scrollable body + footer actions.
 */
export function DocPane({
  eyebrow,
  title,
  titleEmphasis,
  refNumber,
  children,
  actions,
}: Props) {
  return (
    <div className="docpane">
      <div className="docpane-head">
        <div>
          {eyebrow ? <div className="docpane-eyebrow">{eyebrow}</div> : null}
          <h3
            className="docpane-title"
            style={titleEmphasis ? { fontSize: "1.75rem", lineHeight: 1.2 } : undefined}
          >
            {title}
          </h3>
        </div>
        {refNumber ? <div className="docpane-ref">{refNumber}</div> : null}
      </div>

      <div className="docpane-doc">{children}</div>

      {actions ? <div className="docpane-actions">{actions}</div> : null}
    </div>
  );
}
