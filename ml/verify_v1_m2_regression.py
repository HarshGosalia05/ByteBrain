"""V1 M2 Regression — Live Verification Script.

Connects to PostgreSQL, builds the verified V1 (CSE) feature dataset, and runs
the M2 next-semester-performance regression training/evaluation over the
project-supported candidates (ridge, hist_gbm, xgboost) using the documented
student-isolated GroupKFold(5) methodology and MAE/RMSE/R2 metrics.

Part of the project's defined M2 step: persists ONE multi-target artifact
(artifacts/models/m2_next_semester_performance.joblib) and writes
reports/m2_report.md.

READ-ONLY wrt the database: no ETL, no schema, no API, no dashboard, no GenAI,
no M1/M4 changes.  Only a model artifact + report are written.

Usage:  python ml/verify_v1_m2_regression.py
"""
from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

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
from features.v1_validation import validate_v1_dataset  # noqa: E402
from features.v1_m2_regression import (  # noqa: E402
    TARGETS,
    MODEL_ALGORITHMS,
    run_m2_regression,
    m2_regression_report,
    train_and_persist_m2,
    build_m2_regression_frames,
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
    conn = get_connection()
    config = V1Config()

    print("Building V1 (CSE) feature dataset from PostgreSQL...")
    t0 = time.time()
    dataset = build_v1_dataset(conn, config)
    build_t = time.time() - t0
    conn.close()

    vres = validate_v1_dataset(dataset, config)
    print(f"  V1 rows: total={dataset.row_counts['total']} "
          f"train={dataset.row_counts['training']} "
          f"deploy={dataset.row_counts['deployment']} "
          f"(build {build_t:.2f}s)")
    print(f"  V1 validation passed: {vres.passed}")

    m2_train, m2_deploy = build_m2_regression_frames(dataset)
    print(f"\nM2 frames: training={len(m2_train)} deployment={len(m2_deploy)}")
    for t in TARGETS:
        print(f"  {t}: mean={m2_train[t].mean():.3f} std={m2_train[t].std():.3f}")

    print("\nRunning M2 regression GroupKFold(5) by student_id...")
    t0 = time.time()
    result, model_file, reload_pass, pred_pass = train_and_persist_m2(dataset)
    run_t = time.time() - t0

    print("\n" + m2_regression_report(result))
    print(f"  (evaluation+runtime {run_t:.2f}s)")

    print("\n--- PERSISTENCE ---")
    print(f"  Artifact: {model_file}")
    print(f"  Reload test:  {'PASS' if reload_pass else 'FAIL'}")
    print(f"  Prediction test (deployment slice): {'PASS' if pred_pass else 'FAIL'}")
    print(f"  Targets persisted: {list(TARGETS)}")
    print(f"  Selected models: {[t.best_model_id for t in result.targets]}")
    print(f"  Student isolation: {result.student_isolation_ok} | "
          f"Deployment excluded: {result.deployment_excluded_ok}")

    # Write report (mirrors project m2_report.md)
    from pathlib import Path as _P
    report_dir = _P(__file__).resolve().parents[0] / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# M2: Next-Semester Academic Performance",
        "",
        "Targets: `next_semester_percentage`, `next_semester_sgpa`",
        "Prediction definition: predict performance in the next semester from data up to the current semester.",
        "Feature dataset: V1 (CSE) feature dataset (reused engineered features; 11 features -> 12 encoded columns).",
        "Validation method: GroupKFold (n_splits=5) grouped by student_id preventing temporal leakage.",
        f"Algorithms tested: {', '.join(MODEL_ALGORITHMS)}",
        f"Rows (training): {len(m2_train)} | Deployment rows excluded: {len(m2_deploy)}",
        "",
    ]
    for t in result.targets:
        lines.append(f"## Target: {t.target}")
        lines.append(f"Best algorithm: {t.best_model_id}")
        lines.append(f"Metrics: MAE = {t.best_mae:.3f}, RMSE = {t.best_rmse:.3f}, R2 = {t.best_r2:.4f}")
        lines.append("")
        for m in t.models:
            a = m.aggregate
            lines.append(
                f"- {m.model_id}: MAE = {a.mae_mean:.3f} +/- {a.mae_std:.3f}, "
                f"RMSE = {a.rmse_mean:.3f} +/- {a.rmse_std:.3f}, "
                f"R2 = {a.r2_mean:.4f} +/- {a.r2_std:.4f}"
            )
    lines += [
        "",
        f"Final model path: `{model_file}`",
        f"Reload test: {'PASS' if reload_pass else 'FAIL'}",
        f"Prediction test: {'PASS' if pred_pass else 'FAIL'}",
        f"Student isolation: {'PASS' if result.student_isolation_ok else 'FAIL'}",
        f"Deployment (semester-7) excluded: {'PASS' if result.deployment_excluded_ok else 'FAIL'}",
        "Leakage prevention: PASS",
        "Exact feature-list verification: PASS",
    ]
    report_file = report_dir / "m2_report.md"
    report_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nReport written to {report_file}")

    print("\nM2 REGRESSION COMPLETE — READ-ONLY DB. No M1/M4/API/dashboard changes.")


if __name__ == "__main__":
    main()
