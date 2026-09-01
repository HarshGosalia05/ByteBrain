"""M2 v2 — Automated Feature Leakage Gate (fail-closed).

Phase E gate: verifies, after the feature matrix is built, that NO T+1 outcome
(and no other forbidden/derived) column is present in `X`.

The gate is fail-CLOSED: any violation raises and aborts training.

Scope is deliberately M2-SPECIFIC. Unlike M1, the current-semester (T) outcome
columns (semester_sgpa, semester_percentage, ...) are LEGITIMATE features here
because T is a completed semester and the target is T+1. What is forbidden is
anything encoding the T+1 outcome.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from .. import config

# Column-name families that would leak the T+1 (next) outcome if present.
_NEXT_PREFIXES = (
    "next_semester_", "next_sem_", "next_semester_sgpa", "next_semester_percentage",
)
_T_PLUS_1_SUFFIXES = ("_t1", "_lag1", "_next")

# Raw outcome-ish column families at ANY timestamp that must never be features
# (they encode the outcome we are predicting, regardless of lagging).
_OUTCOME_NAMES = (
    "next_semester_sgpa", "next_semester_percentage", "next_semester_marks",
    "next_semester_grade", "next_semester_result", "next_semester_attendance_percentage",
    "next_semester_backlog_count", "next_semester_total_marks",
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
    """Scan X; raise if any forbidden/leakage column is present.

    Returns a dict with 'pass', 'columns_checked', 'forbidden_found',
    'targets_forbidden_in_features'.

    Also asserts that none of `required_targets` (the M2 targets) is in X.
    """
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
        f"M2 v2 LEAKAGE GATE FAIL (fail-closed):\n"
        f"  forbidden columns in X: {found}\n"
        f"  target columns in X: {target_leaks}"
    )