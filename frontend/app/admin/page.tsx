"use client";

import {
  AlertTriangleIcon,
  BotIcon,
  CoinsIcon,
  GaugeIcon,
  ShieldCheckIcon,
  SproutIcon,
  TimerIcon,
  UsersIcon,
} from "lucide-react";
import Link from "next/link";

import { LatencyChart, TrafficChart } from "@/components/admin/charts";
import { Empty, ErrorNote, fmt, LevelBadge, Loading, PageHeader, Panel, Stat } from "@/components/admin/kit";
import { TelemetrySummary } from "@/components/admin/telemetry-summary";
import { Button } from "@/components/ui/button";
import { useLogs, useMetrics } from "@/lib/queries/admin";

export default function AdminOverview() {
  const metrics = useMetrics();
  const problems = useLogs({ level: "warning", limit: 8 });
  const m = metrics.data;
  if (!m) return metrics.error ? <ErrorNote error={metrics.error} /> : <Loading />;

  const sys = m.system;
  const err = (sys.error_rate as number | null) ?? 0;
  const guardEvents = Object.entries(m.safety)
    .filter(([k]) => !["pii_scrubbed", "off_topic_redirects"].includes(k))
    .reduce((s, [, v]) => s + v, 0);

  return (
    <div className="space-y-5">
      <PageHeader title="Overview" description={`Health of the whole system · ${fmt.int(sys.requests)} requests in window · updated ${fmt.time(m.generated_at)}`} />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={GaugeIcon} label="Traffic" value={fmt.rate(sys.requests_per_min)}
          sub={`${fmt.int(sys.requests)} requests · ${fmt.int(m.learning.active_students)} active students`} />
        <Stat icon={TimerIcon} label="API latency (p95)" value={fmt.ms(sys.p95_ms)}
          sub={`p50 ${fmt.ms(sys.p50_ms)} · p99 ${fmt.ms(sys.p99_ms)}`}
          tone={(sys.p95_ms as number) > 1500 ? "warn" : "default"} />
        <Stat icon={AlertTriangleIcon} label="Server errors (5xx)" value={fmt.pct(sys.error_rate, 2)}
          sub={`client errors (4xx) ${fmt.pct(sys.client_error_rate, 1)}`} tone={err > 0.01 ? "bad" : err > 0 ? "warn" : "good"} />
        <Stat icon={BotIcon} label="LLM calls" value={fmt.int(sys.llm_calls)}
          sub={`${fmt.int(sys.llm_calls_live)} live · fallback ${fmt.pct(sys.live_fallback_rate)} of live · cache ${fmt.pct(sys.cache_hit_rate)}`} />
        <Stat icon={CoinsIcon} label="Learner cost / session" value={fmt.usd(m.cost.usd_per_session)}
          sub={`learner ${fmt.usd(m.cost.learner_usd)} · studio ${fmt.usd(m.cost.studio_usd)} · ${fmt.int(m.cost.sessions)} sessions`} />
        <Stat icon={SproutIcon} label="Root-gap detection" value={fmt.pct(m.ai_quality.root_gap_detection_exercised)}
          sub={m.ai_quality.root_gap_planted ? `${m.ai_quality.root_gap_detected}/${m.ai_quality.root_gap_planted} planted misconceptions (all-time, simulator)` : "run the class simulator to measure"}
          tone="good" />
        <Stat icon={UsersIcon} label="Learning" value={fmt.pct(m.learning.accuracy)}
          sub={`answer accuracy · ${fmt.int(m.learning.attempts)} answers · ${fmt.int(m.learning.misconceptions_cleared)} misconceptions cleared`} />
        <Stat icon={ShieldCheckIcon} label="Guardrail events" value={fmt.int(guardEvents)}
          sub={`${m.safety.injection_attempts} injections neutralised · ${m.safety.rate_limited} rate-limited · ${m.safety.blocked_calls} blocked`}
          tone={guardEvents ? "warn" : "default"} />
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Traffic" description="Requests and server errors per time bucket">
          <TrafficChart data={m.timeseries} window={m.window} />
        </Panel>
        <Panel title="Latency" description="p95 API latency per time bucket (SSE endpoints: time to first byte)">
          <LatencyChart data={m.timeseries} window={m.window} />
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Panel title="Recent warnings & errors" description="From the structured log store"
          action={<Button variant="outline" size="sm" asChild><Link href="/admin/logs">All logs</Link></Button>}>
          {!problems.data ? (
            <ErrorNote error={problems.error} />
          ) : problems.data.logs.length === 0 ? (
            <Empty>No warnings or errors in this window.</Empty>
          ) : (
            <ul className="divide-y text-sm">
              {problems.data.logs.map((l) => (
                <li key={l.id} className="flex items-center gap-2 py-1.5">
                  <LevelBadge level={l.level} />
                  <span className="font-mono text-xs">{l.event}</span>
                  <span className="truncate text-xs text-muted-foreground">
                    {Object.entries(l.data).filter(([k]) => k !== "logger").slice(0, 3)
                      .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join(" · ")}
                  </span>
                  <span className="ml-auto shrink-0 text-xs text-muted-foreground tabular-nums">{fmt.time(l.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <TelemetrySummary />
      </div>
    </div>
  );
}
