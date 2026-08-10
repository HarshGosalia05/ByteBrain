"""MD-05 Academic Health Score + "What should I focus on?" - pure rules.

Deterministic product rules (no ML, no GenAI, no DB access). Thresholds and
weights live in ``app.core.config`` following the Threshold Engine convention.

Health score formula
--------------------
The score is the weighted average of up to four 0-100 components:

    attendance   current-semester aggregate attendance % (mean of the
                 per-subject current-semester percentages; falls back to the
                 latest completed semester's stored attendance).
    performance  mean of the latest-attempt completed subject percentages.
    progress     latest completed semester result - semester percentage, or
                 SGPA * 10 when the percentage is not stored.
    consistency  100 - (std-dev of completed-semester SGPA * scale); needs at
                 least two completed semesters.

Weights are configurable; the sum is renormalized over the *available*
components. If fewer than ``HEALTH_AVAILABLE_COMPONENT_MIN`` components are
available the score is not shown (insufficient data). Bands:

    >= 80 Excellent | >= 65 Good | >= 50 Watch | below Needs Attention

NULL is never treated as zero and a pending (unpublished) result is never
fabricated.

Priority ranking (documented severity order, lowest number = highest priority)
--------------------------------------------------------------------------------
    1 attendance        attendance below the target (critical below first)
    2 weak performance  subject needs attention / below the performance band
    3 declining trend   latest SGPA/percentage trend is declining
    4 pending result    current-semester final result still pending
    5 backlog           unresolved backlogs from completed semesters
    6 eligibility       not eligible for the examination in a subject
    7 personal goal     an active goal target is not yet reached
Each present signal produces exactly one item; the top
``STUDENT_PRIORITY_MAX_ITEMS`` are returned.
"""

import math
import statistics
from typing import Any, Dict, List, Optional

from app.core.config import settings


def _round(value: Optional[float], ndigits: int = 1) -> Optional[float]:
    return None if value is None else round(value, ndigits)


# ---------------------------------------------------------------------------
# Health score
# ---------------------------------------------------------------------------


def _attendance_component(
    attendance_pct: Optional[float],
) -> Dict[str, Any]:
    if attendance_pct is None:
        return {
            "available": False,
            "score": None,
            "weight": settings.HEALTH_ATTENDANCE_WEIGHT,
            "reason": "Attendance data is not available yet.",
        }
    return {
        "available": True,
        "score": round(max(0.0, min(100.0, attendance_pct)), 1),
        "weight": settings.HEALTH_ATTENDANCE_WEIGHT,
        "reason": f"Current attendance is {attendance_pct:.1f}%.",
    }


def _performance_component(
    completed_percentages: List[float],
) -> Dict[str, Any]:
    if not completed_percentages:
        return {
            "available": False,
            "score": None,
            "weight": settings.HEALTH_PERFORMANCE_WEIGHT,
            "reason": "No completed subject results yet.",
        }
    avg = sum(completed_percentages) / len(completed_percentages)
    return {
        "available": True,
        "score": round(max(0.0, min(100.0, avg)), 1),
        "weight": settings.HEALTH_PERFORMANCE_WEIGHT,
        "reason": f"Completed subjects average {avg:.1f}%.",
    }


def _progress_component(
    completed_summaries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not completed_summaries:
        return {
            "available": False,
            "score": None,
            "weight": settings.HEALTH_PROGRESS_WEIGHT,
            "reason": "No completed semester progress yet.",
        }
    latest = completed_summaries[-1]
    pct = latest.get("semester_percentage")
    sgpa = latest.get("sgpa")
    score = pct if pct is not None else (sgpa * 10 if sgpa is not None else None)
    if score is None:
        return {
            "available": False,
            "score": None,
            "weight": settings.HEALTH_PROGRESS_WEIGHT,
            "reason": "No completed semester progress yet.",
        }
    source = (
        f"{pct:.1f}%"
        if pct is not None
        else f"SGPA {sgpa:.2f}"
    )
    return {
        "available": True,
        "score": round(max(0.0, min(100.0, score)), 1),
        "weight": settings.HEALTH_PROGRESS_WEIGHT,
        "reason": f"Latest completed semester ended at {source}.",
    }


def _consistency_component(
    completed_summaries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    sgpas = [
        s["sgpa"]
        for s in completed_summaries
        if s.get("sgpa") is not None
    ]
    if len(sgpas) < 2:
        return {
            "available": False,
            "score": None,
            "weight": settings.HEALTH_CONSISTENCY_WEIGHT,
            "reason": "Not enough completed semesters to measure consistency.",
        }
    sd = statistics.pstdev(sgpas)
    score = max(0.0, min(100.0, 100.0 - sd * settings.HEALTH_CONSISTENCY_SD_SCALE))
    if sd <= settings.STUDENT_TREND_STABLE_TOLERANCE:
        reason = f"SGPA is consistent across {len(sgpas)} completed semesters."
    else:
        reason = f"SGPA varies across {len(sgpas)} completed semesters (SD {sd:.2f})."
    return {
        "available": True,
        "score": round(score, 1),
        "weight": settings.HEALTH_CONSISTENCY_WEIGHT,
        "reason": reason,
    }


def _band(score: float) -> str:
    if score >= settings.HEALTH_EXCELLENT_MIN:
        return "Excellent"
    if score >= settings.HEALTH_GOOD_MIN:
        return "Good"
    if score >= settings.HEALTH_WATCH_MIN:
        return "Watch"
    return "Needs Attention"


def compute_health_score(
    attendance_pct: Optional[float],
    completed_percentages: List[float],
    completed_summaries: List[Dict[str, Any]],
    total_backlogs: Optional[int],
    has_pending_result: bool,
    current_semester: Optional[int],
) -> Dict[str, Any]:
    """Deterministic academic health score (0-100) + components + reasons."""
    components = {
        "attendance": _attendance_component(attendance_pct),
        "performance": _performance_component(completed_percentages),
        "progress": _progress_component(completed_summaries),
        "consistency": _consistency_component(completed_summaries),
    }

    available = [
        comp for comp in components.values() if comp["available"]
    ]
    if len(available) < settings.HEALTH_AVAILABLE_COMPONENT_MIN:
        return {
            "available": False,
            "score": None,
            "band": None,
            "components": components,
            "reasons": [
                "Not enough data is available yet to compute a health score."
            ],
        }

    weight_sum = sum(comp["weight"] for comp in available)
    score = (
        sum(comp["score"] * comp["weight"] for comp in available) / weight_sum
        if weight_sum > 0
        else None
    )
    if score is None:
        return {
            "available": True,
            "score": None,
            "band": None,
            "components": components,
            "reasons": [],
        }

    reasons: List[str] = []
    reasons.append(components["attendance"]["reason"])
    reasons.append(components["performance"]["reason"])
    if components["progress"]["available"]:
        reasons.append(components["progress"]["reason"])
    if components["consistency"]["available"]:
        reasons.append(components["consistency"]["reason"])

    backlogs = total_backlogs or 0
    reasons.append(
        "No backlog from completed semesters."
        if backlogs == 0
        else f"{backlogs} backlog(s) recorded from completed semesters."
    )
    if has_pending_result and current_semester is not None:
        reasons.append(
            f"Semester {current_semester} final results are still pending."
        )

    return {
        "available": True,
        "score": round(score, 1),
        "band": _band(score),
        "components": components,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Personal goals
# ---------------------------------------------------------------------------

GOAL_LABELS = {
    "target_sgpa": "SGPA",
    "target_percentage": "Overall percentage",
    "target_attendance": "Attendance",
}

GOAL_SIGNALS = {
    "target_sgpa": "sgpa",
    "target_percentage": "percentage",
    "target_attendance": "attendance",
}


def compute_goal_current_value(
    goal_type: str,
    profile: Dict[str, Any],
    latest_completed_summary: Optional[Dict[str, Any]],
    current_attendance_mean: Optional[float],
) -> Optional[float]:
    """Current progress value for a goal type (deterministic, NULL-safe)."""
    if goal_type == "target_sgpa":
        return profile.get("latest_sgpa")
    if goal_type == "target_percentage":
        pct = profile.get("overall_percentage")
        if pct is None and latest_completed_summary is not None:
            pct = latest_completed_summary.get("semester_percentage")
        return pct
    if goal_type == "target_attendance":
        overall = profile.get("overall_attendance_percentage")
        return overall if overall is not None else current_attendance_mean
    return None


# ---------------------------------------------------------------------------
# "What should I focus on?" priorities
# ---------------------------------------------------------------------------

_PRIORITY_SEVERITY = {
    "attendance": 1,
    "weak_performance": 2,
    "declining_trend": 3,
    "pending_result": 4,
    "backlog": 5,
    "eligibility_issue": 6,
    "goal_gap": 7,
}


def _required_classes_to_target(
    total_classes: Optional[int],
    attended_classes: Optional[int],
    attendance_pct: Optional[float],
    threshold: float,
) -> Optional[int]:
    if attendance_pct is None or attendance_pct >= threshold:
        return None
    if total_classes is None or attended_classes is None or total_classes <= attended_classes:
        return None
    target = threshold / 100.0
    return max(1, math.ceil((target * total_classes - attended_classes) / (1 - target)))


def compute_priorities(
    profile: Dict[str, Any],
    current_attendance_rows: List[Dict[str, Any]],
    needs_attention: List[Dict[str, Any]],
    trends: Dict[str, Any],
    active_goals: List[Dict[str, Any]],
    has_pending_result: bool,
    attendance_threshold: float = settings.FACULTY_ATTENDANCE_THRESHOLD,
    attendance_critical: float = settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD,
    performance_threshold: float = settings.FACULTY_PERFORMANCE_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Rank present risk signals by documented severity, return the top N."""
    current_semester = profile.get("current_semester")
    items: List[Dict[str, Any]] = []

    # 1. Low attendance (aggregated over current-semester subjects).
    below = [
        row
        for row in current_attendance_rows
        if row.get("attendance_percentage") is not None
        and row["attendance_percentage"] < attendance_threshold
    ]
    if below:
        worst = min(below, key=lambda r: r["attendance_percentage"])
        pct = worst["attendance_percentage"]
        critical = pct < attendance_critical
        reason = (
            f"{worst['subject_name']} attendance is {pct:.1f}% - "
            f"{'critically below' if critical else 'below'} the "
            f"{attendance_threshold:.0f}% target."
        )
        required = _required_classes_to_target(
            worst.get("total_classes"),
            worst.get("attended_classes"),
            pct,
            attendance_threshold,
        )
        action = (
            f"Attend the next {required} {worst['subject_name']} classes to reach "
            f"{attendance_threshold:.0f}%."
            if required is not None
            else f"Prioritize attending {worst['subject_name']} lectures."
        )
        items.append(
            {
                "signal": "attendance",
                "severity": _PRIORITY_SEVERITY["attendance"],
                "title": "Low attendance",
                "reason": reason,
                "action": action,
                "subject": worst.get("subject_name"),
                "metric": f"{pct:.1f}%",
            }
        )

    # 2. Weak performance (needs-attention subject, or current below threshold).
    weak = None
    for item in needs_attention:
        if item.get("reason_code") in ("failed", "critical"):
            weak = item
            break
    if weak is None and needs_attention:
        weak = needs_attention[0]
    if weak is None:
        weak_rows = [
            row
            for row in current_attendance_rows
            if row.get("performance_percentage") is not None
            and row["performance_percentage"] < performance_threshold
        ]
        if weak_rows:
            row = min(weak_rows, key=lambda r: r["performance_percentage"])
            weak = {
                "subject_name": row["subject_name"],
                "percentage": row["performance_percentage"],
                "reason": f"Performance is below {performance_threshold:.0f}%",
            }
    if weak is not None:
        pct_txt = (
            f" ({weak['percentage']:.1f}%)"
            if weak.get("percentage") is not None
            else ""
        )
        items.append(
            {
                "signal": "weak_performance",
                "severity": _PRIORITY_SEVERITY["weak_performance"],
                "title": "Weak performance",
                "reason": f"{weak['subject_name']} needs attention{pct_txt}.",
                "action": f"Focus your revision on {weak['subject_name']}.",
                "subject": weak.get("subject_name"),
                "metric": (
                    f"{weak['percentage']:.1f}%"
                    if weak.get("percentage") is not None
                    else None
                ),
            }
        )

    # 3. Declining trend.
    if trends.get("overall_direction") == "declining":
        sgpa = trends.get("movements", {}).get("sgpa") or {}
        if sgpa.get("direction") == "down":
            reason = (
                f"Your SGPA declined from {sgpa['previous_value']:.2f} "
                f"to {sgpa['current_value']:.2f}."
            )
        else:
            reason = "Your latest academic trend is declining."
        items.append(
            {
                "signal": "declining_trend",
                "severity": _PRIORITY_SEVERITY["declining_trend"],
                "title": "Declining trend",
                "reason": reason,
                "action": "Review what changed last semester and set concrete next steps.",
            }
        )

    # 4. Pending result.
    if has_pending_result and current_semester is not None:
        items.append(
            {
                "signal": "pending_result",
                "severity": _PRIORITY_SEVERITY["pending_result"],
                "title": "Final result pending",
                "reason": f"Your final results for semester {current_semester} are still pending.",
                "action": "Keep preparing - final results are awaited.",
            }
        )

    # 5. Backlog.
    backlogs = profile.get("total_backlogs") or 0
    if backlogs > 0:
        items.append(
            {
                "signal": "backlog",
                "severity": _PRIORITY_SEVERITY["backlog"],
                "title": "Backlog to clear",
                "reason": f"{backlogs} backlog(s) from completed semesters must be cleared.",
                "action": "Prioritize clearing backlog subjects in the next attempt cycle.",
                "metric": str(backlogs),
            }
        )

    # 6. Eligibility issue.
    not_eligible = [
        row for row in current_attendance_rows
        if row.get("eligibility_status") == "Not Eligible"
    ]
    if not_eligible:
        first = not_eligible[0]
        items.append(
            {
                "signal": "eligibility_issue",
                "severity": _PRIORITY_SEVERITY["eligibility_issue"],
                "title": "Exam eligibility at risk",
                "reason": (
                    f"You are not eligible to appear for the exam in "
                    f"{first['subject_name']} at your current attendance."
                ),
                "action": "Recover attendance to regain exam eligibility.",
                "subject": first.get("subject_name"),
            }
        )

    # 7. Personal goal gap.
    for goal in active_goals:
        current = goal.get("current_value")
        target = goal.get("target_value")
        if current is None or target is None or current >= target:
            continue
        label = GOAL_LABELS.get(goal["goal_type"], goal["goal_type"])
        items.append(
            {
                "signal": "goal_gap",
                "severity": _PRIORITY_SEVERITY["goal_gap"],
                "title": f"{label} goal in progress",
                "reason": (
                    f"Your {label} goal of {target:.2f} is not yet reached "
                    f"(current {current:.2f})."
                ),
                "action": f"Focus effort on reaching your {label} goal.",
                "metric": f"{current:.2f}",
            }
        )

    items.sort(key=lambda item: item["severity"])
    top = items[: settings.STUDENT_PRIORITY_MAX_ITEMS]
    for rank, item in enumerate(top, start=1):
        item["rank"] = rank
    return top
