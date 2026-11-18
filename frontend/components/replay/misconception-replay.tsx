"use client";

// W3: Misconception replay. Side-by-side "your model" vs "reality", step by step, showing exactly where
// the student's mental model diverges. Built for two concepts: recursion base cases and the BST property.
import { PauseIcon, PlayIcon, RotateCcwIcon, StepForwardIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export const SUPPORTED_REPLAYS = ["recursion_no_base", "bst_subtree_order"] as const;

function useStepper(total: number) {
  const [step, setStep] = useState(0);
  const [wantPlay, setPlaying] = useState(false);
  const playing = wantPlay && step < total - 1;
  useEffect(() => {
    if (!playing) return;
    const t = setTimeout(() => setStep((s) => s + 1), 1100);
    return () => clearTimeout(t);
  }, [playing, step]);
  return {
    step,
    playing,
    play: () => {
      if (step >= total - 1) setStep(0);
      setPlaying(true);
    },
    pause: () => setPlaying(false),
    next: () => setStep((s) => Math.min(total - 1, s + 1)),
    reset: () => {
      setPlaying(false);
      setStep(0);
    },
  };
}

function Controls({ s, total, caption }: { s: ReturnType<typeof useStepper>; total: number; caption: string }) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-t pt-3">
      {s.playing ? (
        <Button size="sm" variant="outline" onClick={s.pause}>
          <PauseIcon /> Pause
        </Button>
      ) : (
        <Button size="sm" onClick={s.play}>
          <PlayIcon /> Play
        </Button>
      )}
      <Button size="sm" variant="outline" onClick={s.next} disabled={s.step >= total - 1}>
        <StepForwardIcon /> Step
      </Button>
      <Button size="icon-sm" variant="ghost" onClick={s.reset} aria-label="Reset">
        <RotateCcwIcon />
      </Button>
      <span className="text-xs text-muted-foreground">
        {s.step + 1}/{total}
      </span>
      <p className="w-full text-sm sm:ml-2 sm:w-auto sm:flex-1">{caption}</p>
    </div>
  );
}

function Pane({ title, tone, children }: { title: string; tone: "you" | "real"; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "rounded-xl border p-3",
        tone === "you" ? "border-rose-500/40 bg-rose-500/5" : "border-emerald-500/40 bg-emerald-500/5",
      )}
    >
      <p className={cn("mb-2 text-xs font-semibold", tone === "you" ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400")}>
        {title}
      </p>
      {children}
    </div>
  );
}

// ------------------------------------------------------------ recursion without a base case
function RecursionReplay() {
  const frames = [3, 2, 1, 0, -1, -2, -3, -4];
  const total = 9;
  const s = useStepper(total);
  const youFrames = frames.slice(0, Math.min(s.step + 1, 4));
  const youStopped = s.step >= 4;
  const realFrames = frames.slice(0, Math.min(s.step + 1, frames.length));
  const overflow = s.step >= 8;
  const captions = [
    "countdown(3) is called and pushes a frame.",
    "It prints 3 and calls countdown(2).",
    "Prints 2, calls countdown(1).",
    "Prints 1, calls countdown(0). Both models agree so far.",
    "Divergence! Your model stops at 0, but nothing in the code says 'stop', so reality calls countdown(-1).",
    "No base case means no return: countdown(-2)…",
    "…the stack keeps growing…",
    "…and growing. Recursion never stops by itself.",
    "RecursionError: maximum recursion depth exceeded. A base case like `if n == 0: return` is the only exit.",
  ];
  const Frame = ({ n, bad }: { n: number; bad?: boolean }) => (
    <motion.div
      layout
      initial={{ opacity: 0, y: -8, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      className={cn("rounded-md border bg-background px-2 py-1 font-mono text-xs", bad && "border-rose-500 text-rose-600")}
    >
      countdown({n})
    </motion.div>
  );
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2">
        <Pane title="Your model: it stops on its own" tone="you">
          <div className="flex min-h-48 flex-col-reverse gap-1">
            <AnimatePresence>{youFrames.map((n) => <Frame key={n} n={n} />)}</AnimatePresence>
          </div>
          {youStopped && <p className="mt-2 text-xs font-medium text-rose-600">✋ “It just stops at 0”</p>}
        </Pane>
        <Pane title="Reality: every call makes another call" tone="real">
          <div className="flex min-h-48 flex-col-reverse gap-1">
            <AnimatePresence>{realFrames.map((n) => <Frame key={n} n={n} bad={n < 0} />)}</AnimatePresence>
          </div>
          {overflow && <p className="mt-2 font-mono text-xs font-medium text-rose-600">💥 RecursionError: stack overflow</p>}
        </Pane>
      </div>
      <Controls s={s} total={total} caption={captions[s.step]} />
    </>
  );
}

// ------------------------------------------------------------ BST property applies to whole subtrees
type TNode = { k: number; x: number; y: number };
const NODES: TNode[] = [
  { k: 10, x: 150, y: 30 },
  { k: 5, x: 80, y: 95 },
  { k: 15, x: 220, y: 95 },
  { k: 12, x: 120, y: 160 },
];
const EDGES: [number, number][] = [
  [10, 5],
  [10, 15],
  [5, 12],
];

function Tree({ highlight, bad, ok, visitedEdges }: { highlight?: number; bad?: number[]; ok?: number[]; visitedEdges?: string[] }) {
  const pos = Object.fromEntries(NODES.map((n) => [n.k, n]));
  return (
    <svg viewBox="0 0 300 200" className="h-48 w-full">
      {EDGES.map(([a, b]) => {
        const on = visitedEdges?.includes(`${a}-${b}`);
        return (
          <motion.line
            key={`${a}-${b}`}
            x1={pos[a].x} y1={pos[a].y} x2={pos[b].x} y2={pos[b].y}
            stroke="currentColor"
            className={on ? "text-primary" : "text-muted-foreground/50"}
            strokeWidth={on ? 3 : 1.5}
            animate={{ strokeWidth: on ? 3 : 1.5 }}
          />
        );
      })}
      {NODES.map((n) => {
        const isBad = bad?.includes(n.k);
        const isOk = ok?.includes(n.k);
        return (
          <g key={n.k}>
            <motion.circle
              cx={n.x} cy={n.y} r={17}
              className={cn(
                "fill-background stroke-[2]",
                isBad ? "stroke-rose-500" : isOk ? "stroke-emerald-500" : highlight === n.k ? "stroke-primary" : "stroke-border",
              )}
              animate={{ scale: highlight === n.k ? 1.15 : 1 }}
              style={{ transformOrigin: `${n.x}px ${n.y}px` }}
            />
            <text x={n.x} y={n.y + 4} textAnchor="middle" className={cn("fill-foreground text-[12px] font-semibold", isBad && "fill-rose-600")}>
              {n.k}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function BstReplay() {
  const total = 6;
  const s = useStepper(total);
  const youChecks: { ok: number[]; edges: string[]; label: string }[] = [
    { ok: [], edges: [], label: "" },
    { ok: [10, 5], edges: ["10-5"], label: "5 < 10 ✓" },
    { ok: [10, 5, 15], edges: ["10-5", "10-15"], label: "15 > 10 ✓" },
    { ok: [10, 5, 15, 12], edges: ["10-5", "10-15", "5-12"], label: "12 > 5 ✓" },
    { ok: [10, 5, 15, 12], edges: ["10-5", "10-15", "5-12"], label: "Every parent–child pair is ordered → 'valid BST!'" },
    { ok: [10, 5, 15, 12], edges: ["10-5", "10-15", "5-12"], label: "Every parent–child pair is ordered → 'valid BST!'" },
  ];
  const real: { hl?: number; edges: string[]; bad: number[]; label: string }[] = [
    { edges: [], bad: [], label: "search(12)" },
    { hl: 10, edges: [], bad: [], label: "At 10: 12 > 10 → go right" },
    { hl: 15, edges: ["10-15"], bad: [], label: "At 15: 12 < 15 → go left" },
    { hl: undefined, edges: ["10-15"], bad: [], label: "15.left is empty → 'not found'" },
    { hl: 12, edges: ["10-15"], bad: [12], label: "But 12 IS in the tree, stranded in 10's LEFT subtree" },
    { hl: 12, edges: ["10-15"], bad: [12], label: "12 > 10, so it breaks the rule for the whole left subtree" },
  ];
  const captions = [
    "The tree 10(5(_, 12), 15). Let's check it two ways.",
    "Your model compares each parent only with its direct child…",
    "…every pair looks fine…",
    "…so the tree seems valid. Meanwhile, reality searches for 12: right at 10, left at 15, empty.",
    "Divergence! Search can't find 12, because BST order must hold for ENTIRE subtrees, not just children.",
    "Fix: every key left of 10 (including 12) must be < 10. This tree is not a BST.",
  ];
  const y = youChecks[s.step];
  const r = real[s.step];
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2">
        <Pane title="Your model: only direct children must be ordered" tone="you">
          <Tree ok={y.ok} visitedEdges={y.edges} />
          <p className="min-h-5 text-xs font-medium">{y.label}</p>
        </Pane>
        <Pane title="Reality: search follows the ordering" tone="real">
          <Tree highlight={r.hl} bad={r.bad} visitedEdges={r.edges} />
          <p className="min-h-5 text-xs font-medium">{r.label}</p>
        </Pane>
      </div>
      <Controls s={s} total={total} caption={captions[s.step]} />
    </>
  );
}

export function MisconceptionReplay({ replayId }: { replayId: string }) {
  if (!SUPPORTED_REPLAYS.includes(replayId as (typeof SUPPORTED_REPLAYS)[number])) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Misconception replay</CardTitle>
        <CardDescription>Watch where your mental model and reality split.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {replayId === "recursion_no_base" ? <RecursionReplay /> : <BstReplay />}
      </CardContent>
    </Card>
  );
}
