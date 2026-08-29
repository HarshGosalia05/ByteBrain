"""V1 M3 Controlled Experimentation — Live Verification Script.

Builds the verified V1 dataset from PostgreSQL and runs the controlled M3
experiment over the project-supported models (LR reference, RFC, hist_gbm)
under identical student-isolated GroupKFold(5) folds, on training rows only.

Does NOT persist a model, tune, oversample, access deployment rows, or change
the DB.  Usage:  python ml/verify_v1_m3_experiment.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np
import psycopg2

_ML_SRC = str(Path(__file__).resolve().parents[0] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from features.v1_config import V1Config  # noqa: E402
from features.v1_dataset import build_v1_dataset  # noqa: E402
from features.v1_m3_experiment import run_m3_experiment, experiment_report  # noqa: E402


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "aws-1-ap-south-1.pooler.supabase.com"),
        port=int(os.getenv("DB_PORT", "6543")),
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres.rtaqkxqdejelxsamnesm"),
        password=os.getenv("DB_PASSWORD", "KenexAI@*195"),
    )


def main():
    print("Connecting to database...")
    conn = get_connection()

    v1_config = V1Config()
    print("Building verified V1 feature dataset...")
    t0 = time.time()
    dataset = build_v1_dataset(conn, v1_config)
    t_build = time.time() - t0

    print("Running controlled M3 experiment...")
    t0 = time.time()
    res = run_m3_experiment(dataset)
    t_eval = time.time() - t0

    print("\n" + experiment_report(res))

    print("\n--- VERIFICATION CHECKS ---")
    print(f"  Student isolation:       {'PASS' if res.student_isolation_ok else 'FAIL'}")
    print(f"  Deployment (sem-7) excl: {'PASS' if res.deployment_excluded_ok else 'FAIL'}")
    print(f"  No student-ID in X:      {'PASS' if 'student_id' not in res.encoded_feature_columns else 'FAIL'}")
    print(f"  No target in X:          {'PASS' if 'is_at_risk_next_sem' not in res.encoded_feature_columns else 'FAIL'}")

    print("\n--- REPRODUCIBILITY ---")
    t0 = time.time()
    res2 = run_m3_experiment(dataset)
    t_repro = time.time() - t0

    same_folds = (
        [f.fold for f in res.reference().folds]
        == [f.fold for f in res2.reference().folds]
    )
    same_metrics = all(
        abs(m.aggregate.f1_mean - m2.aggregate.f1_mean) < 1e-12
        and abs(m.aggregate.roc_auc_mean - m2.aggregate.roc_auc_mean) < 1e-12
        for m, m2 in zip(res.models, res2.models)
    )
    print(f"  Identical folds:            {same_folds}")
    print(f"  Identical aggregate metrics:{same_metrics}")

    print(f"\n--- PERFORMANCE ---")
    print(f"  Build time:  {t_build:.2f}s")
    print(f"  Eval time:   {t_eval:.2f}s")
    print(f"  Repro time:  {t_repro:.2f}s")

    conn.close()
    print("\nEXPERIMENT COMPLETE — NO PRODUCTION MODEL SELECTED/PERSISTED, NO PREDICTIONS")


if __name__ == "__main__":
    main()
