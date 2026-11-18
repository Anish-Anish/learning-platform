"use client";

import { ArrowRightIcon, HeartIcon, RotateCcwIcon, ShieldIcon, SwordsIcon, TrophyIcon } from "lucide-react";
import { AnimatePresence, motion, useAnimationControls } from "motion/react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { announceRewards } from "@/components/game/rewards";
import { QuestionCard, type SubmitPayload } from "@/components/quiz/question-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useSession } from "@/lib/store";
import type { BossAttemptResponse, BossBattle } from "@/lib/types";
import { cn } from "@/lib/utils";

function BossAvatar({ hurt, dead }: { hurt: number; dead: boolean }) {
  const controls = useAnimationControls();
  useEffect(() => {
    if (hurt) void controls.start({ x: [0, -14, 12, -8, 6, 0], rotate: [0, -4, 4, -2, 0], transition: { duration: 0.5 } });
  }, [hurt, controls]);
  return (
    <motion.div animate={controls} className="relative">
      <motion.svg
        viewBox="0 0 120 120"
        className={cn("size-28 drop-shadow-lg sm:size-32", dead && "grayscale")}
        animate={dead ? { rotate: 90, opacity: 0.4, y: 20 } : { y: [0, -6, 0] }}
        transition={dead ? { duration: 0.8 } : { repeat: Infinity, duration: 2.4, ease: "easeInOut" }}
      >
        <defs>
          <radialGradient id="bossg" cx="50%" cy="40%">
            <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.95" />
            <stop offset="100%" stopColor="var(--primary)" stopOpacity="0.55" />
          </radialGradient>
        </defs>
        <path d="M60 8 C 92 8 108 34 108 62 C 108 92 88 112 60 112 C 32 112 12 92 12 62 C 12 34 28 8 60 8 Z" fill="url(#bossg)" />
        <path d="M30 20 L22 4 L40 16 Z M90 20 L98 4 L80 16 Z" fill="var(--primary)" />
        <circle cx="44" cy="54" r="10" fill="white" />
        <circle cx="76" cy="54" r="10" fill="white" />
        <circle cx={hurt % 2 ? 42 : 46} cy="56" r="5" fill="#111" />
        <circle cx={hurt % 2 ? 74 : 78} cy="56" r="5" fill="#111" />
        <path d="M34 40 L54 46 M86 40 L66 46" stroke="#111" strokeWidth="4" strokeLinecap="round" />
        <path d={dead ? "M42 86 Q60 76 78 86" : "M40 80 Q60 96 80 80"} stroke="#111" strokeWidth="4" fill="none" strokeLinecap="round" />
        <path d="M30 90 C 20 100 18 108 26 114 M90 90 C 100 100 102 108 94 114" stroke="var(--primary)" strokeWidth="5" fill="none" strokeLinecap="round" />
      </motion.svg>
    </motion.div>
  );
}

export default function BossPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const studentId = useSession((s) => s.studentId);
  const [battle, setBattle] = useState<BossBattle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<(BossAttemptResponse & { selected: string }) | null>(null);
  const [hits, setHits] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const id = params.id === "new" ? undefined : params.id;
    api
      .boss(studentId, id)
      .then((b) => {
        if (cancelled) return;
        setBattle(b);
        if (!id) router.replace(`/boss/${b.id}`);
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [params.id, studentId, router]);

  async function answer(p: SubmitPayload) {
    if (!battle) return;
    const q = battle.questions[battle.current_index];
    setBusy(true);
    try {
      const r = await api.bossAttempt(battle.id, { question_id: q.id, option_id: p.optionId, confidence: p.confidence });
      setLast({ ...r, selected: p.optionId });
      if (r.is_correct) setHits((h) => h + 1);
      announceRewards(r);
      setBattle((b) => (b ? { ...b, hp: r.hp, status: r.status } : b));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function next() {
    setBattle((b) => (b && last ? { ...b, current_index: last.current_index } : b));
    setLast(null);
  }

  if (error) {
    return (
      <Card className="mx-auto max-w-lg">
        <CardHeader>
          <CardTitle>No boss to fight yet</CardTitle>
          <CardDescription>{error}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link href="/learn">Keep learning</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }
  if (!battle) return <Skeleton className="mx-auto h-[520px] max-w-3xl rounded-2xl" />;

  const q = battle.questions[battle.current_index];
  const done = battle.status !== "active";
  const hpPct = (battle.hp / battle.max_hp) * 100;

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="relative overflow-hidden rounded-2xl border bg-gradient-to-b from-primary/15 via-background to-background p-5 rw-grid-bg">
        <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-center sm:gap-6">
          <div className="relative">
            <BossAvatar hurt={hits} dead={battle.status === "won"} />
            <AnimatePresence>
              {last?.is_correct && (
                <motion.span
                  key={hits}
                  initial={{ opacity: 0, y: 0, scale: 0.6 }}
                  animate={{ opacity: 1, y: -50, scale: 1.3 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.9 }}
                  className="absolute top-2 left-1/2 -translate-x-1/2 text-3xl font-black text-rose-500 drop-shadow"
                >
                  -{last.damage}
                </motion.span>
              )}
            </AnimatePresence>
          </div>
          <div className="w-full flex-1 space-y-2 text-center sm:text-left">
            <p className="text-xs font-medium tracking-widest text-primary uppercase">Root Boss</p>
            <h1 className="text-2xl font-bold tracking-tight">{battle.name}</h1>
            <p className="rounded-xl border bg-card/80 px-3 py-2 text-sm italic shadow-xs">{battle.taunt}</p>
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1 font-medium">
                  <HeartIcon className="size-3.5 text-rose-500" /> HP
                </span>
                <motion.span key={battle.hp} initial={{ scale: 1.4 }} animate={{ scale: 1 }} className="tabular-nums font-semibold">
                  {battle.hp}/{battle.max_hp}
                </motion.span>
              </div>
              <div className="h-3.5 overflow-hidden rounded-full border bg-muted">
                <motion.div
                  className={cn("h-full rounded-full", hpPct > 50 ? "bg-rose-500" : hpPct > 25 ? "bg-orange-500" : "bg-amber-400")}
                  animate={{ width: `${hpPct}%` }}
                  transition={{ type: "spring", stiffness: 120, damping: 18 }}
                />
              </div>
            </div>
            <div className="flex justify-center gap-1.5 sm:justify-start">
              {battle.questions.map((qq, i) => (
                <span
                  key={qq.id}
                  className={cn(
                    "h-1.5 w-8 rounded-full",
                    i < battle.current_index || (last && i === battle.current_index) ? "bg-primary" : "bg-muted",
                  )}
                />
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              <SwordsIcon className="mr-1 inline size-3.5" />
              Each correct answer deals {battle.damage_per_hit} damage. Questions get harder (Bloom level rises).
            </p>
          </div>
        </div>
      </div>

      {battle.status === "won" ? (
        <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}>
          <Card className="border-emerald-500/50 text-center">
            <CardHeader>
              <TrophyIcon className="mx-auto size-10 text-amber-500" />
              <CardTitle className="text-2xl">Boss defeated!</CardTitle>
              <CardDescription>The myth is busted: misconceptions cleared and locked in.</CardDescription>
            </CardHeader>
            <CardContent className="flex justify-center gap-2">
              <Button asChild>
                <Link href="/map">
                  See your map <ArrowRightIcon />
                </Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href="/learn">Keep learning</Link>
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      ) : battle.status === "lost" ? (
        <Card className="text-center">
          <CardHeader>
            <ShieldIcon className="mx-auto size-10 text-muted-foreground" />
            <CardTitle>The boss survives… for now</CardTitle>
            <CardDescription>Review the lesson for your root gap, then come back stronger.</CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center gap-2">
            <Button onClick={() => router.push("/boss/new")}>
              <RotateCcwIcon /> Rematch
            </Button>
            <Button variant="outline" asChild>
              <Link href="/report">Root report</Link>
            </Button>
          </CardContent>
        </Card>
      ) : q ? (
        <div className="space-y-3">
          <QuestionCard
            key={q.id}
            question={q}
            phase="boss"
            studentId={studentId}
            onSubmit={answer}
            submitting={busy}
            allowHints={false}
            result={last ? { selected: last.selected, correct: last.correct_option_id, isCorrect: last.is_correct } : null}
          />
          {last && (
            <div className="flex items-center gap-3">
              <p className="flex-1 text-sm text-muted-foreground">
                {last.is_correct ? "Direct hit! " : "The boss shrugs it off. "}
                {last.explanation}
              </p>
              {!done && (
                <Button onClick={next}>
                  Next <ArrowRightIcon />
                </Button>
              )}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
