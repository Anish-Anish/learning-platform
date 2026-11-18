"use client";

import { CheckIcon, Loader2Icon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import type { StudioJob, SubjectStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS: Record<SubjectStatus, { label: string; className: string }> = {
  draft: { label: "Draft", className: "bg-muted text-muted-foreground" },
  processing: { label: "Generating", className: "bg-sky-500/15 text-sky-700 dark:text-sky-300" },
  review: { label: "Ready for review", className: "bg-amber-500/15 text-amber-700 dark:text-amber-300" },
  published: { label: "Published", className: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
  failed: { label: "Failed", className: "bg-destructive/10 text-destructive" },
};

export function SubjectStatusBadge({ status }: { status: SubjectStatus }) {
  const s = STATUS[status];
  return (
    <Badge variant="outline" className={cn("border-transparent", s.className)}>
      {status === "processing" && <Loader2Icon className="animate-spin" />}
      {s.label}
    </Badge>
  );
}

const STAGES = [
  { id: "parsing", label: "Read files" },
  { id: "figures", label: "Figures & scans" },
  { id: "extracting", label: "Find concepts" },
  { id: "graph", label: "Build graph" },
  { id: "authoring", label: "Notes, quizzes, cards" },
  { id: "saving", label: "Save draft" },
];

export function JobProgress({ job }: { job: StudioJob }) {
  const current = STAGES.findIndex((s) => s.id === job.stage);
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-medium">{job.message || "Working..."}</span>
        <span className="tabular-nums text-muted-foreground">{Math.round(job.progress * 100)}%</span>
      </div>
      <Progress value={job.progress * 100} />
      <ol className="grid grid-cols-3 gap-2 text-xs sm:grid-cols-6">
        {STAGES.map((s, i) => {
          const done = current > i || job.status === "done";
          const active = current === i && job.status === "running";
          return (
            <li key={s.id} className={cn("flex items-center gap-1.5", done || active ? "text-foreground" : "text-muted-foreground")}>
              <span
                className={cn(
                  "grid size-4 shrink-0 place-items-center rounded-full border",
                  done && "border-emerald-500 bg-emerald-500 text-white",
                  active && "border-primary",
                )}
              >
                {done ? <CheckIcon className="size-3" /> : active ? <Loader2Icon className="size-3 animate-spin text-primary" /> : null}
              </span>
              {s.label}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
