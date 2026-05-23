"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ReminderCard } from "./ReminderCard";
import {
  reminderListContainer,
  usePrefersReducedMotion,
  variantsWithReducedMotion,
} from "@/lib/motion";
import type { Reminder } from "@/lib/types";

type Props = {
  reminders: Reminder[];
  emptyMessage?: string;
};

function sortReminders(rs: Reminder[]): Reminder[] {
  return [...rs].sort((a, b) => {
    if (a.due_date && b.due_date) {
      return new Date(a.due_date).getTime() - new Date(b.due_date).getTime();
    }
    if (a.due_date) return -1;
    if (b.due_date) return 1;
    return 0;
  });
}

export function RemindersList({ reminders, emptyMessage }: Props) {
  const reduced = usePrefersReducedMotion();
  const containerVariants = variantsWithReducedMotion(reminderListContainer, reduced);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());

  const active = sortReminders(reminders.filter((r) => !dismissedIds.has(r.id)));

  if (active.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        {emptyMessage ?? "Nu ai acțiuni recomandate momentan."}
      </p>
    );
  }

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={containerVariants}
      className="space-y-3"
    >
      {active.map((r) => (
        <ReminderCard
          key={r.id}
          reminder={r}
          onDismissed={(id) =>
            setDismissedIds((prev) => {
              const next = new Set(prev);
              next.add(id);
              return next;
            })
          }
        />
      ))}
    </motion.div>
  );
}
