"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { toast } from "sonner";

import { api } from "../api";
import { useSession } from "../store";
import type { SubjectDetail } from "../types";

export const studioKeys = {
  subjects: ["studio", "subjects"] as const,
  subject: (id: string) => ["studio", "subject", id] as const,
  graph: (id: string) => ["studio", "graph", id] as const,
  concept: (id: string) => ["studio", "concept", id] as const,
  enrollment: (id: string) => ["studio", "enrollment", id] as const,
  studentSubjects: (sid: string) => ["studio", "student-subjects", sid] as const,
};

const busy = (d?: SubjectDetail) => d?.subject.status === "processing";

export function useSubjects() {
  return useQuery({
    queryKey: studioKeys.subjects,
    queryFn: () => api.subjects(),
    refetchInterval: (q) => (q.state.data?.subjects.some((s) => s.status === "processing") ? 2000 : false),
  });
}

export function useSubject(id: string) {
  return useQuery({
    queryKey: studioKeys.subject(id),
    queryFn: () => api.subject(id),
    refetchInterval: (q) => (busy(q.state.data) ? 1500 : false),
  });
}

export function useStudioGraph(id: string, enabled = true) {
  return useQuery({ queryKey: studioKeys.graph(id), queryFn: () => api.studioGraph(id), enabled });
}

export function useStudioConcept(conceptId: string | null) {
  return useQuery({
    queryKey: studioKeys.concept(conceptId ?? "none"),
    queryFn: () => api.studioConcept(conceptId as string),
    enabled: !!conceptId,
  });
}

export function useEnrollment(id: string, enabled = true) {
  return useQuery({ queryKey: studioKeys.enrollment(id), queryFn: () => api.enrollment(id), enabled });
}

export function useStudentSubjects(studentId: string, enabled = true) {
  return useQuery({
    queryKey: studioKeys.studentSubjects(studentId),
    queryFn: () => api.studentSubjects(studentId),
    enabled,
    staleTime: 30_000,
  });
}

/** Display name of the active subject (falls back to the built-in course name while loading). */
export function useActiveSubjectName() {
  const subjectId = useSession((s) => s.subjectId);
  const subjects = useQuery({ queryKey: studioKeys.subjects, queryFn: () => api.subjects(), staleTime: 30_000 });
  return subjects.data?.subjects.find((s) => s.id === subjectId)?.name ?? "Data Structures";
}

/** Run a studio mutation, refresh everything studio-related, toast errors. */
export function useStudioMutation<A, R>(fn: (args: A) => Promise<R>, success?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["studio"] });
      if (success) toast.success(success);
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

/** Switch the active subject and refetch learner/class data for it.
 * resetQueries (not removeQueries): mounted pages keep their observers, so they show a skeleton and then the new
 * subject's data. Removing queries would orphan those observers and leave the old subject on screen. */
export function useSwitchSubject() {
  const qc = useQueryClient();
  const setSubject = useSession((s) => s.setSubject);
  return useCallback(
    (id: string) => {
      if (id === useSession.getState().subjectId) return;
      setSubject(id); // the API client reads the new subject id on the very next request
      void qc.resetQueries({ predicate: (q) => q.queryKey[0] !== "studio" });
    },
    [qc, setSubject],
  );
}
