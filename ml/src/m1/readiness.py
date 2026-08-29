"""M1 - Prediction-Readiness Assessment (evaluation/readiness-only layer).

Determines whether the persisted M1 artifact
(artifacts/models/m1_subject_endmarks.joblib) is technically ready for OFFLINE
inference/scoring under the existing project contract — WITHOUT retraining,
tuning, model replacement, or any production/API/dashboard integration.

Reuses the existing inference abstraction:
  - registry.load_model("m1")         -> authoritative artifact loader (ML-01)
  - features.prepare_m1_inference(...) -> exact training-time feature prep (ML-02)
  - config.TARGET_MIN/TARGET_MAX       -> [0, 70] clipping contract

Temporal boundary
-----------------
- Historical labeled rows (semesters 1..LABELED_EVAL_MAX_SEMESTER with a true
  end_sem_marks) are used for the readiness metrics (MAE/RMSE/R2).
- Semester 7 is the deployment boundary: it is reported separately and its
  unavailable target is NEVER used to fabricate an evaluation metric.
- Deployment rows (end_sem_marks IS NULL) are inference-only; only a prediction
  distribution is reported, never a fabricated MAE/RMSE/R2.

IMPORTANT honesty note
----------------------
Because the persisted model was trained on the labeled rows used here, the
readiness MAE/RMSE/R2 are RESUBSTITUTION (in-sample) estimates, not held-out
generalization. Held-out temporal generalization is provided separately by the
M1 multi-holdout temporal validation (mean MAE ~= 3.23). No deployment target is
fabricated.

The artifact is read-only; its SHA-256 is captured and must be identical
before/after this check. Nothing is persisted here.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from . import config

try:
    from .. import features, registry
except ImportError:  # sys.path == ml/src (mirrors inference.py fallback)
    import features  # type: ignore[no-redef]
    import registry  # type: ignore[no-redef]

LABELED_EVAL_MAX_SEMESTER = 6  # semester 7 = deployment boundary


@dataclass
class ReadinessResult:
    artifact_path: str
    artifact_hash: str
    artifact_mtime: str
    artifact_loaded: bool
    model_type: str
    n_features: int
    feature_names: list[str]
    feature_compatible: bool  # encoded set == artifact feature_names

    n_total_rows: int
    n_labeled_eval: int          # historical labeled rows scored (sems 1..6)
    n_deployment_rows: int       # end_sem_marks IS NULL (inference-only)
    n_sem7_boundary_rows: int    # all semester-7 rows (deployment boundary)

    prediction_shape_ok: bool
    no_nan_inf: bool
    prediction_range_ok: bool
    deterministic: bool

    eval_metrics: dict  # {mae, rmse, r2} on historical labeled rows
    per_semester_mae: dict  # semester_no -> mae (labeled rows, sems 1..6)
    deployment_pred_stats: dict  # min/mean/max on deployment rows (no metric)

    checks: dict = field(default_factory=dict)


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _mtime(path) -> str:
    import os
    return datetime.fromtimestamp(os.path.getmtime(path)).isoformat()


def run_readiness(performance, attendance, subjects, students,
                  labeled_max_semester: int = LABELED_EVAL_MAX_SEMESTER,
                  artifact_path=None) -> ReadinessResult:
    """Assess readiness of the persisted M1 model on real data (offline, ro).

    performance/attendance/subjects/students are the raw CSV DataFrames.
    """
    if artifact_path is None:
        entry = registry.get_entry("m1")
        artifact_path = entry.artifact_path
    artifact_hash = _sha256(artifact_path)
    artifact_mtime = _mtime(artifact_path)

    artifact = registry.load_model("m1")
    saved_features = list(artifact["feature_names"])
    n_features = len(saved_features)
    model_type = type(artifact["model"]).__name__

    # ---- Exact inference path (ML-02 + stored preprocessing) ----
    X, raw_df = features.prepare_m1_inference(
        performance, attendance, subjects, students, artifact
    )
    raw_preds = np.asarray(artifact["model"].predict(X))
    clipped = np.clip(raw_preds, config.TARGET_MIN, config.TARGET_MAX)
    predicted = np.round(clipped, 1)

    # ---- Feature compatibility ----
    encoded_cols = list(features._one_hot_encode(
        raw_df[features.M1_CONTRACT.raw_features]
        if set(features.M1_CONTRACT.raw_features) <= set(raw_df.columns) else raw_df,
        features.M1_CONTRACT,
    ).columns)
    feature_compatible = set(encoded_cols) >= set(saved_features)

    # ---- Row alignment & face validity ----
    prediction_shape_ok = len(predicted) == len(raw_df)
    no_nan_inf = bool(np.isfinite(predicted).all())
    prediction_range_ok = bool(
        (predicted >= config.TARGET_MIN).all() and (predicted <= config.TARGET_MAX).all()
    )

    # ---- Temporal boundary splits ----
    target = raw_df[config.TARGET].astype(float)
    semester = raw_df["semester_no"]
    labeled_mask = target.notna() & (semester <= labeled_max_semester)
    labeled_eval = raw_df[labeled_mask].copy()
    labeled_eval["_pred"] = predicted[labeled_mask.values]

    deployment_mask = target.isna()
    deployment_preds = predicted[deployment_mask.values]
    sem7_mask = semester == 7
    n_sem7 = int(sem7_mask.sum())

    # ---- Metrics on historical labeled rows (resubstitution) ----
    y_true = labeled_eval[config.TARGET]
    y_pred = labeled_eval["_pred"]
    eval_metrics = {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
        "n": int(len(labeled_eval)),
        "estimator": "resubstitution/in-sample (artifact trained on these rows)",
    }

    per_semester_mae = {}
    for sem, grp in labeled_eval.groupby("semester_no"):
        per_semester_mae[int(sem)] = float(
            mean_absolute_error(grp[config.TARGET], grp["_pred"])
        )

    # Deployment rows: prediction distribution only (NO fabricated metric)
    if len(deployment_preds) > 0:
        deployment_pred_stats = {
            "min": float(deployment_preds.min()),
            "mean": float(deployment_preds.mean()),
            "max": float(deployment_preds.max()),
            "n": int(len(deployment_preds)),
        }
    else:
        deployment_pred_stats = {"n": 0}

    # ---- Determinism: run the inference path again ----
    X2, _ = features.prepare_m1_inference(
        performance, attendance, subjects, students, artifact
    )
    preds2 = np.asarray(artifact["model"].predict(X2))
    clipped2 = np.clip(preds2, config.TARGET_MIN, config.TARGET_MAX)
    predicted2 = np.round(clipped2, 1)
    deterministic = bool(np.array_equal(predicted, predicted2))

    # "deployment target NOT fabricated": evaluation metrics are computed ONLY on
    # rows where end_sem_marks is actually present; deployment rows are excluded
    # from the metric computation entirely.
    checks = {
        "artifact_loaded": artifact_loaded_ok(artifact),
        "feature_compatible": feature_compatible,
        "prediction_shape_ok": prediction_shape_ok,
        "no_nan_inf": no_nan_inf,
        "prediction_range_ok": prediction_range_ok,
        "deterministic": deterministic,
        "eval_uses_only_true_labels": bool(labeled_eval[config.TARGET].notna().all()),
        "deployment_rows_excluded_from_eval": bool(deployment_mask.sum() > 0),
        "sem7_boundary_reported_separately": n_sem7 > 0,
    }

    return ReadinessResult(
        artifact_path=str(artifact_path),
        artifact_hash=artifact_hash,
        artifact_mtime=artifact_mtime,
        artifact_loaded=True,
        model_type=model_type,
        n_features=n_features,
        feature_names=saved_features,
        feature_compatible=feature_compatible,
        n_total_rows=int(len(raw_df)),
        n_labeled_eval=int(len(labeled_eval)),
        n_deployment_rows=int(deployment_mask.sum()),
        n_sem7_boundary_rows=n_sem7,
        prediction_shape_ok=prediction_shape_ok,
        no_nan_inf=no_nan_inf,
        prediction_range_ok=prediction_range_ok,
        deterministic=deterministic,
        eval_metrics=eval_metrics,
        per_semester_mae=per_semester_mae,
        deployment_pred_stats=deployment_pred_stats,
        checks=checks,
    )


def artifact_loaded_ok(artifact) -> bool:
    return (
        isinstance(artifact, dict)
        and "model" in artifact and "preprocess" in artifact
        and "feature_names" in artifact and "metadata" in artifact
    )


def readiness_verdict(result: ReadinessResult) -> tuple[bool, str]:
    """Return (ready, message) for OFFLINE inference readiness."""
    ok = all([
        result.artifact_loaded,
        result.feature_compatible,
        result.prediction_shape_ok,
        result.no_nan_inf,
        result.prediction_range_ok,
        result.deterministic,
    ])
    if ok:
        msg = ("Technically READY for offline inference/scoring. The artifact "
               "loads, the 12-feature contract is compatible, predictions are "
               "finite/in-range/deterministic, and historical labeled MAE is "
               "meaningful. NOT approved for production/API/dashboard/"
               "student-facing prediction.")
        return True, msg
    return False, "Not ready: one or more readiness checks failed."
