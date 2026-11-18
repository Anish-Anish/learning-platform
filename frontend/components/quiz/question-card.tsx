"use client";

import { CheckIcon, HelpCircleIcon, LightbulbIcon, XIcon } from "lucide-react";
import { useState } from "react";

import { RichText } from "@/components/rich-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { api } from "@/lib/api";
import { flags } from "@/lib/flags";
import { BLOOM_LABEL } from "@/lib/states";
import type { Confidence, QuestionPublic } from "@/lib/types";
import { cn } from "@/lib/utils";

const PHASE_LABEL: Record<string, string> = {
  diagnostic: "Diagnostic",
  probe: "Prerequisite probe",
  remediation: "Mastery check",
  practice: "Practice",
  boss: "Boss",
  level: "Mission",
};

export type SubmitPayload = { optionId: string; confidence: Confidence; hintsUsed: number; timeMs: number };

export function QuestionCard({
  question,
  reason,
  phase,
  progress,
  studentId,
  onSubmit,
  submitting,
  result,
  allowHints = true,
  removedOptionIds = [],
  submitLabel = "Submit answer",
}: {
  question: QuestionPublic;
  reason?: string;
  phase?: string;
  progress?: { done: number; total: number };
  studentId: string;
  onSubmit: (p: SubmitPayload) => void;
  submitting?: boolean;
  result?: { selected: string; correct: string | null; isCorrect: boolean } | null;
  allowHints?: boolean;
  removedOptionIds?: string[];
  submitLabel?: string;
}) {
  const [option, setOption] = useState<string>("");
  const [confidence, setConfidence] = useState<Confidence | "">("");
  const [hints, setHints] = useState<string[]>([]);
  const [loadingHint, setLoadingHint] = useState(false);
  const [startedAt] = useState(() => Date.now());
  const locked = !!result || submitting;

  async function getHint() {
    setLoadingHint(true);
    try {
      const h = await api.hint(question.id, hints.length + 1, studentId);
      setHints((xs) => [...xs, h.hint]);
    } finally {
      setLoadingHint(false);
    }
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {phase && (
            <Badge variant={phase === "probe" ? "destructive" : phase === "remediation" ? "default" : "secondary"}>
              {PHASE_LABEL[phase] ?? phase}
            </Badge>
          )}
          <Badge variant="outline">{question.concept_name}</Badge>
          <Badge variant="outline" className="text-muted-foreground">
            {BLOOM_LABEL[question.bloom_level]}
          </Badge>
          {progress && phase === "diagnostic" && (
            <span className="text-xs text-muted-foreground">
              Question {Math.min(progress.done + 1, progress.total)} of {progress.total}
            </span>
          )}
          {reason && (
            <HoverCard openDelay={100}>
              <HoverCardTrigger asChild>
                <button className="ml-auto inline-flex items-center gap-1 text-xs text-primary hover:underline">
                  <HelpCircleIcon className="size-3.5" /> Why this question?
                </button>
              </HoverCardTrigger>
              <HoverCardContent align="end" className="w-80 text-sm">
                <p className="mb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">Adaptive engine</p>
                <p>{reason}</p>
              </HoverCardContent>
            </HoverCard>
          )}
        </div>
        <RichText text={question.stem} className="text-base font-medium [&_p]:my-1" />
      </CardHeader>
      <CardContent className="space-y-5">
        <RadioGroup value={option} onValueChange={setOption} disabled={locked} className="gap-2.5">
          {question.options.map((o, i) => {
            const isSel = result?.selected === o.id;
            const isRight = result?.correct === o.id;
            const removed = removedOptionIds.includes(o.id) && !isRight;
            return (
              <label
                key={o.id}
                htmlFor={`${question.id}-${o.id}`}
                className={cn(
                  "flex cursor-pointer items-start gap-3 rounded-xl border p-3.5 transition-colors",
                  !locked && "hover:border-primary/50 hover:bg-primary/5",
                  option === o.id && !result && "border-primary bg-primary/5 ring-2 ring-primary/20",
                  result && isRight && "border-emerald-500/70 bg-emerald-500/10",
                  result && isSel && !isRight && "border-rose-500/70 bg-rose-500/10",
                  locked && "cursor-default",
                  removed && "pointer-events-none opacity-35 line-through",
                )}
              >
                <RadioGroupItem id={`${question.id}-${o.id}`} value={o.id} className="mt-0.5" disabled={removed} />
                <span className="grid size-5 shrink-0 place-items-center rounded-md bg-muted text-[11px] font-semibold text-muted-foreground">
                  {String.fromCharCode(65 + i)}
                </span>
                <RichText text={o.text} className="flex-1 text-sm [&_p]:my-0" />
                {result && isRight && <CheckIcon className="size-4 text-emerald-600" />}
                {result && isSel && !isRight && <XIcon className="size-4 text-rose-600" />}
              </label>
            );
          })}
        </RadioGroup>

        {hints.length > 0 && (
          <div className="space-y-1.5 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
            {hints.map((h, i) => (
              <p key={i} className="flex gap-2">
                <LightbulbIcon className="mt-0.5 size-4 shrink-0 text-amber-600" /> {h}
              </p>
            ))}
          </div>
        )}
      </CardContent>
      {!result && (
        <CardFooter className="flex flex-wrap items-center gap-3 border-t bg-muted/30 pt-4">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">How sure are you?</span>
            <ToggleGroup
              type="single"
              variant="outline"
              value={confidence}
              onValueChange={(v) => setConfidence((v as Confidence) || "")}
              disabled={locked}
            >
              <ToggleGroupItem value="sure" className="px-4 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground">
                Sure
              </ToggleGroupItem>
              <ToggleGroupItem value="guess" className="px-4 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground">
                Guessing
              </ToggleGroupItem>
            </ToggleGroup>
          </div>
          {allowHints && flags.hints && question.has_hints && hints.length < 3 && (
            <Button variant="ghost" size="sm" onClick={getHint} disabled={locked || loadingHint} className="text-muted-foreground">
              <LightbulbIcon /> Hint <span className="text-xs">(-10 XP)</span>
            </Button>
          )}
          <Button
            className="ml-auto"
            size="lg"
            disabled={!option || !confidence || locked}
            onClick={() =>
              onSubmit({ optionId: option, confidence: confidence as Confidence, hintsUsed: hints.length, timeMs: Date.now() - startedAt })
            }
          >
            {submitting ? "Checking…" : submitLabel}
          </Button>
        </CardFooter>
      )}
    </Card>
  );
}
