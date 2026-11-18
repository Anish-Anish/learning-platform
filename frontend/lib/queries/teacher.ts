"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "../api";

// The teacher dashboard polls so it updates live while students (or the simulator) work.
export function useHeatmap() {
  return useQuery({ queryKey: ["heatmap"], queryFn: () => api.heatmap(), refetchInterval: 5000 });
}

export function useAlerts() {
  return useQuery({ queryKey: ["alerts"], queryFn: () => api.alerts(), refetchInterval: 5000 });
}

export function useMetrics() {
  return useQuery({ queryKey: ["metrics"], queryFn: () => api.metrics(), refetchInterval: 10_000 });
}

export function useTraces(limit = 40) {
  return useQuery({ queryKey: ["traces", limit], queryFn: () => api.traces(limit), refetchInterval: 10_000 });
}
