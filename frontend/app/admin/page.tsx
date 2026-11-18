"use client";

import { ActivityIcon, BadgeCheckIcon, CoinsIcon, GaugeIcon, ShieldCheckIcon, SproutIcon, TimerIcon, ZapIcon } from "lucide-react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useMetrics, useTraces } from "@/lib/queries/teacher";
import { pct } from "@/lib/states";
import { cn } from "@/lib/utils";

const num = (v: unknown, digits = 0) => (typeof v === "number" ? v.toFixed(digits) : "–");
const usd = (v: unknown) => (typeof v === "number" ? `$${v < 0.01 ? v.toFixed(4) : v.toFixed(2)}` : "–");
const asPct = (v: unknown) => (typeof v === "number" ? pct(v, v >= 0.995 || v === 0 ? 0 : 1) : "–");

function Tile({ icon: Icon, label, value, sub, good }: { icon: typeof ZapIcon; label: string; value: string; sub?: string; good?: boolean }) {
  return (
    <Card className="py-4">
      <CardContent className="space-y-1">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Icon className="size-3.5" /> {label}
        </div>
        <p className={cn("text-2xl font-semibold tabular-nums", good && "text-primary")}>{value}</p>
        {sub && <p className="text-[11px] text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}

const latencyCfg = { p50_ms: { label: "p50 ms", color: "var(--chart-2)" }, p95_ms: { label: "p95 ms", color: "var(--chart-1)" } } satisfies ChartConfig;
const featureCfg = { calls: { label: "Calls", color: "var(--chart-1)" }, fallback_pct: { label: "Fallback %", color: "var(--chart-3)" } } satisfies ChartConfig;

export default function AdminPage() {
  const metrics = useMetrics();
  const traces = useTraces(40);
  const m = metrics.data;

  if (!m) return <Skeleton className="h-[600px] w-full" />;
  const q = m.ai_quality;
  const endpoints = m.endpoints.slice(0, 8).map((e) => ({ ...e, name: e.name.replace(/\{[^}]+\}/g, ":id") }));
  const features = m.features.map((f) => ({ feature: f.feature, calls: f.calls, fallback_pct: Math.round(f.fallback_rate * 100) }));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Observability</h1>
          <p className="text-sm text-muted-foreground">Every AI decision is traced, checked and measurable.</p>
        </div>
        <Badge variant={m.llm_mode === "online" ? "default" : "secondary"} className="gap-1">
          <ZapIcon className="size-3" /> LLM {m.llm_mode}
          {m.llm_mode === "offline" && " · deterministic fallbacks"}
        </Badge>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Tile icon={SproutIcon} label="Root-gap detection" good
          value={q.root_gap_detection_exercised != null ? asPct(q.root_gap_detection_exercised) : "–"}
          sub={q.root_gap_planted ? `${q.root_gap_detected}/${q.root_gap_planted} planted (${asPct(q.root_gap_detection)}) · vs simulator ground truth` : "run the simulator"} />
        <Tile icon={BadgeCheckIcon} label="Verifier pass rate" value={asPct(q.verifier_pass_rate)} sub={`${num(q.verifier_checked)} questions checked`} />
        <Tile icon={TimerIcon} label="API p95 latency" value={`${num(m.system.p95_ms, 0)} ms`} sub={`p50 ${num(m.system.p50_ms, 1)} ms · ${num(m.system.requests)} requests`} />
        <Tile icon={CoinsIcon} label="Cost per session" value={usd(m.cost.usd_per_session)} sub={`${num(m.cost.tokens_per_session)} tokens/session · total ${usd(m.cost.total_usd)}`} />
        <Tile icon={GaugeIcon} label="Mastery gain vs control" value={typeof m.learning.eval_mastery_gain_vs_control === "number" ? `+${pct(m.learning.eval_mastery_gain_vs_control)}` : "–"} sub="eval: remediation vs no remediation" />
        <Tile icon={ActivityIcon} label="Fallback / cache hit" value={`${asPct(m.system.fallback_rate)} / ${asPct(m.system.cache_hit_rate)}`} sub={`schema failures ${asPct(m.system.schema_failure_rate)} · retries ${asPct(m.system.retry_rate)}`} />
        <Tile icon={ShieldCheckIcon} label="Safety" value={`${m.safety.injection_attempts_blocked} blocked`} sub={`injections · ${m.safety.moderation_flags} moderation · ${m.safety.off_topic_redirects} off-topic redirects`} />
        <Tile icon={SproutIcon} label="Misconceptions cleared" value={num(m.learning.misconceptions_cleared)} sub={`${num(m.learning.concepts_mastered)} concepts mastered · calibration ${asPct(m.learning.calibration)}`} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Latency by endpoint</CardTitle>
            <CardDescription>p50 / p95 in ms</CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={latencyCfg} className="aspect-auto h-64 w-full">
              <BarChart data={endpoints} layout="vertical" margin={{ left: 8 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" width={150} tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Bar dataKey="p50_ms" fill="var(--color-p50_ms)" radius={3} />
                <Bar dataKey="p95_ms" fill="var(--color-p95_ms)" radius={3} />
              </BarChart>
            </ChartContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">LLM features</CardTitle>
            <CardDescription>Calls and fallback rate per feature (all routed through llm_client)</CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={featureCfg} className="aspect-auto h-64 w-full">
              <BarChart data={features}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="feature" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
                <YAxis tickLine={false} axisLine={false} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Bar dataKey="calls" fill="var(--color-calls)" radius={3} />
                <Bar dataKey="fallback_pct" fill="var(--color-fallback_pct)" radius={3} />
              </BarChart>
            </ChartContainer>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">AI quality & learning outcomes</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            {[
              ["Root concept accuracy", asPct(q.root_concept_accuracy)],
              ["Diagnoses (total / rejected)", `${num(q.diagnoses_total)} / ${num(q.diagnoses_rejected)}`],
              ["Diagnoses by LLM agent", num(q.diagnoses_llm)],
              ["Grounding failures caught", num(q.grounding_failures)],
              ["Answer leakage blocked", num(q.answer_leakage_blocked)],
              ["Teach-scorer agreement (±15)", asPct(q.teach_score_agreement)],
              ["Mastery gain / session", num(m.learning.mastery_gain_per_session, 2)],
              ["Avg attempts to mastery", num(m.learning.avg_attempts_to_mastery, 1)],
              ["Drop-off (< 5 answers)", asPct(m.learning.drop_off_rate)],
              ["Last eval run", (q.last_eval_at as string) ?? "–"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-2 border-b py-1.5">
                <span className="text-muted-foreground">{k}</span>
                <span className="font-medium tabular-nums">{v}</span>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Question health</CardTitle>
            <CardDescription>Observed vs predicted success; never-picked distractors.</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Question</TableHead>
                  <TableHead className="text-right">n</TableHead>
                  <TableHead className="text-right">Obs.</TableHead>
                  <TableHead className="text-right">Pred.</TableHead>
                  <TableHead>Flag</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {m.question_health.slice(0, 8).map((h) => (
                  <TableRow key={h.question_id}>
                    <TableCell className="font-mono text-xs">{h.question_id}</TableCell>
                    <TableCell className="text-right tabular-nums">{h.attempts}</TableCell>
                    <TableCell className="text-right tabular-nums">{pct(h.observed_success)}</TableCell>
                    <TableCell className="text-right tabular-nums">{pct(h.predicted_success)}</TableCell>
                    <TableCell>
                      <Badge variant={h.flag === "ok" ? "outline" : "secondary"}>{h.flag.replace("_", " ")}</Badge>
                      {h.never_picked_options.length > 0 && (
                        <span className="ml-1 text-[10px] text-muted-foreground">unpicked: {h.never_picked_options.join(",")}</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
                {m.question_health.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-muted-foreground">Needs 5+ answers per question.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent LLM calls (llm_calls)</CardTitle>
          <CardDescription>trace_id links each call to the request, attempt and diagnosis that caused it.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Feature</TableHead>
                <TableHead>Prompt</TableHead>
                <TableHead>Model</TableHead>
                <TableHead className="text-right">Tokens</TableHead>
                <TableHead className="text-right">ms</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Trace</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(traces.data?.calls ?? []).map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="text-xs text-muted-foreground">{new Date(c.created_at + "Z").toLocaleTimeString()}</TableCell>
                  <TableCell>{c.feature}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {c.prompt_name}@{c.prompt_version}
                  </TableCell>
                  <TableCell className="text-xs">{c.model}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.input_tokens + c.output_tokens}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.latency_ms}</TableCell>
                  <TableCell className="space-x-1">
                    {c.cache_hit && <Badge variant="outline">cache</Badge>}
                    {c.fallback_used && <Badge variant="secondary">fallback</Badge>}
                    {!c.schema_ok && <Badge variant="destructive">schema</Badge>}
                    {c.guardrail_flags.filter((f) => f !== "offline").map((f) => (
                      <Badge key={f} variant="destructive">{f}</Badge>
                    ))}
                    {!c.cache_hit && !c.fallback_used && c.schema_ok && <Badge>ok</Badge>}
                  </TableCell>
                  <TableCell className="font-mono text-[10px] text-muted-foreground">{c.trace_id}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
