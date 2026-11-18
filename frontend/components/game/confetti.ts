"use client";

// Effects only on hero moments (CLAUDE.md UI rules): unlock, misconception cleared, boss defeated.
export async function celebrate(kind: "unlock" | "cleared" | "boss" | "mastered" = "unlock") {
  if (typeof window === "undefined") return;
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
  const confetti = (await import("canvas-confetti")).default;
  const colors = ["#8b5cf6", "#a78bfa", "#14b8a6", "#f59e0b", "#10b981"];
  if (kind === "boss") {
    const end = Date.now() + 1200;
    const frame = () => {
      confetti({ particleCount: 6, angle: 60, spread: 70, origin: { x: 0 }, colors });
      confetti({ particleCount: 6, angle: 120, spread: 70, origin: { x: 1 }, colors });
      if (Date.now() < end) requestAnimationFrame(frame);
    };
    frame();
    return;
  }
  confetti({ particleCount: kind === "unlock" ? 70 : 110, spread: 75, origin: { y: 0.65 }, colors, scalar: 0.9 });
}
