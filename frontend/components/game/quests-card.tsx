"use client";

import { CheckIcon } from "lucide-react";
import { motion } from "motion/react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Quest } from "@/lib/types";
import { cn } from "@/lib/utils";

export function QuestsCard({ quests }: { quests: Quest[] }) {
  const done = quests.filter((q) => q.done).length;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between text-base">
          <span>📜 Daily quests</span>
          <span className="text-xs font-semibold text-muted-foreground tabular-nums">
            {done}/{quests.length}
          </span>
        </CardTitle>
        <CardDescription>Resets every day. Bragging rights only: XP is for mastery.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2.5">
        {quests.map((q, i) => (
          <motion.div
            key={q.id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.06 }}
            className={cn("flex items-center gap-3 rounded-xl border p-2.5", q.done && "border-emerald-500/50 bg-emerald-500/5")}
          >
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-muted text-lg">{q.emoji}</span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-sm font-semibold">{q.title}</p>
                <span className="text-[11px] text-muted-foreground tabular-nums">
                  {q.progress}/{q.target}
                </span>
              </div>
              <p className="truncate text-xs text-muted-foreground">{q.description}</p>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                <motion.div
                  className={cn("h-full rounded-full", q.done ? "bg-emerald-500" : "bg-amber-400")}
                  initial={{ width: 0 }}
                  animate={{ width: `${(q.progress / q.target) * 100}%` }}
                  transition={{ duration: 0.8, delay: i * 0.06 }}
                />
              </div>
            </div>
            {q.done && (
              <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} className="grid size-6 place-items-center rounded-full bg-emerald-500 text-white">
                <CheckIcon className="size-4" />
              </motion.span>
            )}
          </motion.div>
        ))}
      </CardContent>
    </Card>
  );
}
