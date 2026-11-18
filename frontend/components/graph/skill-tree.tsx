"use client";

import "@xyflow/react/dist/style.css";

import {
  Background,
  Controls,
  Handle,
  type Edge,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
} from "@xyflow/react";
import { LockIcon, TriangleAlertIcon } from "lucide-react";
import { useTheme } from "next-themes";
import { memo, useMemo } from "react";

import { STATE_META } from "@/lib/states";
import type { MapNode, StudentMap } from "@/lib/types";
import { cn } from "@/lib/utils";

type ConceptNodeData = MapNode & { pulse?: boolean; selected?: boolean };

const ConceptNode = memo(function ConceptNode({ data }: NodeProps<Node<ConceptNodeData>>) {
  const meta = STATE_META[data.state];
  const locked = data.state === "locked";
  return (
    <div
      className={cn(
        "w-[196px] rounded-xl border-2 bg-card px-3 py-2 shadow-sm transition-all",
        meta.border,
        data.pulse && "rw-pulse",
        data.selected && "ring-2 ring-primary ring-offset-2 ring-offset-background",
        locked && "opacity-70",
      )}
    >
      <Handle type="target" position={Position.Top} className="!size-1.5 !border-0 !bg-muted-foreground/40" />
      <div className="flex items-start gap-1.5">
        <span className={cn("mt-1 size-2 shrink-0 rounded-full", meta.dot)} />
        <p className={cn("flex-1 text-[12.5px] leading-tight font-medium", locked && "text-muted-foreground")}>{data.name}</p>
        {locked && <LockIcon className="size-3.5 shrink-0 text-muted-foreground" />}
        {data.state === "misconception" && <TriangleAlertIcon className="size-3.5 shrink-0 text-rose-500" />}
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div className={cn("h-full rounded-full", meta.dot)} style={{ width: `${Math.round(data.mastery * 100)}%` }} />
        </div>
        <span className={cn("text-[10px] tabular-nums", meta.text)}>{locked ? meta.label : `${Math.round(data.mastery * 100)}%`}</span>
      </div>
      <Handle type="source" position={Position.Bottom} className="!size-1.5 !border-0 !bg-muted-foreground/40" />
    </div>
  );
});

const nodeTypes = { concept: ConceptNode };

export function layoutMap(map: StudentMap, pulse: Set<string>, selectedId?: string | null) {
  const byDepth = new Map<number, MapNode[]>();
  for (const n of map.nodes) byDepth.set(n.depth, [...(byDepth.get(n.depth) ?? []), n]);
  // Order nodes in each layer by the average x of their prerequisites to reduce edge crossings.
  const xOf = new Map<string, number>();
  const nodes: Node<ConceptNodeData>[] = [];
  const parents = new Map<string, string[]>();
  for (const e of map.edges) parents.set(e.target, [...(parents.get(e.target) ?? []), e.source]);
  for (const depth of [...byDepth.keys()].sort((a, b) => a - b)) {
    const layer = byDepth.get(depth)!;
    layer.sort((a, b) => {
      const avg = (n: MapNode) => {
        const ps = parents.get(n.id) ?? [];
        return ps.length ? ps.reduce((s, p) => s + (xOf.get(p) ?? 0), 0) / ps.length : 0;
      };
      return avg(a) - avg(b) || a.name.localeCompare(b.name);
    });
    const gap = 225;
    layer.forEach((n, i) => {
      const x = (i - (layer.length - 1) / 2) * gap;
      xOf.set(n.id, x);
      nodes.push({
        id: n.id,
        type: "concept",
        position: { x, y: depth * 125 },
        data: { ...n, pulse: pulse.has(n.id), selected: selectedId === n.id },
      });
    });
  }
  return nodes;
}

export function SkillTree({
  map,
  pulse = new Set<string>(),
  selectedId,
  onSelect,
  className,
}: {
  map: StudentMap;
  pulse?: Set<string>;
  selectedId?: string | null;
  onSelect?: (n: MapNode) => void;
  className?: string;
}) {
  const { resolvedTheme } = useTheme();
  const nodes = useMemo(() => layoutMap(map, pulse, selectedId), [map, pulse, selectedId]);
  const stateById = useMemo(() => Object.fromEntries(map.nodes.map((n) => [n.id, n.state])), [map.nodes]);
  const edges: Edge[] = useMemo(
    () =>
      map.edges.map((e) => {
        const solid = stateById[e.source] === "mastered";
        const live = stateById[e.target] !== "locked";
        return {
          id: `${e.source}->${e.target}`,
          source: e.source,
          target: e.target,
          type: "smoothstep",
          animated: live && !solid && stateById[e.target] !== "mastered",
          style: {
            stroke: solid ? "oklch(0.696 0.17 162.48)" : live ? "var(--primary)" : "var(--border)",
            strokeWidth: solid ? 2 : 1.5,
            opacity: live ? 0.9 : 0.6,
          },
        };
      }),
    [map.edges, stateById],
  );
  return (
    <div className={cn("h-[640px] w-full overflow-hidden rounded-xl border bg-card/40", className)}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        minZoom={0.3}
        maxZoom={1.6}
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
        colorMode={resolvedTheme === "dark" ? "dark" : "light"}
        onNodeClick={(_, n) => onSelect?.(n.data as MapNode)}
      >
        <Background gap={20} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

export function StateLegend({ counts }: { counts?: Record<string, number> }) {
  return (
    <div className="flex flex-wrap gap-3 text-xs">
      {(Object.keys(STATE_META) as (keyof typeof STATE_META)[]).map((s) => (
        <span key={s} className="flex items-center gap-1.5 text-muted-foreground">
          <span className={cn("size-2.5 rounded-full", STATE_META[s].dot)} />
          {STATE_META[s].label}
          {counts && <span className="tabular-nums text-foreground">{counts[s] ?? 0}</span>}
        </span>
      ))}
    </div>
  );
}
