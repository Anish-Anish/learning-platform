"use client";

import { useMemo } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { STATE_META, pct } from "@/lib/states";
import type { ConceptState, Heatmap } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ClassHeatmap({
  data,
  onStudent,
  highlightConcept,
}: {
  data: Heatmap;
  onStudent: (id: string) => void;
  highlightConcept?: string | null;
}) {
  const concepts = useMemo(() => [...data.concepts].sort((a, b) => a.depth - b.depth), [data.concepts]);
  const cell = useMemo(() => {
    const m = new Map<string, { state: ConceptState; mastery: number }>();
    for (const c of data.cells) m.set(`${c.student_id}|${c.concept_id}`, { state: c.state, mastery: c.mastery });
    return m;
  }, [data.cells]);
  const students = useMemo(
    () => [...data.students].filter((s) => s.attempts > 0 || !s.is_simulated).sort((a, b) => b.attempts - a.attempts),
    [data.students],
  );

  return (
    <div className="overflow-x-auto">
      <table className="border-separate border-spacing-[3px] text-xs">
        <thead>
          <tr>
            <th className="sticky left-0 z-10 bg-card" />
            {concepts.map((c) => (
              <th key={c.id} className="h-36 w-7 align-bottom">
                <div
                  className={cn(
                    "mx-auto w-5 origin-bottom-left translate-x-3 -rotate-60 text-left font-normal whitespace-nowrap text-muted-foreground",
                    highlightConcept === c.id && "font-semibold text-primary",
                  )}
                >
                  {c.name}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {students.map((s) => (
            <tr key={s.id}>
              <td className="sticky left-0 z-10 bg-card pr-2">
                <button
                  onClick={() => onStudent(s.id)}
                  className="flex w-36 items-center justify-between gap-2 rounded-md px-1.5 py-0.5 text-left hover:bg-muted"
                >
                  <span className="truncate font-medium">{s.display_name}</span>
                  <span className="text-[10px] text-muted-foreground tabular-nums">{s.attempts}</span>
                </button>
              </td>
              {concepts.map((c) => {
                const v = cell.get(`${s.id}|${c.id}`);
                if (!v) return <td key={c.id} />;
                const meta = STATE_META[v.state];
                return (
                  <td key={c.id} className="p-0">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          onClick={() => onStudent(s.id)}
                          className={cn(
                            "block size-6 rounded-[5px] transition-transform hover:scale-125",
                            v.state === "locked" ? "bg-muted" : meta.dot,
                            highlightConcept === c.id && "ring-2 ring-primary ring-offset-1 ring-offset-card",
                          )}
                          style={{ opacity: v.state === "locked" ? 0.6 : 0.35 + 0.65 * v.mastery }}
                          aria-label={`${s.display_name} – ${c.name}: ${meta.label}`}
                        />
                      </TooltipTrigger>
                      <TooltipContent>
                        <b>{s.display_name}</b> · {c.name}
                        <br />
                        {meta.label} · mastery {pct(v.mastery)}
                      </TooltipContent>
                    </Tooltip>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
