// Adventure-mode fixtures (NEXT_PUBLIC_USE_MOCKS=true). Small but shaped exactly like the API.
import type { ClassGame, ConceptDetail, LevelAnswer, LevelRun, LevelStart, Profile, WorldMap } from "../types";

const tid = () => `tr_mock_${Math.random().toString(16).slice(2, 10)}`;
const Q = {
  id: "q_recursion_base_01", concept_id: "recursion_base", concept_name: "Recursion: base case & recursive case",
  bloom_level: "remember" as const, type: "mcq" as const, has_hints: true,
  stem: "What is the role of the base case in a recursive function?",
  options: [
    { id: "a", text: "It returns directly without a recursive call, which stops the recursion" },
    { id: "b", text: "It's optional, because recursion stops on its own when there is nothing left to do" },
    { id: "c", text: "It makes the input bigger so the recursion has room to finish" },
  ],
};
let run: LevelRun = {
  id: "run_mock", concept_id: "recursion_base", concept_name: Q.concept_name, status: "active", hearts: 3, max_hearts: 3,
  index: 0, total: 4, correct: 0, combo: 0, best_combo: 0, stars: 0, fifty_left: 1, powerups_used: 0, question: Q,
  removed_option_ids: [],
};

const level = (concept_id: string, name: string, stars: number, playable = true, has_myth = false) => ({
  concept_id, name, state: playable ? ("fragile" as const) : ("locked" as const), mastery: 0.5, stars, playable,
  locked_reason: playable ? null : "Unlocks at 70% on its prerequisites.", has_myth, prerequisites: [], n_questions: 4, plays: stars ? 1 : 0,
});

export const mockGame = {
  async world(student_id: string): Promise<WorldMap> {
    return {
      trace_id: tid(), student_id, stars_total: 5, stars_max: 63, recommended_concept_id: "recursion_base",
      recommended_reason: "A myth lurks in Recursion. Go bust it!", myths_active: 1,
      worlds: [
        { id: "w1", name: "Memory Meadows", tagline: "Where every name points somewhere.", emoji: "🌱", color: "emerald", stars: 5, max_stars: 9, unlocked: true,
          levels: [level("memory_basics", "Variables, memory & references", 3), level("arrays", "Arrays & indexing", 2), level("linked_lists", "Linked lists", 0)] },
        { id: "w2", name: "Recursion Ruins", tagline: "Calls within calls within calls.", emoji: "🌀", color: "violet", stars: 0, max_stars: 6, unlocked: true,
          levels: [level("recursion_base", Q.concept_name, 0, true, true), level("call_stack", "Recursion & the call stack", 0, false)] },
      ],
    };
  },
  async profile(id: string): Promise<Profile> {
    return {
      trace_id: tid(), student: { id, display_name: "Demo Student", xp_total: 250, level: 2, streak_days: 2, is_simulated: false },
      stars_total: 5, stars_max: 63, levels_completed: 2, levels_total: 21, three_star_levels: 1, bosses_defeated: 0,
      misconceptions_cleared: 1, concepts_mastered: 1, best_combo: 4, runs_played: 3, attempts_total: 14,
      badges: [{ badge_id: "myth_buster", name: "Myth Buster", description: "Cleared your first misconception.", earned: true, earned_at: null }],
      quests: [{ id: "warmup", title: "Warm-up", description: "Answer 5 questions", emoji: "🔥", progress: 3, target: 5, done: false }],
    };
  },
  async conceptDetail(id: string): Promise<ConceptDetail> {
    return { id, name: Q.concept_name, description: "A function that calls itself on a smaller problem.", prerequisites: [],
      key_points: ["the base case stops the recursion"], notes_md: "# Recursion\n\nThe base case stops the recursion.\n\n**Example.** countdown(3).",
      traps: [{ description: "Recursion stops automatically without a base case.", correct_belief: "Nothing stops the calls without a base case." }] };
  },
  async startLevel(): Promise<LevelStart> {
    run = { ...run, status: "active", hearts: 3, index: 0, correct: 0, combo: 0, best_combo: 0, stars: 0, fifty_left: 1, powerups_used: 0, question: Q, removed_option_ids: [] };
    return { trace_id: tid(), run, best_stars: 0 };
  },
  async levelFifty() {
    run = { ...run, fifty_left: 0, powerups_used: 1, removed_option_ids: ["c"] };
    return { trace_id: tid(), run };
  },
  async levelAnswer(_id: string, body: { option_id: string; confidence: "sure" | "guess" }): Promise<LevelAnswer> {
    const ok = body.option_id === "a";
    const index = run.index + 1;
    const hearts = ok ? run.hearts : run.hearts - 1;
    const combo = ok ? run.combo + 1 : 0;
    const done = index >= run.total;
    run = { ...run, index, hearts, combo, best_combo: Math.max(run.best_combo, combo), correct: run.correct + (ok ? 1 : 0),
      status: hearts <= 0 ? "failed" : done ? "completed" : "active", stars: done && hearts > 0 ? (hearts === 3 ? 3 : 2) : 0,
      question: hearts <= 0 || done ? null : Q, removed_option_ids: [] };
    return { trace_id: tid(), run, best_stars: run.stars, new_best: run.stars > 0,
      attempt: { trace_id: tid(), attempt_id: "att", is_correct: ok, correct_option_id: "a", explanation: "The base case stops the recursion.",
        signal: ok ? "mastered_signal" : "misconception_signal", selected_misconception_id: ok ? null : "recursion_base.m1", progress_awarded: true,
        concept_state: { concept_id: "recursion_base", concept_name: Q.concept_name, state: "fragile", mastery: 0.6, n_attempts: 1, active_misconception_ids: [], reason: "" },
        xp_events: [], unlocks: [], badges: [], cleared_misconception_ids: [], diagnosis: { status: null, id: null },
        next_action: { kind: "next_question", concept_id: null, misconception_id: null, message: "" } } };
  },
  async classGame(): Promise<ClassGame> {
    return { trace_id: tid(), totals: { runs: 3, players: 2, players_today: 2, completion_rate: 0.67, avg_stars: 2, three_star_runs: 1 },
      students: [{ student_id: "sim_1", display_name: "Ada", is_simulated: true, stars: 6, levels_completed: 2, runs: 2, wins: 2, fails: 0, best_combo: 4, bosses_defeated: 1, quests_done_today: 2, last_played: null }],
      levels: [{ concept_id: "recursion_base", name: Q.concept_name, world: "Recursion Ruins", plays: 3, completions: 2, fails: 1, completion_rate: 0.67, avg_stars: 2, avg_correct_pct: 0.7, top_myth: "Recursion stops automatically without a base case." }],
      recent_runs: [] };
  },
};
