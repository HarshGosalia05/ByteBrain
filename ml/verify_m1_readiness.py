"""M1 - Prediction-Readiness Assessment: Live Verification Script.

Assesses whether the persisted M1 artifact
(artifacts/models/m1_subject_endmarks.joblib) is technically ready for OFFLINE
inference/scoring under the existing project contract, against the real M1 CSV
dataset (read-only).

Uses the EXACT existing inference layer (ML-02 features.prepare_m1_inference)
and the authoritative loader (ML-01 registry.load_model) with the [0,70]
clipping contract. No retraining, no tuning, no model replacement, no
production/API/dashboard/GenAI/authentication changes, no DB/ETL/schema writes.

Temporal boundary is respected:
  - Historical labeled rows (sems 1..6 with a true end_sem_marks) are scored for
    MAE/RMSE/R2 (RESUBSTITUTION, in-sample — not held-out).
  - Semester-7 deployment boundary is reported separately; its unavailable
    target is NEVER used to fabricate an evaluation metric.
  - Deployment rows (target NULL) are inference-only (prediction distribution).

Held-out temporal generalization is provided independently by the M1
multi-holdout temporal validation (mean MAE ~= 3.23), referenced here.

REPRODUCIBILITY: the readiness check runs the inference path twice and asserts
identical predictions (determinism). The artifact SHA-256 + mtime are captured
and confirmed UNCHANGED before/after (read-only) — no artifact is (re)written.

Usage:  python ml/verify_m1_readiness.py
"""
from __future__ import annotations

import os
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

_ML_SRC = str(Path(__file__).resolve().parents[0] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from m1 import config, data, readiness  # noqa: E402


def main() -> None:
    t0 = time.time()
    print("M1 - Prediction-Readiness Assessment (live verification)")
    print("ML ROOT:", config.ML_ROOT)

    tables = data.load_tables()
    entry = readiness.registry.get_entry("m1")
    path = entry.artifact_path

    # Artifact fingerprint BEFORE (read-only baseline)
    hash_before = readiness._sha256(path)
    mtime_before = os.path.getmtime(path)

    result = readiness.run_readiness(
        tables["performance"], tables["attendance"],
        tables["subjects"], tables["students"],
    )

    # Artifact fingerprint AFTER -> must be unchanged (no writes)
    hash_after = readiness._sha256(path)
    mtime_after = os.path.getmtime(path)

    print("\n" + "=" * 62)
    print("M1 PREDICTION-READINESS ASSESSMENT")
    print("=" * 62)
    print(f"Artifact       : {result.artifact_path}")
    print(f"  SHA-256      : {result.artifact_hash}")
    print(f"  mtime        : {result.artifact_mtime}")
    print(f"  model type   : {result.model_type}")
    print(f"  n_features   : {result.n_features} (contract 12)")
    print(f"  feature_ok   : {result.feature_compatible}")

    print(f"\nRows: total={result.n_total_rows}, "
          f"labeled_eval(sem1-6)={result.n_labeled_eval}, "
          f"deploy(target NULL)={result.n_deployment_rows}, "
          f"sem7_boundary={result.n_sem7_boundary_rows}")

    print("\nReadiness metrics (historical labeled rows, RESUBSTITUTION):")
    m = result.eval_metrics
    print(f"  MAE  = {m['mae']:.4f}")
    print(f"  RMSE = {m['rmse']:.4f}")
    print(f"  R2   = {m['r2']:.4f}   (n={m['n']}, {m['estimator']})")

    print("\nPer-semester MAE (labeled rows, sems 1-6):")
    for sem in sorted(result.per_semester_mae):
        print(f"  sem {sem}: {result.per_semester_mae[sem]:.4f}")

    print("\nDeployment rows (target UNAVAILABLE -> NO fabricated metric):")
    d = result.deployment_pred_stats
    if d["n"]:
        print(f"  predictions min/mean/max = {d['min']:.1f}/{d['mean']:.2f}/{d['max']:.1f} "
              f"(n={d['n']}), clipped to [{config.TARGET_MIN},{config.TARGET_MAX}]")
    else:
        print("  (none)")

    print("\nChecks:")
    for k, v in result.checks.items():
        print(f"  {k}: {v}")
    print(f"  prediction range ok: {result.prediction_range_ok}")

    print("\nReproducibility & artifact integrity:")
    print(f"  deterministic (2 runs identical): {result.deterministic}")
    print(f"  artifact hash UNCHANGED before/after: {hash_before == hash_after}")
    print(f"  artifact mtime UNCHANGED before/after: {mtime_before == mtime_after}")

    ok, verdict = readiness.readiness_verdict(result)
    print("\n" + "-" * 62)
    print(f"VERDICT: {'READY' if ok else 'NOT READY'}")
    print(verdict)
    print(f"\nElapsed: {time.time() - t0:.1f}s")

    if not (ok and hash_before == hash_after and mtime_before == mtime_after):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
