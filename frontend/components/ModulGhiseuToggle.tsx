"use client";

import { useEffect, useState } from "react";
import { getGhiseuPref, setGhiseuPref } from "@/lib/ghiseuPref";

export function ModulGhiseuToggle() {
  const [checked, setChecked] = useState(false);

  // Initialize from localStorage after mount so SSR markup matches.
  useEffect(() => {
    setChecked(getGhiseuPref());
  }, []);

  function toggle() {
    const next = !checked;
    setChecked(next);
    setGhiseuPref(next);
  }

  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 rounded-xl border bg-card p-4">
      <span className="flex flex-col gap-1">
        <span className="text-base font-medium text-foreground">
          Modul Ghișeu
        </span>
        <span className="text-sm text-muted-foreground">
          Doar vorbește cu asistentul. Fără ecrane complicate.
        </span>
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label="Modul Ghișeu"
        onClick={(e) => {
          e.preventDefault();
          toggle();
        }}
        className={
          "relative h-7 w-12 flex-shrink-0 rounded-full transition-colors " +
          (checked ? "bg-primary" : "bg-muted")
        }
      >
        <span
          aria-hidden="true"
          className={
            "absolute top-0.5 left-0.5 h-6 w-6 rounded-full bg-white shadow transition-transform " +
            (checked ? "translate-x-5" : "translate-x-0")
          }
        />
      </button>
    </label>
  );
}
