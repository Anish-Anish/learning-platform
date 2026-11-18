"use client";

import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart } from "recharts";

import { type ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { BLOOM_LABEL } from "@/lib/states";
import type { RootReport } from "@/lib/types";

const config = { accuracy: { label: "Accuracy %", color: "var(--primary)" } } satisfies ChartConfig;

export function BloomRadar({ data }: { data: RootReport["bloom_radar"] }) {
  const rows = data.map((d) => ({ level: `${BLOOM_LABEL[d.level]} (${d.attempts})`, accuracy: Math.round(d.accuracy * 100) }));
  return (
    <ChartContainer config={config} className="mx-auto aspect-square max-h-[260px]">
      <RadarChart data={rows} outerRadius="72%">
        <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
        <PolarGrid />
        <PolarAngleAxis dataKey="level" tick={{ fontSize: 11 }} />
        <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
        <Radar dataKey="accuracy" fill="var(--color-accuracy)" fillOpacity={0.35} stroke="var(--color-accuracy)" strokeWidth={2} />
      </RadarChart>
    </ChartContainer>
  );
}
