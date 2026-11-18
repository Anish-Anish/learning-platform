import { STATE_META } from "@/lib/states";
import type { ConceptState } from "@/lib/types";
import { cn } from "@/lib/utils";

export function StateBadge({ state, className }: { state: ConceptState; className?: string }) {
  const m = STATE_META[state];
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium", m.bg, m.border, m.text, className)}
    >
      <span className={cn("size-1.5 rounded-full", m.dot)} />
      {m.label}
    </span>
  );
}
