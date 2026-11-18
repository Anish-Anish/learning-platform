"use client";

import { LockIcon, StarIcon } from "lucide-react";
import { motion } from "motion/react";

import { AvatarBubble } from "@/components/game/player-hud";
import { QuestsCard } from "@/components/game/quests-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { AVATARS } from "@/lib/avatars";
import { useProfile } from "@/lib/queries/game";
import { sfx } from "@/lib/sound";
import { XP_PER_LEVEL, useSession } from "@/lib/store";
import { cn } from "@/lib/utils";

const BADGE_ICON: Record<string, string> = {
  myth_buster: "👻",
  root_finder: "🌱",
  well_calibrated: "🎯",
  teachers_pet: "🍎",
  streak_3: "🔥",
  streak_7: "☄️",
};

export default function TrophiesPage() {
  const studentId = useSession((s) => s.studentId);
  const avatar = useSession((s) => s.avatar);
  const setAvatar = useSession((s) => s.setAvatar);
  const profile = useProfile(studentId);
  const p = profile.data;
  if (!p) return <Skeleton className="h-[600px] w-full rounded-2xl" />;
  const into = p.student.xp_total % XP_PER_LEVEL;

  return (
    <div className="space-y-5">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-600 via-violet-600 to-fuchsia-600 p-6 text-white shadow-xl"
      >
        <div className="pointer-events-none absolute inset-0 opacity-20 rw-grid-bg" />
        <div className="relative flex flex-col items-center gap-5 sm:flex-row">
          <motion.div animate={{ y: [0, -6, 0] }} transition={{ repeat: Infinity, duration: 2.5 }}>
            <AvatarBubble avatarId={avatar} level={p.student.level} size={96} />
          </motion.div>
          <div className="flex-1 text-center sm:text-left">
            <p className="text-xs font-bold tracking-widest uppercase opacity-80">Trophy room</p>
            <h1 className="text-3xl font-black tracking-tight">Level {p.student.level} hero</h1>
            <div className="mt-2 max-w-sm space-y-1">
              <div className="flex justify-between text-xs opacity-90">
                <span>{p.student.xp_total} XP</span>
                <span>{XP_PER_LEVEL - into} XP to level {p.student.level + 1}</span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-black/25">
                <motion.div className="h-full rounded-full bg-amber-300" initial={{ width: 0 }} animate={{ width: `${(into / XP_PER_LEVEL) * 100}%` }} transition={{ duration: 1 }} />
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-center">
            {[
              ["⭐", `${p.stars_total}/${p.stars_max}`, "stars"],
              ["🔥", `${p.student.streak_days}d`, "streak"],
              ["⚔️", p.bosses_defeated, "bosses"],
              ["👻", p.misconceptions_cleared, "myths busted"],
            ].map(([e, v, l]) => (
              <div key={l as string} className="rounded-xl bg-black/20 px-3 py-2">
                <p className="text-lg font-black tabular-nums">
                  {e} {v}
                </p>
                <p className="text-[10px] uppercase opacity-80">{l}</p>
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>Choose your hero</CardTitle>
              <CardDescription>Earn stars in Adventure levels to unlock new heroes.</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-4 gap-3 sm:grid-cols-8">
              {AVATARS.map((a, i) => {
                const unlocked = p.stars_total >= a.stars;
                const active = avatar === a.id;
                return (
                  <Tooltip key={a.id}>
                    <TooltipTrigger asChild>
                      <motion.button
                        initial={{ opacity: 0, scale: 0.6 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: i * 0.04 }}
                        whileHover={unlocked ? { scale: 1.12, rotate: [0, -6, 6, 0] } : {}}
                        whileTap={unlocked ? { scale: 0.9 } : {}}
                        disabled={!unlocked}
                        onClick={() => {
                          sfx.powerup();
                          setAvatar(a.id);
                        }}
                        className={cn(
                          "relative grid aspect-square place-items-center rounded-2xl bg-gradient-to-br text-3xl shadow-md",
                          a.bg,
                          active && "ring-4 ring-primary ring-offset-2 ring-offset-background",
                          !unlocked && "grayscale opacity-40",
                        )}
                      >
                        {a.emoji}
                        {!unlocked && (
                          <span className="absolute inset-0 grid place-items-center rounded-2xl bg-black/40 text-white">
                            <LockIcon className="size-5" />
                          </span>
                        )}
                      </motion.button>
                    </TooltipTrigger>
                    <TooltipContent>{unlocked ? a.name : `${a.name}: unlocks at ${a.stars} ⭐`}</TooltipContent>
                  </Tooltip>
                );
              })}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Badges</CardTitle>
              <CardDescription>
                {p.badges.filter((b) => b.earned).length} of {p.badges.length} earned
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {p.badges.map((b, i) => (
                <motion.div
                  key={b.badge_id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  whileHover={b.earned ? { y: -4 } : {}}
                  className={cn(
                    "flex flex-col items-center gap-1 rounded-2xl border p-4 text-center",
                    b.earned ? "border-amber-400/60 bg-gradient-to-b from-amber-400/15 to-transparent" : "opacity-55",
                  )}
                >
                  <motion.span
                    className={cn("text-4xl", !b.earned && "grayscale")}
                    animate={b.earned ? { rotate: [0, -8, 8, 0] } : {}}
                    transition={{ repeat: Infinity, duration: 3, delay: i * 0.3 }}
                  >
                    {BADGE_ICON[b.badge_id] ?? "🏅"}
                  </motion.span>
                  <p className="text-sm font-bold">{b.name}</p>
                  <p className="text-xs text-muted-foreground">{b.description}</p>
                  {!b.earned && <LockIcon className="size-3.5 text-muted-foreground" />}
                </motion.div>
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-5">
          <QuestsCard quests={p.quests} />
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <StarIcon className="size-4 fill-amber-400 text-amber-500" /> Adventure stats
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {[
                ["Levels cleared", `${p.levels_completed}/${p.levels_total}`],
                ["3-star levels", p.three_star_levels],
                ["Runs played", p.runs_played],
                ["Best combo", `x${p.best_combo}`],
                ["Concepts mastered", p.concepts_mastered],
                ["Questions answered", p.attempts_total],
              ].map(([k, v]) => (
                <div key={k as string} className="flex justify-between border-b pb-1.5 last:border-0">
                  <span className="text-muted-foreground">{k}</span>
                  <b className="tabular-nums">{v}</b>
                </div>
              ))}
              <Progress value={(p.stars_total / Math.max(1, p.stars_max)) * 100} className="mt-2" />
              <p className="text-center text-xs text-muted-foreground">
                {p.stars_total} / {p.stars_max} stars collected
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
