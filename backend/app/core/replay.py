"""Event-sourced rebuild (§4.2): learner state = fold(attempts + applied diagnoses + boss wins).

Uses the same pure rules as live processing. Exact when question difficulty updates are off for the
student (simulated students), because live updates use the difficulty at the time of each attempt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.attempts import apply_misconception_rules, clear_misconceptions, farming_allowed
from app.core.graph import ContentGraph
from app.core.learner_model import LearnerParams
from app.core.learner_model import update as theta_update
from app.core.student_state import load_attempts
from app.db import models as m


@dataclass
class RowLite:
    theta: float = 0.0
    n_attempts: int = 0
    active_misconception_ids: list[str] = field(default_factory=list)
    misconception_progress: dict[str, int] = field(default_factory=dict)


def rebuild(db: Session, student_id: str, graph: ContentGraph) -> dict[str, RowLite]:
    s = get_settings()
    params = LearnerParams.from_settings()
    attempts = load_attempts(db, student_id)
    dx_by_trigger = {
        d.trigger_attempt_id: d
        for d in db.scalars(
            select(m.Diagnosis).where(m.Diagnosis.student_id == student_id, m.Diagnosis.status == "applied")
        )
        if d.misconception_id and not d.needs_probe
    }
    won = {b.id: b for b in db.scalars(select(m.BossBattle).where(m.BossBattle.student_id == student_id,
                                                                  m.BossBattle.status == "won"))}
    last_boss_attempt = {}
    for a in attempts:
        if a.boss_battle_id in won:
            last_boss_attempt[a.boss_battle_id] = a.id

    rows = {cid: RowLite() for cid in graph.concepts}
    seen: list[m.Attempt] = []
    for a in attempts:
        q = graph.questions[a.question_id]
        allow = farming_allowed(seen[-s.recent_window :], a.question_id)
        r = rows[a.concept_id]
        r.theta = theta_update(r.theta, q.b, a.is_correct, a.confidence, a.hints_used, params, allow).theta  # type: ignore[arg-type]
        r.n_attempts += 1
        apply_misconception_rules(rows, a.concept_id, q.targets, a.is_correct, a.confidence,
                                  a.selected_misconception_id, allow, s.misconception_clear_needed)
        dx = dx_by_trigger.get(a.id)
        if dx and dx.root_concept_id in rows:
            root = rows[dx.root_concept_id]
            if dx.misconception_id not in root.active_misconception_ids:
                root.active_misconception_ids.append(dx.misconception_id)
                root.misconception_progress[dx.misconception_id] = 0
        if a.boss_battle_id in won and last_boss_attempt[a.boss_battle_id] == a.id:
            clear_misconceptions(rows, set(won[a.boss_battle_id].misconception_ids))
        seen.append(a)
    return rows
