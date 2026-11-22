"use client";

import { AlertTriangleIcon, GaugeIcon, TimerIcon, ZapIcon } from "lucide-react";

import { LatencyChart, TrafficChart } from "@/components/admin/charts";
import { Empty, ErrorNote, fmt, Loading, PageHeader, Panel, routeLabel, Stat } from "@/components/admin/kit";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useMetrics } from "@/lib/queries/admin";
import { cn } from "@/lib/utils";

export default function AdminRequests() {
  const metrics = useMetrics();
  const m = metrics.data;
  if (!m) return metrics.error ? <ErrorNote error={metrics.error} /> : <Loading />;
  const s = m.system;
  const maxP95 = Math.max(1, ...m.endpoints.map((e) => e.p95_ms));
  return (
    <div className="space-y-5">
      <PageHeader title="Requests" description="Every API request is timed by middleware and stored (health checks and docs excluded)." />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={GaugeIcon} label="Requests" value={fmt.int(s.requests)} sub={`${fmt.rate(s.requests_per_min)} on average`} />
        <Stat icon={TimerIcon} label="p50 / p95" value={`${fmt.ms(s.p50_ms)} / ${fmt.ms(s.p95_ms)}`} sub={`p99 ${fmt.ms(s.p99_ms)}`} />
        <Stat icon={AlertTriangleIcon} label="5xx rate" value={fmt.pct(s.error_rate, 2)}
          tone={(s.error_rate as number) > 0 ? "bad" : "good"} sub="server errors" />
        <Stat icon={ZapIcon} label="4xx rate" value={fmt.pct(s.client_error_rate, 2)}
          sub={`includes ${fmt.int(m.safety.rate_limited)} rate-limited (429) and ${fmt.int(m.safety.uploads_rejected)} oversized uploads (413)`} />
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Traffic" description="Requests and 5xx errors"><TrafficChart data={m.timeseries} window={m.window} /></Panel>
        <Panel title="Latency" description="p95 per bucket"><LatencyChart data={m.timeseries} window={m.window} /></Panel>
      </div>
      <Panel title="Endpoints" description="Sorted by volume. Bars show p95 relative to the slowest endpoint.">
        {m.endpoints.length === 0 ? <Empty>No requests in this window.</Empty> : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Route</TableHead>
                  <TableHead className="text-right">Requests</TableHead>
                  <TableHead className="text-right">p50</TableHead>
                  <TableHead className="text-right">p95</TableHead>
                  <TableHead className="w-40">p95 relative</TableHead>
                  <TableHead className="text-right">5xx</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {m.endpoints.map((e) => (
                  <TableRow key={e.name}>
                    <TableCell className="font-mono text-xs">{routeLabel(e.name)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt.int(e.count)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt.ms(e.p50_ms)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt.ms(e.p95_ms)}</TableCell>
                    <TableCell>
                      <div className="h-1.5 rounded-full bg-muted">
                        <div className="h-full rounded-full bg-[var(--chart-1)]" style={{ width: `${(e.p95_ms / maxP95) * 100}%` }} />
                      </div>
                    </TableCell>
                    <TableCell className={cn("text-right tabular-nums", e.error_rate > 0 && "text-destructive")}>
                      {fmt.pct(e.error_rate, 1)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Panel>
    </div>
  );
}
