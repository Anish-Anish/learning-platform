"use client";

import { BookOpenIcon, GraduationCapIcon, PlayIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { celebrate } from "@/components/game/confetti";
import { SkillTree, StateLegend } from "@/components/graph/skill-tree";
import { StateBadge } from "@/components/state-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { flags } from "@/lib/flags";
import { useConcepts, useStudentMap } from "@/lib/queries/student";
import { useActiveSubjectName } from "@/lib/queries/studio";
import { STATE_META } from "@/lib/states";
import { useSession } from "@/lib/store";
import type { MapNode } from "@/lib/types";

export default function MapPage() {
  const studentId = useSession((s) => s.studentId);
  const subjectName = useActiveSubjectName();
  const map = useStudentMap(studentId);
  const concepts = useConcepts();
  const [selected, setSelected] = useState<MapNode | null>(null);
  // Unlock / mastery animation: diff against the states seen on the previous visit (read once at mount).
  const storageKey = `rw-map-${studentId}`;
  const [previous] = useState<Record<string, string>>(() => {
    if (typeof window === "undefined") return {};
    try {
      return JSON.parse(localStorage.getItem(storageKey) ?? "{}");
    } catch {
      return {};
    }
  });
  const changes = useMemo(() => {
    const out: { id: string; name: string; kind: "unlocked" | "mastered" }[] = [];
    if (!map.data || !Object.keys(previous).length) return out;
    for (const n of map.data.nodes) {
      if (previous[n.id] === "locked" && n.state !== "locked") out.push({ id: n.id, name: n.name, kind: "unlocked" });
      else if (previous[n.id] && previous[n.id] !== "mastered" && n.state === "mastered")
        out.push({ id: n.id, name: n.name, kind: "mastered" });
    }
    return out;
  }, [map.data, previous]);
  const pulse = useMemo(() => new Set(changes.map((c) => c.id)), [changes]);
  const announced = useRef(false);
  useEffect(() => {
    if (!map.data) return;
    localStorage.setItem(storageKey, JSON.stringify(Object.fromEntries(map.data.nodes.map((n) => [n.id, n.state]))));
    if (announced.current || !changes.length) return;
    announced.current = true;
    for (const c of changes) {
      if (c.kind === "unlocked") toast(`🔓 ${c.name} unlocked`);
      else toast.success(`${c.name} mastered`);
    }
    void celebrate("unlock");
  }, [map.data, changes, storageKey]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const n of map.data?.nodes ?? []) c[n.state] = (c[n.state] ?? 0) + 1;
    return c;
  }, [map.data]);
  const overall = useMemo(() => {
    const ns = map.data?.nodes ?? [];
    return ns.length ? ns.reduce((s, n) => s + (n.n_attempts ? n.mastery : 0), 0) / ns.length : 0;
  }, [map.data]);
  const concept = concepts.data?.find((c) => c.id === selected?.id);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Knowledge map</h1>
          <p className="text-sm text-muted-foreground">
            {subjectName} skill tree. Concepts unlock when every prerequisite reaches 70% mastery.
          </p>
        </div>
        <div className="w-56 space-y-1">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Overall mastery</span>
            <span className="tabular-nums">{Math.round(overall * 100)}%</span>
          </div>
          <Progress value={overall * 100} />
        </div>
      </div>
      <StateLegend counts={counts} />
      {map.isLoading ? (
        <Skeleton className="h-[640px] w-full rounded-xl" />
      ) : map.error ? (
        <Card>
          <CardHeader>
            <CardTitle>No map yet</CardTitle>
            <CardDescription>Start a learning session first so we know where you are.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link href="/learn">Start learning</Link>
            </Button>
          </CardContent>
        </Card>
      ) : map.data ? (
        <SkillTree map={map.data} pulse={pulse} selectedId={selected?.id} onSelect={setSelected} />
      ) : null}

      <Sheet open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <SheetContent className="w-full sm:max-w-md">
          {selected && (
            <>
              <SheetHeader>
                <SheetTitle>{selected.name}</SheetTitle>
                <SheetDescription>{concept?.description}</SheetDescription>
              </SheetHeader>
              <div className="space-y-5 px-4">
                <div className="flex items-center gap-3">
                  <StateBadge state={selected.state} />
                  <span className="text-sm text-muted-foreground">{STATE_META[selected.state].hint}</span>
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>Mastery estimate</span>
                    <span className="tabular-nums">{Math.round(selected.mastery * 100)}%</span>
                  </div>
                  <Progress value={selected.mastery * 100} />
                  <p className="text-xs text-muted-foreground">{selected.n_attempts} attempt(s). {selected.reason}</p>
                </div>
                {concept && concept.prerequisites.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">Prerequisites</p>
                    <div className="flex flex-wrap gap-1.5">
                      {concept.prerequisites.map((p) => (
                        <span key={p} className="rounded-md border px-2 py-0.5 text-xs">
                          {concepts.data?.find((c) => c.id === p)?.name ?? p}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {concept && selected.state !== "locked" && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">Key ideas</p>
                    <ul className="list-disc space-y-1 pl-4 text-sm">
                      {concept.key_points.map((k) => (
                        <li key={k}>{k}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="flex flex-col gap-2">
                  <Button asChild>
                    <Link href="/learn">
                      <PlayIcon /> Continue learning
                    </Link>
                  </Button>
                  {selected.state !== "locked" && (
                    <Button variant="outline" asChild>
                      <Link href={`/learn?lesson=${selected.id}`}>
                        <BookOpenIcon /> Micro-lesson on this concept
                      </Link>
                    </Button>
                  )}
                  {flags.teach && selected.state !== "locked" && (
                    <Button variant="outline" asChild>
                      <Link href={`/teach/${selected.id}`}>
                        <GraduationCapIcon /> Teach it to the bot
                      </Link>
                    </Button>
                  )}
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
