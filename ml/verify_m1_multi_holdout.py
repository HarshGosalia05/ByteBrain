"""M1 - Multi-Holdout Temporal Validation: Live Verification Script.

Runs the multi-holdout temporal sweep (m1.multi_holdout) against the real M1
CSV dataset (read-only) to produce a SPREAD of across-semester generalization
metrics for the verified M1 Stage-A model.

READ-ONLY wrt the database/canvas: no ETL, no schema, no API, no dashboard, no
M2/M3/M4, no Stage-B ablation, no model selection, no artifact writes. The
authoritative M1 artifact (artifacts/models/m1_subject_endmarks.joblib) is NOT
modified.

Usage:  python ml/verify_m1_multi_holdout.py
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

from m1 import config, data  # noqa: E402
from m1.multi_holdout import run_multi_holdout, sweep_all_checks_pass  # noqa: E402


def main() -> None:
    t0 = time.time()
    print("M1 - Multi-Holdout Temporal Validation")
    print("ML ROOT:", config.ML_ROOT)

    train, deploy = data.build_dataset(include_ablation=False)
    result = run_multi_holdout(train)

    print("\n--------------------------------------------------")
    print("M1 MULTI-HOLDOUT TEMPORAL VALIDATION")
    print("--------------------------------------------------")
    print(f"Dataset: training rows = {len(train)}, deployment rows = {len(deploy)}, "
          f"students = {train['student_id'].nunique()}")

    for i, w in enumerate(result.windows, 1):
        print(f"\nWindow {i}:")
        print(f"  Train: semesters "
              f"{w.training_semesters[0]}-{w.training_semesters[-1]}")
        print(f"  Validation: semester {w.validation_semester}")
        print(f"  Train rows: {w.train_n}")
        print(f"  Validation rows: {w.valid_n}")
        print(f"  Train students: {w.train_students}")
        print(f"  Validation students: {w.valid_students}")
        print(f"  Student overlap: {w.student_overlap}")
        print(f"  Features: {len(w.encoded_features)} encoded")
        for m in w.candidate_metrics:
            print(f"  {m.algorithm}: MAE {m.mae:.4f}, RMSE {m.rmse:.4f}, "
                  f"R2 {m.r2:.4f}")

    print("\nAggregate (mean±std across windows):")
    for a in result.aggregates:
        print(f"  {a.algorithm}: mean MAE {a.mae_mean:.4f}±{a.mae_std:.4f}, "
              f"mean RMSE {a.rmse_mean:.4f}±{a.rmse_std:.4f}, "
              f"mean R2 {a.r2_mean:.4f}±{a.r2_std:.4f}")

    # Reproducibility
    r2res = run_multi_holdout(train)
    split_same = all(
        (a.validation_semester == b.validation_semester)
        and (a.training_semesters == b.training_semesters)
        for a, b in zip(result.windows, r2res.windows)
    )
    metrics_same = all(
        abs(a.mae_mean - b.mae_mean) < 1e-12
        for a, b in zip(result.aggregates, r2res.aggregates)
    )
    print("\nReproducibility:")
    print(f"  identical = {'PASS' if (split_same and metrics_same) else 'FAIL'}")

    print("\nLeakage:")
    print("  PASS" if result.checks["all_windows_leakage_free"] else "  FAIL")
    print("Deployment exclusion:")
    print("  PASS" if result.checks["deployment_boundary_excluded"] else "  FAIL")
    print(f"  excluded later semesters: {result.excluded_later_semesters}")

    passed = (
        sweep_all_checks_pass(result)
        and split_same and metrics_same
        and all(np.isfinite(a.mae_mean) for a in result.aggregates)
    )
    print(f"\nVERIFICATION {'PASSED' if passed else 'FAILED'}")
    print("--------------------------------------------------")
    print(f"\nElapsed: {time.time() - t0:.1f}s")
    print("M1 MULTI-HOLDOUT COMPLETE - evaluation only. No model selection, "
          "no artifact/DB/API/dashboard changes.")


if __name__ == "__main__":
    main()
