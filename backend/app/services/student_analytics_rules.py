"""MD-03 Student Performance Analytics — deterministic product rules.

Every function here is a pure, rule-based transform (no ML, no GenAI, no DB
access). Thresholds are configurable and live in ``app.core.config`` following
the repository's Threshold Engine convention.

The rules are intentionally transparent product logic:
  * Strength bands:  Strong >= 75 | Good 60-74.99 | Needs Attention 45-59.99 |
    Critical < 45 (MD-03 feature 2).
  * Needs Attention priority: failed > critical % < 45 > needs-attention band
    45-59.99 > declining > final result pending (MD-03 feature 3).
  * Learning gaps: assessment progression gap (internal -> mid -> end drop) and
    repeated lower performance (MD-03 feature 4).
  * NULL is never treated as zero.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings

# ---------------------------------------------------------------------------
# Subject strength classification (product rule, NOT an ML prediction)
# ---------------------------------------------------------------------------


def classify_subject(percentage: float) -> str:
    if percentage >= settings.STUDENT_STRENGTH_STRONG_MIN:
        return "Strong"
    if percentage >= settings.STUDENT_STRENGTH_GOOD_MIN:
        return "Good"
    if percentage >= settings.STUDENT_NEEDS_ATTENTION_MAX:
        return "Needs Attention"
    return "Critical"


# ---------------------------------------------------------------------------
# Attempt helpers
# ---------------------------------------------------------------------------


def _attempt_key(row: Dict[str, Any]) -> Tuple[int, int]:
    return (int(row.get("attempt_number") or 1), int(row.get("semester") or 0))


def _group_attempts_by_subject(
    performance_rows: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in performance_rows:
        code = row.get("subject_code")
        if not code:
            continue
        grouped.setdefault(code, []).append(row)
    for code in grouped:
        grouped[code].sort(key=_attempt_key)
    return grouped


def _latest_attempt_per_subject(
    performance_rows: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in performance_rows:
        code = row.get("subject_code")
        if not code:
            continue
        if code not in latest or _attempt_key(row) > _attempt_key(latest[code]):
            latest[code] = row
    return latest


# ---------------------------------------------------------------------------
# Feature 1 — Performance trends
# ---------------------------------------------------------------------------


def _compute_movement(rows: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    valid = [r for r in rows if r.get(key) is not None]
    if len(valid) < 2:
        return {"available": False, "metric": key}
    previous = valid[-2]
    current = valid[-1]
    delta = round(float(current[key]) - float(previous[key]), 2)
    tolerance = settings.STUDENT_TREND_STABLE_TOLERANCE
    if delta > tolerance:
        direction = "up"
    elif delta < -tolerance:
        direction = "down"
    else:
        direction = "flat"
    return {
        "available": True,
        "metric": key,
        "previous_semester": previous["semester"],
        "current_semester": current["semester"],
        "previous_value": float(previous[key]),
        "current_value": float(current[key]),
        "delta": delta,
        "direction": direction,
    }


def _overall_direction(rows: List[Dict[str, Any]]) -> str:
    valid = [r for r in rows if r.get("sgpa") is not None]
    if len(valid) < 2:
        return "insufficient"
    diff = float(valid[-1]["sgpa"]) - float(valid[0]["sgpa"])
    tolerance = settings.STUDENT_TREND_STABLE_TOLERANCE
    if diff > tolerance:
        return "improving"
    if diff < -tolerance:
        return "declining"
    return "stable"


def _trend_interpretation(
    movements: Dict[str, Dict[str, Any]], rows: List[Dict[str, Any]]
) -> Optional[str]:
    sgpa = movements.get("sgpa", {})
    if not sgpa.get("available"):
        return "Not enough semester history to determine a trend."
    delta = float(sgpa["delta"])
    prev_sem = sgpa["previous_semester"]
    cur_sem = sgpa["current_semester"]
    if sgpa["direction"] == "up":
        return (
            f"Your SGPA improved by {delta:.2f} from Semester {prev_sem} to "
            f"Semester {cur_sem}."
        )
    if sgpa["direction"] == "down":
        return (
            f"Your performance declined by {abs(delta):.2f} SGPA in the "
            f"latest semester."
        )
    return (
        f"Your SGPA held steady at {float(sgpa['current_value']):.2f} in "
        f"Semester {cur_sem}."
    )


def compute_trends(summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    ordered = sorted(summaries, key=lambda r: int(r.get("semester") or 0))
    points = [
        {
            "semester": row["semester"],
            "academic_year": row.get("academic_year"),
            "sgpa": row.get("sgpa"),
            "percentage": row.get("semester_percentage"),
            "attendance": row.get("attendance_percentage"),
            "result": row.get("semester_result"),
            "standing": row.get("academic_standing"),
        }
        for row in ordered
    ]
    movements = {
        metric: _compute_movement(ordered, key)
        for metric, key in (
            ("sgpa", "sgpa"),
            ("percentage", "semester_percentage"),
            ("attendance", "attendance_percentage"),
        )
    }
    return {
        "points": points,
        "movements": movements,
        "overall_direction": _overall_direction(ordered),
        "interpretation": _trend_interpretation(movements, ordered),
    }


# ---------------------------------------------------------------------------
# Feature 2 — Subject strengths
# ---------------------------------------------------------------------------


def compute_strengths(performance_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    strengths = []
    for row in _latest_attempt_per_subject(performance_rows).values():
        pct = row.get("percentage")
        if pct is None:
            continue
        category = classify_subject(float(pct))
        if category not in ("Strong", "Good"):
            continue
        strengths.append(
            {
                "subject_code": row["subject_code"],
                "subject_name": row["subject_name"],
                "semester": row["semester"],
                "percentage": round(float(pct), 2),
                "grade": row.get("grade"),
                "grade_point": row.get("grade_point"),
                "category": category,
            }
        )
    strengths.sort(key=lambda s: s["percentage"], reverse=True)
    return strengths


# ---------------------------------------------------------------------------
# Feature 3 — Needs Attention
# ---------------------------------------------------------------------------

_NEEDS_ATTENTION_PRIORITY = {
    "failed": 1,
    "critical": 2,
    "needs_attention": 3,
    "declining": 4,
    "incomplete": 5,
}

_NEEDS_ATTENTION_REASON_TEXT = {
    "failed": "Failed result",
    "critical": "Very low percentage",
    "needs_attention": "Needs attention",
    "declining": "Performance declined across attempts",
    "incomplete": "Final result pending",
}


def compute_needs_attention(
    performance_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    items = []
    for code, attempts in _group_attempts_by_subject(performance_rows).items():
        latest = attempts[-1]
        result_status = latest.get("result_status")
        pct = latest.get("percentage")

        reason_code: Optional[str] = None
        if result_status is not None and str(result_status).lower() == "fail":
            reason_code = "failed"
        elif pct is not None and float(pct) < settings.STUDENT_NEEDS_ATTENTION_MAX:
            reason_code = "critical"
        elif pct is not None and float(pct) < settings.STUDENT_STRENGTH_GOOD_MIN:
            reason_code = "needs_attention"
        elif len(attempts) >= 2:
            previous = attempts[-2]
            prev_pct = previous.get("percentage")
            if (
                pct is not None
                and prev_pct is not None
                and float(pct) < float(prev_pct)
            ):
                reason_code = "declining"
        elif pct is None:
            reason_code = "incomplete"

        if reason_code is None:
            continue

        items.append(
            {
                "subject_code": code,
                "subject_name": latest["subject_name"],
                "semester": latest["semester"],
                "percentage": round(float(pct), 2) if pct is not None else None,
                "grade": latest.get("grade"),
                "result_status": result_status,
                "reason": _NEEDS_ATTENTION_REASON_TEXT[reason_code],
                "reason_code": reason_code,
                "priority": _NEEDS_ATTENTION_PRIORITY[reason_code],
            }
        )
    items.sort(key=lambda i: (i["priority"], -(i["percentage"] or 0)))
    return items


# ---------------------------------------------------------------------------
# Feature 4 — Learning-gap detection
# ---------------------------------------------------------------------------


def _component_percentage(marks: Optional[Any], max_mark: int) -> Optional[float]:
    if marks is None or max_mark is None or max_mark <= 0:
        return None
    return float(marks) / float(max_mark) * 100.0


def _assessment_progression_gaps(row: Dict[str, Any]) -> List[Tuple[str, str, float]]:
    components = [
        ("internal", row.get("internal_marks"), settings.MARKS_INTERNAL_MAX),
        ("mid", row.get("mid_sem_marks"), settings.MARKS_MID_SEM_MAX),
        ("end", row.get("end_sem_marks"), settings.MARKS_END_SEM_MAX),
    ]
    labels = {
        "internal": "internal assessment",
        "mid": "mid-sem",
        "end": "end-sem",
    }
    gaps: List[Tuple[str, str, float]] = []
    previous: Optional[Tuple[str, float]] = None
    for name, marks, max_mark in components:
        pct = _component_percentage(marks, max_mark)
        if pct is None:
            previous = None
            continue
        if previous is not None and (previous[1] - pct) >= settings.STUDENT_ASSESSMENT_GAP_DROP:
            gaps.append((previous[0], labels[name], round(previous[1] - pct, 2)))
        previous = (labels[name], pct)
    return gaps


def compute_learning_gaps(
    performance_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    gaps = []
    for code, attempts in _group_attempts_by_subject(performance_rows).items():
        latest = attempts[-1]
        subject_name = latest["subject_name"]
        semester = latest["semester"]

        for from_label, to_label, drop in _assessment_progression_gaps(latest):
            gaps.append(
                {
                    "subject_code": code,
                    "subject_name": subject_name,
                    "semester": semester,
                    "signal": "Assessment progression gap",
                    "signal_code": "assessment_progression_gap",
                    "detail": (
                        f"Your performance drops significantly from {from_label} "
                        f"to {to_label} (by {drop:.1f} percentage points)."
                    ),
                    "percentage": latest.get("percentage"),
                }
            )

        pcts = [
            float(a["percentage"])
            for a in attempts
            if a.get("percentage") is not None
        ]
        if len(attempts) >= 2 and len(pcts) == len(attempts):
            if all(p < settings.STUDENT_NEEDS_ATTENTION_MAX for p in pcts):
                gaps.append(
                    {
                        "subject_code": code,
                        "subject_name": subject_name,
                        "semester": semester,
                        "signal": "Repeated low performance",
                        "signal_code": "repeated_low_performance",
                        "detail": (
                            "Repeated lower performance in this subject may "
                            "indicate that additional preparation could help."
                        ),
                        "percentage": latest.get("percentage"),
                    }
                )
            elif all(p < settings.STUDENT_STRENGTH_GOOD_MIN for p in pcts):
                gaps.append(
                    {
                        "subject_code": code,
                        "subject_name": subject_name,
                        "semester": semester,
                        "signal": "Repeated subject weakness",
                        "signal_code": "repeated_weakness",
                        "detail": (
                            "Repeated lower performance in this subject may "
                            "indicate that additional preparation could help."
                        ),
                        "percentage": latest.get("percentage"),
                    }
                )
    return gaps


# ---------------------------------------------------------------------------
# Feature 5 — Privacy-safe class benchmark
# ---------------------------------------------------------------------------


def compute_benchmark(
    performance_rows: List[Dict[str, Any]],
    class_averages: List[Dict[str, Any]],
    min_cohort: Optional[int] = None,
) -> List[Dict[str, Any]]:
    threshold = (
        min_cohort
        if min_cohort is not None
        else settings.STUDENT_CLASS_BENCHMARK_MIN_COHORT
    )
    avg_by_key = {
        (avg["subject_id"], int(avg["semester_no"]), avg.get("academic_year")): avg
        for avg in class_averages
    }
    items = []
    for row in _latest_attempt_per_subject(performance_rows).values():
        pct = row.get("percentage")
        if pct is None:
            continue
        key = (row.get("subject_id"), int(row.get("semester") or 0), row.get("academic_year"))
        avg = avg_by_key.get(key)
        cohort_size = int(avg["cohort_size"]) if avg else 0
        if avg is None or cohort_size < threshold:
            items.append(
                {
                    "subject_code": row["subject_code"],
                    "subject_name": row["subject_name"],
                    "semester": row["semester"],
                    "your_percentage": round(float(pct), 2),
                    "class_average": None,
                    "difference": None,
                    "cohort_size": cohort_size,
                    "available": False,
                }
            )
            continue
        class_avg = float(avg["class_average"])
        items.append(
            {
                "subject_code": row["subject_code"],
                "subject_name": row["subject_name"],
                "semester": row["semester"],
                "your_percentage": round(float(pct), 2),
                "class_average": round(class_avg, 2),
                "difference": round(float(pct) - class_avg, 2),
                "cohort_size": cohort_size,
                "available": True,
            }
        )
    items.sort(key=lambda i: (not i["available"], i["subject_code"]))
    return items


# ---------------------------------------------------------------------------
# Feature 6 — Attempt / backlog history
# ---------------------------------------------------------------------------


def compute_attempt_history(
    performance_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    history = []
    for code, attempts in _group_attempts_by_subject(performance_rows).items():
        entries = []
        for attempt in attempts:
            pct = attempt.get("percentage")
            entries.append(
                {
                    "attempt_number": int(attempt.get("attempt_number") or 1),
                    "semester": attempt["semester"],
                    "academic_year": attempt.get("academic_year"),
                    "percentage": round(float(pct), 2) if pct is not None else None,
                    "grade": attempt.get("grade"),
                    "grade_point": attempt.get("grade_point"),
                    "result_status": attempt.get("result_status"),
                }
            )
        first_pct = entries[0]["percentage"]
        last_pct = entries[-1]["percentage"]
        improvement = None
        if len(entries) > 1 and first_pct is not None and last_pct is not None:
            improvement = round(last_pct - first_pct, 2)
        history.append(
            {
                "subject_code": code,
                "subject_name": attempts[0]["subject_name"],
                "attempts": entries,
                "has_multiple_attempts": len(entries) > 1,
                "improvement": improvement,
            }
        )
    history.sort(key=lambda h: h["subject_code"])
    return history
