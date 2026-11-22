// Feature flags (CONTRIBUTING.md rule 9). Backend flags live in backend/app/config.py.
const on = (v: string | undefined, dflt = true) => (v === undefined ? dflt : v === "true");

export const flags = {
  useMocks: on(process.env.NEXT_PUBLIC_USE_MOCKS, false),
  replay: on(process.env.NEXT_PUBLIC_FLAG_REPLAY),
  boss: on(process.env.NEXT_PUBLIC_FLAG_BOSS),
  teach: on(process.env.NEXT_PUBLIC_FLAG_TEACH),
  hints: on(process.env.NEXT_PUBLIC_FLAG_HINTS),
} as const;
