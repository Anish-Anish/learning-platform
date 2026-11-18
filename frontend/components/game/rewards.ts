"use client";

import { toast } from "sonner";

import { useSession } from "@/lib/store";
import type { Badge, Unlock, XPEvent } from "@/lib/types";

import { celebrate } from "./confetti";

/** Toast XP / unlocks / badges from any attempt-like response and bump the XP pill. */
export function announceRewards(r: { xp_events: XPEvent[]; unlocks: Unlock[]; badges: Badge[]; cleared_misconception_ids?: string[] }) {
  const add = useSession.getState().addXp;
  let hero: "unlock" | "cleared" | "boss" | "mastered" | null = null;
  for (const x of r.xp_events) {
    if (x.kind === "unlock") continue;
    add(x.amount);
    if (x.amount > 0) toast.success(`+${x.amount} XP`, { description: x.reason });
    else if (x.amount < 0) toast(`${x.amount} XP`, { description: x.reason });
    if (x.kind === "boss_defeated") hero = "boss";
    else if (x.kind === "misconception_cleared" && hero !== "boss") hero = "cleared";
    else if (x.kind === "concept_mastered" && !hero) hero = "mastered";
  }
  for (const u of r.unlocks) {
    toast(`🔓 Unlocked: ${u.concept_name}`, { description: u.reason });
    hero ??= "unlock";
  }
  for (const b of r.badges) toast(`🏅 Badge earned: ${b.name}`, { description: b.description });
  if (hero) void celebrate(hero);
}
