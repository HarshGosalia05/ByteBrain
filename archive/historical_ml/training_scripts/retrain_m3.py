"""ML-13 Slice 2: Feedback-Informed M3 Retraining & Evaluation.

Provides offline, pure, deterministic dataset extraction, cross-validation,
evaluation, model retraining, and artifact persistence for incorporating
ML-12 faculty feedback into M3 Next-Semester Risk Forecasting.

Reuses the exact M3 feature contract from ``ml.src.features.M3_CONTRACT`` and
feedback label semantics from ``ml.src.feedback_labels``.

Does NOT modify database schema, migrations, RLS, or mutate prediction rows.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.src.features import M3_CONTRACT, _one_hot_encode
from ml.src.feedback_labels import ACTION_LABELS, latest_verdicts

logger = logging.getLogger(__name__)

MIN_RETRAINING_SAMPLES = 30
RANDOM_STATE = 42

EXPECTED_M3_COLS = [
    "semester_no",
    "subjects_registered",
    "credits_registered",
    "credits_earned",
    "semester_total_marks",
    "semester_percentage",
    "semester_sgpa",
    "semester_attendance_percentage",
    "backlog_count",
    "department_name_BBA",
    "department_name_CSE",
    "is_male",
]


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


@dataclass
class ModelMetrics:
    """Evaluation metrics for M3 classification."""

    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float


@dataclass
class RetrainingResult:
    """Complete summary result of M3 retraining cycle."""

    status: str
    counts_summary: Dict[str, Any]
    baseline_metrics: Dict[str, float]
    retrained_metrics: Dict[str, float]
    metric_deltas: Dict[str, float]
    artifact_paths: List[str]
    db_invariants_before: Dict[str, int]
    db_invariants_after: Dict[str, int]
    reload_verified: bool
    predict_verified: bool
    serving_verified: bool


def encode_m3_features(df: pd.DataFrame) -> pd.DataFrame:
    """Encode categorical and binary features according to M3_CONTRACT."""
    X_enc = _one_hot_encode(df, M3_CONTRACT)
    X_aligned = pd.DataFrame(0, index=X_enc.index, columns=EXPECTED_M3_COLS)
    for col in EXPECTED_M3_COLS:
        if col in X_enc.columns:
            X_aligned[col] = X_enc[col]
    return X_aligned


def extract_and_validate_feedback_dataset(
    feedback_rows: List[Dict[str, Any]],
    predictions_map: Dict[str, Dict[str, Any]],
    student_features_map: Dict[str, Dict[str, Any]],
    *,
    min_samples: int = MIN_RETRAINING_SAMPLES,
) -> FeedbackDatasetResult:
    """Extract, validate, and shape feedback-informed dataset for M3."""
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
    """Async READ-ONLY helper to extract and validate dataset from PostgreSQL."""
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


async def fetch_historical_training_dataset(pool: Any) -> pd.DataFrame:
    """Fetch ground-truth historical training dataset from PostgreSQL."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
                st.student_id,
                st.department_code AS department_name,
                st.gender,
                ss.semester_no,
                ss.subjects_registered,
                ss.credits_registered,
                ss.credits_earned,
                ss.semester_total_marks,
                ss.semester_percentage,
                ss.semester_sgpa,
                ss.semester_attendance_percentage,
                ss.backlog_count
            FROM student_semester_summary ss
            JOIN students st ON st.student_id = ss.student_id
            ORDER BY st.student_id, ss.semester_no ASC
            """
        )
    df = pd.DataFrame([dict(r) for r in rows])
    df["next_backlogs"] = df.groupby("student_id")["backlog_count"].shift(-1)
    df["next_sgpa"] = df.groupby("student_id")["semester_sgpa"].shift(-1)

    train_hist = df[df["next_backlogs"].notna()].copy()
    train_hist["is_at_risk_next_sem"] = (
        (train_hist["next_backlogs"] > 0) | (train_hist["next_sgpa"] < 4.0)
    ).astype(int)
    return train_hist


def create_m3_pipeline() -> Pipeline:
    """Create standard M3 sklearn pipeline with SimpleImputer, StandardScaler, and LogisticRegression."""
    return Pipeline(
        [
            ("pre_0", SimpleImputer(strategy="median")),
            ("pre_1", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def evaluate_cv(
    pipeline_factory: Any,
    X_df: pd.DataFrame,
    y: np.ndarray,
    *,
    n_splits: int = 5,
    random_state: int = RANDOM_STATE,
) -> Dict[str, float]:
    """Evaluate pipeline using StratifiedKFold cross-validation to prevent leakage."""
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)

    prec_list: List[float] = []
    rec_list: List[float] = []
    f1_list: List[float] = []
    roc_list: List[float] = []
    pr_auc_list: List[float] = []

    for train_idx, val_idx in cv.split(X_df, y):
        X_tr, y_tr = X_df.iloc[train_idx].values, y[train_idx]
        X_va, y_val = X_df.iloc[val_idx].values, y[val_idx]

        pipe = pipeline_factory()
        pipe.fit(X_tr, y_tr)
        y_pred = pipe.predict(X_va)

        if hasattr(pipe, "predict_proba"):
            y_prob = pipe.predict_proba(X_va)[:, 1]
        elif hasattr(pipe, "decision_function"):
            y_prob = pipe.decision_function(X_va)
        else:
            y_prob = y_pred

        prec_list.append(precision_score(y_val, y_pred, zero_division=0))
        rec_list.append(recall_score(y_val, y_pred, zero_division=0))
        f1_list.append(f1_score(y_val, y_pred, zero_division=0))

        try:
            roc_list.append(roc_auc_score(y_val, y_prob))
        except Exception:
            pass

        try:
            pr_auc_list.append(average_precision_score(y_val, y_prob))
        except Exception:
            pass

    return {
        "precision": round(float(np.nanmean(prec_list)), 4),
        "recall": round(float(np.nanmean(rec_list)), 4),
        "f1": round(float(np.nanmean(f1_list)), 4),
        "roc_auc": round(float(np.nanmean(roc_list)), 4),
        "pr_auc": round(float(np.nanmean(pr_auc_list)), 4),
    }


async def get_db_invariants(pool: Any) -> Dict[str, int]:
    """Read counts of all related tables for safety verification."""
    async with pool.acquire() as conn:
        fb_cnt = await conn.fetchval("SELECT count(*) FROM prediction_feedback")
        ml_cnt = await conn.fetchval("SELECT count(*) FROM ml_predictions")
        risk_cnt = await conn.fetchval("SELECT count(*) FROM risk_predictions")
    return {
        "prediction_feedback": fb_cnt,
        "ml_predictions": ml_cnt,
        "risk_predictions": risk_cnt,
    }


async def retrain_m3_model(
    pool: Any,
    *,
    artifact_paths: Optional[List[Path]] = None,
    min_samples: int = MIN_RETRAINING_SAMPLES,
) -> RetrainingResult:
    """Main offline retraining orchestrator for M3 Next-Semester Risk Forecast."""
    # 1. DB Invariants Before
    invariants_before = await get_db_invariants(pool)

    # 2. Extract and validate feedback dataset
    fb_result = await extract_feedback_dataset_from_db(pool, min_samples=min_samples)
    if not fb_result.can_retrain or fb_result.features_df is None or fb_result.labels_series is None:
        raise RuntimeError(f"Cannot retrain M3: {fb_result.reason}")

    # 3. Extract historical baseline training data
    hist_df = await fetch_historical_training_dataset(pool)

    # 4. Prepare aligned features
    X_hist = encode_m3_features(hist_df)
    y_hist = hist_df["is_at_risk_next_sem"].values

    X_fb = encode_m3_features(fb_result.features_df)
    y_fb = fb_result.labels_series.values

    # Combine datasets
    X_combined = pd.concat([X_hist, X_fb], ignore_index=True)
    y_combined = np.concatenate([y_hist, y_fb])

    # 5. Evaluate Baseline CV vs Retrained CV
    baseline_metrics = evaluate_cv(create_m3_pipeline, X_hist, y_hist)
    retrained_metrics = evaluate_cv(create_m3_pipeline, X_combined, y_combined)

    metric_deltas = {
        k: round(retrained_metrics[k] - baseline_metrics[k], 4) for k in baseline_metrics
    }

    # 6. Fit Final Retrained Pipeline on Combined Dataset
    final_pipeline = create_m3_pipeline()
    final_pipeline.fit(X_combined.values, y_combined)

    # 7. Persist Artifact (Single canonical M3 artifact)
    if artifact_paths is None:
        root_dir = Path(__file__).resolve().parents[2]
        artifact_paths = [
            root_dir / "ml" / "artifacts" / "models" / "m3_next_semester_at_risk.joblib",
        ]

    saved_paths = []
    for path in artifact_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(final_pipeline, path)
        saved_paths.append(str(path))
        logger.info("Persisted M3 artifact to %s", path)

    # 8. Reload & Predict Verification
    reload_verified = False
    predict_verified = False
    for path in artifact_paths:
        loaded = joblib.load(path)
        if loaded is not None:
            reload_verified = True
        test_pred = loaded.predict(X_combined.iloc[:5].values)
        if len(test_pred) == 5:
            predict_verified = True

    # 9. PredictionService Serving Verification
    serving_verified = False
    try:
        from ml.src.prediction_service import PredictionService

        service = PredictionService(pool)
        # Verify M3 prediction for a student
        sample_sid = str(hist_df.iloc[0]["student_id"])
        pred_res = await service.predict_m3_for_student(sample_sid)
        if pred_res and pred_res.model_id == "m3" and len(pred_res.predictions) > 0:
            serving_verified = True
    except Exception as exc:
        logger.warning("PredictionService serving verification warning: %s", exc)

    # 10. DB Invariants After
    invariants_after = await get_db_invariants(pool)

    return RetrainingResult(
        status="retrained_successfully",
        counts_summary=fb_result.counts_summary,
        baseline_metrics=baseline_metrics,
        retrained_metrics=retrained_metrics,
        metric_deltas=metric_deltas,
        artifact_paths=saved_paths,
        db_invariants_before=invariants_before,
        db_invariants_after=invariants_after,
        reload_verified=reload_verified,
        predict_verified=predict_verified,
        serving_verified=serving_verified,
    )


if __name__ == "__main__":
    from app.core.database import db

    async def _run():
        await db.connect()
        try:
            res = await retrain_m3_model(db.pool)
            print("Retraining completed successfully!")
            print(f"Status: {res.status}")
            print(f"Artifact paths: {res.artifact_paths}")
            print(f"Baseline metrics: {res.baseline_metrics}")
            print(f"Retrained metrics: {res.retrained_metrics}")
            print(f"Metric deltas: {res.metric_deltas}")
            print(f"Reload verified: {res.reload_verified}")
            print(f"Predict verified: {res.predict_verified}")
            print(f"Serving verified: {res.serving_verified}")
            print(f"DB Invariants Before: {res.db_invariants_before}")
            print(f"DB Invariants After: {res.db_invariants_after}")
        finally:
            await db.disconnect()

    asyncio.run(_run())
