// Friendly aliases for the generated OpenAPI types (lib/api-types.ts is generated: `pnpm gen:types`).
import type { components } from "./api-types";

type S = components["schemas"];

export type QuestionPublic = S["QuestionPublic"];
export type NextQuestion = S["NextQuestionResponse"];
export type SessionStart = S["SessionStartResponse"];
export type AttemptRequest = S["AttemptRequest"];
export type AttemptResponse = S["AttemptResponse"];
export type Diagnosis = S["DiagnosisOut"];
export type NextAction = S["NextAction"];
export type XPEvent = S["XPEventOut"];
export type Unlock = S["UnlockOut"];
export type Badge = S["BadgeOut"];
export type ConceptStateOut = S["ConceptStateOut"];
export type StudentMap = S["StudentMapResponse"];
export type MapNode = S["MapNode"];
export type RootReport = S["RootReportResponse"];
export type RootGap = S["RootGap"];
export type LessonPayload = S["LessonPayload"];
export type BossBattle = S["BossBattleOut"];
export type BossAttemptResponse = S["BossAttemptResponse"];
export type TeachScore = S["TeachScoreResponse"];
export type TeachTurnDone = S["TeachTurnDone"];
export type Heatmap = S["HeatmapResponse"];
export type Alerts = S["AlertsResponse"];
export type AlertOut = S["AlertOut"];
export type Cluster = S["ClusterOut"];
export type AdminMetrics = S["AdminMetricsResponse"];
export type Traces = S["TracesResponse"];
export type LLMCall = S["LLMCallOut"];
export type Concept = S["ConceptOut"];
export type StudentSummary = S["StudentSummary"];
export type Hint = S["HintResponse"];
export type ConceptState = MapNode["state"];
export type Confidence = AttemptRequest["confidence"];

// ---- adventure / game layer
export type WorldMap = S["WorldMapResponse"];
export type WorldInfo = S["WorldInfo"];
export type LevelInfo = S["LevelInfo"];
export type LevelRun = S["LevelRunOut"];
export type LevelStart = S["LevelStartResponse"];
export type LevelAnswer = S["LevelAnswerResponse"];
export type Powerup = S["PowerupResponse"];
export type Profile = S["ProfileResponse"];
export type Quest = S["QuestOut"];
export type ConceptDetail = S["ConceptDetail"];
export type ClassGame = S["ClassGameResponse"];
export type GameRun = S["GameRunOut"];
export type GameStudentStat = S["GameStudentStat"];
export type GameLevelStat = S["GameLevelStat"];
