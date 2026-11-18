"use client";

import { motion } from "motion/react";

import { Stars } from "@/components/game/world-map";
import { Badge } from "@/components/ui/badge";
import type { ClassGame, GameRun } from "@/lib/types";
import { cn } from "@/lib/utils";

export function timeAgo(iso: string | null | undefined) {
  if (!iso) return "–";
  const s = Math.max(0, (Date.now() - new Date(iso + (iso.endsWith("Z") ? "" : "Z")).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

export function RunFeed({ runs, showStudent = true }: { runs: GameRun[]; showStudent?: boolean }) {
  return (
    <div className="space-y-1.5">
      {runs.map((r, i) => (
        <motion.div
          key={r.id}
          layout
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: Math.min(i, 10) * 0.03 }}
          className={cn(
            "flex items-center gap-3 rounded-xl border p-2.5 text-sm",
            r.status === "completed" ? "border-emerald-500/30 bg-emerald-500/5" : "border-rose-500/30 bg-rose-500/5",
          )}
        >
          <span className="text-lg">{r.status === "completed" ? (r.stars === 3 ? "🏆" : "✅") : "💔"}</span>
          <div className="min-w-0 flex-1">
            <p className="truncate">
              {showStudent && <b>{r.display_name}</b>} {showStudent ? (r.status === "completed" ? "cleared" : "failed") : r.status === "completed" ? "Cleared" : "Failed"}{" "}
              <span className="font-medium">{r.concept_name}</span>
            </p>
            <p className="text-xs text-muted-foreground">
              {r.correct}/{r.total} correct · combo x{r.best_combo} · ❤️ {r.hearts_left}
              {r.powerups_used > 0 && " · used 50/50"} · {timeAgo(r.finished_at)}
            </p>
          </div>
          {r.status === "completed" ? <Stars n={r.stars} /> : <Badge variant="destructive">game over</Badge>}
        </motion.div>
      ))}
      {runs.length === 0 && <p className="text-sm text-muted-foreground">No runs yet.</p>}
    </div>
  );
}

export function LevelDifficulty({ levels }: { levels: ClassGame["levels"] }) {
  const played = levels.filter((l) => l.plays > 0).sort((a, b) => (a.completion_rate ?? 1) - (b.completion_rate ?? 1));
  return (
    <div className="space-y-2.5">
      {played.map((l, i) => {
        const rate = l.completion_rate ?? 0;
        return (
          <motion.div key={l.concept_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.03 }} className="space-y-1">
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="truncate font-medium">{l.name}</span>
              <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                {l.plays} plays · {Math.round(rate * 100)}% cleared · {l.avg_stars?.toFixed(1) ?? "–"}⭐
              </span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-muted">
              <motion.div
                className={cn("h-full rounded-full", rate < 0.6 ? "bg-rose-500" : rate < 0.85 ? "bg-amber-500" : "bg-emerald-500")}
                initial={{ width: 0 }}
                animate={{ width: `${rate * 100}%` }}
                transition={{ duration: 0.8 }}
              />
            </div>
            {l.top_myth && <p className="text-xs text-muted-foreground">Most common trap: “{l.top_myth}”</p>}
          </motion.div>
        );
      })}
      {played.length === 0 && <p className="text-sm text-muted-foreground">No levels played yet.</p>}
    </div>
  );
}
