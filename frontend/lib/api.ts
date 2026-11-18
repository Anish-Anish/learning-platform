// Typed API client. Generated types come from FastAPI's OpenAPI (`pnpm gen:types`).
// With NEXT_PUBLIC_USE_MOCKS=true every call is served from lib/mocks (mock-first, CLAUDE.md rule 8).
import createClient from "openapi-fetch";

import type { paths } from "./api-types";
import { flags } from "./flags";
import { mockApi } from "./mocks";
import { readSSE, type SSEHandler } from "./sse";
import type {
  AdminMetrics,
  Alerts,
  ClassGame,
  ConceptDetail,
  LevelAnswer,
  LevelStart,
  Powerup,
  Profile,
  WorldMap,
  AttemptRequest,
  AttemptResponse,
  BossAttemptResponse,
  BossBattle,
  Concept,
  Diagnosis,
  Heatmap,
  Hint,
  NextQuestion,
  RootReport,
  SessionStart,
  StudentMap,
  StudentSummary,
  TeachScore,
  Traces,
} from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const client = createClient<paths>({ baseUrl: API_URL });

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public traceId?: string | null,
  ) {
    super(message);
  }
}

async function unwrap<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  let r: { data?: T; error?: unknown; response: Response };
  try {
    r = await p;
  } catch {
    throw new ApiError(`Can't reach the Rootwise API at ${API_URL}. Is the backend running?`, 0);
  }
  if (r.error !== undefined || r.data === undefined) {
    const err = r.error as { detail?: unknown } | undefined;
    const detail = typeof err?.detail === "string" ? err.detail : `Request failed (${r.response.status})`;
    throw new ApiError(detail, r.response.status, r.response.headers.get("x-trace-id"));
  }
  return r.data;
}

const real = {
  startSession: (student_id: string) =>
    unwrap<SessionStart>(client.POST("/session/start", { body: { student_id } })),
  nextQuestion: (student_id: string) =>
    unwrap<NextQuestion>(client.GET("/next-question", { params: { query: { student_id } } })),
  submitAttempt: (body: AttemptRequest) => unwrap<AttemptResponse>(client.POST("/attempts", { body })),
  diagnosis: (id: string) =>
    unwrap<Diagnosis>(client.GET("/diagnoses/{diagnosis_id}", { params: { path: { diagnosis_id: id } } })),
  student: (student_id: string) =>
    unwrap<StudentSummary>(client.GET("/students/{student_id}", { params: { path: { student_id } } })),
  map: (student_id: string) =>
    unwrap<StudentMap>(client.GET("/students/{student_id}/map", { params: { path: { student_id } } })),
  report: (student_id: string) =>
    unwrap<RootReport>(client.GET("/students/{student_id}/report", { params: { path: { student_id } } })),
  concepts: () => unwrap<Concept[]>(client.GET("/concepts")),
  hint: (question_id: string, level: number, student_id: string) =>
    unwrap<Hint>(
      client.GET("/hint/{question_id}", { params: { path: { question_id }, query: { level, student_id } } }),
    ),
  boss: (student_id: string, battle_id?: string) =>
    unwrap<BossBattle>(
      client.GET("/boss/{student_id}", {
        params: { path: { student_id }, query: battle_id ? { battle_id } : {} },
      }),
    ),
  bossAttempt: (battle_id: string, body: { question_id: string; option_id: string; confidence: "sure" | "guess" }) =>
    unwrap<BossAttemptResponse>(
      client.POST("/boss/{battle_id}/attempt", { params: { path: { battle_id } }, body: { ...body, time_ms: 0 } }),
    ),
  teachScore: (session_id: string) =>
    unwrap<TeachScore>(client.POST("/teach/{session_id}/score", { params: { path: { session_id } } })),
  heatmap: () => unwrap<Heatmap>(client.GET("/class/heatmap")),
  alerts: () => unwrap<Alerts>(client.GET("/class/alerts")),
  metrics: () => unwrap<AdminMetrics>(client.GET("/admin/metrics")),
  traces: (limit = 40) => unwrap<Traces>(client.GET("/admin/traces", { params: { query: { limit } } })),
  feedback: (body: {
    student_id: string;
    target_kind: "lesson" | "question";
    target_id: string;
    rating: number;
    comment?: string;
  }) => unwrap(client.POST("/feedback", { body })),
  simRun: (students = 30) =>
    unwrap(client.POST("/sim/run", { body: { students, attempts_per_student: 40, seed: 7, remediation: true, reset: true } })),

  // ---- adventure mode
  world: (student_id: string) =>
    unwrap<WorldMap>(client.GET("/students/{student_id}/world", { params: { path: { student_id } } })),
  profile: (student_id: string) =>
    unwrap<Profile>(client.GET("/students/{student_id}/profile", { params: { path: { student_id } } })),
  conceptDetail: (concept_id: string) =>
    unwrap<ConceptDetail>(client.GET("/concepts/{concept_id}", { params: { path: { concept_id } } })),
  startLevel: (concept_id: string, student_id: string, restart = false) =>
    unwrap<LevelStart>(
      client.POST("/levels/{concept_id}/start", { params: { path: { concept_id } }, body: { student_id, restart } }),
    ),
  levelAnswer: (
    run_id: string,
    body: { option_id: string; confidence: "sure" | "guess"; hints_used?: number; time_ms?: number; session_id?: string | null },
  ) =>
    unwrap<LevelAnswer>(
      client.POST("/levels/runs/{run_id}/answer", {
        params: { path: { run_id } },
        body: { ...body, hints_used: body.hints_used ?? 0, time_ms: body.time_ms ?? 0 },
      }),
    ),
  levelFifty: (run_id: string) =>
    unwrap<Powerup>(client.POST("/levels/runs/{run_id}/fifty", { params: { path: { run_id } } })),
  classGame: (student_id?: string) =>
    unwrap<ClassGame>(client.GET("/class/game", { params: { query: student_id ? { student_id } : {} } })),

  // ---- SSE endpoints
  streamLesson: async (
    concept_id: string,
    student_id: string,
    misconception_id: string | null | undefined,
    onEvent: SSEHandler,
    signal?: AbortSignal,
  ) => {
    const q = new URLSearchParams({ student_id });
    if (misconception_id) q.set("misconception_id", misconception_id);
    const res = await fetch(`${API_URL}/lesson/${encodeURIComponent(concept_id)}?${q}`, { signal });
    await readSSE(res, onEvent);
  },
  streamTeach: async (
    concept_id: string,
    body: { student_id: string; session_id?: string | null; message: string },
    onEvent: SSEHandler,
    signal?: AbortSignal,
  ) => {
    const res = await fetch(`${API_URL}/teach/${encodeURIComponent(concept_id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    await readSSE(res, onEvent);
  },
};

export type Api = typeof real;

export const api: Api = flags.useMocks ? (mockApi as unknown as Api) : real;
