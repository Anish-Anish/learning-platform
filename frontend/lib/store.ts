"use client";

import { useEffect, useState } from "react";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export const DEFAULT_SUBJECT_ID = "data_structures";

type SessionState = {
  studentId: string;
  subjectId: string;
  sessionId: string | null;
  xp: number;
  level: number;
  avatar: string;
  muted: boolean;
  setAvatar: (a: string) => void;
  toggleMuted: () => void;
  setStudent: (id: string) => void;
  setSubject: (id: string) => void;
  setSession: (id: string | null) => void;
  setXp: (xp: number, level?: number) => void;
  addXp: (amount: number) => void;
};

export const XP_PER_LEVEL = 250;

export const useSession = create<SessionState>()(
  persist(
    (set) => ({
      studentId: "demo_student",
      subjectId: DEFAULT_SUBJECT_ID,
      sessionId: null,
      xp: 0,
      level: 1,
      avatar: "fox",
      muted: false,
      setAvatar: (avatar) => set({ avatar }),
      toggleMuted: () => set((s) => ({ muted: !s.muted })),
      setStudent: (id) => set({ studentId: id, sessionId: null, xp: 0, level: 1 }),
      setSubject: (id) => set({ subjectId: id, sessionId: null }),
      setSession: (id) => set({ sessionId: id }),
      setXp: (xp, level) => set({ xp, level: level ?? 1 + Math.floor(Math.max(0, xp) / XP_PER_LEVEL) }),
      addXp: (amount) =>
        set((s) => {
          const xp = s.xp + amount;
          return { xp, level: 1 + Math.floor(Math.max(0, xp) / XP_PER_LEVEL) };
        }),
    }),
    // Rehydrated explicitly on the client (see useHydrated) so server and first client render match.
    { name: "rootwise-session", storage: createJSONStorage(() => localStorage), skipHydration: true },
  ),
);

/** True once the persisted session (student id, XP) has been loaded from localStorage. */
export function useHydrated() {
  // `persist` is absent during server rendering (no localStorage).
  const [hydrated, setHydrated] = useState(() => useSession.persist?.hasHydrated() ?? false);
  useEffect(() => {
    const p = useSession.persist;
    if (!p) return;
    const unsub = p.onFinishHydration(() => setHydrated(true));
    void p.rehydrate();
    return unsub;
  }, []);
  return hydrated;
}
