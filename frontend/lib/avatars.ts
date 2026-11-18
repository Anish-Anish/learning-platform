// Cosmetic heroes, unlocked by total stars. Purely cosmetic: no learning effect, no XP.
export type Avatar = { id: string; emoji: string; name: string; stars: number; bg: string };

export const AVATARS: Avatar[] = [
  { id: "fox", emoji: "🦊", name: "Fox", stars: 0, bg: "from-orange-400 to-amber-500" },
  { id: "panda", emoji: "🐼", name: "Panda", stars: 0, bg: "from-slate-300 to-slate-500" },
  { id: "owl", emoji: "🦉", name: "Owl", stars: 3, bg: "from-amber-600 to-yellow-700" },
  { id: "robot", emoji: "🤖", name: "Robot", stars: 6, bg: "from-sky-400 to-cyan-600" },
  { id: "octo", emoji: "🐙", name: "Octo", stars: 10, bg: "from-pink-400 to-fuchsia-600" },
  { id: "dragon", emoji: "🐉", name: "Dragon", stars: 15, bg: "from-emerald-400 to-green-700" },
  { id: "unicorn", emoji: "🦄", name: "Unicorn", stars: 25, bg: "from-violet-400 to-fuchsia-500" },
  { id: "wizard", emoji: "🧙", name: "Wizard", stars: 40, bg: "from-indigo-500 to-violet-700" },
];

export const avatarById = (id: string) => AVATARS.find((a) => a.id === id) ?? AVATARS[0];

// Tailwind class sets per world colour (written out so Tailwind can see them).
export const WORLD_THEME: Record<string, { grad: string; ring: string; text: string; soft: string; node: string }> = {
  emerald: { grad: "from-emerald-400 to-teal-600", ring: "ring-emerald-400", text: "text-emerald-600 dark:text-emerald-400", soft: "bg-emerald-500/10", node: "from-emerald-400 to-emerald-600 shadow-emerald-700/40" },
  violet: { grad: "from-violet-500 to-purple-700", ring: "ring-violet-400", text: "text-violet-600 dark:text-violet-400", soft: "bg-violet-500/10", node: "from-violet-400 to-violet-600 shadow-violet-800/40" },
  sky: { grad: "from-sky-400 to-blue-600", ring: "ring-sky-400", text: "text-sky-600 dark:text-sky-400", soft: "bg-sky-500/10", node: "from-sky-400 to-sky-600 shadow-sky-800/40" },
  cyan: { grad: "from-cyan-400 to-teal-600", ring: "ring-cyan-400", text: "text-cyan-600 dark:text-cyan-400", soft: "bg-cyan-500/10", node: "from-cyan-400 to-cyan-600 shadow-cyan-800/40" },
  lime: { grad: "from-lime-400 to-green-600", ring: "ring-lime-400", text: "text-lime-700 dark:text-lime-400", soft: "bg-lime-500/10", node: "from-lime-400 to-green-600 shadow-green-800/40" },
  amber: { grad: "from-amber-400 to-orange-600", ring: "ring-amber-400", text: "text-amber-600 dark:text-amber-400", soft: "bg-amber-500/10", node: "from-amber-400 to-orange-500 shadow-orange-800/40" },
  fuchsia: { grad: "from-fuchsia-500 to-indigo-700", ring: "ring-fuchsia-400", text: "text-fuchsia-600 dark:text-fuchsia-400", soft: "bg-fuchsia-500/10", node: "from-fuchsia-400 to-fuchsia-600 shadow-fuchsia-800/40" },
  rose: { grad: "from-rose-400 to-pink-600", ring: "ring-rose-400", text: "text-rose-600 dark:text-rose-400", soft: "bg-rose-500/10", node: "from-rose-400 to-rose-600 shadow-rose-800/40" },
};
