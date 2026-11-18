"use client";

import { BotIcon, GaugeIcon, SendIcon, ShieldAlertIcon, UserIcon } from "lucide-react";
import { motion } from "motion/react";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { announceRewards } from "@/components/game/rewards";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useConcepts } from "@/lib/queries/student";
import { useSession } from "@/lib/store";
import type { TeachScore } from "@/lib/types";
import { cn } from "@/lib/utils";

type Msg = { role: "student" | "bot"; text: string; offTopic?: boolean };

export default function TeachPage() {
  const { concept } = useParams<{ concept: string }>();
  const studentId = useSession((s) => s.studentId);
  const concepts = useConcepts();
  const info = concepts.data?.find((c) => c.id === concept);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [coverage, setCoverage] = useState({ pct: 0, covered: [] as string[] });
  const [score, setScore] = useState<TeachScore | null>(null);
  const [scoring, setScoring] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const total = info?.key_points.length ?? 4;

  async function send() {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");
    setStreaming(true);
    setMessages((m) => [...m, { role: "student", text }, { role: "bot", text: "" }]);
    try {
      await api.streamTeach(concept, { student_id: studentId, session_id: sessionId, message: text }, (event, data) => {
        const d = data as Record<string, unknown>;
        if (event === "session") setSessionId(d.session_id as string);
        else if (event === "delta")
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { ...copy[copy.length - 1], text: copy[copy.length - 1].text + (d.text as string) };
            return copy;
          });
        else if (event === "done") {
          setCoverage({ pct: d.coverage as number, covered: d.covered_points as string[] });
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { role: "bot", text: d.reply as string, offTopic: d.on_topic === false };
            return copy;
          });
        }
      });
    } catch (e) {
      toast.error((e as Error).message);
      setMessages((m) => m.slice(0, -1));
    } finally {
      setStreaming(false);
    }
  }

  async function finish() {
    if (!sessionId) return;
    setScoring(true);
    try {
      const s = await api.teachScore(sessionId);
      setScore(s);
      announceRewards({ ...s, unlocks: [] });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setScoring(false);
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
      <Card className="flex h-[calc(100vh-9rem)] min-h-[520px] flex-col">
        <CardHeader className="border-b">
          <CardTitle className="flex items-center gap-2">
            <BotIcon className="size-5 text-primary" /> Teach Byte: {info?.name ?? concept}
          </CardTitle>
          <CardDescription>Explain it in your own words. Byte will ask naive follow-ups. No lecturing allowed (for Byte).</CardDescription>
        </CardHeader>
        <CardContent className="flex-1 space-y-3 overflow-y-auto py-4">
          {messages.length === 0 && (
            <div className="flex gap-3">
              <span className="grid size-8 shrink-0 place-items-center rounded-full bg-primary/15 text-primary">
                <BotIcon className="size-4" />
              </span>
              <div className="rounded-2xl rounded-tl-sm bg-muted px-3.5 py-2.5 text-sm">
                Hi! I&apos;m Byte. My exam on <b>{info?.name ?? concept}</b> is tomorrow and I&apos;m so lost. Can you explain it to me? 🥺
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn("flex gap-3", m.role === "student" && "flex-row-reverse")}
            >
              <span
                className={cn(
                  "grid size-8 shrink-0 place-items-center rounded-full",
                  m.role === "bot" ? "bg-primary/15 text-primary" : "bg-foreground text-background",
                )}
              >
                {m.role === "bot" ? <BotIcon className="size-4" /> : <UserIcon className="size-4" />}
              </span>
              <div
                className={cn(
                  "max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm whitespace-pre-wrap",
                  m.role === "bot" ? "rounded-tl-sm bg-muted" : "rounded-tr-sm bg-primary text-primary-foreground",
                  m.role === "bot" && streaming && i === messages.length - 1 && "rw-caret",
                )}
              >
                {m.text}
                {m.offTopic && (
                  <span className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground">
                    <ShieldAlertIcon className="size-3" /> steering back on topic
                  </span>
                )}
              </div>
            </motion.div>
          ))}
          <div ref={bottom} />
        </CardContent>
        <CardFooter className="gap-2 border-t pt-4">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            maxLength={1000}
            placeholder="Explain it like you would to a friend… (Enter to send)"
            className="min-h-12 flex-1 resize-none"
          />
          <Button onClick={send} disabled={!input.trim() || streaming} size="icon-lg" aria-label="Send">
            <SendIcon />
          </Button>
        </CardFooter>
      </Card>

      <aside className="space-y-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <GaugeIcon className="size-4 text-primary" /> Explanation completeness
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-end justify-between">
              <span className="text-3xl font-semibold tabular-nums">{Math.round(coverage.pct * 100)}%</span>
              <span className="text-xs text-muted-foreground">
                {coverage.covered.length}/{total} key ideas
              </span>
            </div>
            <Progress value={coverage.pct * 100} />
            {coverage.covered.length > 0 && (
              <ul className="space-y-1 text-xs">
                {coverage.covered.map((c) => (
                  <li key={c} className="flex gap-1.5 text-emerald-700 dark:text-emerald-400">✓ {c}</li>
                ))}
              </ul>
            )}
            <p className="text-[11px] text-muted-foreground">
              Live estimate. The final score is graded separately and only affects XP, never your mastery.
            </p>
          </CardContent>
        </Card>
        <Button className="w-full" size="lg" disabled={!sessionId || scoring || streaming} onClick={finish}>
          {scoring ? "Grading…" : "I'm done, grade my teaching"}
        </Button>
      </aside>

      <Dialog open={!!score} onOpenChange={(o) => !o && setScore(null)}>
        <DialogContent>
          {score && (
            <>
              <DialogHeader>
                <DialogTitle className="text-center text-4xl tabular-nums">{score.score}/100</DialogTitle>
                <DialogDescription className="text-center">{score.feedback}</DialogDescription>
              </DialogHeader>
              <div className="grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <p className="mb-1 text-xs font-medium text-emerald-600">Covered</p>
                  <ul className="space-y-1">{score.covered_points.map((p) => <li key={p}>✓ {p}</li>)}</ul>
                </div>
                <div>
                  <p className="mb-1 text-xs font-medium text-amber-600">To add next time</p>
                  <ul className="space-y-1">{score.missing_points.map((p) => <li key={p}>• {p}</li>)}</ul>
                </div>
              </div>
              {score.misconceptions_detected.length > 0 && (
                <p className="rounded-md bg-rose-500/10 p-2 text-sm">Watch out: {score.misconceptions_detected.join("; ")}</p>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
