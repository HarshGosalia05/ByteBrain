"""M1 - Temporal Hold-Forward Validation: Live Verification Script.

Runs the temporal hold-forward evaluation layer (m1.temporal) against the real
M1 CSV dataset (read-only) to quantify across-semester generalization of the
verified M1 Stage-A model. Reuses the existing M1 architecture/contract exactly.

READ-ONLY wrt the database/canvas: no ETL, no schema, no API, no dashboard, no
M2/M3/M4, no Stage-B ablation, no artifact writes. The authoritative M1 artifact
(artifacts/models/m1_subject_endmarks.joblib) is NOT modified.

Usage:  python ml/verify_m1_temporal.py
"""
from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np

_ML_SRC = str(Path(__file__).resolve().parents[0] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from m1 import config, data, temporal  # noqa: E402
from m1.temporal import run_hold_forward, all_checks_pass  # noqa: E402


def main() -> None:
    t0 = time.time()
    print("M1 - Subject Performance Predictor: TEMPORAL HOLD-FORWARD VERIFICATION")
    print("ML ROOT:", config.ML_ROOT)

    train, deploy = data.build_dataset(include_ablation=False)
    print("\n--------------------------------------------------")
    print("M1 TEMPORAL HOLD-FORWARD VERIFICATION")
    print("--------------------------------------------------")
    print("Dataset:")
    print(f"    training rows: {len(train)}")
    print(f"    deployment rows: {len(deploy)}")
    print(f"    students: {train['student_id'].nunique()}")

    result = run_hold_forward(train)
    val, train_sems = temporal.derive_hold_forward_boundary(train)

    print("\nTemporal split:")
    print(f"    training semesters: {min(train_sems)}..{max(train_sems)}")
    print(f"    validation semester: {val}")

    print("\nTrain:")
    print(f"    rows: {result.train_n}")
    print(f"    students: {result.train_students}")

    print("\nValidation:")
    print(f"    rows: {result.valid_n}")
    print(f"    students: {result.valid_students}")

    print("\nStudent overlap:")
    print(f"    count: {result.student_overlap}")

    print("\nFeatures:")
    print(f"    raw: {len(config.BASELINE_RAW_FEATURES)}")
    print(f"    encoded: {len(result.encoded_features)}")

    print("\nLeakage:")
    c = result.checks
    print(f"    target leakage: {'NONE' if c['target_not_in_X'] else 'DETECTED'}")
    print(f"    forbidden features: {c['forbidden_found'] or 'NONE'}")
    print(f"    future-semester leakage: "
          f"{'PASS' if c['validation_after_training'] else 'FAIL'}")

    print("\nMetrics:")
    for m in result.candidate_metrics:
        print(f"    {m.algorithm}:")
        print(f"        MAE: {m.mae:.4f}")
        print(f"        RMSE: {m.rmse:.4f}")
        print(f"        R2: {m.r2:.4f}")

    # Reproducibility: run again, compare exact metrics + split
    r2 = run_hold_forward(train)
    split_same = (r2.training_semesters == result.training_semesters
                  and r2.validation_semester == result.validation_semester)
    metrics_same = all(
        abs(a.mae - b.mae) < 1e-9 and abs(a.rmse - b.rmse) < 1e-9 and abs(a.r2 - b.r2) < 1e-9
        for a, b in zip(result.candidate_metrics, r2.candidate_metrics)
    )
    print("\nReproducibility:")
    print(f"    split identical: {split_same}")
    print(f"    metrics identical: {metrics_same}")

    passed = (all_checks_pass(result) and split_same and metrics_same
              and all(np.isfinite(m.mae + m.rmse + m.r2) for m in result.candidate_metrics))
    print(f"\nVERIFICATION {'PASSED' if passed else 'FAILED'}")
    print("--------------------------------------------------")

    elapsed = time.time() - t0
    print(f"\nElapsed: {elapsed:.1f}s")
    print("M1 TEMPORAL VALIDATION COMPLETE - stopped. Evaluation only, "
          "no artifact/DB/API/dashboard changes.")


if __name__ == "__main__":
    main()
