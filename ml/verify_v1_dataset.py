"""V1 Feature Dataset — Live Verification Script.

Connects to the production Supabase PostgreSQL database, builds the V1
feature dataset, validates it, and prints a comprehensive report.

Usage:
    python ml/verify_v1_dataset.py

Does NOT train models or generate predictions.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import psycopg2

# Add ml/src to path (this script is at ml/, so parents[0] = ml/)
_ML_SRC = str(Path(__file__).resolve().parents[0] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

_BACKEND = str(Path(__file__).resolve().parents[1] / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from db_env import db_config  # noqa: E402

from features.v1_config import V1Config, V1_FEATURE_NAMES, V1_NUMERIC_FEATURES
from features.v1_dataset import build_v1_dataset
from features.v1_validation import validate_v1_dataset


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection():
    """Create a psycopg2 connection from the repository environment."""
    db = db_config()
    return psycopg2.connect(
        host=db.host,
        port=db.port,
        dbname=db.name,
        user=db.user,
        password=db.password,
    )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(dataset, validation_result, elapsed_build, elapsed_validate):
    """Print comprehensive verification report."""
    config = V1Config()
    meta = dataset.metadata
    all_df = pd.concat([dataset.training_df, dataset.deployment_df], ignore_index=True)

    print("=" * 72)
    print("V1 FEATURE DATASET — LIVE VERIFICATION REPORT")
    print("=" * 72)

    # --- Scope ---
    print("\n--- SCOPE ---")
    print(f"  Department:           {meta['dept_name']}")
    print(f"  Student range:        {meta['student_id_range']}")
    print(f"  Student count:        {meta['student_count']}")
    print(f"  Prediction semester:  {meta['prediction_semester']}")
    print(f"  Feature semesters:    {meta['feature_semesters']}")

    # --- Row Counts ---
    print("\n--- ROW COUNTS ---")
    print(f"  Total rows:           {dataset.row_counts['total']}")
    print(f"  Training rows:        {dataset.row_counts['training']}")
    print(f"  Deployment rows:      {dataset.row_counts['deployment']}")

    # --- Feature Columns ---
    print("\n--- FEATURE COLUMNS ---")
    print(f"  Count:                {len(dataset.feature_columns)}")
    for i, col in enumerate(dataset.feature_columns, 1):
        print(f"  {i:2d}. {col}")

    # --- Target Distribution ---
    print("\n--- TARGET DISTRIBUTION ---")
    target_col = dataset.target_column
    if target_col in dataset.training_df.columns:
        target_counts = dataset.training_df[target_col].value_counts().sort_index()
        for val, count in target_counts.items():
            label = "at-risk" if val == 1 else "safe"
            print(f"  {val} ({label}):  {count} rows ({count / len(dataset.training_df):.1%})")
        print(f"  Positive rate:        {meta['positive_rate']:.2%}")
        print(f"  At-risk students:     {meta['n_at_risk']}")

    # --- Missing Values ---
    print("\n--- MISSING VALUES ---")
    for col in dataset.feature_columns:
        null_count = dataset.null_counts.get(col, 0)
        pct = null_count / dataset.row_counts["total"] * 100
        status = "OK" if null_count == 0 else f"NULLS={null_count} ({pct:.1f}%)"
        print(f"  {col:35s} {status}")

    # --- Categorical Distributions ---
    print("\n--- CATEGORICAL DISTRIBUTIONS ---")
    for col in ["department_name", "gender"]:
        if col in all_df.columns:
            dist = all_df[col].value_counts()
            print(f"  {col}:")
            for val, count in dist.items():
                print(f"    {val:20s} {count:4d} ({count / len(all_df):.1%})")

    # --- Numeric Statistics ---
    print("\n--- NUMERIC STATISTICS ---")
    for col in V1_NUMERIC_FEATURES:
        if col in all_df.columns:
            vals = all_df[col].dropna()
            print(f"  {col:35s} min={vals.min():8.2f}  max={vals.max():8.2f}  "
                  f"mean={vals.mean():8.2f}  std={vals.std():8.2f}")

    # --- Leakage Check ---
    print("\n--- LEAKAGE CHECK ---")
    config = V1Config()
    forbidden_in_features = [c for c in config.forbidden_columns if c in all_df.columns]
    if forbidden_in_features:
        print(f"  FAIL: Forbidden columns found: {forbidden_in_features}")
    else:
        print("  PASS: No forbidden columns in feature set")

    # Check temporal boundary
    if "semester_no" in dataset.training_df.columns:
        train_sems = sorted(dataset.training_df["semester_no"].unique())
        deploy_sems = sorted(dataset.deployment_df["semester_no"].unique())
        print(f"  Training semesters:   {train_sems}")
        print(f"  Deployment semesters: {deploy_sems}")
        if set(train_sems) == set(config.scope.feature_semesters):
            print("  PASS: Training semesters match expected feature_semesters")
        else:
            print(f"  FAIL: Expected {config.scope.feature_semesters}, got {train_sems}")

    # --- Determinism Check ---
    print("\n--- DETERMINISM CHECK ---")
    print("  (Run twice with same DB state — check below)")

    # --- Grain Check ---
    print("\n--- GRAIN CHECK ---")
    dup = all_df.duplicated(subset=["student_id", "semester_no"]).sum()
    if dup == 0:
        print("  PASS: No duplicate (student_id, semester_no) rows")
    else:
        print(f"  FAIL: {dup} duplicate rows found")

    # --- Validation Summary ---
    print("\n--- VALIDATION ---")
    print(validation_result.summary())

    # --- Timing ---
    print("\n--- PERFORMANCE ---")
    print(f"  Build time:           {elapsed_build:.2f}s")
    print(f"  Validation time:      {elapsed_validate:.2f}s")
    print(f"  Total time:           {elapsed_build + elapsed_validate:.2f}s")

    print("\n" + "=" * 72)
    print("VERIFICATION COMPLETE — NO MODELS TRAINED, NO PREDICTIONS MADE")
    print("=" * 72)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Run V1 dataset build + validation against live database."""
    print("Connecting to database...")
    conn = get_connection()

    config = V1Config()

    # Build
    print("Building V1 feature dataset...")
    t0 = time.time()
    dataset = build_v1_dataset(conn, config)
    elapsed_build = time.time() - t0

    # Validate
    print("Validating V1 feature dataset...")
    t0 = time.time()
    validation_result = validate_v1_dataset(dataset, config)
    elapsed_validate = time.time() - t0

    # Report
    print_report(dataset, validation_result, elapsed_build, elapsed_validate)

    conn.close()

    # Exit code
    if not validation_result.passed:
        print("\nVERIFICATION FAILED — see errors above")
        sys.exit(1)
    else:
        print("\nVERIFICATION PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
