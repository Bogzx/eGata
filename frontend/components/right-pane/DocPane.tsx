"use client";

import type { ReactNode } from "react";

type Props = {
  eyebrow: string;
  title: string;
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
export function DocPane({ eyebrow, title, refNumber, children, actions }: Props) {
  return (
    <div className="docpane">
      <div className="docpane-head">
        <div>
          <div className="docpane-eyebrow">{eyebrow}</div>
          <h3 className="docpane-title">{title}</h3>
        </div>
        {refNumber ? <div className="docpane-ref">{refNumber}</div> : null}
      </div>

      <div className="docpane-doc">{children}</div>

      {actions ? <div className="docpane-actions">{actions}</div> : null}
    </div>
  );
}
