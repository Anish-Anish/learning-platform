"use client";

import { ArrowRightIcon, CheckCircle2Icon, MapIcon, SwordsIcon, XCircleIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { announceRewards } from "@/components/game/rewards";
import { QuestionCard, type SubmitPayload } from "@/components/quiz/question-card";
import { StateBadge } from "@/components/state-badge";
import { LessonPanel } from "@/components/tutor/lesson-panel";
import { RootCard, RootCardSkeleton } from "@/components/tutor/root-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { startSessionOnce } from "@/lib/session-start";
import { flags } from "@/lib/flags";
import { useConcepts, useDiagnosis, useSubmitAttempt } from "@/lib/queries/student";
import { pct } from "@/lib/states";
import { useSession } from "@/lib/store";
import type { AttemptResponse, NextQuestion } from "@/lib/types";
import { cn } from "@/lib/utils";

type LessonTarget = { conceptId: string; misconceptionId?: string | null };

export default function LearnPage() {
  const studentId = useSession((s) => s.studentId);
  // Remount per learner so every piece of session state starts fresh.
  return <Learn key={studentId} studentId={studentId} />;
}

function Learn({ studentId }: { studentId: string }) {
  const router = useRouter();
  const sessionId = useSession((s) => s.sessionId);
  const setSession = useSession((s) => s.setSession);
  const setXp = useSession((s) => s.setXp);
  const concepts = useConcepts();
  const names = useMemo(() => Object.fromEntries((concepts.data ?? []).map((c) => [c.id, c.name])), [concepts.data]);

  const [current, setCurrent] = useState<NextQuestion | null>(null);
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [lesson, setLesson] = useState<LessonTarget | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({ answered: 0, correct: 0 });
  const submit = useSubmitAttempt();
  const dx = useDiagnosis(result?.diagnosis.id);

  // Start (or resume) a session whenever the learner changes.
  useEffect(() => {
    let cancelled = false;
    startSessionOnce(studentId)
      .then((r) => {
        if (cancelled) return;
        setSession(r.session_id);
        setXp(r.student.xp_total, r.student.level);
        setCurrent(r.next);
        // Deep link from the map: /learn?lesson=<concept_id>
        const lessonFor = new URLSearchParams(window.location.search).get("lesson");
        if (lessonFor) setLesson({ conceptId: lessonFor });
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [studentId, setSession, setXp]);

  const loadNext = useCallback(async () => {
    setResult(null);
    setLesson(null);
    setCurrent(null);
    try {
      setCurrent(await api.nextQuestion(studentId));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError((e as Error).message);
    }
  }, [studentId]);

  function onSubmit(p: SubmitPayload) {
    if (!current?.question) return;
    setSelected(p.optionId);
    submit.mutate(
      {
        student_id: studentId,
        question_id: current.question.id,
        option_id: p.optionId,
        confidence: p.confidence,
        time_ms: p.timeMs,
        hints_used: p.hintsUsed,
        session_id: sessionId,
      },
      {
        onSuccess: (r) => {
          setResult(r);
          setStats((s) => ({ answered: s.answered + 1, correct: s.correct + (r.is_correct ? 1 : 0) }));
          announceRewards(r);
        },
        onError: (e) => setError(e.message),
      },
    );
  }

  if (error) {
    return (
      <Card className="mx-auto max-w-xl">
        <CardHeader>
          <CardTitle>We couldn&apos;t reach the tutor</CardTitle>
          <CardDescription>{error}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p>Start the backend, then retry:</p>
          <pre className="rounded-lg bg-muted p-3 font-mono text-xs">cd backend && uv run uvicorn app.main:app --port 8000</pre>
          <Button onClick={() => window.location.reload()}>Retry</Button>
        </CardContent>
      </Card>
    );
  }

  const dxData = dx.data;
  const nextAction = result?.next_action;
  const diagnosisPending = !!result?.diagnosis.id && (!dxData || dxData.status === "pending");

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-w-0 space-y-4">
        {lesson ? (
          <LessonPanel
            key={`${lesson.conceptId}:${lesson.misconceptionId ?? ""}`}
            conceptId={lesson.conceptId}
            misconceptionId={lesson.misconceptionId}
            studentId={studentId}
            onDone={loadNext}
          />
        ) : !current ? (
          <Card>
            <CardHeader className="space-y-3">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-6 w-full" />
            </CardHeader>
            <CardContent className="space-y-2.5">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-12 w-full rounded-xl" />
              ))}
            </CardContent>
          </Card>
        ) : !current.question ? (
          <Card>
            <CardHeader>
              <CardTitle>You&apos;re all caught up 🎉</CardTitle>
              <CardDescription>{current.reason}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {flags.boss && (
                <Button onClick={() => router.push("/boss/new")}>
                  <SwordsIcon /> Root Boss
                </Button>
              )}
              <Button variant="outline" asChild>
                <Link href="/teach">Teach the bot</Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href="/map">Knowledge map</Link>
              </Button>
            </CardContent>
          </Card>
        ) : (
          <QuestionCard
            key={current.question.id + current.trace_id}
            question={current.question}
            reason={current.reason}
            phase={current.phase}
            progress={{ done: current.diagnostic_progress, total: current.diagnostic_total }}
            studentId={studentId}
            onSubmit={onSubmit}
            submitting={submit.isPending}
            result={result ? { selected, correct: result.correct_option_id, isCorrect: result.is_correct } : null}
          />
        )}

        {result && !lesson && (
          <div className="space-y-4">
            <Card className={cn("border-l-4", result.is_correct ? "border-l-emerald-500" : "border-l-rose-500")}>
              <CardContent className="flex flex-col gap-3 pt-6 sm:flex-row sm:items-start">
                {result.is_correct ? (
                  <CheckCircle2Icon className="size-6 shrink-0 text-emerald-600" />
                ) : (
                  <XCircleIcon className="size-6 shrink-0 text-rose-600" />
                )}
                <div className="flex-1 space-y-1.5">
                  <p className="font-medium">
                    {result.is_correct
                      ? result.signal === "fragile_signal"
                        ? "Correct, but you were guessing. Let's make it solid."
                        : "Correct!"
                      : result.signal === "misconception_signal"
                        ? "Not quite, and you were sure. That's a misconception worth tracing."
                        : "Not quite. That's a gap we can fill."}
                  </p>
                  <p className="text-sm text-muted-foreground">{result.explanation}</p>
                  {!result.progress_awarded && (
                    <p className="text-xs text-muted-foreground">You answered this one recently, so no extra progress this time.</p>
                  )}
                </div>
                <div className="flex shrink-0 flex-col items-start gap-1 sm:items-end">
                  <StateBadge state={result.concept_state.state} />
                  <span className="text-xs text-muted-foreground">
                    {result.concept_state.concept_name}: {pct(result.concept_state.mastery)}
                  </span>
                </div>
              </CardContent>
            </Card>

            {result.diagnosis.id && (diagnosisPending ? <RootCardSkeleton /> : dxData && dxData.status !== "rejected" ? (
              <RootCard
                dx={dxData}
                names={names}
                onLesson={() =>
                  setLesson({ conceptId: dxData.root_concept_id ?? result.concept_state.concept_id, misconceptionId: dxData.misconception_id })
                }
                onContinue={loadNext}
              />
            ) : null)}

            {nextAction?.kind === "lesson" && !result.diagnosis.id && nextAction.concept_id && (
              <Card className="border-primary/40">
                <CardHeader>
                  <CardTitle className="text-lg">Good news</CardTitle>
                  <CardDescription>{nextAction.message}</CardDescription>
                </CardHeader>
                <CardContent>
                  <Button onClick={() => setLesson({ conceptId: nextAction.concept_id!, misconceptionId: nextAction.misconception_id })}>
                    Start the micro-lesson <ArrowRightIcon />
                  </Button>
                </CardContent>
              </Card>
            )}

            {nextAction?.kind === "boss" && flags.boss && (
              <Card className="overflow-hidden border-primary/50 bg-gradient-to-br from-primary/10 to-transparent">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <SwordsIcon className="size-5 text-primary" /> The Root Boss awaits
                  </CardTitle>
                  <CardDescription>{nextAction.message}</CardDescription>
                </CardHeader>
                <CardContent className="flex gap-2">
                  <Button onClick={() => router.push("/boss/new")}>Fight the boss</Button>
                  <Button variant="ghost" onClick={loadNext}>
                    Later
                  </Button>
                </CardContent>
              </Card>
            )}

            {(!result.diagnosis.id || dxData?.status === "rejected") && nextAction?.kind !== "boss" && (
              <div className="flex justify-end">
                <Button size="lg" onClick={loadNext}>
                  Next question <ArrowRightIcon />
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      <aside className="space-y-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">This session</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {current && current.diagnostic_progress < current.diagnostic_total && (
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Diagnostic</span>
                  <span>
                    {current.diagnostic_progress}/{current.diagnostic_total}
                  </span>
                </div>
                <Progress value={(current.diagnostic_progress / current.diagnostic_total) * 100} />
              </div>
            )}
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-lg border p-2">
                <p className="text-xs text-muted-foreground">Answered</p>
                <p className="text-lg font-semibold tabular-nums">{stats.answered}</p>
              </div>
              <div className="rounded-lg border p-2">
                <p className="text-xs text-muted-foreground">Accuracy</p>
                <p className="text-lg font-semibold tabular-nums">
                  {stats.answered ? pct(stats.correct / stats.answered) : "–"}
                </p>
              </div>
            </div>
            <Button variant="outline" size="sm" className="w-full" asChild>
              <Link href="/map">
                <MapIcon /> Open knowledge map
              </Link>
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Why we ask “how sure?”</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-1.5 text-xs">
            <div className="rounded-md bg-emerald-500/10 p-2"><b>Sure + right</b><br />mastered signal</div>
            <div className="rounded-md bg-amber-500/10 p-2"><b>Guess + right</b><br />fragile, needs practice</div>
            <div className="rounded-md bg-rose-500/10 p-2"><b>Sure + wrong</b><br />misconception → trace root</div>
            <div className="rounded-md bg-orange-500/10 p-2"><b>Guess + wrong</b><br />knowledge gap</div>
          </CardContent>
        </Card>
      </aside>
    </div>
  );
}
