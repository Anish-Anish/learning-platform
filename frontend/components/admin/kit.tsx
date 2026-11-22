"use client";

import type { LucideIcon } from "lucide-react";
import { RadioIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { WINDOWS, useAdminPrefs } from "@/lib/queries/admin";
import type { MetricsWindow } from "@/lib/types";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------- formatting (null-safe, "–" for no data)
type N = number | string | null | undefined;
const isNum = (v: N): v is number => typeof v === "number" && Number.isFinite(v);
export const fmt = {
  int: (v: N) => (isNum(v) ? Math.round(v).toLocaleString() : "–"),
  num: (v: N, d = 1) => (isNum(v) ? v.toFixed(d) : "–"),
  pct: (v: N, d = 1) => (isNum(v) ? `${(v * 100).toFixed(v === 0 || v === 1 ? 0 : d)}%` : "–"),
  ms: (v: N) => (isNum(v) ? (v >= 1000 ? `${(v / 1000).toFixed(2)} s` : `${v.toFixed(v < 10 ? 1 : 0)} ms`) : "–"),
  usd: (v: N) => (isNum(v) ? (v === 0 ? "$0" : v < 0.01 ? `$${v.toFixed(5)}` : `$${v.toFixed(2)}`) : "–"),
  rate: (perMin: N) => (isNum(perMin) ? (perMin >= 1 || perMin === 0 ? `${perMin.toFixed(1)}/min` : `${(perMin * 60).toFixed(1)}/h`) : "–"),
  secs: (v: N) => (isNum(v) ? (v >= 60 ? `${(v / 60).toFixed(1)} min` : `${v.toFixed(0)} s`) : "–"),
  time: (iso: string | null | undefined) => (iso ? new Date(`${iso}Z`).toLocaleTimeString() : "–"),
  dateTime: (iso: string | null | undefined) => (iso ? new Date(`${iso}Z`).toLocaleString() : "–"),
};

export const routeLabel = (r: string) => r.replace(/\{[^}]+\}/g, ":id");

// ---------------------------------------------------------------- layout pieces
export function PageHeader({ title, description, children }: { title: string; description?: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {children}
    </div>
  );
}

export type Tone = "default" | "good" | "warn" | "bad";
const TONE: Record<Tone, string> = {
  default: "",
  good: "text-emerald-600 dark:text-emerald-400",
  warn: "text-amber-600 dark:text-amber-400",
  bad: "text-destructive",
};

export function Stat({ icon: Icon, label, value, sub, tone = "default", hint }: {
  icon?: LucideIcon; label: string; value: string; sub?: string; tone?: Tone; hint?: string;
}) {
  return (
    <Card className="gap-0 py-4" title={hint}>
      <CardContent className="space-y-1">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {Icon && <Icon className="size-3.5" />} {label}
        </div>
        <p className={cn("text-2xl font-semibold tabular-nums", TONE[tone])}>{value}</p>
        {sub && <p className="text-[11px] leading-snug text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}

export function Panel({ title, description, children, action, className }: {
  title: string; description?: string; children: React.ReactNode; action?: React.ReactNode; className?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
        <div className="space-y-1">
          <CardTitle className="text-base">{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
        {action}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function KV({ rows }: { rows: [string, string, string?][] }) {
  return (
    <dl className="grid gap-x-6 text-sm sm:grid-cols-2">
      {rows.map(([k, v, hint]) => (
        <div key={k} className="flex min-w-0 justify-between gap-3 border-b py-1.5" title={hint}>
          <dt className="shrink-0 text-muted-foreground">{k}</dt>
          <dd className="min-w-0 text-right font-medium break-words tabular-nums [overflow-wrap:anywhere]">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">{children}</p>;
}

export function Loading() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-72" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
      </div>
      <Skeleton className="h-72 rounded-xl" />
    </div>
  );
}

export function ErrorNote({ error }: { error: Error | null }) {
  return error ? <p className="text-sm text-destructive">{error.message}</p> : null;
}

// ---------------------------------------------------------------- shared controls
export function WindowPicker({ className }: { className?: string }) {
  const window = useAdminPrefs((s) => s.window);
  const setWindow = useAdminPrefs((s) => s.setWindow);
  return (
    <Select value={window} onValueChange={(v) => setWindow(v as MetricsWindow)}>
      <SelectTrigger size="sm" className={cn("w-full text-xs", className)} aria-label="Time window">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {WINDOWS.map((w) => <SelectItem key={w.id} value={w.id}>{w.label}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

export function LiveToggle() {
  const live = useAdminPrefs((s) => s.live);
  const setLive = useAdminPrefs((s) => s.setLive);
  return (
    <button
      type="button"
      onClick={() => setLive(!live)}
      aria-pressed={live}
      className={cn(
        "flex w-full items-center justify-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors",
        live ? "border-emerald-500/40 text-emerald-700 dark:text-emerald-300" : "text-muted-foreground",
      )}
    >
      <RadioIcon className={cn("size-3.5", live && "animate-pulse")} /> {live ? "Live refresh on" : "Live refresh paused"}
    </button>
  );
}

export function LevelBadge({ level }: { level: string }) {
  const cls =
    level === "error" || level === "critical"
      ? "bg-destructive/10 text-destructive"
      : level === "warning"
        ? "bg-amber-500/15 text-amber-700 dark:text-amber-300"
        : "bg-muted text-muted-foreground";
  return <Badge variant="outline" className={cn("border-transparent uppercase", cls)}>{level}</Badge>;
}

export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** With OpenTelemetry on, app trace ids are `tr_<32-hex OTel trace id>`; that hex is what OpenObserve shows. */
export function otelTraceId(traceId: string | null | undefined) {
  const m = /^tr_([0-9a-f]{32})$/.exec(traceId ?? "");
  return m ? m[1] : null;
}
