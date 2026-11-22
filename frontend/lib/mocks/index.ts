// Mock-first fixtures shaped exactly like the §11 API (NEXT_PUBLIC_USE_MOCKS=true).
// Small but behaviourally faithful: a 3-question flow with a misconception, a root diagnosis and a lesson.
import type { SSEHandler } from "../sse";
import { mockGame } from "./game";
import { mockStudio } from "./studio";
import type {
  AdminMetrics,
  Alerts,
  AttemptRequest,
  AttemptResponse,
  BossBattle,
  ConceptState,
  Diagnosis,
  Heatmap,
  MapNode,
  NextQuestion,
  QuestionPublic,
  RootReport,
  StudentMap,
} from "../types";

const CONCEPTS: [string, string, string[], number][] = [
  ["memory_basics", "Variables, memory & references", [], 0],
  ["recursion_base", "Recursion: base case & recursive case", [], 0],
  ["arrays", "Arrays & indexing", ["memory_basics"], 1],
  ["linked_lists", "Linked lists", ["memory_basics"], 1],
  ["big_o", "Big-O complexity", ["arrays"], 2],
  ["hashing", "Hash functions", ["arrays"], 2],
  ["stacks", "Stacks", ["arrays", "linked_lists"], 2],
  ["queues", "Queues", ["arrays", "linked_lists"], 2],
  ["graph_basics", "Graph representation", ["arrays", "linked_lists"], 2],
  ["tree_basics", "Tree terminology", ["linked_lists"], 2],
  ["call_stack", "Recursion & the call stack", ["recursion_base", "memory_basics"], 1],
  ["hash_tables", "Hash tables & collisions", ["hashing", "linked_lists"], 3],
  ["binary_trees", "Binary trees", ["tree_basics"], 3],
  ["bfs", "Breadth-first search", ["graph_basics", "queues"], 3],
  ["dfs", "Depth-first search", ["graph_basics", "stacks", "call_stack"], 3],
  ["bst_property", "BST ordering property", ["binary_trees"], 4],
  ["heaps", "Binary heaps", ["binary_trees", "arrays"], 4],
  ["traversals", "Pre/in/post-order traversal", ["binary_trees", "call_stack"], 4],
  ["bst_ops", "BST search & insert", ["bst_property", "recursion_base"], 5],
  ["priority_queues", "Priority queues", ["heaps", "queues"], 5],
  ["bst_delete", "BST deletion", ["bst_ops", "traversals"], 6],
];
const NAME = Object.fromEntries(CONCEPTS.map(([id, n]) => [id, n]));

const Q: (QuestionPublic & { correct: string; traps: Record<string, string> })[] = [
  {
    id: "q_arrays_02", concept_id: "arrays", concept_name: NAME.arrays, bloom_level: "understand", type: "mcq",
    stem: "Why is reading `a[i]` from an array an O(1) operation?", has_hints: true,
    options: [
      { id: "a", text: "The address is computed directly as base + i x element size" },
      { id: "b", text: "The computer scans from index 0 up to i, which is fast enough to count as O(1)" },
      { id: "c", text: "Because indices start at 1, the computer can skip a step" },
    ],
    correct: "a", traps: { b: "arrays.m3", c: "arrays.m1" },
  },
  {
    id: "q_bst_ops_02", concept_id: "bst_ops", concept_name: NAME.bst_ops, bloom_level: "apply", type: "mcq",
    stem: "This recursive BST search has no check for an empty subtree. What happens when you search for a key that is NOT in the tree?\n```python\ndef search(node, k):\n    if k == node.key:\n        return node\n    if k < node.key:\n        return search(node.left, k)\n    return search(node.right, k)\n```",
    has_hints: true,
    options: [
      { id: "a", text: "It reaches a None subtree and crashes trying to read its key" },
      { id: "b", text: "It returns None automatically once it runs out of nodes" },
      { id: "c", text: "It checks every node in the tree, then reports the key is missing" },
    ],
    correct: "a", traps: { b: "recursion_base.m1", c: "bst_ops.m1" },
  },
  {
    id: "q_recursion_base_02", concept_id: "recursion_base", concept_name: NAME.recursion_base, bloom_level: "understand",
    type: "mcq", has_hints: true,
    stem: "What happens when `countdown(3)` runs?\n```python\ndef countdown(n):\n    print(n)\n    countdown(n - 1)\n```",
    options: [
      { id: "a", text: "It prints 3, 2, 1, 0, -1, ... until a RecursionError (stack overflow)" },
      { id: "b", text: "It prints 3, 2, 1 and stops when n reaches 0" },
      { id: "c", text: "It prints 3 forever, because the call never changes n" },
    ],
    correct: "a", traps: { b: "recursion_base.m1", c: "recursion_base.m2" },
  },
];

let step = 0;
const states: Record<string, { state: ConceptState; m: number; n: number; mis: string[] }> = {};
const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));
const tid = () => `tr_mock_${Math.random().toString(16).slice(2, 10)}`;
const strip = (q: (typeof Q)[number]): QuestionPublic =>
  Object.fromEntries(Object.entries(q).filter(([k]) => k !== "correct" && k !== "traps")) as QuestionPublic;

function nextQ(): NextQuestion {
  const q = Q[step % Q.length];
  const phase = step < 2 ? "diagnostic" : step === 2 ? "probe" : "practice";
  const reason =
    phase === "probe"
      ? "Checking whether Recursion: base case & recursive case is the root of this mistake."
      : `Diagnostic ${step + 1}/5: sampling ${q.concept_name} to map where you're starting.`;
  return { trace_id: tid(), question: strip(q), reason, phase, diagnostic_progress: Math.min(step, 5), diagnostic_total: 5 };
}

function mapFixture(): StudentMap {
  const nodes: MapNode[] = CONCEPTS.map(([id, name, pre, depth]) => {
    const s = states[id];
    const state: ConceptState = s?.state ?? (pre.length ? "locked" : "not_started");
    return { id, name, state, mastery: s?.m ?? 0.5, n_attempts: s?.n ?? 0, depth, active_misconception_ids: s?.mis ?? [],
      reason: state === "locked" ? `Unlocks when prerequisites reach 70%: ${pre.map((p) => NAME[p]).join(", ")}.` : "" };
  });
  return { trace_id: tid(), student_id: "demo", nodes,
    edges: CONCEPTS.flatMap(([id, , pre]) => pre.map((p) => ({ source: p, target: id }))) };
}

const DIAG: Diagnosis = {
  trace_id: "tr_mock", id: "dx_mock_2", status: "applied", student_id: "demo", trigger_attempt_id: "att_2",
  failed_concept_id: "recursion_base", root_concept_id: "recursion_base", root_concept_name: NAME.recursion_base,
  misconception_id: "recursion_base.m1", misconception_text: "Recursion stops automatically without a base case.",
  correct_belief: "Without a base case nothing stops the calls; the function recurses until the stack overflows.",
  evidence: [
    "Wrong on q_recursion_base_02 [Recursion], sure (chose 'It prints 3, 2, 1 and stops when n reaches 0')",
    "Wrong on q_bst_ops_02 [BST search & insert], sure (chose 'It returns None automatically...') — same misconception",
  ],
  path: ["bst_ops", "recursion_base"], confidence: 0.85, needs_probe: false, probe_concept_id: null,
  student_message: "Here's the gap: the root is in recursion base cases.", source: "fallback", replay_id: "recursion_no_base",
};

export const mockApi = {
  ...mockGame,
  ...mockStudio,
  async startSession(student_id: string) {
    step = 0;
    return { trace_id: tid(), session_id: "ses_mock", next: nextQ(),
      student: { id: student_id, display_name: "Demo Student", xp_total: 0, level: 1, streak_days: 1, is_simulated: false } };
  },
  async nextQuestion() {
    await delay(150);
    return nextQ();
  },
  async submitAttempt(body: AttemptRequest): Promise<AttemptResponse> {
    await delay(250);
    const q = Q.find((x) => x.id === body.question_id) ?? Q[0];
    const ok = body.option_id === q.correct;
    const mis = ok ? null : q.traps[body.option_id ?? ""] ?? null;
    const s = (states[q.concept_id] ??= { state: "not_started", m: 0.5, n: 0, mis: [] });
    s.n += 1;
    s.m = Math.max(0.05, Math.min(0.95, s.m + (ok ? 0.12 : -0.15)));
    if (mis && body.confidence === "sure") s.mis = [mis];
    s.state = s.mis.length ? "misconception" : ok ? "fragile" : "gap";
    step += 1;
    const isProbeTrigger = q.id === "q_bst_ops_02" && !ok;
    const isRoot = q.id === "q_recursion_base_02" && !ok;
    return {
      trace_id: tid(), attempt_id: `att_${step}`, is_correct: ok, correct_option_id: q.correct,
      explanation: "See the worked explanation in the lesson.",
      signal: ok ? (body.confidence === "sure" ? "mastered_signal" : "fragile_signal") : body.confidence === "sure" ? "misconception_signal" : "gap_signal",
      selected_misconception_id: mis, progress_awarded: true,
      concept_state: { concept_id: q.concept_id, concept_name: q.concept_name, state: s.state, mastery: s.m, n_attempts: s.n,
        active_misconception_ids: s.mis, reason: "" },
      xp_events: [], unlocks: [], badges: [], cleared_misconception_ids: [],
      diagnosis: isProbeTrigger ? { status: "applied", id: "dx_mock_1" } : isRoot ? { status: "applied", id: "dx_mock_2" } : { status: null, id: null },
      next_action: isProbeTrigger
        ? { kind: "probe", concept_id: "recursion_base", misconception_id: "recursion_base.m1", message: "Let's check one recursion question first." }
        : isRoot
          ? { kind: "lesson", concept_id: "recursion_base", misconception_id: "recursion_base.m1", message: DIAG.student_message ?? "" }
          : { kind: "next_question", concept_id: null, misconception_id: null, message: "Nice, keep going." },
    };
  },
  async diagnosis(id: string): Promise<Diagnosis> {
    await delay(300);
    return id === "dx_mock_1"
      ? { ...DIAG, id, needs_probe: true, probe_concept_id: "recursion_base", confidence: 0.55, evidence: DIAG.evidence.slice(1),
          student_message: "Your answer hints the real snag might be in recursion. Let's check one quick question." }
      : DIAG;
  },
  async student(id: string) {
    return { id, display_name: "Demo Student", xp_total: 0, level: 1, streak_days: 1, is_simulated: false };
  },
  async map() {
    return mapFixture();
  },
  async report(): Promise<RootReport> {
    return {
      trace_id: tid(), student_id: "demo",
      root_gaps: [{ concept_id: "recursion_base", concept_name: NAME.recursion_base, state: "misconception", mastery: 0.32,
        misconception_id: "recursion_base.m1", misconception_text: DIAG.misconception_text, evidence: DIAG.evidence,
        diagnosis_id: DIAG.id, path: DIAG.path }],
      bloom_radar: [
        { level: "remember", accuracy: 0.8, attempts: 5 }, { level: "understand", accuracy: 0.6, attempts: 5 },
        { level: "apply", accuracy: 0.4, attempts: 5 }, { level: "analyze", accuracy: 0.25, attempts: 4 },
      ],
      calibration: { score: 0.62, n: 19, sure_correct: 9, sure_wrong: 5, guess_correct: 2, guess_wrong: 3 },
      next_step: { kind: "lesson", concept_id: "recursion_base", label: "Fix the root: recursion base cases", reason: "Top root gap." },
      xp_total: 420, level: 2, streak_days: 3,
      badges: [{ badge_id: "myth_buster", name: "Myth Buster", description: "Cleared your first misconception.", earned_at: null }],
      recent_xp: [{ kind: "misconception_cleared", amount: 150, reason: "Cleared misconception", concept_id: "queues" }],
      state_counts: { mastered: 2, fragile: 3, misconception: 1, gap: 1, not_started: 2, locked: 12 },
      attempts_total: 19, accuracy: 0.58,
    };
  },
  async concepts() {
    return CONCEPTS.map(([id, name, pre]) => ({ id, name, description: "", prerequisites: pre, key_points: [], content_version: 1, status: "approved" as const }));
  },
  async hint(question_id: string, level: number) {
    return { trace_id: tid(), question_id, level, hint: "Think about what stops a recursive function.", xp_cost: 10 };
  },
  async boss(student_id: string): Promise<BossBattle> {
    return { trace_id: tid(), id: "boss_mock", student_id, name: "The Infinite Echo",
      taunt: "\"Recursion stops automatically without a base case.\" ...or so I've convinced you. Prove me wrong!",
      hp: 100, max_hp: 100, status: "active", misconception_ids: ["recursion_base.m1"], questions: Q.map(strip),
      current_index: 0, damage_per_hit: 50 };
  },
  async bossAttempt(_id: string, body: { question_id: string; option_id: string }) {
    const q = Q.find((x) => x.id === body.question_id) ?? Q[0];
    const ok = q.correct === body.option_id;
    return { trace_id: tid(), is_correct: ok, correct_option_id: q.correct, explanation: "", damage: ok ? 50 : 0, hp: ok ? 50 : 100,
      max_hp: 100, status: "active", current_index: 1, xp_events: [], badges: [], cleared_misconception_ids: [], unlocks: [] };
  },
  async teachScore(session_id: string) {
    return { trace_id: tid(), session_id, concept_id: "stacks", score: 75, covered_points: ["a stack is last-in first-out (LIFO)"],
      missing_points: ["popping an empty stack is an underflow error that must be checked"], misconceptions_detected: [],
      feedback: "Nice! Add what happens when you pop an empty stack.", xp_events: [], badges: [], source: "fallback" };
  },
  async heatmap(): Promise<Heatmap> {
    const names = ["Ada", "Linus", "Grace", "Alan", "Barbara", "Edsger"];
    const pick: ConceptState[] = ["mastered", "fragile", "misconception", "gap", "not_started", "locked"];
    return {
      trace_id: tid(),
      students: names.map((n, i) => ({ id: `sim_${i}`, display_name: n, is_simulated: true, xp_total: 100 * i, calibration: 0.5 + i * 0.05, attempts: 30 })),
      concepts: CONCEPTS.map(([id, name, , depth]) => ({ id, name, depth })),
      cells: names.flatMap((_, i) => CONCEPTS.map(([id], j) => ({ student_id: `sim_${i}`, concept_id: id,
        state: pick[(i * 7 + j * 3) % 6], mastery: ((i * 13 + j * 7) % 90) / 100 + 0.05 }))),
    };
  },
  async alerts(): Promise<Alerts> {
    return { trace_id: tid(), class_size: 6, clusters: [{ misconception_id: "recursion_base.m1", description: DIAG.misconception_text ?? "",
      concept_id: "recursion_base", root_concept_id: "recursion_base", student_ids: ["sim_0", "sim_2"], share: 0.33 }],
      alerts: [{ id: "class:recursion_base.m1", kind: "class_misconception", severity: "critical", student_id: null, concept_id: "recursion_base",
        misconception_id: "recursion_base.m1", message: "33% of class shares the misconception \"Recursion stops automatically\"; root is recursion base cases.",
        reason: "2 of 6 active students have it active." }] };
  },
  async metrics(window: AdminMetrics["window"] = "24h"): Promise<AdminMetrics> {
    const now = new Date().toISOString().slice(0, 19);
    return { trace_id: tid(), llm_mode: "offline", window, window_start: null, generated_at: now,
      system: { requests: 1200, requests_per_min: 4.2, p50_ms: 6, p95_ms: 18, p99_ms: 40, error_rate: 0, client_error_rate: 0.01,
        llm_calls: 900, llm_calls_live: 0, cache_hit_rate: 0.1, schema_failure_rate: null, retry_rate: null, fallback_rate: 1,
        live_fallback_rate: null, llm_p95_ms: 0 },
      endpoints: [{ name: "/attempts", count: 600, p50_ms: 9, p95_ms: 21, error_rate: 0 }],
      features: [{ feature: "diagnosis", calls: 300, input_tokens: 0, output_tokens: 0, cost_usd: 0, p50_ms: 1, p95_ms: 3, fallback_rate: 1, cache_hit_rate: 0 }],
      cost: { total_usd: 0, learner_usd: 0, studio_usd: 0, total_tokens: 0, sessions: 31, active_students: 31, students_total: 31,
        usd_per_session: 0, usd_per_active_student: 0, tokens_per_session: 0 },
      ai_quality: { root_gap_detection: 0.77, root_gap_detection_exercised: 0.98, root_gap_detected: 43, root_gap_planted: 56, root_concept_accuracy: 0.88, verifier_pass_rate: 1, verifier_checked: 73, verifier_first_pass_rate: null, grounding_failures: 0, answer_leakage_blocked: 0, teach_score_agreement: 0.75, diagnoses_total: 427, diagnoses_rejected: 0, diagnoses_llm: 0, last_eval_at: null },
      safety: { injection_attempts: 2, blocked_calls: 0, moderation_flags: 0, off_topic_redirects: 1, pii_scrubbed: 0, budget_exceeded: 0,
        job_budget_exceeded: 0, rate_limited: 0, uploads_rejected: 0, document_injection_suspects: 0, output_guardrail_drops: 0, studio_moderation_flags: 0 },
      learning: { attempts: 1437, active_students: 31, accuracy: 0.62, mastery_gain_per_session: 0.9, misconceptions_cleared: 40, concepts_mastered: 60, avg_attempts_to_mastery: 4.2, calibration: 0.6, drop_off_rate: 0, eval_mastery_gain_vs_control: 0.33 },
      studio: { subjects_total: 1, subjects_published: 1, subjects_in_review: 0, jobs: 0, jobs_running: 0, jobs_failed: 0, job_success_rate: null,
        avg_job_seconds: null, p95_job_seconds: null, documents: 0, documents_failed: 0, pages_parsed: 0, figures_described: 0, pages_ocr: 0,
        concepts_generated: 0, questions_generated: 0, flashcards_generated: 0, studio_llm_calls: 0, studio_tokens: 0, studio_usd: 0 },
      timeseries: [], question_health: [] };
  },
  async traces() {
    return { trace_id: tid(), calls: [], total: 0 };
  },
  async logs() {
    return { trace_id: tid(), logs: [], total: 0, levels: {}, next_before_id: null };
  },
  async telemetry() {
    return { trace_id: tid(), otel_enabled: false, service_name: "rootwise-backend", environment: "mock", endpoint: null,
      auth_configured: false, sample_ratio: 1, openobserve_ui_url: "http://localhost:5080", openobserve_org: "default",
      exports: {}, stored: { app_logs: 0, request_metrics: 0, llm_calls: 0 }, retention: { log_days: 7, log_max_rows: 50000, request_metrics_days: 30 } };
  },
  async feedback() {
    return { trace_id: tid(), id: "fb_mock", queued_for_review: true };
  },
  async simRun() {
    return { trace_id: tid() };
  },
  async streamLesson(concept_id: string, _sid: string, misconception_id: string | null | undefined, onEvent: SSEHandler) {
    onEvent("meta", { concept_id, concept_name: NAME[concept_id], misconception_id, misconception_text: DIAG.misconception_text,
      correct_belief: DIAG.correct_belief, replay_id: "recursion_no_base" });
    const text = `**A common belief:** "${DIAG.misconception_text}"\n\n**What's actually true:** ${DIAG.correct_belief}\n\nRecursion does not stop by itself. The base case is the smallest version of the problem, answered directly without another recursive call.`;
    for (const w of text.split(" ")) {
      onEvent("delta", { text: w + " " });
      await delay(25);
    }
    onEvent("lesson", { concept_id, concept_name: NAME[concept_id], misconception_id, lesson_md: text,
      worked_example: "`countdown(3)` prints 3, 2, 1 and stops at the base case `n == 0`.",
      analogy: "Two mirrors facing each other: nothing makes the reflections stop by themselves.",
      socratic_questions: ["If countdown(n) always calls countdown(n - 1), what call happens right after countdown(0)?"],
      citations: ["Recursion does not stop by itself."], mastery_check_question_ids: ["q_recursion_base_03"], replay_id: "recursion_no_base", source: "mock" });
    onEvent("done", {});
  },
  async streamTeach(_c: string, body: { message: string }, onEvent: SSEHandler) {
    onEvent("session", { session_id: "teach_mock" });
    const reply = `Okay, I think I follow... but my friend told me a stack removes the oldest item first. Is that true?`;
    for (const w of reply.split(" ")) {
      onEvent("delta", { text: w + " " });
      await delay(30);
    }
    onEvent("done", { session_id: "teach_mock", reply, on_topic: true, covered_points: body.message.length > 20 ? ["a stack is last-in first-out (LIFO)"] : [],
      missing_points: [], coverage: body.message.length > 20 ? 0.25 : 0, flags: [], source: "mock" });
  },
};
