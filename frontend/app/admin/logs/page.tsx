"use client";

import { ChevronDownIcon, ChevronRightIcon, SearchIcon, XIcon } from "lucide-react";
import { Fragment, useState } from "react";

import { Empty, ErrorNote, fmt, LevelBadge, PageHeader, Panel, useDebounced } from "@/components/admin/kit";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { LogQuery } from "@/lib/api";
import { useLogs } from "@/lib/queries/admin";
import type { LogEntry } from "@/lib/types";

type Level = NonNullable<LogQuery["level"]>;
const LEVELS: { id: Level; label: string }[] = [
  { id: "info", label: "Info and above" },
  { id: "warning", label: "Warnings and errors" },
  { id: "error", label: "Errors only" },
];

function summary(l: LogEntry) {
  return Object.entries(l.data)
    .slice(0, 4)
    .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join("  ");
}

export default function AdminLogs() {
  const [level, setLevel] = useState<Level>("info");
  const [search, setSearch] = useState("");
  const [event, setEvent] = useState<string | null>(null);
  const [trace, setTrace] = useState<string | null>(null);
  const [limit, setLimit] = useState(100);
  const [open, setOpen] = useState<number | null>(null);
  const q = useDebounced(search.trim());
  const logs = useLogs({ level, limit, ...(q && { q }), ...(event && { event }), ...(trace && { trace_id: trace }) });
  const d = logs.data;

  return (
    <div className="space-y-5">
      <PageHeader title="Logs"
        description="Structured application logs (INFO and above), stored with their trace id. Also exported to OpenObserve when telemetry is on." />
      <div className="flex flex-wrap items-center gap-2">
        <Select value={level} onValueChange={(v) => setLevel(v as Level)}>
          <SelectTrigger size="sm" className="w-48 text-xs" aria-label="Minimum level"><SelectValue /></SelectTrigger>
          <SelectContent>{LEVELS.map((l) => <SelectItem key={l.id} value={l.id}>{l.label}</SelectItem>)}</SelectContent>
        </Select>
        <div className="relative">
          <SearchIcon className="absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search events and fields"
            className="h-8 w-72 pl-7 text-xs" aria-label="Search logs" />
        </div>
        {event && <Badge variant="secondary" className="gap-1">event: {event}<button aria-label="Clear event filter" onClick={() => setEvent(null)}><XIcon className="size-3" /></button></Badge>}
        {trace && <Badge variant="secondary" className="gap-1 font-mono">trace: {trace.slice(0, 14)}…<button aria-label="Clear trace filter" onClick={() => setTrace(null)}><XIcon className="size-3" /></button></Badge>}
        <div className="ml-auto flex items-center gap-1.5 text-xs">
          {d && Object.entries(d.levels).sort().map(([lv, n]) => (
            <span key={lv} className="flex items-center gap-1"><LevelBadge level={lv} /><span className="tabular-nums">{fmt.int(n)}</span></span>
          ))}
        </div>
      </div>
      <Panel title={d ? `${fmt.int(d.total)} matching entries` : "Loading…"}
        description="Click a row to expand it; click an event or trace id to filter by it.">
        <ErrorNote error={logs.error} />
        {d && d.logs.length === 0 ? <Empty>No logs match these filters in this window.</Empty> : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-6" />
                  <TableHead>Time</TableHead>
                  <TableHead>Level</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead>Details</TableHead>
                  <TableHead>Trace</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {d?.logs.map((l) => (
                  <Fragment key={l.id}>
                    <TableRow className="cursor-pointer" onClick={() => setOpen(open === l.id ? null : l.id)}>
                      <TableCell>{open === l.id ? <ChevronDownIcon className="size-3.5" /> : <ChevronRightIcon className="size-3.5" />}</TableCell>
                      <TableCell className="text-xs whitespace-nowrap text-muted-foreground tabular-nums">{fmt.dateTime(l.created_at)}</TableCell>
                      <TableCell><LevelBadge level={l.level} /></TableCell>
                      <TableCell>
                        <button className="font-mono text-xs hover:underline" onClick={(e) => { e.stopPropagation(); setEvent(l.event); }}>
                          {l.event}
                        </button>
                      </TableCell>
                      <TableCell className="max-w-xl truncate font-mono text-[11px] text-muted-foreground">{summary(l)}</TableCell>
                      <TableCell>
                        {l.trace_id && (
                          <button className="font-mono text-[10px] text-muted-foreground hover:text-foreground hover:underline"
                            onClick={(e) => { e.stopPropagation(); setTrace(l.trace_id); }}>
                            {l.trace_id.slice(0, 14)}…
                          </button>
                        )}
                      </TableCell>
                    </TableRow>
                    {open === l.id && (
                      <TableRow>
                        <TableCell />
                        <TableCell colSpan={5}>
                          <pre className="overflow-x-auto rounded-lg bg-muted p-3 text-[11px] whitespace-pre-wrap">
                            {JSON.stringify({ logger: l.logger, trace_id: l.trace_id, student_id: l.student_id, ...l.data }, null, 2)}
                          </pre>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
        {d && d.total > d.logs.length && limit < 500 && (
          <div className="mt-3 flex justify-center">
            <Button variant="outline" size="sm" onClick={() => setLimit(Math.min(500, limit + 150))}>
              Show more ({fmt.int(d.total - d.logs.length)} older)
            </Button>
          </div>
        )}
      </Panel>
    </div>
  );
}
