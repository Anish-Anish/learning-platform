"use client";

import { BookOpenIcon, PlayIcon, SkullIcon, StarIcon, TrophyIcon, ZapIcon } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Mascot } from "@/components/game/mascot";
import { QuestsCard } from "@/components/game/quests-card";
import { StudyScroll } from "@/components/game/study-scroll";
import { Stars, WorldSection } from "@/components/game/world-map";
import { StateBadge } from "@/components/state-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { WORLD_THEME } from "@/lib/avatars";
import { flags } from "@/lib/flags";
import { useProfile, useWorld } from "@/lib/queries/game";
import { sfx } from "@/lib/sound";
import { useSession } from "@/lib/store";
import type { LevelInfo } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function AdventurePage() {
  const router = useRouter();
  const studentId = useSession((s) => s.studentId);
  const world = useWorld(studentId);
  const profile = useProfile(studentId);
  const [selected, setSelected] = useState<LevelInfo | null>(null);
  const [scroll, setScroll] = useState<string | null>(null);
  const w = world.data;
  const names = Object.fromEntries((w?.worlds ?? []).flatMap((x) => x.levels).map((l) => [l.concept_id, l.name]));
  const selectedWorld = w?.worlds.find((x) => x.levels.some((l) => l.concept_id === selected?.concept_id));

  function select(lv: LevelInfo) {
    if (!lv.playable) {
      toast("🔒 Level locked", { description: lv.locked_reason ?? "Finish the earlier levels first." });
    }
    setSelected(lv);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 space-y-8">
        {/* Hero banner */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative overflow-hidden rounded-3xl border bg-gradient-to-br from-violet-600 via-fuchsia-600 to-amber-500 p-5 text-white shadow-xl"
        >
          <div className="pointer-events-none absolute inset-0 opacity-20 rw-grid-bg" />
          {["✨", "⭐", "💫", "✨"].map((e, i) => (
            <motion.span
              key={i}
              className="pointer-events-none absolute text-xl select-none"
              style={{ left: `${15 + i * 22}%`, top: `${10 + (i % 2) * 55}%` }}
              animate={{ y: [0, -10, 0], opacity: [0.4, 1, 0.4], rotate: [0, 20, 0] }}
              transition={{ repeat: Infinity, duration: 3 + i, delay: i * 0.4 }}
            >
              {e}
            </motion.span>
          ))}
          <div className="relative flex flex-col items-center gap-4 sm:flex-row">
            <Mascot mood="idle" size={92} />
            <div className="flex-1 text-center sm:text-left">
              <p className="text-xs font-bold tracking-widest uppercase opacity-80">Adventure mode</p>
              <h1 className="text-2xl font-black tracking-tight sm:text-3xl">Choose your next quest</h1>
              <p className="mt-1 text-sm opacity-90">{w?.recommended_reason ?? "Loading the map…"}</p>
              <div className="mt-3 flex flex-wrap justify-center gap-2 sm:justify-start">
                {w?.recommended_concept_id && (
                  <Button
                    size="lg"
                    className="bg-white font-bold text-violet-700 shadow-lg hover:bg-white/90"
                    onClick={() => {
                      sfx.click();
                      router.push(`/play/${w.recommended_concept_id}`);
                    }}
                  >
                    <PlayIcon className="fill-current" /> Play {names[w.recommended_concept_id]}
                  </Button>
                )}
                <Button size="lg" variant="outline" className="border-white/50 bg-white/10 text-white hover:bg-white/20 hover:text-white" asChild>
                  <Link href="/learn">
                    <ZapIcon /> Quick play
                  </Link>
                </Button>
              </div>
            </div>
            {w && (
              <div className="rounded-2xl bg-black/20 px-4 py-3 text-center backdrop-blur-sm">
                <p className="flex items-center justify-center gap-1 text-3xl font-black tabular-nums">
                  <StarIcon className="size-7 fill-amber-300 text-amber-300" /> {w.stars_total}
                </p>
                <p className="text-xs opacity-80">of {w.stars_max} stars</p>
              </div>
            )}
          </div>
        </motion.div>

        {world.isLoading || !w ? (
          <div className="space-y-4">
            <Skeleton className="h-28 w-full rounded-2xl" />
            <Skeleton className="h-96 w-full rounded-2xl" />
          </div>
        ) : (
          <div className="mx-auto max-w-xl space-y-4">
            {w.worlds.map((wd, i) => (
              <WorldSection key={wd.id} world={wd} index={i} recommendedId={w.recommended_concept_id} onSelect={select} />
            ))}
          </div>
        )}
      </div>

      <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
        {flags.boss && w && (
          <motion.div whileHover={{ scale: 1.02 }}>
            <Card
              className={cn(
                "overflow-hidden border-0 text-white shadow-lg",
                w.myths_active ? "bg-gradient-to-br from-rose-700 via-red-800 to-zinc-900" : "bg-gradient-to-br from-zinc-600 to-zinc-800",
              )}
            >
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <motion.span animate={w.myths_active ? { rotate: [0, -10, 10, 0] } : {}} transition={{ repeat: Infinity, duration: 2 }}>
                    <SkullIcon className="size-5" />
                  </motion.span>
                  Myth Boss lair
                </CardTitle>
                <CardDescription className="text-white/80">
                  {w.myths_active
                    ? `${w.myths_active} myth${w.myths_active > 1 ? "s" : ""} roam the land. Beat the boss built from your own mistakes to banish them.`
                    : "The lair is quiet. Myths appear when you answer something wrong while feeling sure."}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  disabled={!w.myths_active}
                  className="w-full bg-white font-bold text-rose-700 hover:bg-white/90"
                  onClick={() => router.push("/boss/new")}
                >
                  ⚔️ Enter the lair
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        )}
        {profile.data && <QuestsCard quests={profile.data.quests} />}
        {profile.data && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <TrophyIcon className="size-4 text-amber-500" /> Progress
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Levels cleared</span>
                <b className="tabular-nums">
                  {profile.data.levels_completed}/{profile.data.levels_total}
                </b>
              </div>
              <Progress value={(profile.data.levels_completed / Math.max(1, profile.data.levels_total)) * 100} />
              <div className="flex justify-between">
                <span className="text-muted-foreground">3-star levels</span>
                <b className="tabular-nums">{profile.data.three_star_levels}</b>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Best combo</span>
                <b className="tabular-nums">x{profile.data.best_combo}</b>
              </div>
              <Button variant="outline" size="sm" className="mt-1 w-full" asChild>
                <Link href="/trophies">🏆 Trophy room</Link>
              </Button>
            </CardContent>
          </Card>
        )}
      </aside>

      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent>
          {selected && (
            <>
              <DialogHeader>
                <div className={cn("mx-auto grid size-16 place-items-center rounded-2xl bg-gradient-to-br text-3xl text-white shadow-md", WORLD_THEME[selectedWorld?.color ?? "violet"]?.grad)}>
                  {selected.has_myth ? "👻" : selectedWorld?.emoji}
                </div>
                <DialogTitle className="text-center text-xl">{selected.name}</DialogTitle>
                <DialogDescription className="text-center">{selectedWorld?.name}</DialogDescription>
              </DialogHeader>
              <div className="space-y-3">
                <div className="flex items-center justify-center gap-3">
                  <Stars n={selected.stars} size={24} />
                  <StateBadge state={selected.state} />
                </div>
                {selected.has_myth && (
                  <p className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-2 text-center text-sm">
                    👻 A myth lurks here. Play the level to bust it!
                  </p>
                )}
                {selected.playable ? (
                  <>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>Mastery</span>
                        <span className="tabular-nums">{Math.round(selected.mastery * 100)}%</span>
                      </div>
                      <Progress value={selected.mastery * 100} />
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                      <div className="rounded-lg bg-muted p-2">❤️ 3 hearts</div>
                      <div className="rounded-lg bg-muted p-2">❓ {Math.min(4, selected.n_questions)} questions</div>
                      <div className="rounded-lg bg-muted p-2">🎮 {selected.plays} plays</div>
                    </div>
                    <p className="text-center text-xs text-muted-foreground">⭐ finish · ⭐⭐ at most 1 mistake · ⭐⭐⭐ flawless and every answer marked Sure</p>
                  </>
                ) : (
                  <p className="rounded-lg bg-muted p-3 text-center text-sm">🔒 {selected.locked_reason}</p>
                )}
              </div>
              <DialogFooter className="gap-2 sm:justify-center">
                <Button variant="outline" onClick={() => setScroll(selected.concept_id)}>
                  <BookOpenIcon /> Study scroll
                </Button>
                {selected.playable && (
                  <Button
                    className="font-bold"
                    onClick={() => {
                      sfx.click();
                      router.push(`/play/${selected.concept_id}`);
                    }}
                  >
                    <PlayIcon className="fill-current" /> {selected.stars ? "Play again" : "Play level"}
                  </Button>
                )}
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
      <StudyScroll conceptId={scroll} open={!!scroll} onOpenChange={(o) => !o && setScroll(null)} />
    </div>
  );
}
