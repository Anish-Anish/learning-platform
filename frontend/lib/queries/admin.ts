"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import { api, type LogQuery, type TraceQuery } from "../api";
import type { MetricsWindow } from "../types";

export const WINDOWS: { id: MetricsWindow; label: string }[] = [
  { id: "1h", label: "Last hour" },
  { id: "24h", label: "Last 24 hours" },
  { id: "7d", label: "Last 7 days" },
  { id: "30d", label: "Last 30 days" },
  { id: "all", label: "All time" },
];

type AdminPrefs = { window: MetricsWindow; live: boolean; setWindow: (w: MetricsWindow) => void; setLive: (v: boolean) => void };

/** Time window + live-refresh toggle shared by every admin page (persisted per browser). */
export const useAdminPrefs = create<AdminPrefs>()(
  persist(
    (set) => ({
      window: "24h",
      live: true,
      setWindow: (window) => set({ window }),
      setLive: (live) => set({ live }),
    }),
    { name: "rootwise-admin", storage: createJSONStorage(() => localStorage) },
  ),
);

const every = (ms: number) => () => (useAdminPrefs.getState().live ? ms : false);

export function useMetrics() {
  const window = useAdminPrefs((s) => s.window);
  return useQuery({
    queryKey: ["admin", "metrics", window],
    queryFn: () => api.metrics(window),
    refetchInterval: every(10_000),
    placeholderData: keepPreviousData,
  });
}

export function useTraces(query: TraceQuery, enabled = true) {
  const window = useAdminPrefs((s) => s.window);
  const q = { window, ...query };
  return useQuery({
    queryKey: ["admin", "traces", q],
    queryFn: () => api.traces(q),
    enabled,
    refetchInterval: every(10_000),
    placeholderData: keepPreviousData,
  });
}

export function useLogs(query: LogQuery, enabled = true) {
  const window = useAdminPrefs((s) => s.window);
  const q = { window, ...query };
  return useQuery({
    queryKey: ["admin", "logs", q],
    queryFn: () => api.logs(q),
    enabled,
    refetchInterval: every(5_000),
    placeholderData: keepPreviousData,
  });
}

export function useTelemetry() {
  return useQuery({ queryKey: ["admin", "telemetry"], queryFn: () => api.telemetry(), refetchInterval: every(15_000) });
}
