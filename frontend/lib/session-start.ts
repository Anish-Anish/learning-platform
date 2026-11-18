"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "./api";

// One in-flight POST /session/start per learner (React StrictMode mounts effects twice in dev).
const startCache = new Map<string, ReturnType<typeof api.startSession>>();

export function startSessionOnce(studentId: string) {
  let p = startCache.get(studentId);
  if (!p) {
    p = api.startSession(studentId);
    startCache.set(studentId, p);
    setTimeout(() => startCache.delete(studentId), 3000);
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
