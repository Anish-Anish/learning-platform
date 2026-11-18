"use client";

// Tiny synthesized sound effects (Web Audio, no asset files). Respects the HUD mute toggle.
import { useSession } from "./store";

let ctx: AudioContext | null = null;

function audio(): AudioContext | null {
  if (typeof window === "undefined" || useSession.getState().muted) return null;
  try {
    ctx ??= new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    if (ctx.state === "suspended") void ctx.resume();
    return ctx;
  } catch {
    return null;
  }
}

function tone(freq: number, start: number, dur: number, type: OscillatorType = "sine", gain = 0.08) {
  const a = audio();
  if (!a) return;
  const o = a.createOscillator();
  const g = a.createGain();
  o.type = type;
  o.frequency.setValueAtTime(freq, a.currentTime + start);
  g.gain.setValueAtTime(0, a.currentTime + start);
  g.gain.linearRampToValueAtTime(gain, a.currentTime + start + 0.015);
  g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + start + dur);
  o.connect(g).connect(a.destination);
  o.start(a.currentTime + start);
  o.stop(a.currentTime + start + dur + 0.02);
}

export const sfx = {
  click: () => tone(660, 0, 0.06, "triangle", 0.04),
  correct: () => {
    tone(660, 0, 0.12, "triangle");
    tone(990, 0.08, 0.18, "triangle");
  },
  combo: (n: number) => {
    const base = 520 + Math.min(n, 8) * 60;
    [0, 0.07, 0.14].forEach((t, i) => tone(base * (1 + i * 0.25), t, 0.14, "square", 0.04));
  },
  wrong: () => {
    tone(220, 0, 0.18, "sawtooth", 0.05);
    tone(160, 0.12, 0.25, "sawtooth", 0.05);
  },
  heart: () => tone(140, 0, 0.35, "square", 0.05),
  star: (i: number) => tone([784, 988, 1175][i] ?? 1175, 0, 0.25, "triangle", 0.09),
  win: () => [523, 659, 784, 1047].forEach((f, i) => tone(f, i * 0.11, 0.3, "triangle", 0.08)),
  lose: () => [392, 330, 262, 196].forEach((f, i) => tone(f, i * 0.14, 0.3, "sine", 0.07)),
  powerup: () => [880, 1320, 1760].forEach((f, i) => tone(f, i * 0.05, 0.12, "sine", 0.06)),
  unlock: () => [523, 784, 1047, 1568].forEach((f, i) => tone(f, i * 0.08, 0.22, "triangle", 0.07)),
};
