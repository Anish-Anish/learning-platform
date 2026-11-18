"""Gamification rules (PROJECT_CONTEXT §9.5). Deterministic; XP only for mastery events.

Pure rule functions return proposed awards; `persist_awards` writes them. LLM output never reaches here
except teach-the-bot scores, which only affect XP/badges, never mastery (rule 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import models as m
from app.schemas.api import BadgeOut, UnlockOut, XPEventOut

BADGES: dict[str, tuple[str, str]] = {
    "myth_buster": ("Myth Buster", "Cleared your first misconception."),
    "root_finder": ("Root Finder", "Fixed a root gap the tutor diagnosed."),
    "well_calibrated": ("Well Calibrated", "Confidence matched correctness on 80%+ of 20 attempts."),
    "teachers_pet": ("Teacher's Pet", "Scored 90+ teaching the bot."),
    "streak_3": ("On a Roll", "3-day learning streak."),
    "streak_7": ("Unstoppable", "7-day learning streak."),
}


def badge_out(badge_id: str, earned_at=None) -> BadgeOut:
    name, desc = BADGES[badge_id]
    return BadgeOut(badge_id=badge_id, name=name, description=desc, earned_at=earned_at)  # type: ignore[arg-type]


@dataclass
class Awards:
    xp: list[XPEventOut] = field(default_factory=list)
    unlocks: list[UnlockOut] = field(default_factory=list)
    badges: list[str] = field(default_factory=list)

    def add_xp(self, kind: str, amount: int, reason: str, concept_id: str | None = None) -> None:
        self.xp.append(XPEventOut(kind=kind, amount=amount, reason=reason, concept_id=concept_id))  # type: ignore[arg-type]

    def extend(self, other: Awards) -> None:
        self.xp.extend(other.xp)
        self.unlocks.extend(other.unlocks)
        for b in other.badges:
            if b not in self.badges:
                self.badges.append(b)


# ---------------------------------------------------------------- pure rules
def mastery_awards(newly_mastered: list[tuple[str, str]]) -> Awards:
    s = get_settings()
    a = Awards()
    for cid, name in newly_mastered:
        a.add_xp("concept_mastered", s.xp_concept_mastered, f"Mastered {name}", cid)
    return a


def misconception_awards(cleared: list[tuple[str, str]], had_cleared_before: bool) -> Awards:
    s = get_settings()
    a = Awards()
    for mid, desc in cleared:
        a.add_xp("misconception_cleared", s.xp_misconception_cleared, f"Cleared misconception: {desc}", mid.split(".")[0])
    if cleared and not had_cleared_before:
        a.badges.append("myth_buster")
    return a


def unlock_awards(newly_unlocked: list[tuple[str, str]], prereq_names: dict[str, list[str]]) -> Awards:
    a = Awards()
    for cid, name in newly_unlocked:
        reason = "All prerequisites reached 70%: " + ", ".join(prereq_names.get(cid, []))
        a.unlocks.append(UnlockOut(concept_id=cid, concept_name=name, reason=reason))
        a.add_xp("unlock", 0, f"Unlocked {name}", cid)
    return a


def hint_awards(hints_used: int) -> Awards:
    s = get_settings()
    a = Awards()
    if hints_used > 0:
        a.add_xp("hint", -s.xp_hint_cost * hints_used, f"Used {hints_used} hint(s)")
    return a


def streak_awards(attempt_dates: list[date], today: date, streak: int) -> Awards:
    """+20 on the first attempt of a day that continues a streak (>= 2 consecutive days)."""
    s = get_settings()
    a = Awards()
    first_today = attempt_dates.count(today) == 1
    if first_today and streak >= 2:
        a.add_xp("daily_streak", s.xp_daily_streak, f"{streak}-day streak")
    if streak >= 3:
        a.badges.append("streak_3")
    if streak >= 7:
        a.badges.append("streak_7")
    return a


def calibration_awards(n: int, score: float | None) -> Awards:
    a = Awards()
    if n >= 20 and score is not None and score >= 0.8:
        a.badges.append("well_calibrated")
    return a


def boss_awards(battle_name: str) -> Awards:
    s = get_settings()
    a = Awards()
    a.add_xp("boss_defeated", s.xp_boss_defeated, f"Defeated {battle_name}")
    return a


def teach_awards(score: int, concept_id: str, concept_name: str, already_awarded: bool) -> Awards:
    s = get_settings()
    a = Awards()
    if score >= 80 and not already_awarded:
        a.add_xp("teach_score", s.xp_teach_good, f"Taught {concept_name} to the bot (score {score})", concept_id)
    if score >= 90:
        a.badges.append("teachers_pet")
    return a


# ---------------------------------------------------------------- persistence
def owned_badges(db: Session, student_id: str) -> set[str]:
    return set(db.scalars(select(m.StudentBadge.badge_id).where(m.StudentBadge.student_id == student_id)))


def persist_awards(db: Session, student_id: str, awards: Awards) -> list[BadgeOut]:
    """Write XP events + new badges. Returns only badges newly earned."""
    for x in awards.xp:
        db.add(m.XPEvent(student_id=student_id, kind=x.kind, amount=x.amount, reason=x.reason, concept_id=x.concept_id))
    have = owned_badges(db, student_id)
    new: list[BadgeOut] = []
    for b in awards.badges:
        if b in have or b not in BADGES:
            continue
        row = m.StudentBadge(student_id=student_id, badge_id=b)
        db.add(row)
        have.add(b)
        new.append(badge_out(b))
    db.flush()
    return new
