"""Request/response contracts for every endpoint in PROJECT_CONTEXT §11. SHARED CONTRACT.

Every response model carries `trace_id`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .common import (
    AlertKind,
    BadgeId,
    BloomLevel,
    ConceptState,
    Confidence,
    ConfidenceSignal,
    DiagnosisStatus,
    FeedbackTarget,
    NextActionKind,
    Phase,
    Severity,
    XPKind,
)
from .content import QuestionPublic


class Traced(BaseModel):
    trace_id: str


# ---------------------------------------------------------------- gamification bits
class XPEventOut(BaseModel):
    kind: XPKind
    amount: int
    reason: str
    concept_id: str | None = None


class UnlockOut(BaseModel):
    concept_id: str
    concept_name: str
    reason: str


class BadgeOut(BaseModel):
    badge_id: BadgeId
    name: str
    description: str
    earned_at: datetime | None = None


class ConceptStateOut(BaseModel):
    concept_id: str
    concept_name: str
    state: ConceptState
    mastery: float = Field(description="sigmoid(theta), 0..1")
    n_attempts: int
    active_misconception_ids: list[str]
    reason: str


# ---------------------------------------------------------------- session / questions
class SessionStartRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")


class StudentSummary(BaseModel):
    id: str
    display_name: str
    xp_total: int
    level: int
    streak_days: int
    is_simulated: bool


class NextQuestionResponse(Traced):
    question: QuestionPublic | None
    reason: str
    phase: Phase
    diagnostic_progress: int = Field(description="How many of the 5 diagnostic questions are done")
    diagnostic_total: int = 5


class SessionStartResponse(Traced):
    session_id: str
    student: StudentSummary
    next: NextQuestionResponse


class AttemptRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=64)
    question_id: str
    option_id: str | None = None
    answer_text: str | None = Field(default=None, max_length=1000)
    confidence: Confidence
    time_ms: int = Field(default=0, ge=0)
    hints_used: int = Field(default=0, ge=0, le=3)
    reasoning_text: str | None = Field(default=None, max_length=1000)
    session_id: str | None = None


class DiagnosisRef(BaseModel):
    status: DiagnosisStatus | None = None
    id: str | None = None


class NextAction(BaseModel):
    kind: NextActionKind
    concept_id: str | None = None
    misconception_id: str | None = None
    message: str


class AttemptResponse(Traced):
    attempt_id: str
    is_correct: bool
    correct_option_id: str | None
    explanation: str
    signal: ConfidenceSignal
    selected_misconception_id: str | None
    progress_awarded: bool = Field(description="False when anti-farming blocked progress")
    concept_state: ConceptStateOut
    xp_events: list[XPEventOut]
    unlocks: list[UnlockOut]
    badges: list[BadgeOut]
    cleared_misconception_ids: list[str]
    diagnosis: DiagnosisRef
    next_action: NextAction


class DiagnosisOut(Traced):
    id: str
    status: DiagnosisStatus
    student_id: str
    trigger_attempt_id: str
    failed_concept_id: str
    root_concept_id: str | None
    root_concept_name: str | None
    misconception_id: str | None
    misconception_text: str | None
    correct_belief: str | None
    evidence: list[str]
    path: list[str]
    confidence: float | None
    needs_probe: bool
    probe_concept_id: str | None
    student_message: str | None
    source: str | None = Field(default=None, description="'llm' or 'fallback'")
    replay_id: str | None = None


# ---------------------------------------------------------------- map / report
class MapNode(BaseModel):
    id: str
    name: str
    state: ConceptState
    mastery: float
    n_attempts: int
    depth: int
    active_misconception_ids: list[str]
    reason: str


class MapEdge(BaseModel):
    source: str  # prerequisite
    target: str  # dependent concept


class StudentMapResponse(Traced):
    student_id: str
    nodes: list[MapNode]
    edges: list[MapEdge]


class RootGap(BaseModel):
    concept_id: str
    concept_name: str
    state: ConceptState
    mastery: float
    misconception_id: str | None
    misconception_text: str | None
    evidence: list[str]
    diagnosis_id: str | None
    path: list[str] = Field(default_factory=list)


class BloomScore(BaseModel):
    level: BloomLevel
    accuracy: float
    attempts: int


class Calibration(BaseModel):
    score: float | None
    n: int
    sure_correct: int
    sure_wrong: int
    guess_correct: int
    guess_wrong: int


class NextStep(BaseModel):
    kind: NextActionKind
    concept_id: str | None
    label: str
    reason: str


class RootReportResponse(Traced):
    student_id: str
    root_gaps: list[RootGap]
    bloom_radar: list[BloomScore]
    calibration: Calibration
    next_step: NextStep
    xp_total: int
    level: int
    streak_days: int
    badges: list[BadgeOut]
    recent_xp: list[XPEventOut]
    state_counts: dict[str, int]
    attempts_total: int
    accuracy: float | None


# ---------------------------------------------------------------- tutor
class LessonPayload(BaseModel):
    concept_id: str
    concept_name: str
    misconception_id: str | None
    lesson_md: str
    worked_example: str
    analogy: str
    socratic_questions: list[str]
    citations: list[str]
    mastery_check_question_ids: list[str]
    replay_id: str | None
    source: str


class TeachTurnDone(BaseModel):
    """Payload of the final `done` SSE event of POST /teach/{concept_id}."""

    session_id: str
    reply: str
    on_topic: bool
    covered_points: list[str]
    missing_points: list[str]
    coverage: float
    flags: list[str]
    source: str


class HintResponse(Traced):
    question_id: str
    level: int
    hint: str
    xp_cost: int


# ---------------------------------------------------------------- boss
class BossBattleOut(Traced):
    id: str
    student_id: str
    name: str
    taunt: str
    hp: int
    max_hp: int
    status: str  # active / won / lost
    misconception_ids: list[str]
    questions: list[QuestionPublic]
    current_index: int
    damage_per_hit: int


class BossAttemptRequest(BaseModel):
    question_id: str
    option_id: str
    confidence: Confidence = "sure"
    time_ms: int = 0


class BossAttemptResponse(Traced):
    is_correct: bool
    correct_option_id: str | None
    explanation: str
    damage: int
    hp: int
    max_hp: int
    status: str
    current_index: int
    xp_events: list[XPEventOut]
    badges: list[BadgeOut]
    cleared_misconception_ids: list[str]
    unlocks: list[UnlockOut]


# ---------------------------------------------------------------- teach the bot
class TeachMessageRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=64)
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=1000)


class TeachScoreResponse(Traced):
    session_id: str
    concept_id: str
    score: int
    covered_points: list[str]
    missing_points: list[str]
    misconceptions_detected: list[str]
    feedback: str
    xp_events: list[XPEventOut]
    badges: list[BadgeOut]
    source: str


# ---------------------------------------------------------------- class / teacher
class HeatmapStudent(BaseModel):
    id: str
    display_name: str
    is_simulated: bool
    xp_total: int
    calibration: float | None
    attempts: int


class HeatmapConcept(BaseModel):
    id: str
    name: str
    depth: int


class HeatmapCell(BaseModel):
    student_id: str
    concept_id: str
    state: ConceptState
    mastery: float


class HeatmapResponse(Traced):
    students: list[HeatmapStudent]
    concepts: list[HeatmapConcept]
    cells: list[HeatmapCell]


class AlertOut(BaseModel):
    id: str
    kind: AlertKind
    severity: Severity
    student_id: str | None
    concept_id: str | None
    misconception_id: str | None
    message: str
    reason: str


class ClusterOut(BaseModel):
    misconception_id: str
    description: str
    concept_id: str
    root_concept_id: str | None
    student_ids: list[str]
    share: float


class AlertsResponse(Traced):
    alerts: list[AlertOut]
    clusters: list[ClusterOut]
    class_size: int


class FeedbackRequest(BaseModel):
    student_id: str
    target_kind: FeedbackTarget
    target_id: str
    rating: int = Field(ge=-1, le=1, description="-1 thumbs down, 0 report, 1 thumbs up")
    comment: str | None = Field(default=None, max_length=500)


class FeedbackResponse(Traced):
    id: str
    queued_for_review: bool


# ---------------------------------------------------------------- admin
class LatencyStat(BaseModel):
    name: str
    count: int
    p50_ms: float
    p95_ms: float
    error_rate: float


class FeatureCost(BaseModel):
    feature: str
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    p50_ms: float
    p95_ms: float
    fallback_rate: float
    cache_hit_rate: float


class QuestionHealth(BaseModel):
    question_id: str
    concept_id: str
    attempts: int
    observed_success: float
    predicted_success: float
    flag: str  # too_easy / too_hard / ok
    never_picked_options: list[str]
    reports: int


MetricsWindow = Literal["1h", "24h", "7d", "30d", "all"]


class TimeBucket(BaseModel):
    start: datetime
    requests: int
    errors: int
    p95_ms: float | None  # None = no requests in the bucket (a gap, not 0 ms)
    llm_calls: int
    cost_usd: float


class AdminMetricsResponse(Traced):
    window: MetricsWindow
    window_start: datetime | None
    generated_at: datetime
    system: dict[str, float | int | None]
    endpoints: list[LatencyStat]
    features: list[FeatureCost]
    cost: dict[str, float | int | None]
    ai_quality: dict[str, float | int | str | None]
    safety: dict[str, int]
    learning: dict[str, float | int | None]
    studio: dict[str, float | int | None]
    timeseries: list[TimeBucket]
    question_health: list[QuestionHealth]
    llm_mode: str


class LLMCallOut(BaseModel):
    id: str
    trace_id: str
    feature: str
    prompt_name: str
    prompt_version: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    schema_ok: bool
    retries: int
    fallback_used: bool
    guardrail_flags: list[str]
    cache_hit: bool
    created_at: datetime
    scope: str
    student_id: str | None
    error: str | None


class TracesResponse(Traced):
    calls: list[LLMCallOut]
    total: int


class LogEntryOut(BaseModel):
    id: int
    created_at: datetime
    level: str
    event: str
    logger: str | None
    trace_id: str | None
    student_id: str | None
    data: dict


class LogsResponse(Traced):
    logs: list[LogEntryOut]
    total: int
    levels: dict[str, int]
    next_before_id: int | None


class ExportHealth(BaseModel):
    exported: int
    failed: int
    last_success_at: datetime | None
    last_error: str | None


class TelemetryStatus(Traced):
    otel_enabled: bool
    service_name: str
    environment: str
    endpoint: str | None
    auth_configured: bool
    sample_ratio: float
    openobserve_ui_url: str
    openobserve_org: str
    exports: dict[str, ExportHealth]
    stored: dict[str, int]
    retention: dict[str, int]


class SimRunRequest(BaseModel):
    students: int = Field(default=30, ge=1, le=200)
    attempts_per_student: int = Field(default=40, ge=5, le=200)
    seed: int = 7
    remediation: bool = True
    reset: bool = False


class SimRunResponse(Traced):
    students: int
    attempts: int
    diagnoses: int
    planted: int
    detected: int
    detection_accuracy: float | None
    duration_s: float


# ---------------------------------------------------------------- game layer (adventure mode)
# Additive contracts for the self-directed game: worlds of levels (one level = one concept),
# level runs with hearts / combo / stars, a study scroll, daily quests, profile, and class game stats.
# Stars and quests are deterministic and never award XP (XP stays mastery-only, §9.5).
class LevelInfo(BaseModel):
    concept_id: str
    name: str
    state: ConceptState
    mastery: float
    stars: int = Field(description="Best stars earned on this level, 0-3")
    playable: bool
    locked_reason: str | None
    has_myth: bool = Field(description="An active misconception lurks here")
    prerequisites: list[str]
    n_questions: int
    plays: int


class WorldInfo(BaseModel):
    id: str
    name: str
    tagline: str
    emoji: str
    color: str
    levels: list[LevelInfo]
    stars: int
    max_stars: int
    unlocked: bool


class WorldMapResponse(Traced):
    student_id: str
    worlds: list[WorldInfo]
    stars_total: int
    stars_max: int
    recommended_concept_id: str | None
    recommended_reason: str
    myths_active: int = Field(description="Active misconceptions: the Myth Boss lair opens when > 0")


class LevelRunOut(BaseModel):
    id: str
    concept_id: str
    concept_name: str
    status: str  # active / completed / failed
    hearts: int
    max_hearts: int
    index: int
    total: int
    correct: int
    combo: int
    best_combo: int
    stars: int
    fifty_left: int
    powerups_used: int
    question: QuestionPublic | None
    removed_option_ids: list[str] = Field(default_factory=list, description="Options removed by 50/50 on this question")


class LevelStartRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=64)
    restart: bool = False


class LevelStartResponse(Traced):
    run: LevelRunOut
    best_stars: int


class LevelAnswerRequest(BaseModel):
    option_id: str
    confidence: Confidence
    hints_used: int = Field(default=0, ge=0, le=3)
    time_ms: int = Field(default=0, ge=0)
    session_id: str | None = None


class LevelAnswerResponse(Traced):
    run: LevelRunOut
    attempt: AttemptResponse
    best_stars: int
    new_best: bool


class PowerupResponse(Traced):
    run: LevelRunOut


class CommonTrap(BaseModel):
    description: str
    correct_belief: str


class ConceptDetail(BaseModel):
    id: str
    name: str
    description: str
    prerequisites: list[str]
    key_points: list[str]
    notes_md: str
    traps: list[CommonTrap]


class QuestOut(BaseModel):
    id: str
    title: str
    description: str
    emoji: str
    progress: int
    target: int
    done: bool


class ProfileBadge(BaseModel):
    badge_id: str
    name: str
    description: str
    earned: bool
    earned_at: datetime | None


class ProfileResponse(Traced):
    student: StudentSummary
    stars_total: int
    stars_max: int
    levels_completed: int
    levels_total: int
    three_star_levels: int
    bosses_defeated: int
    misconceptions_cleared: int
    concepts_mastered: int
    best_combo: int
    runs_played: int
    attempts_total: int
    badges: list[ProfileBadge]
    quests: list[QuestOut]


class GameRunOut(BaseModel):
    id: str
    student_id: str
    display_name: str
    concept_id: str
    concept_name: str
    status: str
    stars: int
    correct: int
    total: int
    hearts_left: int
    best_combo: int
    powerups_used: int
    finished_at: datetime | None


class GameStudentStat(BaseModel):
    student_id: str
    display_name: str
    is_simulated: bool
    stars: int
    levels_completed: int
    runs: int
    wins: int
    fails: int
    best_combo: int
    bosses_defeated: int
    quests_done_today: int
    last_played: datetime | None


class GameLevelStat(BaseModel):
    concept_id: str
    name: str
    world: str
    plays: int
    completions: int
    fails: int
    completion_rate: float | None
    avg_stars: float | None
    avg_correct_pct: float | None
    top_myth: str | None = Field(description="Misconception most often chosen on this level's runs")


class ClassGameResponse(Traced):
    students: list[GameStudentStat]
    levels: list[GameLevelStat]
    recent_runs: list[GameRunOut]
    totals: dict[str, int | float | None]
