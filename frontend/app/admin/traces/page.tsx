"use client";

import { CopyIcon, SearchIcon, XIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Empty, ErrorNote, fmt, LevelBadge, otelTraceId, PageHeader, Panel, useDebounced } from "@/components/admin/kit";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useLogs, useMetrics, useTraces } from "@/lib/queries/admin";
import type { LLMCall } from "@/lib/types";
import { cn } from "@/lib/utils";

function StatusBadges({ c }: { c: LLMCall }) {
  const flags = c.guardrail_flags.filter((f) => f !== "offline");
  return (
    <span className="flex flex-wrap gap-1">
      {c.cache_hit && <Badge variant="outline">cache</Badge>}
      {c.fallback_used && <Badge variant="secondary">{c.guardrail_flags.includes("offline") ? "offline" : "fallback"}</Badge>}
      {!c.schema_ok && <Badge variant="destructive">schema</Badge>}
      {c.retries > 0 && <Badge variant="outline">retry</Badge>}
      {flags.map((f) => <Badge key={f} variant="destructive">{f}</Badge>)}
      {!c.cache_hit && !c.fallback_used && c.schema_ok && flags.length === 0 && <Badge>ok</Badge>}
    </span>
  );
}

function copy(text: string) {
  void navigator.clipboard?.writeText(text).then(() => toast.success("Copied"));
}

function TraceSheet({ call, onClose }: { call: LLMCall | null; onClose: () => void }) {
  const logs = useLogs({ trace_id: call?.trace_id, level: "debug", window: "all", limit: 100 }, !!call);
  const related = useTraces({ trace_id: call?.trace_id, window: "all", limit: 50 }, !!call);
  const otelId = otelTraceId(call?.trace_id);
  return (
    <Sheet open={!!call} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full sm:max-w-xl" data-accent="teal">
        <SheetHeader>
          <SheetTitle>{call?.feature} · {call?.prompt_name}@{call?.prompt_version}</SheetTitle>
          <SheetDescription className="font-mono text-xs">{call?.trace_id}</SheetDescription>
        </SheetHeader>
        {call && (
          <ScrollArea className="h-[calc(100vh-7rem)] px-4">
            <div className="space-y-5 pb-8 text-sm">
              <dl className="grid grid-cols-2 gap-2">
                {[
                  ["Model", call.model], ["Scope", call.scope], ["Latency", fmt.ms(call.latency_ms)],
                  ["Tokens", `${call.input_tokens} in / ${call.output_tokens} out`], ["Cost", fmt.usd(call.cost_usd)],
                  ["Retries", String(call.retries)], ["Learner", call.student_id ?? "–"], ["When", fmt.dateTime(call.created_at)],
                ].map(([k, v]) => (
                  <div key={k} className="rounded-lg border p-2">
                    <dt className="text-xs text-muted-foreground">{k}</dt>
                    <dd className="truncate font-medium">{v}</dd>
                  </div>
                ))}
              </dl>
              <StatusBadges c={call} />
              {call.error && <p className="rounded-lg border border-destructive/40 bg-destructive/5 p-2 text-xs text-destructive">{call.error}</p>}
              {otelId && (
                <div className="space-y-1 rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">OpenTelemetry trace id (search it in OpenObserve → Traces)</p>
                  <div className="flex items-center gap-2">
                    <code className="truncate text-xs">{otelId}</code>
                    <Button variant="ghost" size="icon-xs" aria-label="Copy trace id" onClick={() => copy(otelId)}><CopyIcon /></Button>
                  </div>
                </div>
              )}
              <section className="space-y-2">
                <h3 className="font-medium">All LLM calls in this trace ({related.data?.total ?? "…"})</h3>
                <ul className="divide-y rounded-lg border">
                  {related.data?.calls.map((c) => (
                    <li key={c.id} className={cn("flex items-center gap-2 px-3 py-1.5 text-xs", c.id === call.id && "bg-muted")}>
                      <span className="font-mono">{c.feature}</span>
                      <span className="text-muted-foreground">{fmt.ms(c.latency_ms)}</span>
                      <span className="ml-auto"><StatusBadges c={c} /></span>
                    </li>
                  ))}
                </ul>
              </section>
              <section className="space-y-2">
                <h3 className="font-medium">Logs for this trace ({logs.data?.total ?? "…"})</h3>
                {logs.data?.logs.length ? (
                  <ul className="divide-y rounded-lg border">
                    {logs.data.logs.map((l) => (
                      <li key={l.id} className="space-y-0.5 px-3 py-1.5 text-xs">
                        <div className="flex items-center gap-2">
                          <LevelBadge level={l.level} />
                          <span className="font-mono">{l.event}</span>
                          <span className="ml-auto text-muted-foreground">{fmt.time(l.created_at)}</span>
                        </div>
                        <pre className="overflow-x-auto text-[11px] whitespace-pre-wrap text-muted-foreground">{JSON.stringify(l.data)}</pre>
                      </li>
                    ))}
                  </ul>
                ) : <Empty>No stored logs for this trace.</Empty>}
              </section>
            </div>
          </ScrollArea>
        )}
      </SheetContent>
    </Sheet>
  );
}

export default function AdminTraces() {
  const features = useMetrics().data?.features.map((f) => f.feature) ?? [];
  const [scope, setScope] = useState<"all" | "learner" | "studio">("all");
  const [feature, setFeature] = useState("all");
  const [flagged, setFlagged] = useState(false);
  const [traceInput, setTraceInput] = useState("");
  const traceId = useDebounced(traceInput.trim());
  const [selected, setSelected] = useState<LLMCall | null>(null);
  const traces = useTraces({
    limit: 200, flagged,
    ...(scope !== "all" && { scope }), ...(feature !== "all" && { feature }), ...(traceId && { trace_id: traceId }),
  });

  return (
    <div className="space-y-5">
      <PageHeader title="Traces"
        description="One row per LLM call (llm_calls). The trace id ties it to the request, attempt, diagnosis or studio job." />
      <div className="flex flex-wrap items-center gap-2">
        <Select value={scope} onValueChange={(v) => setScope(v as typeof scope)}>
          <SelectTrigger size="sm" className="w-36 text-xs" aria-label="Scope"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All scopes</SelectItem>
            <SelectItem value="learner">Learner-facing</SelectItem>
            <SelectItem value="studio">Studio generation</SelectItem>
          </SelectContent>
        </Select>
        <Select value={feature} onValueChange={setFeature}>
          <SelectTrigger size="sm" className="w-44 text-xs" aria-label="Feature"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All features</SelectItem>
            {features.map((f) => <SelectItem key={f} value={f}>{f}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button variant={flagged ? "default" : "outline"} size="sm" onClick={() => setFlagged(!flagged)} aria-pressed={flagged}>
          Problems only
        </Button>
        <div className="relative">
          <SearchIcon className="absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input value={traceInput} onChange={(e) => setTraceInput(e.target.value)} placeholder="Trace id"
            className="h-8 w-64 pl-7 font-mono text-xs" aria-label="Filter by trace id" />
        </div>
        {(scope !== "all" || feature !== "all" || flagged || traceInput) && (
          <Button variant="ghost" size="sm" onClick={() => { setScope("all"); setFeature("all"); setFlagged(false); setTraceInput(""); }}>
            <XIcon /> Clear
          </Button>
        )}
        <span className="ml-auto text-xs text-muted-foreground">
          {traces.data ? `${fmt.int(traces.data.calls.length)} of ${fmt.int(traces.data.total)} calls` : ""}
        </span>
      </div>
      <Panel title="LLM calls" description="Click a row for details, related calls and logs.">
        <ErrorNote error={traces.error} />
        {traces.data && traces.data.calls.length === 0 ? <Empty>No calls match these filters.</Empty> : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Feature</TableHead>
                  <TableHead>Scope</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead className="text-right">Tokens</TableHead>
                  <TableHead className="text-right">Latency</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Trace</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {traces.data?.calls.map((c) => (
                  <TableRow key={c.id} className="cursor-pointer" onClick={() => setSelected(c)}>
                    <TableCell className="text-xs text-muted-foreground tabular-nums">{fmt.time(c.created_at)}</TableCell>
                    <TableCell className="font-mono text-xs">{c.feature}</TableCell>
                    <TableCell className="text-xs">{c.scope}</TableCell>
                    <TableCell className="text-xs">{c.model}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt.int(c.input_tokens + c.output_tokens)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt.ms(c.latency_ms)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt.usd(c.cost_usd)}</TableCell>
                    <TableCell><StatusBadges c={c} /></TableCell>
                    <TableCell className="max-w-40 truncate font-mono text-[10px] text-muted-foreground">{c.trace_id}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Panel>
      <TraceSheet call={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
