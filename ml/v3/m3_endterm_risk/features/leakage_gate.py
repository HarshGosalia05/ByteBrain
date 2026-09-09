"""M3 v3 — Automated Feature Leakage Gate (fail-closed).

Verifies that NO end-semester / T+1 / placement column is present in X.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from .. import config

_NEXT_PREFIXES = ("next_semester_", "next_sem_", "next_")
_T_PLUS_1_SUFFIXES = ("_t1", "_lag1", "_next")
_OUTCOME_NAMES = (
    "is_at_risk_end_sem", "is_at_risk_next_sem",
    "semester_sgpa", "semester_percentage", "semester_total_marks",
    "semester_result", "end_semester_grade",
    "subj_end_sem_marks_mean", "subj_end_sem_marks_std",
    "subj_failed_subjects_count",
    "next_semester_sgpa", "next_semester_percentage",
    "next_semester_marks", "next_semester_grade", "next_semester_result",
    "next_semester_attendance_percentage", "next_semester_backlog_count",
    "next_backlog_count", "next_result",
    "placement_status", "package_lpa", "package_tier", "placement_domain",
)


def _is_forbidden(col: str) -> bool:
    if col in config.FORBIDDEN_FEATURES:
        return True
    if col in _OUTCOME_NAMES:
        return True
    if any(col.startswith(p) for p in _NEXT_PREFIXES):
        return True
    if any(col.endswith(s) for s in _T_PLUS_1_SUFFIXES):
        return True
    return False


def run_leakage_gate(X: pd.DataFrame,
                     required_targets: Iterable[str] = ()) -> dict:
    """Scan X; raise if any forbidden/leakage column is present."""
    columns = list(X.columns)
    found = [c for c in columns if _is_forbidden(c)]
    target_leaks = [t for t in required_targets if t in columns]

    result = {
        "pass": len(found) == 0 and len(target_leaks) == 0,
        "columns_checked": len(columns),
        "forbidden_found": found,
        "targets_forbidden_in_features": target_leaks,
    }
    if result["pass"]:
        return result
    raise ValueError(
        f"M3 v3 LEAKAGE GATE FAIL (fail-closed):\n"
        f"  forbidden columns in X: {found}\n"
        f"  target columns in X: {target_leaks}"
    )
