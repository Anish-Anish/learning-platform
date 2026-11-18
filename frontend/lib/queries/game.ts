"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "../api";

export const gameKeys = {
  world: (sid: string) => ["world", sid] as const,
  profile: (sid: string) => ["profile", sid] as const,
  concept: (cid: string) => ["concept", cid] as const,
};

export function useWorld(studentId: string) {
  return useQuery({ queryKey: gameKeys.world(studentId), queryFn: () => api.world(studentId), retry: 1 });
}

export function useProfile(studentId: string, enabled = true) {
  return useQuery({ queryKey: gameKeys.profile(studentId), queryFn: () => api.profile(studentId), retry: 0, enabled });
}

export function useConceptDetail(conceptId: string | null | undefined) {
  return useQuery({
    queryKey: gameKeys.concept(conceptId ?? ""),
    queryFn: () => api.conceptDetail(conceptId as string),
    enabled: !!conceptId,
    staleTime: 10 * 60_000,
  });
}

export function useClassGame(studentId?: string) {
  return useQuery({ queryKey: ["class-game", studentId ?? "all"], queryFn: () => api.classGame(studentId), refetchInterval: 5000 });
}
