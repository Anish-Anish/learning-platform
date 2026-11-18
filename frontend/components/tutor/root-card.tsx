"use client";

import { ArrowRightIcon, ChevronRightIcon, MicroscopeIcon, SearchCheckIcon, SproutIcon } from "lucide-react";
import { motion } from "motion/react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Diagnosis } from "@/lib/types";
import { cn } from "@/lib/utils";

export function RootCardSkeleton() {
  return (
    <Card className="border-primary/40">
      <CardHeader>
        <div className="flex items-center gap-2 text-sm text-primary">
          <MicroscopeIcon className="size-4 animate-pulse" /> Tracing the mistake back to its root…
        </div>
        <Skeleton className="h-6 w-2/3" />
      </CardHeader>
      <CardContent className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-4/6" />
      </CardContent>
    </Card>
  );
}

function PathCrumbs({ path, names }: { path: string[]; names: Record<string, string> }) {
  if (path.length < 2) return null;
  return (
    <div className="flex flex-wrap items-center gap-1 text-xs">
      {path.map((c, i) => (
        <span key={c} className="flex items-center gap-1">
          <span
            className={cn(
              "rounded-md border px-2 py-0.5",
              i === path.length - 1 ? "border-primary bg-primary/10 font-medium text-primary" : "text-muted-foreground",
            )}
          >
            {names[c] ?? c}
          </span>
          {i < path.length - 1 && <ChevronRightIcon className="size-3 text-muted-foreground" />}
        </span>
      ))}
    </div>
  );
}

export function RootCard({
  dx,
  names,
  onLesson,
  onContinue,
  lessonLabel = "Start the micro-lesson",
  continueLabel,
  extra,
}: {
  dx: Diagnosis;
  names: Record<string, string>;
  onLesson: () => void;
  onContinue: () => void;
  lessonLabel?: string;
  continueLabel?: string;
  extra?: React.ReactNode;
}) {
  const probe = dx.needs_probe;
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
      <Card className={cn("overflow-hidden", probe ? "border-amber-500/50" : "border-primary/50")}>
        <div className={cn("h-1", probe ? "bg-amber-500" : "bg-primary")} />
        <CardHeader>
          <div className="flex items-center gap-2 text-xs font-medium tracking-wide uppercase text-muted-foreground">
            {probe ? <SearchCheckIcon className="size-4 text-amber-600" /> : <SproutIcon className="size-4 text-primary" />}
            {probe ? "Checking a prerequisite" : "Root found"}
            {dx.confidence != null && (
              <span className="ml-auto rounded-full bg-muted px-2 py-0.5 normal-case tracking-normal">
                confidence {(dx.confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
          <CardTitle className="text-xl">
            {probe ? (
              <>Is <span className="text-amber-600 dark:text-amber-400">{names[dx.probe_concept_id ?? ""] ?? dx.probe_concept_id}</span> the real snag?</>
            ) : (
              <>The root is <span className="text-primary">{dx.root_concept_name}</span></>
            )}
          </CardTitle>
          <CardDescription className="text-sm">{dx.student_message}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <PathCrumbs path={dx.path} names={names} />
          {dx.misconception_text && !probe && (
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="rounded-lg border border-rose-500/40 bg-rose-500/5 p-3 text-sm">
                <p className="mb-1 text-xs font-medium text-rose-600 dark:text-rose-400">Your mental model</p>
                {dx.misconception_text}
              </div>
              <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-3 text-sm">
                <p className="mb-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">What&apos;s actually true</p>
                {dx.correct_belief}
              </div>
            </div>
          )}
          {dx.evidence.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-medium text-muted-foreground">Evidence</p>
              <ul className="space-y-1 text-sm">
                {dx.evidence.map((e, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary/60" /> {e}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
        <CardFooter className="gap-2 border-t bg-muted/30 pt-4">
          {probe ? (
            <Button onClick={onContinue}>
              {continueLabel ?? "Take the check question"} <ArrowRightIcon />
            </Button>
          ) : (
            <>
              <Button onClick={onLesson}>
                {lessonLabel} <ArrowRightIcon />
              </Button>
              <Button variant="ghost" onClick={onContinue}>
                {continueLabel ?? "Skip for now"}
              </Button>
            </>
          )}
          {extra}
          <span className="ml-auto text-[11px] text-muted-foreground">
            {dx.source === "llm" ? "AI agent proposal" : "Deterministic agent"} · validated by core rules
          </span>
        </CardFooter>
      </Card>
    </motion.div>
  );
}
