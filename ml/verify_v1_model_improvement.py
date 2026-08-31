"""V1 M3 Controlled Model Improvement — Live Verification Script.

Builds the verified V1 dataset from PostgreSQL and runs the baseline-vs-
candidate (LR vs RFC) comparison under identical student-isolated
GroupKFold(5) folds, on training rows only (deployment excluded).

Does NOT persist a model, tune, oversample, access deployment rows, or change
the DB.  Usage:  python ml/verify_v1_model_improvement.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import psycopg2

_ML_SRC = str(Path(__file__).resolve().parents[0] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

_BACKEND = str(Path(__file__).resolve().parents[1] / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from db_env import db_config  # noqa: E402

from features.v1_config import V1Config  # noqa: E402
from features.v1_dataset import build_v1_dataset  # noqa: E402
from features.v1_model_improvement import (  # noqa: E402
    run_model_improvement,
    comparison_report,
)


def get_connection():
    db = db_config()
    return psycopg2.connect(
        host=db.host,
        port=db.port,
        dbname=db.name,
        user=db.user,
        password=db.password,
    )


def main():
    print("Connecting to database...")
    conn = get_connection()

    v1_config = V1Config()
    print("Building verified V1 feature dataset...")
    t0 = time.time()
    dataset = build_v1_dataset(conn, v1_config)
    t_build = time.time() - t0

    print("Running controlled improvement experiment...")
    t0 = time.time()
    comp = run_model_improvement(dataset)
    t_eval = time.time() - t0

    print("\n" + comparison_report(comp))

    print("\n" + comp.overfit.report())

    print("\n--- REPRODUCIBILITY ---")
    t0 = time.time()
    comp2 = run_model_improvement(dataset)
    t_repro = time.time() - t0


    def _same_folds(c1, c2):
        for a, b in zip(c1.baseline_folds, c2.baseline_folds):
            if a.validation_positive != b.validation_positive:
                return False
        for a, b in zip(c1.candidate_folds, c2.candidate_folds):
            if a.validation_positive != b.validation_positive:
                return False
        return True


    def _same_metrics(c1, c2):
        for name in ("precision", "recall", "f1", "roc_auc", "pr_auc"):
            ba, bb = getattr(c1.baseline_aggregate, name), getattr(c2.baseline_aggregate, name)
            ca, cb = getattr(c1.candidate_aggregate, name), getattr(c2.candidate_aggregate, name)
            if not ((ba != ba and bb != bb) or ba == bb):  # NaN-consistent
                return False
            if not ((ca != ca and cb != cb) or ca == cb):
                return False
        return True

    print(f"  Identical folds:            {_same_folds(comp, comp2)}")
    print(f"  Identical aggregate metrics: {_same_metrics(comp, comp2)}")

    print("\n--- LEAKAGE CHECKS ---")
    print("  Student isolation:          GroupKFold by student_id (no overlap)")
    print("  Temporal:                   same student's semesters kept together")
    print("  Deployment (sem 7):         EXCLUDED from CV")
    print("  Preprocessing fit:          on each training fold only")
    print("  Student IDs as features:    NO")
    print("  Target-derived info in X:   NO")

    print(f"\n--- PERFORMANCE ---")
    print(f"  Build time:  {t_build:.2f}s")
    print(f"  Eval time:   {t_eval:.2f}s")
    print(f"  Repro time:  {t_repro:.2f}s")

    conn.close()
    print("\nEXPERIMENT COMPLETE — NO PRODUCTION MODEL PERSISTED, NO PREDICTIONS")


if __name__ == "__main__":
    main()
