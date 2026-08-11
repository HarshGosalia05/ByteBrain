"""MD-06 Career Intelligence — pure deterministic rules.

No ML, no GenAI, no DB access. Thresholds and weights live in
``app.core.config`` following the Threshold Engine convention.

Career Readiness score
----------------------
The score is the weighted average of up to six 0-100 components:

    academic     mean of the latest-attempt completed subject percentages.
    consistency  100 - (std-dev of completed-semester SGPA * scale); needs at
                 least two completed semesters.
    alignment    mean % of completed subjects that are domain-relevant for the
                 student's preferred domain (see DOMAIN_SUBJECT_KEYWORDS).
    attendance   current-semester aggregate attendance % (falls back to the
                 latest completed semester's stored attendance, then to the
                 stored overall attendance).
    internship   career_preferences.internship_completed mapped to 100 ('Yes')
                 or 0 ('No').
    readiness    career_preferences.placement_readiness_level mapped to a
                 score (Low 25 / Medium 50 / High 75 / Excellent 100).

Weights are configurable; the sum is renormalized over the *available*
components. If fewer than ``CAREER_READINESS_AVAILABLE_COMPONENT_MIN``
components are available the score is not shown (insufficient data). Bands:

    >= 80 Strong | >= 60 Good | >= 40 Developing | below Needs Attention

Domain alignment
----------------
A completed subject counts as domain-relevant when its name matches one of the
configured keywords for the student's preferred domain. Alignment = the share
of completed subjects that are domain-relevant (0-100). NULL is never treated
as zero and a pending (unpublished) result is never fabricated.
"""

import statistics
from typing import Any, Dict, List, Optional

from app.core.config import settings

# Deterministic, configuration-based mapping of career domains to the subject
# keywords that make a subject domain-relevant. Matches are case-insensitive
# substrings against the canonical subject name.
DOMAIN_SUBJECT_KEYWORDS: Dict[str, List[str]] = {
    "Data Science": [
        "data", "statistics", "analytics", "machine learning",
        "artificial intelligence", "python", "probability", "database",
    ],
    "Cyber Security": [
        "security", "cryptography", "computer networks", "network", "operating systems",
    ],
    "Backend Development": [
        "java", "python", "database", "operating systems", "object oriented",
        "programming", "scripting", "compiler", "software", "linux",
    ],
    "Mobile Development": [
        "mobile", "android", "java", "programming", "object oriented",
    ],
    "UI / UX": [
        "human computer interaction", "design", "computer programming",
        "computer applications", "software engineering",
    ],
    "Full Stack Development": [
        "java", "python", "database", "web", "software", "scripting",
        "programming", "operating systems", "object oriented",
    ],
    "AI / ML": [
        "artificial intelligence", "machine learning", "deep learning",
        "natural language", "python", "statistics", "probability",
        "data", "recommender", "image", "computer vision",
    ],
    "Cloud Computing": [
        "cloud", "operating systems", "computer networks", "virtualization",
    ],
    "DevOps": [
        "linux", "scripting", "operating systems", "computer networks", "cloud",
    ],
    "Software Development": [
        "java", "python", "software", "programming", "database",
        "operating systems", "object oriented", "scripting", "compiler",
    ],
    "Business Analytics": [
        "analytics", "statistics", "business statistics", "computer applications",
        "management information systems", "business mathematics", "research methodology",
    ],
    "Operations": [
        "operations", "supply chain", "production", "project management",
    ],
    "Marketing": [
        "marketing", "consumer behavior", "digital marketing", "retail",
        "services marketing", "business communication",
    ],
    "Digital Marketing": [
        "digital marketing", "marketing", "e-commerce", "consumer behavior",
    ],
    "Banking": [
        "banking", "financial", "income tax", "investment", "business economics",
        "financial accounting", "cost accounting", "business law",
    ],
    "Finance": [
        "financial", "income tax", "investment", "banking", "business economics",
        "financial accounting", "cost accounting",
    ],
    "Human Resources": [
        "human resource", "organizational behavior", "personality development",
        "business communication", "leadership",
    ],
    "Sales": [
        "marketing", "retail", "consumer behavior", "business communication",
    ],
    "Entrepreneurship": [
        "entrepreneurship", "innovation", "strategic management", "project management",
    ],
}

PLACEMENT_READINESS_SCORES: Dict[str, float] = {
    "Low": 25.0,
    "Medium": 50.0,
    "High": 75.0,
    "Excellent": 100.0,
}


def _round(value: Optional[float], ndigits: int = 1) -> Optional[float]:
    return None if value is None else round(value, ndigits)


def _float_or_none(value: Any) -> Optional[float]:
    """Normalize DB numeric types (asyncpg returns NUMERIC as Decimal) to float."""
    return None if value is None else float(value)


def subject_is_relevant(preferred_domain: Optional[str], subject_name: str) -> bool:
    """Whether a subject counts as domain-relevant for the preferred domain.

    Deterministic substring matching (case-insensitive) against the
    ``DOMAIN_SUBJECT_KEYWORDS`` map. Unknown domains match nothing so the
    alignment stays explainable instead of guessing.
    """
    if not preferred_domain:
        return False
    keywords = DOMAIN_SUBJECT_KEYWORDS.get(preferred_domain, [])
    haystack = (subject_name or "").lower()
    return any(keyword in haystack for keyword in keywords)


# ---------------------------------------------------------------------------
# Domain alignment
# ---------------------------------------------------------------------------


def _alignment_band(score: float) -> str:
    if score >= settings.CAREER_ALIGNMENT_STRONG_MIN:
        return "Strong"
    if score >= settings.CAREER_ALIGNMENT_GOOD_MIN:
        return "Good"
    if score >= settings.CAREER_ALIGNMENT_DEVELOPING_MIN:
        return "Developing"
    return "Needs Attention"


def compute_domain_alignment(
    preferred_domain: Optional[str],
    completed_subjects: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Domain alignment: share of completed subjects relevant to the domain.

    ``completed_subjects`` must be the latest-attempt completed rows (each
    carrying at least ``subject_name`` and ``percentage``). Rows with a missing
    ``percentage`` are ignored (a pending result is never treated as zero).
    """
    aligned: List[Dict[str, Any]] = []
    other: List[Dict[str, Any]] = []
    for row in completed_subjects:
        if row.get("percentage") is None:
            continue
        relevant = subject_is_relevant(preferred_domain, row.get("subject_name", ""))
        if relevant:
            aligned.append(
                {
                    **row,
                    "relevant": True,
                    "reason": f"Relevant to {preferred_domain}",
                }
            )
        else:
            other.append(
                {
                    **row,
                    "relevant": False,
                    "reason": f"Not directly related to {preferred_domain}",
                }
            )

    total = len(aligned) + len(other)
    if total == 0 or not preferred_domain:
        return {
            "available": False,
            "score": None,
            "band": None,
            "aligned_subjects": aligned,
            "other_subjects": other,
            "aligned_count": len(aligned),
            "total_completed": total,
            "reasons": [
                (
                    "No preferred career domain recorded yet."
                    if not preferred_domain
                    else "No completed subjects available to measure alignment."
                )
            ],
        }

    score = round(len(aligned) / total * 100, 1)
    return {
        "available": True,
        "score": score,
        "band": _alignment_band(score),
        "aligned_subjects": aligned,
        "other_subjects": other,
        "aligned_count": len(aligned),
        "total_completed": total,
        "reasons": [
            f"{len(aligned)} of {total} completed subjects are relevant to {preferred_domain}."
        ],
    }


# ---------------------------------------------------------------------------
# Career Readiness score
# ---------------------------------------------------------------------------


def _academic_component(completed_percentages: List[float]) -> Dict[str, Any]:
    if not completed_percentages:
        return {
            "available": False,
            "score": None,
            "weight": settings.CAREER_ACADEMIC_WEIGHT,
            "reason": "No completed subject results yet.",
        }
    avg = sum(completed_percentages) / len(completed_percentages)
    return {
        "available": True,
        "score": round(max(0.0, min(100.0, avg)), 1),
        "weight": settings.CAREER_ACADEMIC_WEIGHT,
        "reason": f"Completed subjects average {avg:.1f}%.",
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
            "weight": settings.CAREER_CONSISTENCY_WEIGHT,
            "reason": "Not enough completed semesters to measure consistency.",
        }
    sd = statistics.pstdev(sgpas)
    score = max(
        0.0,
        min(100.0, 100.0 - sd * settings.CAREER_CONSISTENCY_SD_SCALE),
    )
    return {
        "available": True,
        "score": round(score, 1),
        "weight": settings.CAREER_CONSISTENCY_WEIGHT,
        "reason": (
            f"SGPA varied by {sd:.2f} across {len(sgpas)} completed semesters."
        ),
    }


def _alignment_component(alignment_score: Optional[float]) -> Dict[str, Any]:
    if alignment_score is None:
        return {
            "available": False,
            "score": None,
            "weight": settings.CAREER_ALIGNMENT_WEIGHT,
            "reason": "Domain alignment could not be measured yet.",
        }
    return {
        "available": True,
        "score": round(max(0.0, min(100.0, alignment_score)), 1),
        "weight": settings.CAREER_ALIGNMENT_WEIGHT,
        "reason": f"Domain alignment is {alignment_score:.1f}%.",
    }


def _attendance_component(attendance_pct: Optional[float]) -> Dict[str, Any]:
    if attendance_pct is None:
        return {
            "available": False,
            "score": None,
            "weight": settings.CAREER_ATTENDANCE_WEIGHT,
            "reason": "Attendance data is not available yet.",
        }
    return {
        "available": True,
        "score": round(max(0.0, min(100.0, attendance_pct)), 1),
        "weight": settings.CAREER_ATTENDANCE_WEIGHT,
        "reason": f"Attendance is {attendance_pct:.1f}%.",
    }


def _internship_component(internship_completed: Optional[str]) -> Dict[str, Any]:
    if internship_completed is None:
        return {
            "available": False,
            "score": None,
            "weight": settings.CAREER_INTERNSHIP_WEIGHT,
            "reason": "No internship status recorded in the career survey.",
        }
    score = 100.0 if internship_completed == "Yes" else 0.0
    return {
        "available": True,
        "score": score,
        "weight": settings.CAREER_INTERNSHIP_WEIGHT,
        "reason": (
            "Internship completed."
            if score > 0
            else "No internship completed yet — a key placement input."
        ),
    }


def _readiness_component(placement_readiness_level: Optional[str]) -> Dict[str, Any]:
    if placement_readiness_level is None:
        return {
            "available": False,
            "score": None,
            "weight": settings.CAREER_READINESS_WEIGHT,
            "reason": "No self-assessed placement readiness recorded yet.",
        }
    score = PLACEMENT_READINESS_SCORES.get(placement_readiness_level)
    if score is None:
        return {
            "available": False,
            "score": None,
            "weight": settings.CAREER_READINESS_WEIGHT,
            "reason": f"Placement readiness level '{placement_readiness_level}' is not mapped.",
        }
    return {
        "available": True,
        "score": score,
        "weight": settings.CAREER_READINESS_WEIGHT,
        "reason": f"Self-assessed placement readiness: {placement_readiness_level}.",
    }


def _career_band(score: float) -> str:
    if score >= settings.CAREER_READINESS_STRONG_MIN:
        return "Strong"
    if score >= settings.CAREER_READINESS_GOOD_MIN:
        return "Good"
    if score >= settings.CAREER_READINESS_DEVELOPING_MIN:
        return "Developing"
    return "Needs Attention"


def compute_career_readiness(
    completed_percentages: List[float],
    completed_summaries: List[Dict[str, Any]],
    alignment_score: Optional[float],
    attendance_pct: Optional[float],
    internship_completed: Optional[str],
    placement_readiness_level: Optional[str],
) -> Dict[str, Any]:
    """Deterministic career readiness score (0-100) + components + reasons."""
    completed_percentages = [
        float(value) for value in completed_percentages if value is not None
    ]
    completed_summaries = [
        {
            **summary,
            "sgpa": _float_or_none(summary.get("sgpa")),
            "semester_percentage": _float_or_none(summary.get("semester_percentage")),
        }
        for summary in completed_summaries
    ]
    components = {
        "academic": _academic_component(completed_percentages),
        "consistency": _consistency_component(completed_summaries),
        "alignment": _alignment_component(alignment_score),
        "attendance": _attendance_component(_float_or_none(attendance_pct)),
        "internship": _internship_component(internship_completed),
        "readiness": _readiness_component(placement_readiness_level),
    }

    available = [comp for comp in components.values() if comp["available"]]
    if len(available) < settings.CAREER_READINESS_AVAILABLE_COMPONENT_MIN:
        return {
            "available": False,
            "score": None,
            "band": None,
            "components": components,
            "reasons": [
                "Not enough data is available yet to compute a career readiness score."
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
    for key in (
        "academic",
        "consistency",
        "alignment",
        "attendance",
        "internship",
        "readiness",
    ):
        comp = components[key]
        if comp["available"]:
            reasons.append(comp["reason"])

    return {
        "available": True,
        "score": round(score, 1),
        "band": _career_band(score),
        "components": components,
        "reasons": reasons,
    }
