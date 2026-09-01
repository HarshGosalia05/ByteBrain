"""M3 v2 — Automated Feature Leakage Gate (fail-closed).

Phase F gate: verifies, after the feature matrix is built, that NO T+1 / future
/ placement outcome column is present in `X`.

The gate is fail-CLOSED: any violation raises and aborts training.

Scope is deliberately M3-SPECIFIC. Unlike M1, current-semester (T) outcome
columns are LEGITIMATE features here (T is complete, target is T+1 risk). What
is forbidden is anything encoding the T+1 outcome or post-graduation outcome.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from .. import config

# Column-name families that would leak the T+1 (next) outcome if present.
_NEXT_PREFIXES = ("next_semester_", "next_sem_", "next_")
_T_PLUS_1_SUFFIXES = ("_t1", "_lag1", "_next")
# Raw T+1 outcome-ish columns (any timestamp) that must never be features.
_OUTCOME_NAMES = (
    "is_at_risk_next_sem", "next_semester_sgpa", "next_semester_percentage",
    "next_semester_marks", "next_semester_grade", "next_semester_result",
    "next_semester_attendance_percentage", "next_semester_backlog_count",
    "next_semester_total_marks", "next_backlog_count", "next_result",
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

    Also asserts that none of `required_targets` (the M3 target) is in X.
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
        f"M3 v2 LEAKAGE GATE FAIL (fail-closed):\n"
        f"  forbidden columns in X: {found}\n"
        f"  target columns in X: {target_leaks}"
    )