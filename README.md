# Rootwise

> Don't just find the mistake. Fix the root.

Rootwise is an adaptive AI tutor. When a student gets something wrong, it traces the mistake back to the
**root prerequisite gap** that caused it, reteaches exactly that, and proves it's fixed with deterministic,
explainable mastery tracking. Teachers can turn their own PDFs and notes into a full course (concept graph,
quizzes and flashcards), review it, publish it, and assign it to students. Every request and AI call is traced,
measured and guarded.

Built for the TCS OpenAI Hackathon: problem **5B** (adaptive tutor) and **5A** (teacher studio).

- Full spec: [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md)
- Engineering rules: [`CONTRIBUTING.md`](CONTRIBUTING.md)

---

## Contents

- [Quick start (Linux)](#quick-start-linux)
- [Features](#features)
- [Configuration](#configuration)
- [Manual setup (any OS)](#manual-setup-any-os)
- [Demo walkthrough](#demo-walkthrough)
- [Observability](#observability)
- [Guardrails](#guardrails)
- [Architecture](#architecture)
- [Tests and evals](#tests-and-evals)
- [Decisions and deviations](#decisions-and-deviations)
- [Troubleshooting](#troubleshooting)

---

## Quick start (Linux)

Works on Ubuntu/Debian, Fedora/RHEL, Arch, openSUSE, Alpine and WSL. The only requirement is `bash`; the setup
script installs everything else (system packages via your package manager, plus **uv**/Python 3.12 and
**Node 22**/pnpm in your home directory, so no global installs).

```bash
bash scripts/setup.sh          # install toolchain + dependencies, create .env files, seed the DB, run tests, build
bash scripts/run.sh            # start backend + frontend (hot reload), Ctrl-C stops both
```

Then open:

| What | URL |
|---|---|
| Home | http://localhost:3000 |
| Student app | http://localhost:3000/play |
| Teacher app | http://localhost:3000/teacher |
| Admin / observability | http://localhost:3000/admin |
| API docs (OpenAPI) | http://localhost:8000/docs |

### `setup.sh` options

| Option | What it does |
|---|---|
| `--openai-key sk-...` | Enables live AI features (stored in `backend/.env`). Without a key the app runs in **offline mode**. |
| `--with-observability` | Starts **OpenObserve** in Docker, generates strong credentials and turns on OpenTelemetry export. |
| `--api-url URL` | Public URL of the backend as seen by browsers (default `http://localhost:8000`). |
| `--frontend-url URL` | Public URL of the frontend; added to the backend's CORS list. |
| `--skip-tests` / `--skip-build` | Skip the backend test suite / the production frontend build. |
| `--reset-db` | Delete the SQLite database and reseed it. |
| `-y`, `--yes` | Install missing system packages without asking. |

Re-running `setup.sh` is safe: it keeps your existing `backend/.env` and only installs what's missing.

### `run.sh` options

| Option / variable | What it does |
|---|---|
| *(none)* | Dev servers with hot reload; logs streamed to the terminal and saved in `logs/`. |
| `--prod` | Production frontend build (`next start`) and a backend without auto-reload. |
| `--detach` | Run in the background; stop with `bash scripts/stop.sh`. |
| `HOST=0.0.0.0` | Listen on all interfaces (default `127.0.0.1`). |
| `BACKEND_PORT`, `FRONTEND_PORT` | Change ports (defaults 8000 / 3000). |

**Serving on a remote machine:** run setup with the URLs browsers will use, then start on all interfaces.

```bash
bash scripts/setup.sh --api-url http://my-server:8000 --frontend-url http://my-server:3000
HOST=0.0.0.0 bash scripts/run.sh --prod --detach
```

---

## Features

### Student app (`/play`, `/learn`, `/map`, `/teach`, `/report`, `/trophies`)

- **Confidence-aware answers.** Every answer is marked *Sure* or *Guessing*, so a lucky guess and a confident
  misconception are treated differently (mastered / fragile / misconception / gap signals).
- **Diagnostic start.** A short diagnostic samples the course to find where each learner stands.
- **Root-cause diagnosis.** On a wrong answer, a diagnosis agent walks the prerequisite graph, asks probe
  questions on earlier concepts when needed, and names the root gap with its evidence and the path it followed.
  Every wrong option is tagged with the misconception that produces it.
- **Micro-lessons.** Streamed lessons grounded in the teacher's notes, with a worked example, an everyday
  analogy, Socratic questions, and an animated **misconception replay** for selected concepts.
- **Mastery checks.** After a lesson, questions one Bloom level higher prove the gap is closed.
- **Root Boss.** A boss battle built from the learner's own confident mistakes.
- **Teach the bot.** Explain a concept to a curious, slightly confused bot; a scorer checks the explanation
  against the concept's key points.
- **Skill tree.** A live prerequisite graph coloured by state (locked, ready, gap, misconception, fragile, mastered)
  with unlock animations.
- **Adventure mode.** A world map with one level per concept: short runs of rising Bloom level, 3 hearts,
  combos and fever mode, a 50/50 power-up, 1–3 stars, a study scroll (notes, key ideas, common traps) before each
  level, a reactive mascot and sound effects (mutable).
- **Rewards that don't cheat mastery.** XP only for mastery events (anti-farming, hints cost XP); daily quests,
  badges and a trophy room of unlockable heroes.
- **Root Report.** Root gaps with evidence, a Bloom radar, confidence calibration and the recommended next step.
- **Subject switcher.** Learners see every course assigned to them and switch instantly; all screens update live.
- **Pseudonymous IDs** only: names never reach the AI.

### Teacher app (`/teacher`)

- **Class overview.** A live student × concept heatmap, alerts that always state their reason (e.g. *"42% of the class
  shares misconception X; root is Y"*), misconception clusters with the diagnosed root, and per-student drill-down
  (report, game results). Works per subject.
- **Game results** (`/teacher/games`). Leaderboard, the hardest levels and the trap students fall into most, and a
  live feed of level runs.
- **Teacher studio** (`/teacher/studio`). Turn your own material into a course:
  1. **Upload** PDFs (text, tables, diagrams, charts and scanned pages), Markdown or text files, up to 10 files /
     200 MB each. Huge PDFs are parsed locally; only meaningful figures and scanned pages go to a vision model.
  2. **Generate**, with live progress: figure descriptions and OCR, concept extraction, a prerequisite graph
     grouped into units (validated by code: no cycles, no dangling links), grounded teacher notes, misconceptions,
     verified quiz questions whose wrong options target those misconceptions, and flashcards.
  3. **Review and edit**: an editable concept graph (names, prerequisites with loop prevention, key points, notes),
     every question (correct answer, traps, verifier status) and every flashcard. Delete concepts and dependents are
     rewired automatically. Moderation flags and auto-fixes are shown for review.
  4. **Publish** (nothing reaches students before this) and **assign** the subject to students.
- **Demo data.** A one-click class simulator fills the built-in course with 30 simulated students.

### Admin app (`/admin`)

Every page has a shared time window (last hour, 24 hours, 7 days, 30 days, all time) and live refresh.

| Page | Shows |
|---|---|
| Overview | Traffic, p50/p95/p99 latency, 5xx and 4xx rates, LLM calls, learner cost per session vs studio cost, root-gap detection, guardrail events, recent warnings, telemetry health |
| Requests | Traffic and latency over time, per-endpoint volume, latency and error rate |
| LLM & cost | Spend and calls over time, per-feature tokens/cost/latency/fallback/cache, reliability (schema failures, retries, fallbacks) |
| Traces | Every LLM call (filter by scope, feature, problems, trace id) with a detail view of related calls and logs |
| Logs | Structured application logs with level, search, event and trace filters |
| AI quality | Root-gap detection vs simulator ground truth, verifier first-pass rate, learning outcomes, studio pipeline stats, question health |
| Guardrails | What every guard does and how often it fired |
| Telemetry | OpenTelemetry export health, configuration and links into OpenObserve |

### AI that suggests while code decides

- **Every** model call goes through one client (`backend/app/ai/llm_client.py`): structured output and schema
  validation, one retry, then a deterministic fallback; timeouts, token caps, caching, guardrails, and a row in
  `llm_calls` with its trace id, tokens, latency and cost.
- Model output never changes mastery, XP, unlocks or scores directly. Diagnoses are proposals that code validates
  (IDs must exist, the root must be a real prerequisite, confidence thresholds, probe budget) before applying them.
- Prompts are versioned files in `backend/prompts/`; the version is logged on every call.
- **Offline mode:** with no API key, every AI feature falls back to a deterministic, notes-grounded implementation,
  so the whole app still works (the studio can still extract concepts from headings and draft flashcards).

---

## Configuration

`backend/.env` (created from [`backend/.env.example`](backend/.env.example) by the setup script):

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | *(empty)* | Empty = offline mode |
| `OPENAI_BASE_URL` | `https://genailab.tcs.in/` | OpenAI-compatible TCS GenAI Lab gateway |
| `OPENAI_VERIFY_SSL` | `false` | Required by the hackathon gateway example |
| `OPENAI_MODEL_FAST`, `OPENAI_MODEL_SMART` | `genailab-openai-gpt-5.6-luna` | Models from the gateway's `/v1/models` list (never hard-coded) |
| `PRICE_*` | per 1M tokens | Cost accounting on the admin pages |
| `DATABASE_URL` | `sqlite:///./rootwise.db` | Database |
| `CORS_ORIGINS` | localhost:3000 | Allowed frontend origins |
| `OTEL_ENABLED` | `false` | Export traces, metrics and logs over OTLP/HTTP |
| `OTEL_EXPORTER_ENDPOINT` | `http://localhost:5080/api/default` | OTLP base URL (OpenObserve org endpoint) |
| `OPENOBSERVE_USER`, `OPENOBSERVE_PASSWORD` | | Basic auth for OpenObserve |
| `OPENOBSERVE_UI_URL`, `OPENOBSERVE_ORG` | `http://localhost:5080`, `default` | Links from the admin pages |
| `LOG_RETENTION_DAYS`, `LOG_MAX_ROWS` | `7`, `50000` | Log store retention |
| `STUDIO_MAX_TOKENS_PER_JOB` | `2500000` | Cost cap per studio generation job |
| `STUDIO_JOBS_PER_MINUTE` | `5` | Generation rate limit per client |
| `RATE_LIMIT_HINT_PER_MINUTE`, `RATE_LIMIT_LESSON_PER_MINUTE` | `20`, `10` | Per-student limits |
| `FLAG_*` | `true` | Feature flags (boss, teach-the-bot, replay, hints, simulator endpoint, studio) |

More tunables (learner-model constants, thresholds, studio limits) live in
[`backend/app/config.py`](backend/app/config.py). The frontend reads `NEXT_PUBLIC_API_URL` from
`frontend/.env.local` (written by the setup script) and supports `NEXT_PUBLIC_USE_MOCKS=true` for a backend-free UI.

---

## Manual setup (any OS)

Requirements: [uv](https://docs.astral.sh/uv/) (installs Python 3.12 for you), Node.js ≥ 20.9 and pnpm 10.

```bash
# backend
cd backend
uv sync
cp .env.example .env                          # then set OPENAI_API_KEY if you have one
uv run python -m app.db.seed                  # 21 concepts, 44 misconceptions, 73 questions
uv run uvicorn app.main:app --reload --port 8000

# frontend (new terminal)
cd frontend
pnpm install                                  # or: npx pnpm@10.34.9 install
pnpm dev                                      # http://localhost:3000
```

Useful commands:

```bash
cd backend && uv run pytest                                  # full test suite
cd backend && uv run python -m app.sim.run --students 30     # simulated class
cd backend && uv run python -m app.evals.run                 # eval harness -> app/evals/results/
cd backend && uv run python -m app.ai.pipeline --concept bst_property --bloom apply --n 3   # draft questions
cd frontend && pnpm gen:types                                # regenerate API types from the running backend
cd frontend && pnpm typecheck && pnpm lint
```

---

## Demo walkthrough

1. **Student, `/learn`:** take the 5-question diagnostic. On *BST search & insert*, pick *"It returns None
   automatically…"* and mark **Sure**. The node turns red and the root card asks whether recursion is the real snag.
2. Answer the probe with the "recursion stops on its own" option (**Sure**): **Root found: Recursion base case**,
   with evidence from both answers and the path BST search → Recursion.
3. Start the micro-lesson (streamed, grounded, with an analogy, Socratic questions and the misconception replay),
   then pass two mastery checks. The misconception clears: +150 XP, badges, confetti.
4. Fight the **Root Boss** and win (+250 XP); the skill tree on `/map` updates.
5. **Teacher, `/teacher`:** run the demo class simulator, then explore the heatmap, the reasoned alerts and the clusters.
6. **Studio, `/teacher/studio`:** upload a PDF, watch generation, review the graph, quizzes and flashcards, publish,
   and assign it to `demo_student`. Back on `/play`, switch subject in the top bar.
7. **Admin, `/admin`:** detection accuracy, latency, cost, guardrail events, every LLM call with its trace, and logs.

---

## Observability

- **Request tracing:** each request gets a trace id (returned in `x-trace-id`) that ties together the request,
  attempts, diagnoses, studio jobs, LLM calls and logs.
- **OpenTelemetry** (on with `OTEL_ENABLED=true`): a server span per request; a span per LLM call or agent turn with
  GenAI attributes (model, tokens, cost, fallback, guardrail flags, never prompt text); a `studio.job` trace with a
  child span per pipeline stage and concept; metrics (`rootwise.llm.calls/tokens/cost/duration`,
  `rootwise.guardrail.flags`, `rootwise.studio.jobs`, HTTP server metrics); and every structured log event as an
  OTel log record linked to its trace. With OTel on, the app's trace id is `tr_<OTel trace id>`.
- **OpenObserve:** `bash scripts/setup.sh --with-observability` (or
  `docker compose -f deploy/openobserve/docker-compose.yml up -d` with credentials in `deploy/openobserve/.env`).
  UI at http://localhost:5080; search Traces for service `rootwise-backend`.
- **Built-in store:** request metrics, `llm_calls` and INFO+ logs are also kept in the database (bounded by age and
  row count), so the admin pages work without any external service.

---

## Guardrails

| Layer | Guards |
|---|---|
| Input | Student and document text wrapped in data delimiters (never followed as instructions); prompt-injection detection; moderation (OpenAI moderation, local list offline); PII scrubbing; length limits; off-topic redirects in teach-the-bot |
| Output | Schema validation with retry and fallback; grounding checks against teacher notes and source material; answer-leakage blocking for hints and lessons; tone fixes; studio content screening (ungrounded or instruction-carrying cards/questions dropped, moderation flags surfaced to the teacher); question verifier (deterministic + LLM) |
| Decisions | AI proposes, code validates and applies; teacher approval before any generated content reaches students |
| Cost and abuse | Per-student daily token budget; per-job token budget for studio generation; rate limits on hints, lessons, teach-the-bot and generation (429 + `Retry-After`); upload type, magic-byte and size checks with oversized requests rejected before they're read |
| Requests | Client trace ids sanitised; security headers (`nosniff`, `X-Frame-Options: DENY`, `no-referrer`, `no-store`) |

---

## Architecture

```
frontend/                Next.js 16 (App Router), TypeScript strict, Tailwind v4, shadcn/ui, TanStack Query,
  app/(student)/         Zustand, React Flow, Motion, Recharts. Typed client generated from OpenAPI.
  app/teacher/           class overview, game results, studio (/teacher/studio/[id])
  app/admin/             overview, requests, llm, traces, logs, quality, guardrails, telemetry
  components/  lib/      UI components; API client, query hooks, mocks, stores
backend/app/
  api/                   FastAPI routes (student, class, studio, admin)
  core/                  deterministic engine: learner model (Elo/IRT), states, adaptive engine, gamification,
                         analytics, diagnosis validation, boss, levels, studio persistence + graph rules
  ai/                    llm_client (only entry point to models), prompt registry, diagnosis agent, generators,
                         teach-bot, verifier, question pipeline, studio pipeline, ingest/ (PDF parsing, chunking)
  guardrails/            input, PII, moderation, output, generated-content checks, budgets and rate limits
  observability/         trace ids, OpenTelemetry, request metrics middleware, log store, telemetry writer
  sim/  evals/           simulated students through the real API; eval harness with a control group
backend/prompts/         versioned prompt files
backend/seed/            built-in Data Structures course (concepts, misconceptions, notes, questions, worlds)
deploy/openobserve/      OpenObserve docker-compose
scripts/                 setup.sh, run.sh, stop.sh (Linux)
docs/                    PROJECT_CONTEXT.md (full spec)
```

Subjects are isolated: each request runs against the subject named in the `X-Subject-Id` header (default: the
built-in course), and class analytics only count students enrolled in that subject.

---

## Tests and evals

`cd backend && uv run pytest` runs ~85 tests: learner-model and adaptive math, states, diagnosis, guardrails, the
LLM client (with a fake model), API contract flows, adventure mode, the studio pipeline end to end (parsing a real PDF
with tables, figures and a scanned page; generation; review edits; publish; enrollment; subject scoping; rate limits)
and observability (metrics windows, log store, OTel spans and OTLP export).

Current eval numbers (offline mode, 30 simulated students, seed 7):

| Metric | Value |
|---|---|
| Root-gap detection (planted misconceptions a student actually ran into) | **97.8%** (44/45) |
| Root-gap detection (all planted, incl. never-reached concepts) | 78.6% (44/56) |
| Root concept accuracy (of detected) | 95.5% |
| Mastery on planted concepts: remediation vs no-remediation control | **+32 points** |
| Teach-the-bot scorer agreement (±15, 8 hand-labelled; offline scorer) | 75% |

The teach scorer's threshold was tuned on the same 8 labelled items it's scored on, so treat that 75% as optimistic.

---

## Decisions and deviations

- **Tuned values** (§9 says these are tunable): `K_s = 1.0` instead of 0.4, because with 3–5 questions per concept
  0.4 needs ~10 correct answers to reach mastery. Anti-farming only blocks progress for re-answering a question you got
  right in your last 10 attempts.
- **Diagnostic concepts** for the built-in course: arrays, linked lists, queues, hashing, BST search (configurable via
  `DIAGNOSTIC_CONCEPTS`); generated subjects pick theirs automatically, spread across the learning order.
- **Streaming:** lessons and bot replies are generated as structured output, validated, and only then streamed, which
  keeps guardrails in front of the student at the cost of time-to-first-token.
- **Studio:** generation runs in the backend process; if the server restarts mid-job the job is marked failed and can
  be regenerated. Subjects that students have practised can't be regenerated or deleted (unpublish instead).
- **Additive contract changes** beyond the original spec are listed in `docs/PROJECT_CONTEXT.md` §11.
- **Not yet built:** authentication (teacher and admin pages are open to anyone who can reach the app) and a student
  flashcard review screen.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `uv` or `node` not found after setup | Open a new shell, or run `export PATH="$HOME/.local/bin:$PATH"; . ~/.nvm/nvm.sh` |
| Port already in use | `BACKEND_PORT=8010 FRONTEND_PORT=3010 bash scripts/run.sh` |
| "Can't reach the Rootwise API" in the browser | The browser must reach `NEXT_PUBLIC_API_URL`; re-run setup with `--api-url` and `--frontend-url` |
| AI features return generic answers | Offline mode: set `OPENAI_API_KEY` (or `setup.sh --openai-key ...`) and restart |
| OpenObserve won't start | Its root password needs 8+ characters with upper, lower, digit and symbol (`deploy/openobserve/.env`) |
| Start over with a clean database | `bash scripts/setup.sh --reset-db --skip-build` |
| Logs | `logs/backend.log`, `logs/frontend.log`, or the admin Logs page |
