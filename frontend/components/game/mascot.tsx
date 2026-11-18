"use client";

// "Byte", the guide. An animated SVG buddy that reacts to how the run is going.
import { AnimatePresence, motion, type TargetAndTransition } from "motion/react";

import { cn } from "@/lib/utils";

export type Mood = "idle" | "happy" | "sad" | "think" | "party" | "fever";

const BODY: Record<Mood, string> = {
  idle: "#8b5cf6",
  think: "#6366f1",
  happy: "#10b981",
  party: "#f59e0b",
  fever: "#f97316",
  sad: "#64748b",
};

const MOTION: Record<Mood, TargetAndTransition> = {
  idle: { y: [0, -6, 0], transition: { repeat: Infinity, duration: 2.4, ease: "easeInOut" } },
  think: { rotate: [0, -6, 0, 6, 0], transition: { repeat: Infinity, duration: 3 } },
  happy: { y: [0, -26, 0, -10, 0], scale: [1, 1.08, 0.96, 1.03, 1], transition: { duration: 0.7 } },
  party: { rotate: [0, 360], y: [0, -30, 0], transition: { duration: 0.9 } },
  fever: { y: [0, -10, 0], scale: [1, 1.06, 1], transition: { repeat: Infinity, duration: 0.6 } },
  sad: { x: [0, -8, 8, -5, 5, 0], y: [0, 6, 6], transition: { duration: 0.6 } },
};

export function Mascot({ mood = "idle", size = 96, say, className }: { mood?: Mood; size?: number; say?: string | null; className?: string }) {
  const happy = mood === "happy" || mood === "party" || mood === "fever";
  return (
    <div className={cn("relative inline-flex flex-col items-center", className)} style={{ width: size }}>
      <AnimatePresence>
        {say && (
          <motion.div
            key={say}
            initial={{ opacity: 0, y: 6, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0 }}
            className="absolute -top-2 left-1/2 z-10 w-max max-w-56 -translate-x-1/2 -translate-y-full rounded-2xl border bg-card px-3 py-1.5 text-center text-xs font-medium text-card-foreground shadow-md"
          >
            {say}
            <span className="absolute -bottom-1.5 left-1/2 size-3 -translate-x-1/2 rotate-45 border-r border-b bg-card" />
          </motion.div>
        )}
      </AnimatePresence>
      <motion.svg key={mood} viewBox="0 0 100 100" width={size} height={size} animate={MOTION[mood]} className="drop-shadow-md">
        {mood === "fever" && (
          <motion.path
            d="M30 30 Q35 5 45 22 Q50 0 57 20 Q66 4 70 30 Z"
            fill="#fb923c"
            animate={{ scaleY: [1, 1.25, 1], opacity: [0.9, 1, 0.9] }}
            transition={{ repeat: Infinity, duration: 0.35 }}
            style={{ transformOrigin: "50px 30px" }}
          />
        )}
        <motion.path
          d="M50 18 C78 18 88 38 88 58 C88 80 72 92 50 92 C28 92 12 80 12 58 C12 38 22 18 50 18 Z"
          animate={{ fill: BODY[mood] }}
          transition={{ duration: 0.3 }}
        />
        <ellipse cx="50" cy="92" rx="26" ry="3" fill="black" opacity="0.08" />
        <path d="M50 18 L46 6 M50 18 L56 7" stroke={BODY[mood]} strokeWidth="3" strokeLinecap="round" />
        <circle cx="46" cy="5" r="3" fill="#fde047" />
        {/* eyes */}
        {mood === "sad" ? (
          <>
            <path d="M32 52 Q38 48 44 52" stroke="white" strokeWidth="4" fill="none" strokeLinecap="round" />
            <path d="M56 52 Q62 48 68 52" stroke="white" strokeWidth="4" fill="none" strokeLinecap="round" />
            <motion.ellipse cx="66" cy="60" rx="2.5" ry="4" fill="#7dd3fc" animate={{ cy: [58, 72], opacity: [1, 0] }} transition={{ repeat: Infinity, duration: 1.2 }} />
          </>
        ) : happy ? (
          <>
            <path d="M32 54 Q38 44 44 54" stroke="white" strokeWidth="4.5" fill="none" strokeLinecap="round" />
            <path d="M56 54 Q62 44 68 54" stroke="white" strokeWidth="4.5" fill="none" strokeLinecap="round" />
          </>
        ) : (
          <>
            <circle cx="38" cy="52" r="8" fill="white" />
            <circle cx="62" cy="52" r="8" fill="white" />
            <motion.circle cx={mood === "think" ? 41 : 39} cy={mood === "think" ? 49 : 53} r="4" fill="#1e1b4b"
              animate={{ scaleY: [1, 1, 0.1, 1] }} transition={{ repeat: Infinity, duration: 3.5, times: [0, 0.9, 0.95, 1] }} />
            <motion.circle cx={mood === "think" ? 65 : 63} cy={mood === "think" ? 49 : 53} r="4" fill="#1e1b4b"
              animate={{ scaleY: [1, 1, 0.1, 1] }} transition={{ repeat: Infinity, duration: 3.5, times: [0, 0.9, 0.95, 1] }} />
          </>
        )}
        {/* mouth */}
        {mood === "sad" ? (
          <path d="M40 76 Q50 68 60 76" stroke="white" strokeWidth="3.5" fill="none" strokeLinecap="round" />
        ) : happy ? (
          <path d="M36 66 Q50 84 64 66 Z" fill="white" />
        ) : mood === "think" ? (
          <circle cx="54" cy="72" r="3.5" fill="white" />
        ) : (
          <path d="M40 70 Q50 78 60 70" stroke="white" strokeWidth="3.5" fill="none" strokeLinecap="round" />
        )}
        <circle cx="28" cy="64" r="4" fill="#fda4af" opacity="0.6" />
        <circle cx="72" cy="64" r="4" fill="#fda4af" opacity="0.6" />
        {(mood === "party" || mood === "happy") &&
          [0, 1, 2].map((i) => (
            <motion.text key={i} x={[8, 84, 46][i]} y={[30, 34, 12][i]} fontSize="12"
              initial={{ opacity: 0, scale: 0 }} animate={{ opacity: [0, 1, 0], scale: [0, 1.3, 0.8] }}
              transition={{ duration: 0.9, delay: i * 0.1 }}>
              ✨
            </motion.text>
          ))}
      </motion.svg>
    </div>
  );
}
