"use client";

import { LockIcon, StarIcon } from "lucide-react";
import { motion } from "motion/react";

import { WORLD_THEME } from "@/lib/avatars";
import { sfx } from "@/lib/sound";
import type { LevelInfo, WorldInfo } from "@/lib/types";
import { cn } from "@/lib/utils";

export function Stars({ n, size = 14, className }: { n: number; size?: number; className?: string }) {
  return (
    <span className={cn("inline-flex gap-0.5", className)}>
      {[0, 1, 2].map((i) => (
        <StarIcon
          key={i}
          style={{ width: size, height: size }}
          className={i < n ? "fill-amber-400 text-amber-500 drop-shadow-[0_1px_0_rgba(0,0,0,0.25)]" : "fill-muted text-muted-foreground/40"}
        />
      ))}
    </span>
  );
}

const ZIGZAG = [0, 64, 96, 64, 0, -64, -96, -64];

function nodeIcon(lv: LevelInfo) {
  if (!lv.playable) return <LockIcon className="size-6" />;
  if (lv.has_myth) return <span className="text-3xl">👻</span>;
  if (lv.state === "mastered" && lv.stars === 3) return <span className="text-3xl">👑</span>;
  if (lv.stars > 0) return <span className="text-2xl">⭐</span>;
  return <span className="ml-1 text-2xl">▶</span>;
}

function LevelNode({ lv, color, recommended, index, onSelect }: { lv: LevelInfo; color: string; recommended: boolean; index: number; onSelect: (lv: LevelInfo) => void }) {
  const theme = WORLD_THEME[color] ?? WORLD_THEME.violet;
  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.8 }}
      whileInView={{ opacity: 1, y: 0, scale: 1 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.06, type: "spring", stiffness: 220, damping: 16 }}
      className="relative flex flex-col items-center"
      style={{ x: ZIGZAG[index % ZIGZAG.length] }}
    >
      {recommended && (
        <motion.div
          className="absolute -top-9 z-10 rounded-xl bg-foreground px-2.5 py-1 text-[11px] font-black tracking-wider text-background shadow-lg"
          animate={{ y: [0, -5, 0] }}
          transition={{ repeat: Infinity, duration: 1.2 }}
        >
          START
          <span className="absolute -bottom-1 left-1/2 size-2.5 -translate-x-1/2 rotate-45 bg-foreground" />
        </motion.div>
      )}
      <motion.button
        whileHover={{ scale: lv.playable ? 1.08 : 1.02, y: -2 }}
        whileTap={{ scale: 0.92, y: 4 }}
        onClick={() => {
          sfx.click();
          onSelect(lv);
        }}
        className={cn(
          "relative grid size-[72px] place-items-center rounded-full border-b-[6px] text-white transition-colors",
          lv.playable ? cn("bg-gradient-to-b shadow-lg", theme.node, "border-black/25") : "border-black/15 bg-muted text-muted-foreground",
          lv.has_myth && lv.playable && "from-rose-400 to-rose-600 shadow-rose-800/40",
          recommended && "ring-4 ring-offset-2 ring-offset-background",
          recommended && theme.ring,
        )}
        aria-label={`${lv.name}${lv.playable ? "" : " (locked)"}`}
      >
        {lv.has_myth && lv.playable && (
          <motion.span
            className="absolute inset-0 rounded-full ring-4 ring-rose-400"
            animate={{ scale: [1, 1.25], opacity: [0.8, 0] }}
            transition={{ repeat: Infinity, duration: 1.4 }}
          />
        )}
        {lv.playable && (
          <svg viewBox="0 0 80 80" className="pointer-events-none absolute -inset-1.5 size-[84px] -rotate-90">
            <circle cx="40" cy="40" r="37" fill="none" stroke="currentColor" strokeOpacity="0.15" strokeWidth="4" className="text-foreground" />
            <circle
              cx="40" cy="40" r="37" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round"
              className="text-amber-400" pathLength={100} strokeDasharray={`${Math.round(lv.mastery * 100)} 100`}
            />
          </svg>
        )}
        {nodeIcon(lv)}
      </motion.button>
      <Stars n={lv.stars} className="mt-1.5" />
      <p className={cn("mt-0.5 w-32 text-center text-xs leading-tight font-semibold", !lv.playable && "text-muted-foreground")}>{lv.name}</p>
    </motion.div>
  );
}

export function WorldSection({ world, recommendedId, onSelect, index }: { world: WorldInfo; recommendedId: string | null; onSelect: (lv: LevelInfo) => void; index: number }) {
  const theme = WORLD_THEME[world.color] ?? WORLD_THEME.violet;
  const pct = world.max_stars ? world.stars / world.max_stars : 0;
  return (
    <section className="relative">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className={cn("relative overflow-hidden rounded-2xl bg-gradient-to-br p-4 text-white shadow-lg", theme.grad, !world.unlocked && "opacity-60 grayscale")}
      >
        <motion.span
          className="pointer-events-none absolute -top-4 right-4 text-7xl opacity-30 select-none"
          animate={{ rotate: [0, 8, -6, 0], y: [0, -4, 0] }}
          transition={{ repeat: Infinity, duration: 6 }}
        >
          {world.emoji}
        </motion.span>
        <p className="text-[11px] font-bold tracking-widest uppercase opacity-80">World {index + 1}</p>
        <h2 className="text-xl font-black tracking-tight drop-shadow-sm">
          {world.emoji} {world.name}
        </h2>
        <p className="text-sm opacity-90">{world.tagline}</p>
        <div className="mt-3 flex items-center gap-2">
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-black/20">
            <motion.div className="h-full rounded-full bg-amber-300" initial={{ width: 0 }} whileInView={{ width: `${pct * 100}%` }} viewport={{ once: true }} transition={{ duration: 1 }} />
          </div>
          <span className="flex items-center gap-1 text-sm font-bold tabular-nums">
            <StarIcon className="size-4 fill-amber-300 text-amber-300" /> {world.stars}/{world.max_stars}
          </span>
        </div>
      </motion.div>
      <div className="relative flex flex-col items-center gap-9 py-10">
        {/* the trail */}
        <div className="pointer-events-none absolute inset-y-6 left-1/2 w-0 -translate-x-1/2 border-l-4 border-dashed border-muted-foreground/15" />
        {world.levels.map((lv, i) => (
          <LevelNode key={lv.concept_id} lv={lv} color={world.color} index={i} recommended={lv.concept_id === recommendedId} onSelect={onSelect} />
        ))}
      </div>
    </section>
  );
}
