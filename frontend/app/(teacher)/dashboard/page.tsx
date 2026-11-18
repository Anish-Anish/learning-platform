"use client";

import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangleIcon, BotIcon, ExternalLinkIcon, InfoIcon, SproutIcon, UsersIcon } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { StateLegend } from "@/components/graph/skill-tree";
import { StateBadge } from "@/components/state-badge";
import { ClassHeatmap } from "@/components/teacher/heatmap";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useReport } from "@/lib/queries/student";
import { useActiveSubjectName } from "@/lib/queries/studio";
import { useAlerts, useHeatmap } from "@/lib/queries/teacher";
import { pct } from "@/lib/states";
import { cn } from "@/lib/utils";

function StudentSheet({ studentId, name, onClose }: { studentId: string | null; name?: string; onClose: () => void }) {
  const report = useReport(studentId ?? "");
  return (
    <Sheet open={!!studentId} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full sm:max-w-lg" data-accent="teal">
        <SheetHeader>
          <SheetTitle>{name}</SheetTitle>
          <SheetDescription className="font-mono text-xs">{studentId}</SheetDescription>
        </SheetHeader>
        {report.data ? (
          <ScrollArea className="h-[calc(100vh-8rem)] px-4">
            <div className="space-y-4 pb-6">
              <div className="grid grid-cols-3 gap-2 text-center text-sm">
                <div className="rounded-lg border p-2">
                  <p className="text-xs text-muted-foreground">Answers</p>
                  <p className="font-semibold">{report.data.attempts_total}</p>
                </div>
                <div className="rounded-lg border p-2">
                  <p className="text-xs text-muted-foreground">Accuracy</p>
                  <p className="font-semibold">{pct(report.data.accuracy)}</p>
                </div>
                <div className="rounded-lg border p-2">
                  <p className="text-xs text-muted-foreground">Calibration</p>
                  <p className="font-semibold">{pct(report.data.calibration.score)}</p>
                </div>
              </div>
              <div>
                <p className="mb-2 text-sm font-medium">Root gaps</p>
                <div className="space-y-2">
                  {report.data.root_gaps.map((g) => (
                    <div key={g.concept_id} className="rounded-lg border p-3 text-sm">
                      <div className="mb-1 flex items-center gap-2">
                        <span className="font-medium">{g.concept_name}</span>
                        <StateBadge state={g.state} />
                      </div>
                      {g.misconception_text && <p className="text-muted-foreground">“{g.misconception_text}”</p>}
                      <ul className="mt-1.5 space-y-0.5 text-xs text-muted-foreground">
                        {g.evidence.slice(0, 3).map((e, i) => (
                          <li key={i}>• {e}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                  {report.data.root_gaps.length === 0 && <p className="text-sm text-muted-foreground">No root gaps right now.</p>}
                </div>
              </div>
              <StateLegend counts={report.data.state_counts} />
              <Button asChild className="w-full">
                <Link href={`/students/${studentId}`}>
                  Open full profile <ExternalLinkIcon />
                </Link>
              </Button>
            </div>
          </ScrollArea>
        ) : (
          <div className="space-y-2 px-4">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

export default function DashboardPage() {
  const heatmap = useHeatmap();
  const alerts = useAlerts();
  const qc = useQueryClient();
  const subjectName = useActiveSubjectName();
  const [student, setStudent] = useState<string | null>(null);
  const [focusConcept, setFocusConcept] = useState<string | null>(null);
  const [simming, setSimming] = useState(false);
  const names = useMemo(() => Object.fromEntries((heatmap.data?.students ?? []).map((s) => [s.id, s.display_name])), [heatmap.data]);
  const conceptNames = useMemo(() => Object.fromEntries((heatmap.data?.concepts ?? []).map((c) => [c.id, c.name])), [heatmap.data]);
  const active = (heatmap.data?.students ?? []).filter((s) => s.attempts > 0);
  const classMastery = useMemo(() => {
    const cells = (heatmap.data?.cells ?? []).filter((c) => c.state !== "locked" && c.state !== "not_started");
    return cells.length ? cells.reduce((s, c) => s + c.mastery, 0) / cells.length : 0;
  }, [heatmap.data]);

  async function runSim() {
    setSimming(true);
    const t = toast.loading("Running 30 simulated students through the real API…");
    try {
      await api.simRun(30);
      toast.success("Simulation finished", { id: t });
      await qc.invalidateQueries();
    } catch (e) {
      toast.error((e as Error).message, { id: t });
    } finally {
      setSimming(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Class dashboard</h1>
          <p className="text-sm text-muted-foreground">{subjectName} · live (refreshes every 5s)</p>
        </div>
        <Button variant="outline" onClick={runSim} disabled={simming}>
          <BotIcon /> {simming ? "Simulating…" : "Run class simulator"}
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-4">
        {[
          { label: "Active students", value: active.length, icon: UsersIcon },
          { label: "Avg mastery (started concepts)", value: pct(classMastery), icon: SproutIcon },
          { label: "Critical alerts", value: (alerts.data?.alerts ?? []).filter((a) => a.severity === "critical").length, icon: AlertTriangleIcon },
          { label: "Misconception clusters", value: alerts.data?.clusters.length ?? 0, icon: InfoIcon },
        ].map((t) => (
          <Card key={t.label} className="py-4">
            <CardContent className="flex items-center gap-3">
              <span className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary">
                <t.icon className="size-4" />
              </span>
              <div>
                <p className="text-xs text-muted-foreground">{t.label}</p>
                <p className="text-xl font-semibold tabular-nums">{t.value}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>Student × concept heatmap</CardTitle>
            <CardDescription>Colour = state, intensity = mastery. Click a student for details.</CardDescription>
            <StateLegend />
          </CardHeader>
          <CardContent>
            {heatmap.isLoading ? (
              <Skeleton className="h-96 w-full" />
            ) : heatmap.data && active.length ? (
              <ClassHeatmap data={heatmap.data} onStudent={setStudent} highlightConcept={focusConcept} />
            ) : (
              <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                No student activity yet. Run the class simulator or have a student start learning.
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>Alerts</CardTitle>
              <CardDescription>Every alert comes with its reason.</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[340px] pr-3">
                <div className="space-y-2">
                  {(alerts.data?.alerts ?? []).map((a) => (
                    <Alert
                      key={a.id}
                      variant={a.severity === "critical" ? "destructive" : "default"}
                      className={cn("cursor-pointer", a.severity === "warning" && "border-amber-500/50")}
                      onClick={() => (a.student_id ? setStudent(a.student_id) : setFocusConcept(a.concept_id))}
                    >
                      {a.severity === "critical" ? <AlertTriangleIcon /> : <InfoIcon />}
                      <AlertTitle className="line-clamp-none">{a.message}</AlertTitle>
                      <AlertDescription>{a.reason}</AlertDescription>
                    </Alert>
                  ))}
                  {alerts.data && alerts.data.alerts.length === 0 && <p className="text-sm text-muted-foreground">All quiet.</p>}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Misconception clusters</CardTitle>
              <CardDescription>Students grouped by shared active misconceptions, with the diagnosed root.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(alerts.data?.clusters ?? []).slice(0, 6).map((c) => (
                <button
                  key={c.misconception_id}
                  onClick={() => setFocusConcept(focusConcept === c.concept_id ? null : c.concept_id)}
                  className={cn(
                    "w-full space-y-1.5 rounded-lg border p-3 text-left text-sm transition-colors hover:bg-muted/60",
                    focusConcept === c.concept_id && "border-primary",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium">“{c.description}”</span>
                    <Badge variant="secondary" className="shrink-0 tabular-nums">
                      {pct(c.share)}
                    </Badge>
                  </div>
                  <Progress value={c.share * 100} className="h-1.5" />
                  <p className="text-xs text-muted-foreground">
                    Root: <b>{conceptNames[c.root_concept_id ?? c.concept_id] ?? c.root_concept_id}</b> ·{" "}
                    {c.student_ids.slice(0, 4).map((s) => names[s] ?? s).join(", ")}
                    {c.student_ids.length > 4 && ` +${c.student_ids.length - 4}`}
                  </p>
                </button>
              ))}
              {alerts.data && alerts.data.clusters.length === 0 && <p className="text-sm text-muted-foreground">No shared misconceptions.</p>}
            </CardContent>
          </Card>
        </div>
      </div>

      <StudentSheet studentId={student} name={student ? names[student] : undefined} onClose={() => setStudent(null)} />
    </div>
  );
}
