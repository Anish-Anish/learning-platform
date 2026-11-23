"use client";

import "@xyflow/react/dist/style.css";

import { Background, Controls, Handle, type Edge, type Node, type NodeProps, Position, ReactFlow } from "@xyflow/react";
import { BookOpenIcon, FileStackIcon, TriangleAlertIcon } from "lucide-react";
import { useTheme } from "next-themes";
import { memo, useMemo } from "react";

import { WORLD_THEME } from "@/lib/avatars";
import type { StudioConcept, StudioWorld } from "@/lib/types";
import { cn } from "@/lib/utils";

type Data = StudioConcept & { color: string; selected: boolean };

const StudioNode = memo(function StudioNode({ data }: NodeProps<Node<Data>>) {
  const theme = WORLD_THEME[data.color] ?? WORLD_THEME.violet;
  const empty = data.n_questions === 0;
  return (
    <div
      className={cn(
        "w-[200px] overflow-hidden rounded-xl border bg-card shadow-sm transition-all",
        empty && "border-amber-500/70",
        data.selected && "ring-2 ring-primary ring-offset-2 ring-offset-background",
      )}
    >
      <div className={cn("h-1.5 bg-gradient-to-r", theme.grad)} />
      <Handle type="target" position={Position.Top} className="!size-1.5 !border-0 !bg-muted-foreground/40" />
      <div className="px-3 py-2">
        <div className="flex items-start gap-1.5">
          <p className="flex-1 text-[12.5px] leading-tight font-medium">{data.name}</p>
          {empty && <TriangleAlertIcon className="size-3.5 shrink-0 text-amber-500" />}
        </div>
        <div className="mt-1.5 flex gap-3 text-[10.5px] text-muted-foreground">
          <span className={cn("flex items-center gap-1", empty && "text-amber-600 dark:text-amber-400")}>
            <BookOpenIcon className="size-3" /> {data.n_questions} Q
          </span>
          <span className="flex items-center gap-1">
            <FileStackIcon className="size-3" /> {data.n_flashcards} cards
          </span>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!size-1.5 !border-0 !bg-muted-foreground/40" />
    </div>
  );
});

const nodeTypes = { studio: StudioNode };

function layout(concepts: StudioConcept[], colorOf: Record<string, string>, selectedId: string | null) {
  const byDepth = new Map<number, StudioConcept[]>();
  for (const c of concepts) byDepth.set(c.depth, [...(byDepth.get(c.depth) ?? []), c]);
  const xOf = new Map<string, number>();
  const nodes: Node<Data>[] = [];
  for (const depth of [...byDepth.keys()].sort((a, b) => a - b)) {
    const layer = byDepth.get(depth)!;
    const avg = (c: StudioConcept) =>
      c.prerequisites.length ? c.prerequisites.reduce((s, p) => s + (xOf.get(p) ?? 0), 0) / c.prerequisites.length : 0;
    layer.sort((a, b) => avg(a) - avg(b) || a.name.localeCompare(b.name));
    layer.forEach((c, i) => {
      const x = (i - (layer.length - 1) / 2) * 230;
      xOf.set(c.id, x);
      nodes.push({
        id: c.id,
        type: "studio",
        position: { x, y: depth * 120 },
        data: { ...c, color: colorOf[c.id] ?? "violet", selected: selectedId === c.id },
      });
    });
  }
  return nodes;
}

export function StudioConceptGraph({
  concepts,
  worlds,
  selectedId,
  onSelect,
  fullHeight = false,
}: {
  concepts: StudioConcept[];
  worlds: StudioWorld[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  fullHeight?: boolean;
}) {
  const { resolvedTheme } = useTheme();
  const colorOf = useMemo(
    () => Object.fromEntries(worlds.flatMap((w) => w.concepts.map((c) => [c, w.color]))),
    [worlds],
  );
  const nodes = useMemo(() => layout(concepts, colorOf, selectedId), [concepts, colorOf, selectedId]);
  const edges: Edge[] = useMemo(
    () =>
      concepts.flatMap((c) =>
        c.prerequisites.map((p) => ({
          id: `${p}->${c.id}`,
          source: p,
          target: c.id,
          type: "smoothstep",
          style: { stroke: "var(--primary)", strokeWidth: 1.5, opacity: 0.7 },
        })),
      ),
    [concepts],
  );
  return (
    <div className={cn("w-full overflow-hidden rounded-xl border bg-card/40", fullHeight ? "h-full min-h-0" : "h-[560px]")}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.25}
        maxZoom={1.6}
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
        colorMode={resolvedTheme === "dark" ? "dark" : "light"}
        onNodeClick={(_, n) => onSelect(n.id)}
      >
        <Background gap={20} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

export function WorldLegend({ worlds, names }: { worlds: StudioWorld[]; names: Record<string, string> }) {
  return (
    <div className="flex flex-wrap gap-2">
      {worlds.map((w) => {
        const theme = WORLD_THEME[w.color] ?? WORLD_THEME.violet;
        return (
          <div key={w.id} className={cn("rounded-lg border px-2.5 py-1.5 text-xs", theme.soft)} title={w.concepts.map((c) => names[c] ?? c).join(", ")}>
            <span className="mr-1">{w.emoji}</span>
            <span className={cn("font-medium", theme.text)}>{w.name}</span>
            <span className="ml-1.5 text-muted-foreground">{w.concepts.length}</span>
          </div>
        );
      })}
    </div>
  );
}
