"""Synthetic students (PROJECT_CONTEXT §15.1).

Each has a true ability per concept and 1–3 planted misconceptions. Policy: if an option carries a
planted (not yet unlearned) misconception, pick it with high probability and 'sure'; otherwise answer
correctly with probability sigmoid(true_ability - b); confidence correlates with ability plus noise.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.core.graph import ContentGraph
from app.core.learner_model import sigmoid

# Popular misconceptions (weights) so class-level clusters emerge, plus a long tail.
POPULAR = {
    "recursion_base.m1": 0.40,
    "queues.m1": 0.30,
    "bst_property.m1": 0.25,
    "arrays.m1": 0.15,
    "hashing.m1": 0.15,
    "linked_lists.m1": 0.15,
    "memory_basics.m1": 0.12,
    "call_stack.m1": 0.10,
    "hash_tables.m1": 0.10,
    "big_o.m1": 0.10,
}

NAMES = [
    "Ada", "Linus", "Grace", "Alan", "Barbara", "Edsger", "Margaret", "Dennis", "Radia", "Ken", "Frances",
    "Donald", "Katherine", "Tim", "Hedy", "Guido", "Sophie", "Bjarne", "Anita", "John", "Shafi", "Niklaus",
    "Lynn", "Vint", "Jean", "Yukihiro", "Adele", "James", "Carol", "Leslie", "Mary", "Brian", "Fran", "Robin",
]


@dataclass
class SimStudent:
    id: str
    display_name: str
    ability: dict[str, float]
    planted: list[str]
    rng: random.Random
    engagement: float = 0.8  # probability of following a suggested lesson / boss (real classes don't do every one)
    unlearned: set[str] = field(default_factory=set)

    @property
    def active_planted(self) -> list[str]:
        return [m for m in self.planted if m not in self.unlearned]

    def answer(self, q: dict, graph: ContentGraph) -> tuple[str, str]:
        """q is a QuestionPublic dict. Returns (option_id, confidence)."""
        info = graph.questions[q["id"]]
        trap = [o for o in info.options if o.misconception_id in self.active_planted]
        if trap and self.rng.random() < 0.85:
            return trap[0].id, ("sure" if self.rng.random() < 0.9 else "guess")
        p = sigmoid(self.ability.get(info.concept_id, 0.0) - info.b)
        if self.rng.random() < p:
            opt = info.correct_option
            conf_p = min(0.95, max(0.1, 0.25 + 0.6 * p + self.rng.gauss(0, 0.1)))
            return opt.id, ("sure" if self.rng.random() < conf_p else "guess")  # type: ignore[union-attr]
        wrong = [o for o in info.options if not o.is_correct]
        opt = self.rng.choice(wrong)
        conf_p = min(0.6, max(0.05, 0.2 + self.rng.gauss(0, 0.1)))
        return opt.id, ("sure" if self.rng.random() < conf_p else "guess")

    def study(self, concept_id: str, misconception_id: str | None, graph: ContentGraph) -> bool:
        """Learning effect after a micro-lesson. Returns True if a planted misconception was unlearned."""
        unlearned = False
        for mid in list(self.active_planted):
            if mid == misconception_id or graph.misconceptions[mid].concept_id == concept_id:
                if self.rng.random() < 0.8:
                    self.unlearned.add(mid)
                    unlearned = True
        self.ability[concept_id] = self.ability.get(concept_id, 0.0) + (1.0 if unlearned else 0.5)
        return unlearned


def make_students(n: int, graph: ContentGraph, seed: int = 7, prefix: str = "sim") -> list[SimStudent]:
    rng = random.Random(seed)
    students = []
    pool = [m for m in POPULAR if m in graph.misconceptions]
    for i in range(n):
        srng = random.Random(rng.random())
        base = srng.gauss(0.6, 0.7)
        ability = {cid: base + srng.gauss(0, 0.5) - 0.1 * c.depth for cid, c in graph.concepts.items()}
        planted = [m for m in pool if srng.random() < POPULAR[m]][:3]
        if not planted:
            planted = [srng.choices(pool, weights=[POPULAR[m] for m in pool])[0]]
        for mid in planted:
            cid = graph.misconceptions[mid].concept_id
            ability[cid] -= 1.0
            for d in graph.concepts[cid].dependents:
                ability[d] -= 0.3
        name = f"{NAMES[i % len(NAMES)]}{'' if i < len(NAMES) else ' ' + str(i // len(NAMES) + 1)}"
        students.append(SimStudent(id=f"{prefix}_{seed}_{i:02d}", display_name=name, ability=ability,
                                   planted=planted, rng=srng, engagement=srng.uniform(0.35, 0.95)))
    return students
