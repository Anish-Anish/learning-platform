# Rootwise

> Don't just find the mistake. Fix the root.

An adaptive Data Structures tutor that traces wrong answers back to the **root prerequisite gap**,
reteaches exactly that, and proves it's fixed. Built for the TCS OpenAI Hackathon (problem 5B).
Full spec: [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md). Rules for contributors / Claude Code: [`CLAUDE.md`](CLAUDE.md).

## Quick start

```bash
# backend (Python 3.11+, uv)
cd backend && uv sync
uv run python -m app.db.seed                 # load 21 concepts, 44 misconceptions, 73 questions
uv run python -m app.sim.run --students 30   # optional: a simulated class for the teacher dashboard
uv run uvicorn app.main:app --reload --port 8000
```

```bash
# frontend (Node 20+, pnpm; `corepack pnpm@10.34.9 …` works if pnpm isn't installed)
cd frontend && pnpm install && pnpm dev       # http://localhost:3000
```

No OpenAI key? Everything still works: the app runs in **offline mode**, where each LLM feature falls back
to a deterministic, notes-grounded implementation, and every call is still traced in `llm_calls`. To go online, copy
`backend/.env.example` to `backend/.env` and set `OPENAI_API_KEY`, `OPENAI_MODEL_FAST`, `OPENAI_MODEL_SMART`.

Other commands:

```bash
cd backend && uv run pytest          # 50 tests: learner math, adaptive engine, guardrails, llm client, API flows, replay
cd backend && uv run python -m app.evals.run    # eval harness → app/evals/results/<timestamp>.json (diffs vs last run)
cd backend && uv run python -m app.ai.pipeline --concept bst_property --bloom apply --n 3   # generate questions for review
cd frontend && pnpm gen:types        # regenerate lib/api-types.ts from the running backend's OpenAPI
```

## Demo path (≈90 s)

1. `/learn`: do the 5-question diagnostic; on **BST search & insert**, pick *"It returns None automatically…"* and mark **Sure**.
   The node turns red (misconception), and the Root card says *"Is Recursion the real snag?"*
2. Take the probe question, choose the "recursion stops on its own" option (**Sure**), and you get **Root found: Recursion base case**,
   with evidence from both answers and the path BST search → Recursion.
3. Start the micro-lesson (streamed, grounded in notes, with an analogy, Socratic questions and the **misconception replay** animation),
   then take 2 mastery checks one Bloom level up. The misconception clears (+150 XP, Myth Buster + Root Finder badges, confetti).
4. Fight the **Root Boss** (questions built from your own confident mistakes) and win: +250 XP, and the recursion node gets close to green on `/map`.
5. `/dashboard`: live heatmap, misconception clusters, and an alert such as *"45% of class shares misconception X; root is Y"*.
6. `/admin`: root-gap detection, verifier pass rate, p95 latency, cost per session, fallback/cache rates, and the `llm_calls` trace table.

## Adventure mode (the student game)

Students learn by themselves on `/play`: an adventure map of **7 worlds** (one level per concept, 21 levels).
They pick levels, can read the **study scroll** (teacher notes, key ideas, common traps) before playing, and then play
short runs: up to 4 questions of rising Bloom level, **3 hearts**, **combo / fever mode**, and one **50/50** power-up
(it caps the run at 2★ and counts as a hint). Stars: ⭐ finish · ⭐⭐ at most one mistake · ⭐⭐⭐ flawless and every answer marked Sure.
An animated mascot reacts to every answer, and synthesized sound effects can be muted in the HUD.
Wrong answers still go to the root-cause tutor ("Train with the mentor" or "Go to that level"), and myths open the **Myth Boss lair**.
Also included: daily quests, a Trophy room with heroes that unlock with stars, and badges.
Stars and quests never award XP (XP stays mastery-only).

Teachers see it all on `/arena` (**Game results**): a leaderboard, the hardest levels with the trap students fall into most,
and a live feed of runs. Each student profile has a "Game results" tab. The simulator plays levels too, so the page has data.

## Current eval numbers (offline mode, 30 simulated students, seed 7)

| Metric | Value |
|---|---|
| Root-gap detection (planted misconceptions a student actually ran into) | **97.8%** (44/45) |
| Root-gap detection (all planted, incl. never-reached concepts) | 78.6% (44/56) |
| Root concept accuracy (of detected) | 95.5% |
| Mastery on planted concepts: remediation vs no-remediation control | **+32 points** |
| Verifier pass rate (question bank, deterministic checks) | 100% (73/73) |
| Teach-the-bot scorer agreement (±15, 8 hand-labelled; offline keyword scorer) | 75% |
| API p95 latency (in-process) | ~17 ms |

The teach scorer's threshold was tuned on the same 8 labelled items it's scored on, so treat that 75% as optimistic.
LLM-mode numbers need an API key.

## Architecture (as built)

```
frontend/ (Next.js 16, TS strict, Tailwind v4, shadcn/ui, TanStack Query, Zustand, React Flow, Motion, Recharts)
   │  typed client generated from OpenAPI (lib/api-types.ts), SSE for lessons + teach-the-bot, mock mode
backend/app/
   api/        FastAPI routes for every endpoint in §11 (+ GET /concepts, GET /students/{id})
   core/       deterministic engine: learner_model (Elo/IRT), states, adaptive, gamification, analytics,
               attempts (event bus pipeline), diagnosis (validate + apply proposals), boss, replay, quality
   ai/         llm_client (the only LLM entry point), prompts registry, diagnosis agent (tool-calling loop +
               deterministic baseline), generators, teach_bot, verifier, pipeline, cache
   guardrails/ input (delimiters, injection, length), pii, moderation, output (grounding, leakage, tone), budget
   observability/ trace_id middleware, request metrics, structlog JSON, async telemetry writer
   sim/ evals/ synthetic students through the real API; eval harness with a control group
backend/prompts/*.md   versioned prompts (version logged on every call)
backend/seed/          concepts, misconceptions (+ static analogies/socratic fallbacks), notes, question bank
```

**AI suggests, code decides:** the diagnosis agent (LLM or deterministic) only *proposes*. `core/diagnosis.py`
validates it (IDs must exist, root must be the failed concept or a prerequisite, confidence ≥ 0.35,
probe budget) and then activates a misconception or schedules a probe. Mastery, XP and unlocks are only
ever written by `core/`. A test enforces that `ai/` never touches those tables.

## Decisions and deviations to review

- **Tuned values** (§9 says these are tunable): `K_s = 1.0` instead of 0.4, because with 3–5 questions per concept,
  0.4 would need ~10 correct answers to reach mastery. Anti-farming blocks progress only for re-answering a question
  you got *right* in your last 10 attempts; retrying a missed question counts as retrieval practice, which boss battles rely on.
- **Diagnostic concepts**: arrays, linked lists, queues, hashing, BST search (configurable via `DIAGNOSTIC_CONCEPTS`).
  BST search is included so the demo's "confident BST mistake → probe recursion" path happens in the first five questions.
- **Diagnosis**: a confidently chosen, tagged misconception is treated as the strongest evidence. Some distractors are
  tagged with a *prerequisite's* misconception (e.g. a BST option tagged `recursion_base.m1`), and that tag is how the agent finds the root.
- **Additive schema/table changes** (not in §7/§11): diagnosis status `pending`; tables `sessions`, `scheduled_items`,
  `request_metrics`; a few columns on attempts/mastery/diagnoses; response models `TeachTurnDone`, `LessonPayload`;
  `GET /concepts`, `GET /students/{id}`, and an optional `battle_id` on `GET /boss/{student_id}`.
- **Streaming**: lessons and bot replies are generated as structured output, validated (grounding, answer leakage, tone),
  and only then streamed over SSE. This keeps the guardrails in front of the student at the cost of time-to-first-token.
- **Content**: the seed question bank is hand-authored (no API key was available to run the generation pipeline);
  the pipeline + verifier exist for generating more. Options are shown in a deterministic shuffled order per question.
- **Open decisions from §21 that are still yours**: final name, hosting/Langfuse-or-Phoenix, timeline. Misconception
  replay was built for *recursion base case* and *BST property* (§21 suggested BST property + traversals).
- `PROJECT_CONTEXT.md` was moved to `docs/` to match the paths in `CLAUDE.md`.
