"use client";

import { BookOpenIcon, BotIcon, CoinsIcon, RefreshCwIcon, TimerIcon } from "lucide-react";

import { CallsChart, SpendChart } from "@/components/admin/charts";
import { Empty, ErrorNote, fmt, KV, Loading, PageHeader, Panel, Stat } from "@/components/admin/kit";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useMetrics } from "@/lib/queries/admin";
import { cn } from "@/lib/utils";

export default function AdminLLM() {
  const metrics = useMetrics();
  const m = metrics.data;
  if (!m) return metrics.error ? <ErrorNote error={metrics.error} /> : <Loading />;
  const s = m.system;
  const c = m.cost;
  const offline = m.llm_mode === "offline";
  return (
    <div className="space-y-5">
      <PageHeader title="LLM & cost"
        description="Every model call goes through llm_client: schema-validated, retried once, then a deterministic fallback." />
      {offline && (
        <p className="rounded-lg border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-sm">
          The LLM is <b>offline</b> (no API key): calls are served by deterministic fallbacks and cost $0.
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={CoinsIcon} label="Total spend" value={fmt.usd(c.total_usd)} sub={`${fmt.int(c.total_tokens)} tokens`} />
        <Stat icon={BotIcon} label="Learner cost / session" value={fmt.usd(c.usd_per_session)}
          sub={`${fmt.usd(c.learner_usd)} over ${fmt.int(c.sessions)} sessions · ${fmt.num(c.tokens_per_session, 0)} tokens/session`} />
        <Stat icon={BookOpenIcon} label="Studio generation" value={fmt.usd(c.studio_usd)}
          sub={`${fmt.int(m.studio.studio_llm_calls)} calls · ${fmt.int(m.studio.studio_tokens)} tokens (not in cost/session)`} />
        <Stat icon={TimerIcon} label="Live call p95" value={fmt.ms(s.llm_p95_ms)}
          sub={`${fmt.int(s.llm_calls_live)} live of ${fmt.int(s.llm_calls)} calls`} />
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Spend over time" description="Estimated from token usage × configured prices">
          <SpendChart data={m.timeseries} window={m.window} />
        </Panel>
        <Panel title="Calls over time"><CallsChart data={m.timeseries} window={m.window} /></Panel>
      </div>
      <Panel title="Reliability" description="Rates over live calls only (offline fallbacks excluded) unless noted">
        <KV rows={[
          ["Schema failures", fmt.pct(s.schema_failure_rate), "structured output failed validation"],
          ["Retries", fmt.pct(s.retry_rate)],
          ["Fallbacks (live calls)", fmt.pct(s.live_fallback_rate), "call failed twice or was blocked"],
          ["Fallbacks (all calls)", fmt.pct(s.fallback_rate), "includes offline mode"],
          ["Cache hit rate", fmt.pct(s.cache_hit_rate)],
          ["Grounding failures caught", fmt.int(m.ai_quality.grounding_failures)],
        ]} />
      </Panel>
      <Panel title="By feature" description="Latency excludes cache hits">
        {m.features.length === 0 ? <Empty>No LLM calls in this window.</Empty> : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Feature</TableHead>
                  <TableHead className="text-right">Calls</TableHead>
                  <TableHead className="text-right">Tokens in / out</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                  <TableHead className="text-right">p50</TableHead>
                  <TableHead className="text-right">p95</TableHead>
                  <TableHead className="text-right">Fallback</TableHead>
                  <TableHead className="text-right">Cache</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {m.features.map((f) => (
                  <TableRow key={f.feature}>
                    <TableCell className="font-mono text-xs">
                      {f.feature}
                      {f.feature.startsWith("studio_") && <span className="ml-1.5 text-muted-foreground">(studio)</span>}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{fmt.int(f.calls)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt.int(f.input_tokens)} / {fmt.int(f.output_tokens)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt.usd(f.cost_usd)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt.ms(f.p50_ms)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt.ms(f.p95_ms)}</TableCell>
                    <TableCell className={cn("text-right tabular-nums", !offline && f.fallback_rate > 0.1 && "text-amber-600")}>
                      {fmt.pct(f.fallback_rate)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{fmt.pct(f.cache_hit_rate)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Panel>
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <RefreshCwIcon className="size-3" /> Prices come from PRICE_* in backend/.env; change them to match your model.
      </p>
    </div>
  );
}
