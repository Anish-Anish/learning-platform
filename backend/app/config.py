"""Runtime configuration + feature flags. Values marked (tunable) in PROJECT_CONTEXT live here."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
SEED_DIR = BACKEND_DIR / "seed"
PROMPTS_DIR = BACKEND_DIR / "prompts"
EVAL_RESULTS_DIR = BACKEND_DIR / "app" / "evals" / "results"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{BACKEND_DIR / 'rootwise.db'}"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- OpenAI (rule 10: model names only from env; empty => offline/fallback mode) ---
    openai_api_key: str = ""
    openai_model_fast: str = ""
    openai_model_smart: str = ""
    openai_moderation_model: str = "omni-moderation-latest"
    llm_timeout_s: float = 20.0
    # USD per 1M tokens, for cost accounting (set to your model's prices).
    price_fast_in: float = 0.40
    price_fast_out: float = 1.60
    price_smart_in: float = 2.00
    price_smart_out: float = 8.00

    # --- learner model (§9.1, tunable) ---
    # K_s raised from the spec's 0.4 starting point: with ~3-5 questions per concept, 0.4 needs ~10 correct
    # answers to reach mastery. 1.0 => unlock after ~2-3 correct+sure at p~0.7, mastered after ~3-4.
    k_student: float = 1.0
    k_question: float = 0.05
    update_question_difficulty: bool = True
    w_correct_sure: float = 1.0
    w_correct_guess: float = 0.5
    w_wrong_sure: float = 1.2
    w_wrong_guess: float = 0.8

    # --- states / adaptive (§9.3, §9.4) ---
    unlock_threshold: float = 0.7
    mastered_threshold: float = 0.8
    fragile_threshold: float = 0.5
    target_p: float = 0.7
    recent_window: int = 10
    diagnostic_concepts: str = "arrays,linked_lists,queues,hashing,bst_ops"
    misconception_clear_needed: int = 2

    # --- gamification (§9.5) ---
    xp_concept_mastered: int = 100
    xp_misconception_cleared: int = 150
    xp_boss_defeated: int = 250
    xp_teach_good: int = 100
    xp_daily_streak: int = 20
    xp_hint_cost: int = 10
    boss_questions: int = 5
    boss_max_hp: int = 100

    # --- analytics alerts (§9.6) ---
    alert_no_progress_n: int = 8
    alert_class_share: float = 0.30
    alert_low_calibration: float = 0.40

    # --- guardrails (§13) ---
    max_free_text_chars: int = 1000
    rate_limit_per_minute: int = 20
    student_daily_token_budget: int = 60_000

    # --- observability (§14) ---
    tracing_export: str = ""  # "", "langfuse", "phoenix"
    log_level: str = "INFO"

    # --- flags (rule 9) ---
    flag_sim_endpoint: bool = True
    flag_boss: bool = True
    flag_teach_bot: bool = True
    flag_replay: bool = True
    flag_hints: bool = True
    lesson_stream_delay_ms: int = 18

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key and self.openai_model_fast and self.openai_model_smart)

    @property
    def diagnostic_concept_ids(self) -> list[str]:
        return [c.strip() for c in self.diagnostic_concepts.split(",") if c.strip()]

    def model_for(self, tier: str) -> str:
        return self.openai_model_smart if tier == "smart" else self.openai_model_fast


@lru_cache
def get_settings() -> Settings:
    return Settings()
