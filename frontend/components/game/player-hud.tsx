"use client";

import { FlameIcon, StarIcon, Volume2Icon, VolumeXIcon } from "lucide-react";
import { animate, motion, useMotionValue, useTransform } from "motion/react";
import Link from "next/link";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { avatarById } from "@/lib/avatars";
import { useProfile } from "@/lib/queries/game";
import { XP_PER_LEVEL, useSession } from "@/lib/store";
import { cn } from "@/lib/utils";

function Counter({ value }: { value: number }) {
  const mv = useMotionValue(value);
  const shown = useTransform(mv, (v) => Math.round(v).toString());
  useEffect(() => {
    const c = animate(mv, value, { duration: 0.8, ease: "easeOut" });
    return () => c.stop();
  }, [value, mv]);
  return <motion.span className="tabular-nums">{shown}</motion.span>;
}

export function AvatarBubble({ avatarId, level, size = 36 }: { avatarId: string; level?: number; size?: number }) {
  const a = avatarById(avatarId);
  return (
    <span className="relative inline-grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <span className={cn("grid size-full place-items-center rounded-full bg-gradient-to-br shadow-sm ring-2 ring-background", a.bg)}>
        <span style={{ fontSize: size * 0.55 }}>{a.emoji}</span>
      </span>
      {level !== undefined && (
        <span className="absolute -right-1 -bottom-1 grid min-w-4 place-items-center rounded-full bg-primary px-1 text-[9px] leading-4 font-bold text-primary-foreground ring-2 ring-background">
          {level}
        </span>
      )}
    </span>
  );
}

/** Game-style heads-up display for the student header: hero, level, XP bar, stars, streak, sound. */
export function PlayerHud() {
  const studentId = useSession((s) => s.studentId);
  const avatar = useSession((s) => s.avatar);
  const xp = useSession((s) => s.xp);
  const level = useSession((s) => s.level);
  const setXp = useSession((s) => s.setXp);
  const muted = useSession((s) => s.muted);
  const toggleMuted = useSession((s) => s.toggleMuted);
  const profile = useProfile(studentId);

  // Keep the pill in sync with the server after navigation / reload.
  useEffect(() => {
    if (profile.data) setXp(profile.data.student.xp_total, profile.data.student.level);
  }, [profile.data, setXp]);

  const into = ((xp % XP_PER_LEVEL) + XP_PER_LEVEL) % XP_PER_LEVEL;
  const stars = profile.data?.stars_total ?? 0;
  const streak = profile.data?.student.streak_days ?? 0;

  return (
    <div className="flex items-center gap-1.5">
      <Tooltip>
        <TooltipTrigger asChild>
          <Link href="/trophies" className="flex items-center gap-2 rounded-full border bg-card py-0.5 pr-3 pl-0.5 shadow-xs transition hover:shadow-md">
            <AvatarBubble avatarId={avatar} level={level} size={30} />
            <div className="hidden w-20 flex-col gap-0.5 sm:flex">
              <div className="flex justify-between text-[10px] leading-none text-muted-foreground">
                <span>Lv {level}</span>
                <span>
                  <Counter value={xp} /> XP
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500"
                  animate={{ width: `${(into / XP_PER_LEVEL) * 100}%` }}
                  transition={{ duration: 0.8 }}
                />
              </div>
            </div>
          </Link>
        </TooltipTrigger>
        <TooltipContent>Your hero and trophies. XP comes only from mastery: mastering concepts, busting myths, beating bosses.</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="flex items-center gap-1 rounded-full border bg-card px-2 py-1 text-xs font-semibold shadow-xs">
            <StarIcon className="size-3.5 fill-amber-400 text-amber-500" />
            <Counter value={stars} />
          </span>
        </TooltipTrigger>
        <TooltipContent>Stars from Adventure levels (3 per level). They unlock new heroes.</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className={cn("hidden items-center gap-1 rounded-full border bg-card px-2 py-1 text-xs font-semibold shadow-xs sm:flex", streak > 0 && "text-orange-600 dark:text-orange-400")}>
            <FlameIcon className={cn("size-3.5", streak > 0 && "fill-orange-400 text-orange-500")} />
            {streak}
          </span>
        </TooltipTrigger>
        <TooltipContent>Daily streak</TooltipContent>
      </Tooltip>
      <Button variant="ghost" size="icon-sm" onClick={toggleMuted} aria-label={muted ? "Unmute sounds" : "Mute sounds"}>
        {muted ? <VolumeXIcon /> : <Volume2Icon />}
      </Button>
    </div>
  );
}
