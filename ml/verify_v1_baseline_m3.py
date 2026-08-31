"""V1 M3 Baseline Training & Evaluation — Live Verification Script.

Connects to PostgreSQL, builds the verified V1 feature dataset, and runs the
M3 BASELINE (LogisticRegression, class_weight='balanced', SimpleImputer median +
StandardScaler) under student-isolated GroupKFold(5) on the training rows only.

Does NOT tune, compare algorithms, optimize thresholds, oversample, train a
final deployable artifact, or generate predictions.

Usage:  python ml/verify_v1_baseline_m3.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import psycopg2

# Resolve ml/src for imports (script lives at ml/).
_ML_SRC = str(Path(__file__).resolve().parents[0] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

_BACKEND = str(Path(__file__).resolve().parents[1] / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from db_env import db_config  # noqa: E402

from features.v1_config import V1Config  # noqa: E402
from features.v1_dataset import build_v1_dataset  # noqa: E402
from features.v1_baseline_m3 import build_and_evaluate_baseline  # noqa: E402


def get_connection():
    db = db_config()
    return psycopg2.connect(
        host=db.host,
        port=db.port,
        dbname=db.name,
        user=db.user,
        password=db.password,
    )


def fmt(v):
    return "n/a" if np.isnan(v) else f"{v:.3f}"


def main():
    print("Connecting to database...")
    conn = get_connection()

    v1_config = V1Config()
    print("Building verified V1 feature dataset (Step 1)...")
    t0 = time.time()
    dataset = build_v1_dataset(conn, v1_config)
    t_build = time.time() - t0

    print("Running M3 BASELINE GroupKFold(5) evaluation...")
    t0 = time.time()
    result = build_and_evaluate_baseline(dataset)
    t_eval = time.time() - t0

    print("\n" + "=" * 72)
    print("V1 M3 BASELINE — LIVE EVALUATION REPORT")
    print("=" * 72)

    print("\n--- DATASET ---")
    print(f"  Students:               {result.n_students}")
    print(f"  Positive students:      {result.n_positive_students}")
    print(f"  Positive rows:          {result.n_positive_rows}")
    print(f"  Total training rows:    {result.n_rows}")
    print(f"  Class distribution:     {result.class_distribution}")
    print(f"  Feature count:          {result.feature_count}")
    print(f"  Features:               {result.encoded_feature_columns}")
    print(f"  Encoding:               one-hot dept (BBA/CSE), gender->is_male")

    print("\n--- MODEL / EVAL CONFIG ---")
    print(f"  Model:                  {result.model} (class_weight='{result.class_weight}')")
    print(f"  Preprocessing:          {result.preprocessing}")
    print(f"  Evaluation:             {result.grouping}")
    print(f"  Random state:           {result.random_state}")
    print(f"  Deployment rows:        EXCLUDED from CV (sem-7 only)")

    print("\n--- PER-FOLD METRICS (positive_absent flagged; no fabrication) ---")
    print(result.per_fold_report())

    print("\n--- AGGREGATE (mean over defined folds only) ---")
    a = result.aggregate
    print(f"  Accuracy:  {fmt(a.accuracy)}   (over {a.accuracy_folds}/{result.n_folds} folds)")
    print(f"  Precision: {fmt(a.precision)}   (over {a.precision_folds}/{result.n_folds} folds)")
    print(f"  Recall:    {fmt(a.recall)}   (over {a.recall_folds}/{result.n_folds} folds)")
    print(f"  F1:        {fmt(a.f1)}   (over {a.f1_folds}/{result.n_folds} folds)")
    print(f"  ROC-AUC:   {fmt(a.roc_auc)}   (over {a.roc_auc_folds}/{result.n_folds} folds)")
    print(f"  PR-AUC:    {fmt(a.pr_auc)}   (over {a.pr_auc_folds}/{result.n_folds} folds)")
    print(f"  Folds with positive class present: {result.n_folds_with_positive_class}/{result.n_folds}")

    print("\n--- REPRODUCIBILITY ---")
    t0 = time.time()
    result2 = build_and_evaluate_baseline(dataset)
    t_repro = time.time() - t0

    def _fold_equal(f1, f2):
        a = np.array([f1.accuracy, f1.precision, f1.recall, f1.f1, f1.roc_auc, f1.pr_auc])
        b = np.array([f2.accuracy, f2.precision, f2.recall, f2.f1, f2.roc_auc, f2.pr_auc])
        return bool(np.allclose(a, b, equal_nan=True))

    same = [_fold_equal(f, r2) for f, r2 in zip(result.folds, result2.folds)]
    exact_class = all(
        (f.validation_positive, f.validation_negative) ==
        (r2.validation_positive, r2.validation_negative)
        for f, r2 in zip(result.folds, result2.folds)
    )
    print(f"  Repeated run identical per-fold (NaN-aware): {all(same)}")
    print(f"  Fold class counts identical:                {exact_class}")
    print(f"  Aggregate ROC-AUC equal: {result.aggregate.roc_auc == result2.aggregate.roc_auc}")

    print("\n--- PERFORMANCE ---")
    print(f"  Step 1 build time:  {t_build:.2f}s")
    print(f"  Baseline eval time: {t_eval:.2f}s")
    print(f"  Reproducibility:    {t_repro:.2f}s")

    conn.close()
    print("\nBASELINE EVALUATION COMPLETE — NO FINAL MODEL PERSISTED, NO PREDICTIONS MADE")


if __name__ == "__main__":
    main()
