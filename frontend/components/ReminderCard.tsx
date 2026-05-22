"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Reminder } from "@/lib/types";

type Props = {
  reminder: Reminder;
};

export function ReminderCard({ reminder }: Props) {
  const isExternal = reminder.kind === "external_redirect";
  const href =
    !isExternal && reminder.procedure_id ? `/req/${reminder.procedure_id}` : null;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <Card className="border-l-4 border-l-primary">
        <CardContent className="space-y-2 p-4">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2">
              <span aria-hidden className="text-xl">
                {isExternal ? "↪" : "⚠"}
              </span>
              <p className="font-medium">{reminder.title}</p>
            </div>
            {isExternal ? (
              <Badge variant="outline">{reminder.redirect_target}</Badge>
            ) : null}
          </div>
          {reminder.due_date ? (
            <p className="text-xs text-muted-foreground">
              Termen: {new Date(reminder.due_date).toLocaleDateString("ro-RO")}
            </p>
          ) : null}
          {href ? (
            <Link href={href}>
              <Button size="sm" variant="outline">
                Începe acum
              </Button>
            </Link>
          ) : (
            <Button size="sm" variant="outline" disabled>
              Vezi instrucțiuni
            </Button>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
