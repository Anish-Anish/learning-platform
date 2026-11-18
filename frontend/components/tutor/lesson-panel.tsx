"use client";

import { ArrowRightIcon, BookOpenIcon, MessageCircleQuestionIcon, QuoteIcon, ThumbsDownIcon, ThumbsUpIcon, WandSparklesIcon } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { MisconceptionReplay } from "@/components/replay/misconception-replay";
import { RichText } from "@/components/rich-text";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { flags } from "@/lib/flags";
import type { LessonPayload } from "@/lib/types";

type Meta = { concept_name?: string; misconception_text?: string | null; correct_belief?: string | null };

export function LessonPanel({
  conceptId,
  misconceptionId,
  studentId,
  onDone,
  doneLabel,
}: {
  conceptId: string;
  misconceptionId?: string | null;
  studentId: string;
  onDone: () => void;
  doneLabel?: string;
}) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [text, setText] = useState("");
  const [lesson, setLesson] = useState<LessonPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rated, setRated] = useState<number | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const ctrl = new AbortController();
    api
      .streamLesson(
        conceptId,
        studentId,
        misconceptionId,
        (event, data) => {
          if (event === "meta") setMeta(data as Meta);
          else if (event === "delta") setText((t) => t + (data as { text: string }).text);
          else if (event === "lesson") setLesson(data as LessonPayload);
        },
        ctrl.signal,
      )
      .catch((e: Error) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    // StrictMode double-mount: keep the single stream alive
  }, [conceptId, misconceptionId, studentId]);

  async function rate(r: number) {
    setRated(r);
    await api.feedback({ student_id: studentId, target_kind: "lesson", target_id: `${conceptId}:${misconceptionId ?? ""}`, rating: r });
    toast("Thanks! Feedback helps us improve lessons.");
  }

  const streaming = !lesson && !error;
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <Card className="border-primary/40">
        <CardHeader>
          <div className="flex items-center gap-2 text-xs font-medium tracking-wide text-primary uppercase">
            <BookOpenIcon className="size-4" /> Micro-lesson
          </div>
          <CardTitle className="text-xl">{meta?.concept_name ?? <Skeleton className="h-6 w-60" />}</CardTitle>
          <CardDescription>Grounded in your teacher&apos;s notes. Under 2 minutes.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {error && <p className="text-sm text-destructive">{error}</p>}
          {!text && !error ? (
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-11/12" />
              <Skeleton className="h-4 w-4/6" />
            </div>
          ) : (
            <RichText text={lesson?.lesson_md ?? text} streaming={streaming} />
          )}

          {lesson && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }} className="space-y-4">
              {lesson.worked_example && (
                <div className="rounded-xl border bg-muted/40 p-4">
                  <p className="mb-1 text-xs font-semibold text-muted-foreground">Worked example</p>
                  <RichText text={lesson.worked_example} className="text-sm" />
                </div>
              )}
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
                  <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-primary">
                    <WandSparklesIcon className="size-3.5" /> Real-world analogy
                  </p>
                  <p className="text-sm leading-relaxed">{lesson.analogy}</p>
                </div>
                <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-4">
                  <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-amber-700 dark:text-amber-400">
                    <MessageCircleQuestionIcon className="size-3.5" /> Think it through
                  </p>
                  <ul className="space-y-1.5 text-sm">
                    {lesson.socratic_questions.map((q, i) => (
                      <li key={i}>{q}</li>
                    ))}
                  </ul>
                </div>
              </div>
              {lesson.citations.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">From the notes</p>
                  {lesson.citations.map((c, i) => (
                    <p key={i} className="flex gap-2 text-xs text-muted-foreground italic">
                      <QuoteIcon className="size-3 shrink-0" /> {c}
                    </p>
                  ))}
                </div>
              )}
            </motion.div>
          )}
        </CardContent>
        {lesson && (
          <CardFooter className="flex flex-wrap gap-2 border-t bg-muted/30 pt-4">
            <Button onClick={onDone} size="lg">
              {doneLabel ?? `Take the mastery check (${lesson.mastery_check_question_ids.length} questions)`} <ArrowRightIcon />
            </Button>
            <div className="ml-auto flex items-center gap-1">
              <span className="mr-1 text-xs text-muted-foreground">Helpful?</span>
              <Button size="icon-sm" variant={rated === 1 ? "default" : "ghost"} onClick={() => rate(1)} aria-label="Helpful">
                <ThumbsUpIcon />
              </Button>
              <Button size="icon-sm" variant={rated === -1 ? "default" : "ghost"} onClick={() => rate(-1)} aria-label="Not helpful">
                <ThumbsDownIcon />
              </Button>
            </div>
          </CardFooter>
        )}
      </Card>
      {lesson?.replay_id && flags.replay && <MisconceptionReplay replayId={lesson.replay_id} />}
    </motion.div>
  );
}
