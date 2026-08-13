"""ML-12 §12.4: render faculty feedback into a labeled dataset.

Pure, dependency-free, READ-ONLY helpers that turn append-only
``prediction_feedback`` rows into the labeled dataset shape consumed by
the next M3 training cycle. Nothing here writes, trains, or otherwise
side-effects: it only transforms rows already captured by the backend.

Label contract
--------------
Each reviewed prediction contributes exactly one training row whose
``is_at_risk_label`` mirrors the M3 target (``is_at_risk_next_sem``):

    feedback_action == 'confirmed' -> is_at_risk_label == 1
    feedback_action == 'dismissed' -> is_at_risk_label == 0

NULL semantics: ``note`` and ``model_version`` pass through unchanged
(missing notes stay ``None``; they are never coerced to empty strings or
fake zeros).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

ACTION_LABELS = {"confirmed": 1, "dismissed": 0}


def _sort_key(row: Dict[str, Any]) -> tuple:
    """Order feedback rows newest-first, deterministically.

    Rows are dicts carrying ``feedback_timestamp`` (typically an ISO
    string or a datetime). Missing/equal timestamps fall back to input
    position so the result never depends on unstable ordering.
    """
    ts = row.get("feedback_timestamp")
    if ts is None:
        return (0, 0)
    return (1, ts)


def latest_verdicts(feedback_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return the newest feedback row per judged prediction ("latest wins").

    Preserves the repository's newest-first convention. Rows without a
    ``prediction_id`` are ignored. Deterministic for equal timestamps.
    """
    verdicts: Dict[Any, Dict[str, Any]] = {}
    positions: Dict[Any, int] = {}
    for index, row in enumerate(feedback_rows):
        prediction_id = row.get("prediction_id")
        if prediction_id is None:
            continue
        if prediction_id not in verdicts:
            verdicts[prediction_id] = row
            positions[prediction_id] = index
            continue
        existing = verdicts[prediction_id]
        if _sort_key(row) > _sort_key(existing) or (
            _sort_key(row) == _sort_key(existing)
            and positions[prediction_id] < index
        ):
            verdicts[prediction_id] = row
            positions[prediction_id] = index
    ordered = sorted(
        verdicts.values(),
        key=lambda r: _sort_key(r),
        reverse=True,
    )
    return ordered


def render_feedback_labels(
    feedback_rows: List[Dict[str, Any]],
    *,
    latest_per_prediction: bool = True,
) -> List[Dict[str, Any]]:
    """Render feedback rows into the §12.4 labeled-dataset shape.

    ``latest_per_prediction=True`` (default) emits exactly one training
    row per judged prediction using its latest verdict; ``False`` emits
    every recorded review (full audit history). Unrecognized actions are
    skipped rather than mislabeled.
    """
    rows = latest_verdicts(feedback_rows) if latest_per_prediction else feedback_rows

    labeled: List[Dict[str, Any]] = []
    for row in rows:
        action = row.get("feedback_action")
        is_at_risk = ACTION_LABELS.get(action)
        if is_at_risk is None:
            continue
        labeled.append(
            {
                "prediction_id": row.get("prediction_id"),
                "student_id": row.get("student_id"),
                "reviewer_faculty_id": row.get("faculty_id"),
                "model_version": row.get("model_version"),
                "label": action,
                "is_at_risk_label": is_at_risk,
                "note": row.get("note"),
                "feedback_timestamp": row.get("feedback_timestamp"),
            }
        )
    return labeled


def labeled_dataset_summary(labeled_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summary counts for the labeled dataset (deterministic).

    Returns total rows plus per-label counts. ``NULL model_version``
    rows are counted separately so version-less feedback is never
    silently assigned a fake version.
    """
    total = len(labeled_rows)
    confirmed = sum(1 for r in labeled_rows if r.get("label") == "confirmed")
    dismissed = sum(1 for r in labeled_rows if r.get("label") == "dismissed")
    without_version = sum(1 for r in labeled_rows if r.get("model_version") is None)
    return {
        "total": total,
        "confirmed": confirmed,
        "dismissed": dismissed,
        "without_model_version": without_version,
    }
