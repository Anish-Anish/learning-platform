"use client";

import { Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import { Empty, fmt } from "@/components/admin/kit";
import {
  type ChartConfig,
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import type { MetricsWindow, TimeBucket } from "@/lib/types";

// One measure per chart (no dual axes). Errors use the reserved status colour and are always labelled.
const trafficCfg = {
  requests: { label: "Requests", color: "var(--chart-2)" },
  errors: { label: "5xx errors", color: "var(--destructive)" },
} satisfies ChartConfig;
const latencyCfg = { p95_ms: { label: "p95 latency (ms)", color: "var(--chart-1)" } } satisfies ChartConfig;
const spendCfg = { cost_usd: { label: "LLM cost (USD)", color: "var(--chart-3)" } } satisfies ChartConfig;
const callsCfg = { llm_calls: { label: "LLM calls", color: "var(--chart-5)" } } satisfies ChartConfig;

function tick(window: MetricsWindow) {
  return (iso: string) => {
    const d = new Date(`${iso}Z`);
    return window === "1h" || window === "24h"
      ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : d.toLocaleDateString([], { month: "short", day: "numeric" });
  };
}

const axis = { tickLine: false, axisLine: false, tick: { fontSize: 11 } } as const;
const tooltipLabel = (_: unknown, p: readonly { payload?: { start?: string } }[]) =>
  fmt.dateTime(p?.[0]?.payload?.start);

export function TrafficChart({ data, window }: { data: TimeBucket[]; window: MetricsWindow }) {
  if (!data.some((d) => d.requests)) return <Empty>No requests in this window.</Empty>;
  return (
    <ChartContainer config={trafficCfg} className="aspect-auto h-56 w-full">
      <AreaChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
        <CartesianGrid vertical={false} strokeOpacity={0.5} />
        <XAxis dataKey="start" tickFormatter={tick(window)} minTickGap={32} {...axis} />
        <YAxis width={40} allowDecimals={false} {...axis} />
        <ChartTooltip content={<ChartTooltipContent labelFormatter={tooltipLabel} />} />
        <ChartLegend content={<ChartLegendContent />} />
        <Area dataKey="requests" type="monotone" stroke="var(--color-requests)" strokeWidth={2}
          fill="var(--color-requests)" fillOpacity={0.15} />
        <Area dataKey="errors" type="monotone" stroke="var(--color-errors)" strokeWidth={2}
          fill="var(--color-errors)" fillOpacity={0.2} />
      </AreaChart>
    </ChartContainer>
  );
}

export function LatencyChart({ data, window }: { data: TimeBucket[]; window: MetricsWindow }) {
  if (!data.some((d) => d.requests)) return <Empty>No requests in this window.</Empty>;
  return (
    <ChartContainer config={latencyCfg} className="aspect-auto h-56 w-full">
      <LineChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
        <CartesianGrid vertical={false} strokeOpacity={0.5} />
        <XAxis dataKey="start" tickFormatter={tick(window)} minTickGap={32} {...axis} />
        <YAxis width={48} unit=" ms" {...axis} />
        <ChartTooltip content={<ChartTooltipContent labelFormatter={tooltipLabel} />} />
        {/* Empty buckets are gaps (null), not 0 ms; dots keep isolated points visible. */}
        <Line dataKey="p95_ms" type="monotone" stroke="var(--color-p95_ms)" strokeWidth={2}
          dot={{ r: 3, strokeWidth: 0, fill: "var(--color-p95_ms)" }} activeDot={{ r: 5 }} connectNulls={false} />
      </LineChart>
    </ChartContainer>
  );
}

export function SpendChart({ data, window }: { data: TimeBucket[]; window: MetricsWindow }) {
  if (!data.some((d) => d.llm_calls)) return <Empty>No LLM calls in this window.</Empty>;
  return (
    <ChartContainer config={spendCfg} className="aspect-auto h-56 w-full">
      <BarChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
        <CartesianGrid vertical={false} strokeOpacity={0.5} />
        <XAxis dataKey="start" tickFormatter={tick(window)} minTickGap={32} {...axis} />
        <YAxis width={56} tickFormatter={(v: number) => `$${v < 1 ? v.toFixed(3) : v.toFixed(2)}`} {...axis} />
        <ChartTooltip content={<ChartTooltipContent labelFormatter={tooltipLabel} />} />
        <Bar dataKey="cost_usd" fill="var(--color-cost_usd)" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ChartContainer>
  );
}

export function CallsChart({ data, window }: { data: TimeBucket[]; window: MetricsWindow }) {
  if (!data.some((d) => d.llm_calls)) return <Empty>No LLM calls in this window.</Empty>;
  return (
    <ChartContainer config={callsCfg} className="aspect-auto h-56 w-full">
      <BarChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
        <CartesianGrid vertical={false} strokeOpacity={0.5} />
        <XAxis dataKey="start" tickFormatter={tick(window)} minTickGap={32} {...axis} />
        <YAxis width={40} allowDecimals={false} {...axis} />
        <ChartTooltip content={<ChartTooltipContent labelFormatter={tooltipLabel} />} />
        <Bar dataKey="llm_calls" fill="var(--color-llm_calls)" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ChartContainer>
  );
}
