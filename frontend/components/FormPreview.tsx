"use client";

import { motion } from "framer-motion";
import type { Procedure } from "@/lib/types";

type Props = {
  procedure: Procedure;
  values: Record<string, unknown>;
  activeField?: string;
};

export function FormPreview({ procedure, values, activeField }: Props) {
  return (
    <article
      aria-labelledby="form-preview-title"
      className="rounded-lg border bg-white p-8 font-serif text-black shadow-sm"
    >
      <header className="mb-6 border-b border-black/20 pb-4 text-center">
        <h2
          id="form-preview-title"
          className="text-2xl font-bold uppercase tracking-wider"
        >
          {procedure.title}
        </h2>
        {procedure.description ? (
          <p className="mt-1 text-sm">{procedure.description}</p>
        ) : null}
      </header>

      <dl className="space-y-3">
        {procedure.fields.map((field) => {
          const v = values[field.name];
          const filled = v !== undefined && v !== null && String(v).length > 0;
          const isActive = activeField === field.name;
          return (
            <motion.div
              key={field.name}
              data-testid={`field-${field.name}`}
              data-active={isActive ? "true" : "false"}
              initial={false}
              animate={
                isActive
                  ? { backgroundColor: "rgb(254 240 138)" }
                  : { backgroundColor: "rgba(0,0,0,0)" }
              }
              transition={{ duration: 0.2 }}
              className="grid grid-cols-[12rem_1fr] items-baseline gap-3 rounded px-2 py-1"
            >
              <dt className="text-sm font-medium">
                {field.label}
                {field.required ? <span aria-hidden> *</span> : null}
              </dt>
              <dd className="border-b border-dotted border-black/40 text-base">
                {filled ? <span>{String(v)}</span> : <span>________________</span>}
              </dd>
            </motion.div>
          );
        })}
      </dl>

      <footer className="mt-8 grid grid-cols-2 gap-8 text-sm">
        <div>
          <p className="font-medium">Data:</p>
          <p>____________</p>
        </div>
        <div className="text-right">
          <p className="font-medium">Semnătură:</p>
          <p>____________</p>
        </div>
      </footer>
    </article>
  );
}
