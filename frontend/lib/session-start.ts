"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "./api";
import { useSession } from "./store";

// One in-flight POST /session/start per learner and subject (React StrictMode mounts effects twice in dev).
// The subject is part of the key: the response carries that subject's first question.
const startCache = new Map<string, ReturnType<typeof api.startSession>>();

export function startSessionOnce(studentId: string) {
  const key = `${studentId}:${useSession.getState().subjectId}`;
  let p = startCache.get(key);
  if (!p) {
    p = api.startSession(studentId);
    startCache.set(key, p);
    setTimeout(() => startCache.delete(key), 3000);
  }
  return p;
}

/** Makes sure the pseudonymous student exists on the backend; returns readiness and any error. */
export function useEnsureStudent(studentId: string, enabled = true) {
  const qc = useQueryClient();
  const [readyFor, setReadyFor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    startSessionOnce(studentId)
      .then(() => {
        if (cancelled) return;
        setReadyFor(studentId);
        void qc.invalidateQueries({ queryKey: ["profile", studentId] });
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [studentId, enabled, qc]);
  return { ready: readyFor === studentId, error };
}
