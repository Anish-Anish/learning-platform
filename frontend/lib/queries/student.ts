"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api";
import type { AttemptRequest } from "../types";

export const keys = {
  next: (sid: string) => ["next", sid] as const,
  map: (sid: string) => ["map", sid] as const,
  report: (sid: string) => ["report", sid] as const,
  student: (sid: string) => ["student", sid] as const,
  diagnosis: (id: string) => ["diagnosis", id] as const,
  concepts: ["concepts"] as const,
  boss: (sid: string, id?: string) => ["boss", sid, id ?? "current"] as const,
};

export function useStartSession() {
  return useMutation({ mutationFn: (studentId: string) => api.startSession(studentId) });
}

export function useNextQuestion(studentId: string, enabled = true) {
  return useQuery({ queryKey: keys.next(studentId), queryFn: () => api.nextQuestion(studentId), enabled, staleTime: Infinity });
}

export function useSubmitAttempt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AttemptRequest) => api.submitAttempt(body),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: keys.map(vars.student_id) });
      qc.invalidateQueries({ queryKey: keys.report(vars.student_id) });
      qc.invalidateQueries({ queryKey: keys.student(vars.student_id) });
      qc.invalidateQueries({ queryKey: ["profile", vars.student_id] });
      qc.invalidateQueries({ queryKey: ["world", vars.student_id] });
    },
  });
}

export function useDiagnosis(id: string | null | undefined) {
  return useQuery({
    queryKey: keys.diagnosis(id ?? "none"),
    queryFn: () => api.diagnosis(id as string),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data?.status === "pending" ? 700 : false),
  });
}

export function useStudentMap(studentId: string) {
  return useQuery({ queryKey: keys.map(studentId), queryFn: () => api.map(studentId), retry: 1 });
}

export function useReport(studentId: string) {
  return useQuery({ queryKey: keys.report(studentId), queryFn: () => api.report(studentId), retry: 1, enabled: !!studentId });
}

export function useStudent(studentId: string) {
  return useQuery({ queryKey: keys.student(studentId), queryFn: () => api.student(studentId), retry: 0 });
}

export function useConcepts() {
  return useQuery({ queryKey: keys.concepts, queryFn: () => api.concepts(), staleTime: 5 * 60_000 });
}

export function useBoss(studentId: string, battleId?: string, enabled = true) {
  return useQuery({
    queryKey: keys.boss(studentId, battleId),
    queryFn: () => api.boss(studentId, battleId),
    enabled,
    retry: 0,
    staleTime: Infinity,
  });
}
