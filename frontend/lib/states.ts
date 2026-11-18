import type { ConceptState } from "./types";

export const STATE_META: Record<
  ConceptState,
  { label: string; dot: string; bg: string; border: string; text: string; hint: string }
> = {
  mastered: {
    label: "Mastered",
    dot: "bg-emerald-500",
    bg: "bg-emerald-500/12 dark:bg-emerald-500/15",
    border: "border-emerald-500/60",
    text: "text-emerald-700 dark:text-emerald-300",
    hint: "Solid: confident and correct.",
  },
  fragile: {
    label: "Fragile",
    dot: "bg-amber-500",
    bg: "bg-amber-500/12 dark:bg-amber-500/15",
    border: "border-amber-500/60",
    text: "text-amber-700 dark:text-amber-300",
    hint: "Partly there, or the last correct answer was a guess.",
  },
  misconception: {
    label: "Misconception",
    dot: "bg-rose-500",
    bg: "bg-rose-500/12 dark:bg-rose-500/15",
    border: "border-rose-500/70",
    text: "text-rose-700 dark:text-rose-300",
    hint: "A confident wrong answer revealed a wrong mental model.",
  },
  gap: {
    label: "Gap",
    dot: "bg-orange-500",
    bg: "bg-orange-500/12 dark:bg-orange-500/15",
    border: "border-orange-500/60",
    text: "text-orange-700 dark:text-orange-300",
    hint: "Low mastery after some attempts.",
  },
  not_started: {
    label: "Ready",
    dot: "bg-sky-500",
    bg: "bg-sky-500/10 dark:bg-sky-500/12",
    border: "border-sky-500/50",
    text: "text-sky-700 dark:text-sky-300",
    hint: "Unlocked and ready to start.",
  },
  locked: {
    label: "Locked",
    dot: "bg-neutral-400",
    bg: "bg-muted/60",
    border: "border-border border-dashed",
    text: "text-muted-foreground",
    hint: "Unlocks when prerequisites reach 70%.",
  },
};

export const STATE_ORDER: ConceptState[] = ["mastered", "fragile", "misconception", "gap", "not_started", "locked"];

export const BLOOM_LABEL: Record<string, string> = {
  remember: "Remember",
  understand: "Understand",
  apply: "Apply",
  analyze: "Analyze",
};

export const pct = (x: number | null | undefined, digits = 0) =>
  x === null || x === undefined ? "–" : `${(x * 100).toFixed(digits)}%`;
