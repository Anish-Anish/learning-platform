"use client";

import { ArrowRightIcon, AwardIcon, FlameIcon, SparklesIcon, SproutIcon, TargetIcon } from "lucide-react";
import Link from "next/link";

import { BloomRadar } from "@/components/charts/bloom-radar";
import { CalibrationMeter } from "@/components/charts/calibration-meter";
import { StateLegend } from "@/components/graph/skill-tree";
import { StateBadge } from "@/components/state-badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { pct } from "@/lib/states";
import type { RootReport } from "@/lib/types";

export function ReportView({ report, names, teacher = false }: { report: RootReport; names: Record<string, string>; teacher?: boolean }) {
  const step = report.next_step;
  const href =
    step.kind === "lesson" && step.concept_id ? `/learn?lesson=${step.concept_id}` : step.kind === "boss" ? "/boss/new" : "/learn";
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        {[
          { icon: SparklesIcon, label: "XP", value: report.xp_total, sub: `Level ${report.level}` },
          { icon: FlameIcon, label: "Streak", value: `${report.streak_days}d`, sub: "consecutive days" },
          { icon: TargetIcon, label: "Accuracy", value: pct(report.accuracy), sub: `${report.attempts_total} answers` },
          { icon: AwardIcon, label: "Badges", value: report.badges.length, sub: report.badges.map((b) => b.name).join(", ") || "none yet" },
        ].map((t) => (
          <Card key={t.label} className="py-4">
            <CardContent className="flex items-center gap-3">
              <span className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary">
                <t.icon className="size-4" />
              </span>
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground">{t.label}</p>
                <p className="text-lg leading-tight font-semibold tabular-nums">{t.value}</p>
                <p className="truncate text-[11px] text-muted-foreground">{t.sub}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <SproutIcon className="size-5 text-primary" /> Top root gaps
            </CardTitle>
            <CardDescription>Where mistakes actually come from, with the evidence the tutor used.</CardDescription>
          </CardHeader>
          <CardContent>
            {report.root_gaps.length === 0 ? (
              <p className="text-sm text-muted-foreground">No root gaps detected yet. Keep answering honestly (Sure vs Guessing) so we can find them.</p>
            ) : (
              <Accordion type="multiple" defaultValue={[report.root_gaps[0].concept_id]} className="w-full">
                {report.root_gaps.map((g, i) => (
                  <AccordionItem key={g.concept_id} value={g.concept_id}>
                    <AccordionTrigger className="hover:no-underline">
                      <div className="flex flex-1 flex-wrap items-center gap-2 text-left">
                        <span className="grid size-6 place-items-center rounded-full bg-primary/10 text-xs font-semibold text-primary">{i + 1}</span>
                        <span className="font-medium">{g.concept_name}</span>
                        <StateBadge state={g.state} />
                        {g.misconception_id && g.state !== "misconception" && <Badge variant="outline">misconception cleared</Badge>}
                        <span className="ml-auto mr-2 text-xs text-muted-foreground tabular-nums">{pct(g.mastery)}</span>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="space-y-3">
                      {g.misconception_text && (
                        <p className="rounded-md border border-rose-500/30 bg-rose-500/5 p-2 text-sm">
                          <span className="text-xs font-medium text-rose-600 dark:text-rose-400">Misconception: </span>
                          {g.misconception_text}
                        </p>
                      )}
                      {(g.path ?? []).length > 1 && (
                        <p className="text-xs text-muted-foreground">
                          Traced from {(g.path ?? []).map((c) => names[c] ?? c).join(" → ")}
                        </p>
                      )}
                      <ul className="space-y-1 text-sm">
                        {g.evidence.map((e, j) => (
                          <li key={j} className="flex gap-2">
                            <span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary/60" /> {e}
                          </li>
                        ))}
                      </ul>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          {!teacher && (
            <Card className="border-primary/40 bg-gradient-to-br from-primary/10 to-transparent">
              <CardHeader>
                <CardDescription>Next best step</CardDescription>
                <CardTitle>{step.label}</CardTitle>
                <p className="text-sm text-muted-foreground">{step.reason}</p>
              </CardHeader>
              <CardContent>
                <Button asChild>
                  <Link href={href}>
                    Go <ArrowRightIcon />
                  </Link>
                </Button>
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader className="pb-0">
              <CardTitle className="text-base">Calibration</CardTitle>
            </CardHeader>
            <CardContent>
              <CalibrationMeter cal={report.calibration} />
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Bloom&apos;s taxonomy radar</CardTitle>
            <CardDescription>Accuracy by thinking level (number of answers in brackets).</CardDescription>
          </CardHeader>
          <CardContent>
            <BloomRadar data={report.bloom_radar} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Concepts by state</CardTitle>
            <CardDescription>Across all 21 concepts in the course.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <StateLegend counts={report.state_counts} />
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">Recent XP</p>
              <ul className="space-y-1.5 text-sm">
                {report.recent_xp.filter((x) => x.amount !== 0).slice(0, 6).map((x, i) => (
                  <li key={i} className="flex justify-between gap-2">
                    <span className="truncate text-muted-foreground">{x.reason}</span>
                    <span className={x.amount > 0 ? "font-medium text-primary tabular-nums" : "tabular-nums text-muted-foreground"}>
                      {x.amount > 0 ? "+" : ""}
                      {x.amount}
                    </span>
                  </li>
                ))}
                {report.recent_xp.filter((x) => x.amount !== 0).length === 0 && (
                  <li className="text-muted-foreground">XP comes only from mastery events, not raw answers.</li>
                )}
              </ul>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
