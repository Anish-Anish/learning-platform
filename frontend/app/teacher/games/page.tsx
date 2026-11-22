"use client";

import { GamepadIcon, PercentIcon, StarIcon, TrophyIcon, UsersIcon } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";

import { LevelDifficulty, RunFeed, timeAgo } from "@/components/teacher/game-results";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useClassGame } from "@/lib/queries/game";
import { pct } from "@/lib/states";

const MEDAL = ["🥇", "🥈", "🥉"];

export default function ArenaPage() {
  const game = useClassGame();
  const g = game.data;
  if (!g) return <Skeleton className="h-[600px] w-full" />;
  const maxStars = Math.max(1, ...g.students.map((s) => s.stars));
  const t = g.totals;
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Game results</h1>
        <p className="text-sm text-muted-foreground">How the class is doing in Adventure mode · live (refreshes every 5s)</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-5">
        {[
          { icon: GamepadIcon, label: "Level runs", value: t.runs ?? 0 },
          { icon: UsersIcon, label: "Players today", value: `${t.players_today ?? 0}/${t.players ?? 0}` },
          { icon: PercentIcon, label: "Clear rate", value: pct(t.completion_rate as number | null) },
          { icon: StarIcon, label: "Avg stars (cleared)", value: t.avg_stars ?? "–" },
          { icon: TrophyIcon, label: "3-star runs", value: t.three_star_runs ?? 0 },
        ].map((k, i) => (
          <motion.div key={k.label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
            <Card className="py-4">
              <CardContent className="flex items-center gap-3">
                <span className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary">
                  <k.icon className="size-4" />
                </span>
                <div>
                  <p className="text-xs text-muted-foreground">{k.label}</p>
                  <p className="text-xl font-semibold tabular-nums">{k.value}</p>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>Leaderboard</CardTitle>
            <CardDescription>Ranked by stars (best per level). Click a student to see their full profile.</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">#</TableHead>
                  <TableHead>Student</TableHead>
                  <TableHead>Stars</TableHead>
                  <TableHead className="text-right">Levels</TableHead>
                  <TableHead className="text-right">Won / lost</TableHead>
                  <TableHead className="text-right">Combo</TableHead>
                  <TableHead className="text-right">Bosses</TableHead>
                  <TableHead className="text-right">Quests today</TableHead>
                  <TableHead className="text-right">Last played</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {g.students.map((s, i) => (
                  <TableRow key={s.student_id} className="cursor-pointer">
                    <TableCell className="font-bold">{MEDAL[i] ?? i + 1}</TableCell>
                    <TableCell>
                      <Link href={`/teacher/students/${s.student_id}`} className="font-medium hover:underline">
                        {s.display_name}
                      </Link>
                      {!s.is_simulated && <Badge variant="outline" className="ml-1.5 text-[10px]">live</Badge>}
                    </TableCell>
                    <TableCell className="w-44">
                      <div className="flex items-center gap-2">
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                          <motion.div className="h-full rounded-full bg-amber-400" initial={{ width: 0 }} animate={{ width: `${(s.stars / maxStars) * 100}%` }} transition={{ duration: 0.8, delay: i * 0.02 }} />
                        </div>
                        <span className="w-8 text-right text-sm font-semibold tabular-nums">{s.stars}⭐</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{s.levels_completed}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      <span className="text-emerald-600 dark:text-emerald-400">{s.wins}</span> / <span className="text-rose-600 dark:text-rose-400">{s.fails}</span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">x{s.best_combo}</TableCell>
                    <TableCell className="text-right tabular-nums">{s.bosses_defeated}</TableCell>
                    <TableCell className="text-right tabular-nums">{s.quests_done_today}/4</TableCell>
                    <TableCell className="text-right text-xs text-muted-foreground">{timeAgo(s.last_played)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>Where students get stuck</CardTitle>
              <CardDescription>Levels by clear rate (hardest first), with the trap students fall into most.</CardDescription>
            </CardHeader>
            <CardContent>
              <LevelDifficulty levels={g.levels} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Live feed</CardTitle>
              <CardDescription>Latest level runs across the class.</CardDescription>
            </CardHeader>
            <CardContent>
              <RunFeed runs={g.recent_runs} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
