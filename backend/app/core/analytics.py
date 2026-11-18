"""Class analytics + student report (PROJECT_CONTEXT §9.6, C7). Deterministic, every alert has a reason."""

from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import DEFAULT_SUBJECT_ID, get_settings
from app.core.graph import ContentGraph
from app.core.learner_model import calibration, mastery
from app.core.states import AttemptLite, StateThresholds, classify
from app.core.student_state import (
    calibration_for,
    concept_state_out,
    load_attempts,
    load_rows,
    recompute,
    student_summary,
)
from app.db import models as m
from app.schemas.api import (
    AlertOut,
    BloomScore,
    Calibration,
    ClusterOut,
    HeatmapCell,
    HeatmapConcept,
    HeatmapResponse,
    HeatmapStudent,
    MapEdge,
    MapNode,
    NextStep,
    RootGap,
    RootReportResponse,
    StudentMapResponse,
    XPEventOut,
)
from app.schemas.common import BLOOM_ORDER


# ---------------------------------------------------------------- student map
def student_map(db: Session, student_id: str, graph: ContentGraph, trace_id: str) -> StudentMapResponse:
    attempts = load_attempts(db, student_id)
    rows = load_rows(db, student_id, graph)
    results = recompute(rows, attempts, graph)
    nodes = []
    for cid, c in graph.concepts.items():
        cs = concept_state_out(cid, rows, results, graph)
        nodes.append(
            MapNode(
                id=cid,
                name=c.name,
                state=cs.state,
                mastery=cs.mastery,
                n_attempts=cs.n_attempts,
                depth=c.depth,
                active_misconception_ids=cs.active_misconception_ids,
                reason=cs.reason,
            )
        )
    edges = [MapEdge(source=p, target=cid) for cid, c in graph.concepts.items() for p in c.prerequisites]
    return StudentMapResponse(trace_id=trace_id, student_id=student_id, nodes=nodes, edges=edges)


# ---------------------------------------------------------------- root report
def _attempt_evidence(a: m.Attempt, graph: ContentGraph) -> str:
    verdict = "Correct" if a.is_correct else "Wrong"
    q = graph.questions.get(a.question_id)
    chosen = ""
    if q and a.option_id and not a.is_correct:
        o = next((o for o in q.options if o.id == a.option_id), None)
        chosen = f": chose '{o.text}'" if o else ""
    return f"{verdict} on {a.question_id} ({a.confidence}){chosen}"


def root_report(db: Session, student_id: str, graph: ContentGraph, trace_id: str) -> RootReportResponse:
    student = db.get(m.Student, student_id)
    assert student is not None
    attempts = load_attempts(db, student_id)
    rows = load_rows(db, student_id, graph)
    results = recompute(rows, attempts, graph)
    summary = student_summary(db, student)

    diagnoses = db.scalars(
        select(m.Diagnosis)
        .where(m.Diagnosis.student_id == student_id, m.Diagnosis.status == "applied", m.Diagnosis.needs_probe.is_(False))
        .order_by(m.Diagnosis.created_at.desc())
    ).all()
    latest_dx_by_root: dict[str, m.Diagnosis] = {}
    for d in diagnoses:
        if d.root_concept_id and d.root_concept_id not in latest_dx_by_root:
            latest_dx_by_root[d.root_concept_id] = d

    # Rank weak concepts: misconception > gap > fragile, then lower mastery, then more dependents (root-ness).
    rank = {"misconception": 0, "gap": 1, "fragile": 2}
    shaky = {a.concept_id for a in attempts if not a.is_correct or a.confidence == "guess"}
    weak = [
        cid for cid, r in results.items()
        if r.state in ("misconception", "gap")
        or (r.state == "fragile" and (cid in shaky or cid in latest_dx_by_root))
    ]
    weak.sort(key=lambda c: (rank[results[c].state], -len(graph.descendants(c)) * 0.01 + mastery(rows[c].theta)))
    # Diagnosed roots first.
    weak.sort(key=lambda c: 0 if c in latest_dx_by_root else 1)
    gaps: list[RootGap] = []
    for cid in weak[:3]:
        r = rows[cid]
        dx = latest_dx_by_root.get(cid)
        mid = (r.active_misconception_ids or [None])[0] or (dx.misconception_id if dx else None)
        mc = graph.misconceptions.get(mid or "")
        if dx:
            evidence = list(dx.evidence or [])[:4]
        else:
            evidence = [_attempt_evidence(a, graph) for a in attempts if a.concept_id == cid][-3:]
        gaps.append(
            RootGap(
                concept_id=cid,
                concept_name=graph.name(cid),
                state=results[cid].state,
                mastery=round(mastery(r.theta), 3),
                misconception_id=mid,
                misconception_text=mc.description if mc else None,
                evidence=evidence,
                diagnosis_id=dx.id if dx else None,
                path=list(dx.path or []) if dx else [],
            )
        )

    bloom_stats: dict[str, list[bool]] = defaultdict(list)
    for a in attempts:
        q = graph.questions.get(a.question_id)
        if q:
            bloom_stats[q.bloom_level].append(a.is_correct)
    radar = [
        BloomScore(level=b, accuracy=round(sum(v) / len(v), 3) if (v := bloom_stats.get(b)) else 0.0,
                   attempts=len(bloom_stats.get(b, [])))
        for b in BLOOM_ORDER
    ]
    cal = calibration_for(attempts)

    if gaps and gaps[0].state == "misconception":
        g = gaps[0]
        step = NextStep(kind="lesson", concept_id=g.concept_id, label=f"Fix the root: {g.concept_name}",
                        reason="It's your top root gap with an active misconception. A micro-lesson plus 2 checks clears it.")
    elif any(a.selected_misconception_id and not a.is_correct and a.confidence == "sure" for a in attempts[-15:]) and not gaps:
        step = NextStep(kind="boss", concept_id=None, label="Face the Root Boss",
                        reason="You recently cleared misconceptions. Beat the boss to lock them in.")
    elif gaps:
        g = gaps[0]
        step = NextStep(kind="next_question", concept_id=g.concept_id, label=f"Practice {g.concept_name}",
                        reason=f"{g.concept_name} is your weakest concept ({g.mastery:.0%}).")
    else:
        step = NextStep(kind="next_question", concept_id=None, label="Keep learning",
                        reason="No gaps detected right now. Unlock new concepts.")

    from app.core.gamification import badge_out

    badges = [
        badge_out(b.badge_id, b.earned_at)
        for b in db.scalars(select(m.StudentBadge).where(m.StudentBadge.student_id == student_id)).all()
    ]
    recent_xp = [
        XPEventOut(kind=x.kind, amount=x.amount, reason=x.reason, concept_id=x.concept_id)  # type: ignore[arg-type]
        for x in db.scalars(
            select(m.XPEvent).where(m.XPEvent.student_id == student_id).order_by(m.XPEvent.created_at.desc()).limit(10)
        ).all()
    ]
    counts = Counter(r.state for r in results.values())
    return RootReportResponse(
        trace_id=trace_id,
        student_id=student_id,
        root_gaps=gaps,
        bloom_radar=radar,
        calibration=Calibration(score=cal.score, n=cal.n, sure_correct=cal.sure_correct, sure_wrong=cal.sure_wrong,
                                guess_correct=cal.guess_correct, guess_wrong=cal.guess_wrong),
        next_step=step,
        xp_total=summary.xp_total,
        level=summary.level,
        streak_days=summary.streak_days,
        badges=badges,
        recent_xp=recent_xp,
        state_counts=dict(counts),
        attempts_total=len(attempts),
        accuracy=round(sum(a.is_correct for a in attempts) / len(attempts), 3) if attempts else None,
    )


# ---------------------------------------------------------------- class-wide
def class_states(db: Session, graph: ContentGraph):
    """Bulk version of recompute for every student: returns (students, rows_by_student, results, attempts)."""
    t = StateThresholds.from_settings()
    sq = select(m.Student).order_by(m.Student.is_simulated, m.Student.id)
    if graph.subject_id != DEFAULT_SUBJECT_ID:
        enrolled = select(m.Enrollment.student_id).where(m.Enrollment.subject_id == graph.subject_id)
        sq = sq.where(m.Student.id.in_(enrolled))
    students = db.scalars(sq).all()
    cids = list(graph.concepts)
    rows_all = db.scalars(select(m.MasteryState).where(m.MasteryState.concept_id.in_(cids))).all()
    attempts_all = db.scalars(
        select(m.Attempt).where(m.Attempt.concept_id.in_(cids)).order_by(m.Attempt.student_id, m.Attempt.seq)
    ).all()
    rows_by: dict[str, dict[str, m.MasteryState]] = defaultdict(dict)
    for r in rows_all:
        rows_by[r.student_id][r.concept_id] = r
    att_by: dict[str, list[m.Attempt]] = defaultdict(list)
    for a in attempts_all:
        att_by[a.student_id].append(a)
    names = graph.names()
    results: dict[str, dict[str, tuple[str, float, list[str]]]] = {}
    for s in students:
        rows = rows_by.get(s.id, {})
        by_c: dict[str, list[AttemptLite]] = defaultdict(list)
        for a in att_by.get(s.id, []):
            by_c[a.concept_id].append(AttemptLite(a.is_correct, a.confidence))
        out = {}
        for cid in graph.topo_order:
            r = rows.get(cid)
            theta = r.theta if r else 0.0
            n = r.n_attempts if r else 0
            active = list(r.active_misconception_ids or []) if r else []
            pm = {p: mastery(rows[p].theta) if p in rows else 0.5 for p in graph.concepts[cid].prerequisites}
            res = classify(mastery(theta), n, by_c.get(cid, []), active, pm, t, names)
            out[cid] = (res.state, mastery(theta), active)
        results[s.id] = out
    return students, rows_by, results, att_by


def heatmap(db: Session, graph: ContentGraph, trace_id: str) -> HeatmapResponse:
    students, _rows, results, att_by = class_states(db, graph)
    xp = {sid: int(total or 0) for sid, total in _xp_totals(db)}
    out_students = []
    cells = []
    for s in students:
        atts = att_by.get(s.id, [])
        cal = calibration((a.is_correct, a.confidence) for a in atts)
        out_students.append(
            HeatmapStudent(id=s.id, display_name=s.display_name, is_simulated=s.is_simulated,
                           xp_total=xp.get(s.id, 0), calibration=cal.score, attempts=len(atts))
        )
        for cid, (state, mval, _active) in results[s.id].items():
            cells.append(HeatmapCell(student_id=s.id, concept_id=cid, state=state, mastery=round(mval, 3)))  # type: ignore[arg-type]
    concepts = [HeatmapConcept(id=cid, name=c.name, depth=c.depth) for cid, c in graph.concepts.items()]
    return HeatmapResponse(trace_id=trace_id, students=out_students, concepts=concepts, cells=cells)


def _xp_totals(db: Session) -> list[tuple[str, int]]:
    from sqlalchemy import func

    return list(db.execute(select(m.XPEvent.student_id, func.sum(m.XPEvent.amount)).group_by(m.XPEvent.student_id)).all())


def alerts(db: Session, graph: ContentGraph) -> tuple[list[AlertOut], list[ClusterOut], int]:
    s = get_settings()
    students, _rows, results, att_by = class_states(db, graph)
    active_students = [st for st in students if att_by.get(st.id)]
    class_size = len(active_students)
    out: list[AlertOut] = []

    # Root concept per misconception from applied diagnoses (most common).
    dx_rows = db.scalars(select(m.Diagnosis).where(m.Diagnosis.status == "applied", m.Diagnosis.needs_probe.is_(False))).all()
    roots_by_mis: dict[str, Counter] = defaultdict(Counter)
    for d in dx_rows:
        if d.misconception_id and d.root_concept_id:
            roots_by_mis[d.misconception_id][d.root_concept_id] += 1

    # Misconception clusters.
    holders: dict[str, list[str]] = defaultdict(list)
    for st in active_students:
        seen: set[str] = set()
        for _cid, (_state, _m, active) in results[st.id].items():
            for mid in active:
                if mid not in seen:
                    seen.add(mid)
                    holders[mid].append(st.id)
    clusters = []
    for mid, sids in sorted(holders.items(), key=lambda kv: -len(kv[1])):
        mc = graph.misconceptions.get(mid)
        if not mc:
            continue
        root = roots_by_mis[mid].most_common(1)[0][0] if roots_by_mis.get(mid) else mc.concept_id
        share = len(sids) / class_size if class_size else 0.0
        clusters.append(ClusterOut(misconception_id=mid, description=mc.description, concept_id=mc.concept_id,
                                   root_concept_id=root, student_ids=sids, share=round(share, 3)))
        if share >= s.alert_class_share and len(sids) >= 2:
            out.append(
                AlertOut(
                    id=f"class:{mid}", kind="class_misconception", severity="critical", student_id=None,
                    concept_id=root, misconception_id=mid,
                    message=f"{share:.0%} of class shares the misconception \"{mc.description}\"; root is {graph.name(root)}.",
                    reason=f"{len(sids)} of {class_size} active students have it active (threshold {s.alert_class_share:.0%}).",
                )
            )

    names = {st.id: st.display_name for st in students}
    for st in active_students:
        atts = att_by[st.id]
        # >= 2 confident-wrong answers on one concept (recent 20 attempts), concept not mastered.
        cw = Counter(a.concept_id for a in atts[-20:] if not a.is_correct and a.confidence == "sure" and a.boss_battle_id is None)
        for cid, n in cw.items():
            if n >= 2 and results[st.id][cid][0] != "mastered":
                out.append(AlertOut(
                    id=f"cw:{st.id}:{cid}", kind="confident_wrong", severity="warning", student_id=st.id,
                    concept_id=cid, misconception_id=None,
                    message=f"{names[st.id]} was confidently wrong {n}x on {graph.name(cid)}.",
                    reason="Two or more 'Sure' answers were wrong on the same concept: a likely misconception.",
                ))
        # No progress in N attempts.
        n = s.alert_no_progress_n
        if len(atts) >= n:
            gain = sum(mastery(a.theta_after) - mastery(a.theta_before) for a in atts[-n:])
            if gain <= 0.0:
                out.append(AlertOut(
                    id=f"np:{st.id}", kind="no_progress", severity="warning", student_id=st.id, concept_id=None,
                    misconception_id=None, message=f"{names[st.id]} made no mastery progress in the last {n} attempts.",
                    reason=f"Net mastery change over the last {n} attempts is {gain:+.2f}.",
                ))
        cal = calibration((a.is_correct, a.confidence) for a in atts)
        if cal.n >= 10 and cal.score is not None and cal.score < s.alert_low_calibration:
            out.append(AlertOut(
                id=f"cal:{st.id}", kind="low_calibration", severity="info", student_id=st.id, concept_id=None,
                misconception_id=None, message=f"{names[st.id]}'s confidence rarely matches results ({cal.score:.0%}).",
                reason=f"Calibration below {s.alert_low_calibration:.0%} over {cal.n} attempts. Coach on when to say 'Guessing'.",
            ))
    sev = {"critical": 0, "warning": 1, "info": 2}
    out.sort(key=lambda a: (sev[a.severity], a.kind))
    return out, clusters, class_size
