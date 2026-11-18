"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ArrowRightIcon, BookOpenIcon, HeartIcon, MapIcon, RotateCcwIcon, SparklesIcon, XIcon } from "lucide-react";
import { AnimatePresence, motion, useAnimationControls } from "motion/react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { celebrate } from "@/components/game/confetti";
import { Mascot, type Mood } from "@/components/game/mascot";
import { announceRewards } from "@/components/game/rewards";
import { StudyScroll } from "@/components/game/study-scroll";
import { Stars } from "@/components/game/world-map";
import { QuestionCard, type SubmitPayload } from "@/components/quiz/question-card";
import { StateBadge } from "@/components/state-badge";
import { LessonPanel } from "@/components/tutor/lesson-panel";
import { RootCard, RootCardSkeleton } from "@/components/tutor/root-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { WORLD_THEME } from "@/lib/avatars";
import { api } from "@/lib/api";
import { useConceptDetail, useWorld } from "@/lib/queries/game";
import { useDiagnosis } from "@/lib/queries/student";
import { sfx } from "@/lib/sound";
import { useSession } from "@/lib/store";
import type { LevelAnswer, LevelRun, QuestionPublic, Unlock, XPEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

type Stage = "intro" | "play" | "lesson";

const CHEERS = ["Nice!", "Boom! 💥", "You got it!", "Big brain move 🧠", "Clean!"];
const OOPS = ["Ouch! Let's find the root.", "Not quite… I've seen this trap before.", "Hmm, a myth got you!"];

function Hearts({ hearts, max }: { hearts: number; max: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: max }).map((_, i) => {
        const alive = i < hearts;
        return (
          <motion.span
            key={i}
            animate={alive ? { scale: [1, 1.15, 1] } : { scale: [1.4, 0.8], rotate: [0, -20], opacity: [1, 0.35] }}
            transition={alive ? { repeat: Infinity, duration: 1.6, delay: i * 0.2 } : { duration: 0.5 }}
          >
            <HeartIcon className={cn("size-6", alive ? "fill-rose-500 text-rose-600" : "fill-muted text-muted-foreground")} />
          </motion.span>
        );
      })}
    </div>
  );
}

export default function LevelPage() {
  const { concept } = useParams<{ concept: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const studentId = useSession((s) => s.studentId);
  const sessionId = useSession((s) => s.sessionId);
  const world = useWorld(studentId);
  const detail = useConceptDetail(concept);
  const [stage, setStage] = useState<Stage>("intro");
  const [run, setRun] = useState<LevelRun | null>(null);
  const [bestBefore, setBestBefore] = useState(0);
  const [last, setLast] = useState<(LevelAnswer & { selected: string }) | null>(null);
  const [results, setResults] = useState<(boolean | null)[]>([]);
  const [answered, setAnswered] = useState<QuestionPublic | null>(null);
  const [showEnd, setShowEnd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mood, setMood] = useState<Mood>("think");
  const [say, setSay] = useState<string | null>("Ready, hero?");
  const [earned, setEarned] = useState<{ xp: XPEvent[]; unlocks: Unlock[] }>({ xp: [], unlocks: [] });
  const [lessonFor, setLessonFor] = useState<{ conceptId: string; misconceptionId?: string | null } | null>(null);
  const [scroll, setScroll] = useState(false);
  const shake = useAnimationControls();
  const dx = useDiagnosis(last?.attempt.diagnosis.id);

  const allWorlds = world.data?.worlds ?? [];
  const levelWorld = allWorlds.find((w) => w.levels.some((l) => l.concept_id === concept));
  const levelInfo = levelWorld ? { world: levelWorld, level: levelWorld.levels.find((l) => l.concept_id === concept)! } : null;
  const names = Object.fromEntries(allWorlds.flatMap((w) => w.levels).map((l) => [l.concept_id, l.name]));
  const theme = WORLD_THEME[levelInfo?.world.color ?? "violet"] ?? WORLD_THEME.violet;
  const finished = !!run && run.status !== "active" && showEnd && stage === "play";

  // Hero moments on the end screens.
  useEffect(() => {
    if (!finished || !run) return;
    if (run.status === "completed") {
      sfx.win();
      if (run.stars === 3 || last?.new_best) void celebrate(run.stars === 3 ? "boss" : "unlock");
    } else {
      sfx.lose();
    }
  }, [finished, run, last?.new_best]);

  async function start(restart = false) {
    setBusy(true);
    setError(null);
    try {
      const r = await api.startLevel(concept, studentId, restart);
      setRun(r.run);
      setBestBefore(r.best_stars);
      setLast(null);
      setShowEnd(false);
      setAnswered(null);
      setResults(Array.from({ length: r.run.index }, () => null));
      setEarned({ xp: [], unlocks: [] });
      setStage("play");
      setMood("think");
      setSay("Hmm… let's see.");
      sfx.powerup();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onAnswer(p: SubmitPayload) {
    if (!run?.question) return;
    setAnswered(run.question);
    setBusy(true);
    try {
      const r = await api.levelAnswer(run.id, {
        option_id: p.optionId, confidence: p.confidence, hints_used: p.hintsUsed, time_ms: p.timeMs, session_id: sessionId,
      });
      setLast({ ...r, selected: p.optionId });
      setResults((xs) => [...xs, r.attempt.is_correct]);
      setEarned((e) => ({ xp: [...e.xp, ...r.attempt.xp_events.filter((x) => x.amount > 0)], unlocks: [...e.unlocks, ...r.attempt.unlocks] }));
      announceRewards(r.attempt);
      if (r.attempt.is_correct) {
        const c = r.run.combo;
        if (c >= 3) {
          sfx.combo(c);
          setMood("fever");
          setSay(`ON FIRE! x${c} combo 🔥`);
        } else {
          sfx.correct();
          setMood("happy");
          setSay(CHEERS[(r.run.index + c) % CHEERS.length]);
        }
      } else {
        sfx.wrong();
        setTimeout(() => sfx.heart(), 180);
        void shake.start({ x: [0, -12, 12, -8, 8, -3, 0], transition: { duration: 0.45 } });
        setMood("sad");
        setSay(r.attempt.signal === "misconception_signal" ? OOPS[r.run.index % OOPS.length] : "That's a gap. We can fill it!");
      }
      setRun(r.run);
      if (r.run.status !== "active") {
        void qc.invalidateQueries({ queryKey: ["profile", studentId] });
        void qc.invalidateQueries({ queryKey: ["world", studentId] });
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function activateFifty() {
    if (!run) return;
    try {
      const r = await api.levelFifty(run.id);
      sfx.powerup();
      setRun(r.run);
      setSay("Poof! Two choices left. (Max 2⭐ now)");
      setMood("happy");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function next() {
    if (run && run.status !== "active") {
      setShowEnd(true);
      return;
    }
    setLast(null);
    setMood(run && run.combo >= 3 ? "fever" : "think");
    setSay(run && run.combo >= 3 ? `x${run.combo} combo. Keep it going!` : "Next one…");
  }

  // ------------------------------------------------------------------ screens
  if (error && !run) {
    return (
      <Card className="mx-auto max-w-md text-center">
        <CardContent className="space-y-3 pt-6">
          <Mascot mood="sad" size={80} className="mx-auto" />
          <p className="font-semibold">{error}</p>
          <Button asChild>
            <Link href="/play">Back to the map</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (stage === "lesson" && lessonFor) {
    return (
      <div className="mx-auto max-w-3xl space-y-3">
        <Button variant="ghost" size="sm" onClick={() => setStage("play")}>
          ← Back to the mission
        </Button>
        <LessonPanel
          conceptId={lessonFor.conceptId}
          misconceptionId={lessonFor.misconceptionId}
          studentId={studentId}
          doneLabel={run?.status === "active" ? "Back to the mission" : "Try the level again"}
          onDone={() => {
            if (run?.status === "active") {
              setStage("play");
              next();
            } else {
              void start(true);
            }
          }}
        />
      </div>
    );
  }

  if (stage === "intro") {
    return (
      <div className="mx-auto max-w-2xl">
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          className={cn("relative overflow-hidden rounded-3xl bg-gradient-to-br p-6 text-center text-white shadow-2xl", theme.grad)}
        >
          <div className="pointer-events-none absolute inset-0 opacity-20 rw-grid-bg" />
          <motion.span className="pointer-events-none absolute top-4 right-6 text-6xl opacity-40" animate={{ rotate: [0, 10, -10, 0] }} transition={{ repeat: Infinity, duration: 5 }}>
            {levelInfo?.world.emoji ?? "🗺️"}
          </motion.span>
          <p className="text-xs font-bold tracking-widest uppercase opacity-80">{levelInfo?.world.name ?? "Adventure"}</p>
          <h1 className="mt-1 text-3xl font-black tracking-tight drop-shadow">{detail.data?.name ?? <Skeleton className="mx-auto h-8 w-64" />}</h1>
          <p className="mx-auto mt-1 max-w-md text-sm opacity-90">{detail.data?.description}</p>
          <div className="mt-12 mb-5 flex justify-center">
            <Mascot mood={levelInfo?.level.has_myth ? "think" : "idle"} size={110} say={levelInfo?.level.has_myth ? "A myth hides here. Ready to bust it?" : "Ready, hero?"} />
          </div>
          {levelInfo && <Stars n={levelInfo.level.stars} size={28} className="justify-center" />}
          <div className="mx-auto mt-4 grid max-w-md grid-cols-3 gap-2 text-xs font-medium">
            <div className="rounded-xl bg-black/20 p-2">❤️ 3 hearts</div>
            <div className="rounded-xl bg-black/20 p-2">🔥 Combos</div>
            <div className="rounded-xl bg-black/20 p-2">✂️ One 50/50</div>
          </div>
          <p className="mt-3 text-xs opacity-85">⭐ finish · ⭐⭐ at most 1 mistake · ⭐⭐⭐ flawless + every answer marked “Sure”</p>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <Button size="lg" variant="outline" className="border-white/50 bg-white/10 text-white hover:bg-white/20 hover:text-white" onClick={() => setScroll(true)}>
              <BookOpenIcon /> Study scroll first
            </Button>
            <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
              <Button size="lg" disabled={busy} className="bg-white px-8 text-base font-black text-violet-700 shadow-xl hover:bg-white/90" onClick={() => start(false)}>
                {busy ? "Loading…" : "START ▶"}
              </Button>
            </motion.div>
          </div>
          {error && <p className="mt-3 rounded-lg bg-black/30 p-2 text-sm">{error}</p>}
        </motion.div>
        <StudyScroll conceptId={concept} open={scroll} onOpenChange={setScroll} />
      </div>
    );
  }

  if (!run) return <Skeleton className="mx-auto h-[520px] max-w-3xl rounded-2xl" />;

  // ---------------------------------------------------------------- end screens
  if (finished) {
    const won = run.status === "completed";
    return (
      <div className="mx-auto max-w-xl">
        <motion.div
          initial={{ scale: 0.8, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 200, damping: 18 }}
          className={cn(
            "relative overflow-hidden rounded-3xl p-6 text-center text-white shadow-2xl",
            won ? cn("bg-gradient-to-br", theme.grad) : "bg-gradient-to-br from-slate-600 to-slate-900",
          )}
        >
          <div className="pointer-events-none absolute inset-0 opacity-20 rw-grid-bg" />
          {won && last?.new_best && (
            <motion.div
              initial={{ rotate: -20, scale: 0 }}
              animate={{ rotate: -12, scale: 1 }}
              transition={{ delay: 1.6, type: "spring" }}
              className="absolute top-4 -left-1 rounded-r-lg bg-amber-400 px-3 py-1 text-xs font-black text-amber-950 shadow"
            >
              NEW BEST!
            </motion.div>
          )}
          <Mascot mood={won ? "party" : "sad"} size={96} className="mx-auto" />
          <motion.h1
            initial={{ scale: 0.5 }}
            animate={{ scale: 1 }}
            className="mt-2 text-3xl font-black tracking-tight drop-shadow"
          >
            {won ? (run.stars === 3 ? "PERFECT RUN!" : run.stars === 2 ? "GREAT JOB!" : "LEVEL CLEARED!") : "OUT OF HEARTS"}
          </motion.h1>
          <p className="text-sm opacity-90">{run.concept_name}</p>
          {won ? (
            <div className="my-5 flex justify-center gap-3">
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  initial={{ scale: 0, rotate: -180 }}
                  animate={{ scale: i < run.stars ? 1 : 0.8, rotate: 0 }}
                  transition={{ delay: 0.4 + i * 0.45, type: "spring", stiffness: 260, damping: 12 }}
                  onAnimationComplete={() => i < run.stars && sfx.star(i)}
                >
                  <svg viewBox="0 0 24 24" className={cn("size-16 drop-shadow-lg", i === 1 && "-mt-3 size-20")}>
                    <path
                      d="M12 2l2.9 6.9 7.1.6-5.4 4.7 1.7 7-6.3-3.9-6.3 3.9 1.7-7L2 9.5l7.1-.6z"
                      fill={i < run.stars ? "#fbbf24" : "rgba(0,0,0,0.25)"}
                      stroke={i < run.stars ? "#b45309" : "rgba(255,255,255,0.3)"}
                      strokeWidth="1"
                    />
                  </svg>
                </motion.div>
              ))}
            </div>
          ) : (
            <p className="mx-auto my-4 max-w-sm text-sm opacity-90">
              Every wrong answer told the tutor something. Train with the mentor on the root gap, then try again.
            </p>
          )}
          <div className="grid grid-cols-3 gap-2 text-sm">
            <div className="rounded-xl bg-black/20 p-2">
              <p className="text-[11px] opacity-80">Correct</p>
              <p className="text-lg font-black tabular-nums">
                {run.correct}/{run.total}
              </p>
            </div>
            <div className="rounded-xl bg-black/20 p-2">
              <p className="text-[11px] opacity-80">Best combo</p>
              <p className="text-lg font-black tabular-nums">x{run.best_combo}</p>
            </div>
            <div className="rounded-xl bg-black/20 p-2">
              <p className="text-[11px] opacity-80">Hearts left</p>
              <p className="text-lg font-black tabular-nums">{Math.max(0, run.hearts)}</p>
            </div>
          </div>
          {(earned.xp.length > 0 || earned.unlocks.length > 0) && (
            <div className="mt-4 space-y-1.5 rounded-xl bg-black/20 p-3 text-left text-sm">
              {earned.xp.map((x, i) => (
                <motion.p key={`x${i}`} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 1.8 + i * 0.15 }} className="flex justify-between">
                  <span className="truncate">{x.reason}</span>
                  <b className="text-amber-300">+{x.amount} XP</b>
                </motion.p>
              ))}
              {earned.unlocks.map((u) => (
                <motion.p key={u.concept_id} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 2 }} className="font-bold">
                  🔓 New level unlocked: {u.concept_name}
                </motion.p>
              ))}
            </div>
          )}
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            {won ? (
              <Button
                size="lg"
                className="bg-white font-black text-violet-700 hover:bg-white/90"
                onClick={async () => {
                  const w = await world.refetch();
                  const nextId = w.data?.recommended_concept_id;
                  router.push(nextId && nextId !== concept ? `/play/${nextId}` : "/play");
                }}
              >
                Next quest <ArrowRightIcon />
              </Button>
            ) : (
              <Button
                size="lg"
                className="bg-white font-black text-slate-800 hover:bg-white/90"
                onClick={() => {
                  setLessonFor({ conceptId: concept });
                  setStage("lesson");
                }}
              >
                <SparklesIcon /> Train with the mentor
              </Button>
            )}
            <Button size="lg" variant="outline" className="border-white/50 bg-white/10 text-white hover:bg-white/20 hover:text-white" onClick={() => start(true)}>
              <RotateCcwIcon /> {won && run.stars < 3 ? "Go for 3 ⭐" : "Play again"}
            </Button>
            <Button size="lg" variant="ghost" className="text-white hover:bg-white/10 hover:text-white" asChild>
              <Link href="/play">
                <MapIcon /> Map
              </Link>
            </Button>
          </div>
          {bestBefore > 0 && won && !last?.new_best && <p className="mt-3 text-xs opacity-75">Your best on this level: {bestBefore} ⭐</p>}
        </motion.div>
      </div>
    );
  }

  // ---------------------------------------------------------------- playing
  const q = last ? null : run.question;
  const dxData = dx.data;
  const fever = run.combo >= 3;
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      {/* HUD */}
      <div className="sticky top-14 z-30 -mx-4 flex items-center gap-3 border-b bg-background/85 px-4 py-2.5 backdrop-blur">
        <Button variant="ghost" size="icon-sm" asChild aria-label="Exit to map">
          <Link href="/play">
            <XIcon />
          </Link>
        </Button>
        <div className="flex flex-1 gap-1">
          {Array.from({ length: run.total }).map((_, i) => (
            <motion.div
              key={i}
              className={cn(
                "h-3 flex-1 rounded-full",
                i < results.length
                  ? results[i] === null
                    ? "bg-primary/60"
                    : results[i]
                      ? "bg-emerald-500"
                      : "bg-rose-500"
                  : i === results.length
                    ? "bg-primary/40"
                    : "bg-muted",
              )}
              animate={i === results.length ? { opacity: [0.5, 1, 0.5] } : {}}
              transition={{ repeat: Infinity, duration: 1.4 }}
            />
          ))}
        </div>
        <AnimatePresence mode="popLayout">
          {run.combo >= 2 && (
            <motion.span
              key={run.combo}
              initial={{ scale: 2, rotate: -15, opacity: 0 }}
              animate={{ scale: 1, rotate: 0, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              className={cn(
                "rounded-full px-2.5 py-0.5 text-sm font-black text-white shadow",
                fever ? "bg-gradient-to-r from-orange-500 to-rose-500" : "bg-amber-500",
              )}
            >
              🔥 x{run.combo}
            </motion.span>
          )}
        </AnimatePresence>
        <Hearts hearts={run.hearts} max={run.max_hearts} />
      </div>

      <div className="flex items-end gap-3">
        <Mascot mood={mood} size={74} say={say} className="mt-8 shrink-0" />
        <div className="flex-1 pb-2">
          <p className="text-xs font-bold tracking-widest text-muted-foreground uppercase">
            {levelInfo?.world.emoji} {levelInfo?.world.name} · Question {Math.min(run.index + (last ? 0 : 1), run.total)} of {run.total}
          </p>
          <p className="text-lg font-black tracking-tight">{run.concept_name}</p>
        </div>
        {q && (
          <Button
            variant="outline"
            size="sm"
            disabled={run.fifty_left <= 0 || busy || (run.removed_option_ids?.length ?? 0) > 0}
            onClick={activateFifty}
            className="gap-1 font-bold"
            title="Remove wrong options. Caps this run at 2 stars and counts as a hint."
          >
            ✂️ 50/50 <span className="text-xs text-muted-foreground">({run.fifty_left})</span>
          </Button>
        )}
      </div>

      <motion.div animate={shake} className={cn("relative rounded-2xl transition-shadow", fever && "shadow-[0_0_0_3px_rgba(249,115,22,0.6),0_0_40px_rgba(249,115,22,0.35)]")}>
        {fever && (
          <motion.div
            className="pointer-events-none absolute -inset-1 rounded-2xl bg-gradient-to-r from-orange-500/20 via-rose-500/20 to-amber-400/20"
            animate={{ opacity: [0.4, 1, 0.4] }}
            transition={{ repeat: Infinity, duration: 1 }}
          />
        )}
        {q ? (
          <QuestionCard
            key={q.id + run.index}
            question={q}
            phase="level"
            studentId={studentId}
            onSubmit={onAnswer}
            submitting={busy}
            removedOptionIds={run.removed_option_ids ?? []}
            submitLabel="Lock it in!"
          />
        ) : last && answered ? (
          <QuestionCard
            key={`done-${last.attempt.attempt_id}`}
            question={answered}
            phase="level"
            studentId={studentId}
            onSubmit={() => undefined}
            result={{ selected: last.selected, correct: last.attempt.correct_option_id, isCorrect: last.attempt.is_correct }}
          />
        ) : null}
      </motion.div>

      {last && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
          <Card className={cn("border-l-4", last.attempt.is_correct ? "border-l-emerald-500" : "border-l-rose-500")}>
            <CardContent className="flex flex-col gap-2 pt-5 sm:flex-row sm:items-start">
              <div className="flex-1 space-y-1">
                <p className="font-bold">{last.attempt.is_correct ? "✅ Correct!" : last.attempt.signal === "misconception_signal" ? "💔 A myth got you" : "💔 Not quite"}</p>
                <p className="text-sm text-muted-foreground">{last.attempt.explanation}</p>
              </div>
              <StateBadge state={last.attempt.concept_state.state} />
            </CardContent>
          </Card>
          {last.attempt.diagnosis.id &&
            (!dxData || dxData.status === "pending" ? (
              <RootCardSkeleton />
            ) : dxData.status !== "rejected" ? (
              <RootCard
                dx={dxData}
                names={names}
                lessonLabel="Train with the mentor"
                continueLabel="Keep playing"
                onLesson={() => {
                  setLessonFor({ conceptId: dxData.root_concept_id ?? concept, misconceptionId: dxData.misconception_id });
                  setStage("lesson");
                }}
                onContinue={next}
                extra={
                  (dxData.probe_concept_id ?? dxData.root_concept_id) && (dxData.probe_concept_id ?? dxData.root_concept_id) !== concept ? (
                    <Button variant="outline" asChild>
                      <Link href={`/play/${dxData.probe_concept_id ?? dxData.root_concept_id}`}>🗺️ Go to that level</Link>
                    </Button>
                  ) : null
                }
              />
            ) : null)}
          <div className="flex justify-end">
            <Button size="lg" className="font-bold" onClick={next}>
              {run.status === "active" ? "Next question" : "See results"} <ArrowRightIcon />
            </Button>
          </div>
        </motion.div>
      )}
    </div>
  );
}
