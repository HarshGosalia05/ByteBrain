"""ML-13 Slice 1: Feedback Dataset Extraction & Validation.

Provides pure, deterministic, READ-ONLY dataset extraction and safety validation
for incorporating ML-12 faculty feedback into M3 retraining.

Reuses the exact M3 feature contract from ``ml.src.features.M3_CONTRACT`` and
feedback label semantics from ``ml.src.feedback_labels``.

Does NOT run model training, alter model artifacts, or modify database state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from ml.src.features import M3_CONTRACT
from ml.src.feedback_labels import ACTION_LABELS, latest_verdicts


MIN_RETRAINING_SAMPLES = 30


@dataclass
class FeedbackDatasetResult:
    """Structured result of feedback dataset extraction and validation."""

    status: str  # "sufficient_data" or "insufficient_feedback_data"
    can_retrain: bool
    reason: str
    counts_summary: Dict[str, Any]
    features_df: Optional[pd.DataFrame] = None
    labels_series: Optional[pd.Series] = None
    excluded_records: List[Dict[str, Any]] = field(default_factory=list)


def extract_and_validate_feedback_dataset(
    feedback_rows: List[Dict[str, Any]],
    predictions_map: Dict[str, Dict[str, Any]],
    student_features_map: Dict[str, Dict[str, Any]],
    *,
    min_samples: int = MIN_RETRAINING_SAMPLES,
) -> FeedbackDatasetResult:
    """Extract, validate, and shape feedback-informed dataset for M3.

    Parameters
    ----------
    feedback_rows:
        List of raw feedback dicts from ``prediction_feedback``.
    predictions_map:
        Dict mapping ``prediction_id`` -> prediction row dict (from ``ml_predictions``).
    student_features_map:
        Dict mapping ``student_id`` -> M3 raw feature dict.
    min_samples:
        Minimum eligible sample count required for safe retraining (default 30).

    Returns
    -------
    FeedbackDatasetResult
        Status, safety flags, detailed counts, and optional features/labels.
    """
    total_feedback = len(feedback_rows)
    confirmed_count = sum(1 for r in feedback_rows if r.get("feedback_action") == "confirmed")
    dismissed_count = sum(1 for r in feedback_rows if r.get("feedback_action") == "dismissed")

    # 1. Detect duplicate / conflicting feedback cases
    pred_feedback_actions: Dict[str, List[str]] = {}
    for r in feedback_rows:
        pid = r.get("prediction_id")
        action = r.get("feedback_action")
        if pid and action in ACTION_LABELS:
            pred_feedback_actions.setdefault(str(pid), []).append(action)

    duplicate_cases = sum(1 for actions in pred_feedback_actions.values() if len(actions) > 1)
    conflicting_cases = sum(
        1 for actions in pred_feedback_actions.values() if len(set(actions)) > 1
    )

    # 2. Apply ML-12 latest_verdicts resolution ("latest verdict wins")
    resolved_verdicts = latest_verdicts(feedback_rows)

    excluded_records: List[Dict[str, Any]] = []
    eligible_samples: List[Dict[str, Any]] = []

    expected_features = M3_CONTRACT.raw_features

    # 3. Validate eligibility of each resolved verdict
    for verdict in resolved_verdicts:
        pid = str(verdict.get("prediction_id", ""))
        sid = verdict.get("student_id")
        action = verdict.get("feedback_action")
        label = ACTION_LABELS.get(action)

        if label is None:
            excluded_records.append(
                {
                    "feedback_id": verdict.get("feedback_id"),
                    "prediction_id": pid,
                    "reason": f"unrecognized_action: {action}",
                }
            )
            continue

        pred = predictions_map.get(pid)
        if not pred:
            excluded_records.append(
                {
                    "feedback_id": verdict.get("feedback_id"),
                    "prediction_id": pid,
                    "reason": "missing_prediction_record",
                }
            )
            continue

        if pred.get("prediction_type") != "m3":
            excluded_records.append(
                {
                    "feedback_id": verdict.get("feedback_id"),
                    "prediction_id": pid,
                    "reason": f"non_m3_prediction_type: {pred.get('prediction_type')}",
                }
            )
            continue

        raw_feat = student_features_map.get(sid) if sid else None
        if not raw_feat:
            excluded_records.append(
                {
                    "feedback_id": verdict.get("feedback_id"),
                    "prediction_id": pid,
                    "student_id": sid,
                    "reason": "missing_student_features",
                }
            )
            continue

        # Check required columns presence without coercing NULLs
        feat_dict = {}
        missing_cols = []
        for col in expected_features:
            val = raw_feat.get(col)
            feat_dict[col] = val
            if val is None or (isinstance(val, float) and pd.isna(val)):
                missing_cols.append(col)

        sample_row = {
            "prediction_id": pid,
            "student_id": sid,
            "feedback_action": action,
            "is_at_risk_next_sem": label,
            "missing_cols_count": len(missing_cols),
            "feedback_timestamp": verdict.get("feedback_timestamp", ""),
            **feat_dict,
        }
        eligible_samples.append(sample_row)

    # 4. Sort deterministically: student_id, prediction_id, feedback_timestamp
    eligible_samples.sort(
        key=lambda s: (
            str(s.get("student_id", "")),
            str(s.get("prediction_id", "")),
            str(s.get("feedback_timestamp", "")),
        )
    )

    eligible_count = len(eligible_samples)
    positive_labels = sum(1 for s in eligible_samples if s["is_at_risk_next_sem"] == 1)
    negative_labels = sum(1 for s in eligible_samples if s["is_at_risk_next_sem"] == 0)
    unique_students = len(set(s["student_id"] for s in eligible_samples))

    # Feature completeness calculation
    total_cells = eligible_count * len(expected_features) if eligible_count > 0 else 0
    missing_cells = (
        sum(s["missing_cols_count"] for s in eligible_samples) if eligible_count > 0 else 0
    )
    feature_completeness_pct = (
        ((total_cells - missing_cells) / total_cells * 100.0) if total_cells > 0 else 0.0
    )

    counts_summary = {
        "total_feedback_records": total_feedback,
        "confirmed_records": confirmed_count,
        "dismissed_records": dismissed_count,
        "duplicate_feedback_cases": duplicate_cases,
        "conflicting_feedback_cases": conflicting_cases,
        "eligible_labeled_samples": eligible_count,
        "excluded_samples": len(excluded_records),
        "unique_students": unique_students,
        "positive_labels": positive_labels,
        "negative_labels": negative_labels,
        "class_balance_positive_pct": (
            round(positive_labels / eligible_count * 100.0, 2) if eligible_count > 0 else 0.0
        ),
        "class_balance_negative_pct": (
            round(negative_labels / eligible_count * 100.0, 2) if eligible_count > 0 else 0.0
        ),
        "feature_completeness_pct": round(feature_completeness_pct, 2),
        "min_required_samples": min_samples,
    }

    # 5. Evaluate Small Dataset Safety Threshold
    if eligible_count < min_samples:
        return FeedbackDatasetResult(
            status="insufficient_feedback_data",
            can_retrain=False,
            reason=(
                f"Eligible labeled samples ({eligible_count}) is below minimum threshold "
                f"({min_samples}) required for statistically meaningful retraining."
            ),
            counts_summary=counts_summary,
            excluded_records=excluded_records,
        )

    if positive_labels == 0 or negative_labels == 0:
        return FeedbackDatasetResult(
            status="insufficient_feedback_data",
            can_retrain=False,
            reason=(
                f"Dataset lacks class balance diversity (positive={positive_labels}, "
                f"negative={negative_labels}). Retraining requires both classes."
            ),
            counts_summary=counts_summary,
            excluded_records=excluded_records,
        )

    # 6. Build DataFrames for usable dataset
    df = pd.DataFrame(eligible_samples)
    X_df = df[expected_features].copy()
    y_series = df["is_at_risk_next_sem"].copy()

    return FeedbackDatasetResult(
        status="sufficient_data",
        can_retrain=True,
        reason="Dataset extraction successful and meets retraining safety criteria.",
        counts_summary=counts_summary,
        features_df=X_df,
        labels_series=y_series,
        excluded_records=excluded_records,
    )


async def extract_feedback_dataset_from_db(
    pool: Any,
    *,
    min_samples: int = MIN_RETRAINING_SAMPLES,
) -> FeedbackDatasetResult:
    """Async READ-ONLY helper to extract and validate dataset from PostgreSQL.

    Executes strictly SELECT queries on ``prediction_feedback``, ``ml_predictions``,
    ``students``, and ``student_semester_summary``.
    """
    async with pool.acquire() as conn:
        fb_rows = await conn.fetch(
            """
            SELECT feedback_id, prediction_id, student_id, faculty_id,
                   feedback_action, note, model_version, created_at AS feedback_timestamp
            FROM prediction_feedback
            ORDER BY created_at DESC
            """
        )
        feedback_list = [dict(r) for r in fb_rows]

        pred_ids = [str(r["prediction_id"]) for r in feedback_list if r.get("prediction_id")]
        predictions_map: Dict[str, Dict[str, Any]] = {}
        if pred_ids:
            p_rows = await conn.fetch(
                """
                SELECT prediction_id, student_id, prediction_type, generated_at
                FROM ml_predictions
                WHERE prediction_id = ANY($1::uuid[])
                """,
                pred_ids,
            )
            predictions_map = {str(r["prediction_id"]): dict(r) for r in p_rows}

        student_ids = list(set(r["student_id"] for r in feedback_list if r.get("student_id")))
        student_features_map: Dict[str, Dict[str, Any]] = {}
        if student_ids:
            # Query latest student_semester_summary joined with students
            feat_rows = await conn.fetch(
                """
                SELECT DISTINCT ON (st.student_id)
                    st.student_id,
                    ss.semester_no,
                    ss.subjects_registered,
                    ss.credits_registered,
                    ss.credits_earned,
                    ss.semester_total_marks,
                    ss.semester_percentage,
                    ss.semester_sgpa,
                    ss.semester_attendance_percentage,
                    ss.backlog_count,
                    st.department_code AS department_name,
                    st.gender
                FROM students st
                LEFT JOIN student_semester_summary ss ON ss.student_id = st.student_id
                WHERE st.student_id = ANY($1::varchar[])
                ORDER BY st.student_id, ss.semester_no DESC
                """,
                student_ids,
            )
            student_features_map = {r["student_id"]: dict(r) for r in feat_rows}

    return extract_and_validate_feedback_dataset(
        feedback_list,
        predictions_map,
        student_features_map,
        min_samples=min_samples,
    )
