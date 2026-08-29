"""V1 Training Dataset Preparation — Live Verification Script.

Connects to the live PostgreSQL database, builds the verified V1 feature
dataset (Step 1), prepares the train/validation/test split (Step 2), and
prints a comprehensive report.

Usage:
    python ml/verify_v1_training_dataset.py

Does NOT train models or generate predictions.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
import psycopg2

# Add ml/src to path (this script is at ml/, so parents[0] = ml/)
_ML_SRC = str(Path(__file__).resolve().parents[0] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from features.v1_config import V1Config  # noqa: E402
from features.v1_dataset import build_v1_dataset  # noqa: E402
from features.v1_split import prepare_v1_dataset  # noqa: E402
from features.v1_split_config import V1SplitConfig  # noqa: E402
from features.v1_split_coverage import assess_positive_coverage  # noqa: E402
from features.v1_split_validation import validate_v1_split  # noqa: E402


def get_connection():
    """Create a psycopg2 connection from environment variables."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "aws-1-ap-south-1.pooler.supabase.com"),
        port=int(os.getenv("DB_PORT", "6543")),
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres.rtaqkxqdejelxsamnesm"),
        password=os.getenv("DB_PASSWORD", "KenexAI@*195"),
    )


def _class_dist(y: pd.Series) -> str:
    n = len(y)
    pos = int((y == 1).sum())
    neg = int((y == 0).sum())
    return f"0={neg} ({neg / n:.1%}), 1={pos} ({pos / n:.1%})"


def print_report(prepared, validation_result):
    """Print comprehensive Step-2 verification report."""
    m = prepared.split_metadata

    print("=" * 72)
    print("V1 TRAINING DATASET PREPARATION — LIVE VERIFICATION REPORT")
    print("=" * 72)

    print("\n--- DATASET (source) ---")
    print(f"  Target rows (source):  {m['train_rows'] + m['validation_rows'] + m['test_rows']}")
    print(f"  Deployment rows:       {m['deployment_rows']}")

    print("\n--- SPLIT STRATEGY ---")
    print(f"  Strategy:              {m['strategy']}")
    print(f"  Test fraction:         {m['test_fraction']}")
    print(f"  Validation fraction:   {m['validation_fraction']}")
    print(f"  Random state:          {m['random_state']}")

    print("\n--- SPLITS ---")
    print(f"  Train rows:            {m['train_rows']}  ({m['n_train_students']} students)")
    print(f"    Class dist:          {_class_dist(prepared.y_train)}")
    print(f"  Validation rows:       {m['validation_rows']}  ({m['n_validation_students']} students)")
    print(f"    Class dist:          {_class_dist(prepared.y_validation)}")
    print(f"  Test rows:             {m['test_rows']}  ({m['n_test_students']} students)")
    print(f"    Class dist:          {_class_dist(prepared.y_test)}")

    print("\n--- FEATURES ---")
    print(f"  Raw feature count:     {m['feature_count_raw']}")
    print(f"  Encoded feature count: {m['feature_count_encoded']}")
    print(f"  Encoded feature names: {list(prepared.encoded_feature_columns)}")

    print("\n--- LEAKAGE CHECKS ---")
    print(validation_result.summary())

    print("\n" + "=" * 72)
    print("PREPARATION COMPLETE — NO MODELS TRAINED, NO PREDICTIONS MADE")
    print("=" * 72)


def main():
    """Run Step 2: prepare + validate train/val/test against live DB."""
    print("Connecting to database...")
    conn = get_connection()

    v1_config = V1Config()
    split_config = V1SplitConfig()

    # Step 1: build verified feature dataset
    print("Building verified V1 feature dataset (Step 1)...")
    t0 = time.time()
    dataset = build_v1_dataset(conn, v1_config)
    t_build = time.time() - t0

    # Step 2: prepare train/val/test
    print("Preparing train/validation/test split (Step 2)...")
    t0 = time.time()
    prepared = prepare_v1_dataset(dataset, split_config)
    t_split = time.time() - t0

    # Validate
    print("Validating prepared dataset...")
    t0 = time.time()
    validation_result = validate_v1_split(prepared, dataset, split_config)
    t_validate = time.time() - t0

    # Report
    print_report(prepared, validation_result)

    # Coverage / split-strategy suitability assessment (no model fitting)
    print("\n" + assess_positive_coverage(prepared, dataset, split_config).report())

    print("\n--- REPRODUCIBILITY ---")
    t0 = time.time()
    prepared2 = prepare_v1_dataset(dataset, split_config)
    t_repro = time.time() - t0
    same_train = prepared.X_train.equals(prepared2.X_train)
    same_y = prepared.y_train.equals(prepared2.y_train)
    same_ids = prepared.train_ids.equals(prepared2.train_ids)
    identical = same_train and same_y and same_ids
    print(f"  Repeated run identical: {identical}")
    print(f"  X_train equal:        {same_train}")
    print(f"  y_train equal:        {same_y}")
    print(f"  train_ids equal:      {same_ids}")

    print(f"\n--- PERFORMANCE ---")
    print(f"  Step 1 build time:    {t_build:.2f}s")
    print(f"  Step 2 split time:    {t_split:.2f}s")
    print(f"  Validation time:      {t_validate:.2f}s")
    print(f"  Reproducibility time: {t_repro:.2f}s")

    conn.close()

    if not validation_result.passed:
        print("\nVERIFICATION FAILED — see errors above")
        sys.exit(1)
    else:
        print("\nVERIFICATION PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
