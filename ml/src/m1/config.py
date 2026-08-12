"""M1 - Subject Performance Predictor: configuration and path resolution.

Workspace is locked to D:\\KenexAi\\ByteBrain\\ml. All data, source,
artifacts and reports live under this root.
"""
from __future__ import annotations

from pathlib import Path

ML_ROOT = Path(__file__).resolve().parents[2]  # .../ml  (config.py lives at ml/src/m1)
DATA_DIR = ML_ROOT / "data" / "raw"
ARTIFACT_DIR = ML_ROOT / "artifacts" / "models"
REPORT_DIR = ML_ROOT / "reports"

MODEL_NAME = "m1_subject_endmarks"
MODEL_FILE = ARTIFACT_DIR / f"{MODEL_NAME}.joblib"
REPORT_FILE = REPORT_DIR / "m1_report.md"

RANDOM_STATE = 42
N_FOLDS = 5
N_SEEDS = 3
TARGET = "end_sem_marks"

# ---- Baseline (Stage A) - approved pre-end-semester signals + safe metadata.
BASELINE_RAW_FEATURES = [
    "internal_marks",
    "mid_sem_marks",
    "attendance_percentage",
    "subject_type",
    "credits",
    "semester_no",
    "department_name",
    "gender",
]

# ---- Ablation tier (Stage B) - historical academic aggregates. OFF by default.
ABLATION_RAW_FEATURES = [
    "prior_avg_percentage",
    "prior_avg_sgpa",
    "prior_avg_attendance",
    "prior_avg_end_marks",
    "prior_backlog_total",
    "prior_atkt_count",
    "prior_n_sems",
]

# Stage B trigger: baseline is judged insufficient only if CV MAE exceeds
# this threshold OR CV R2 falls below this threshold.
BASELINE_INSUFFICIENT_MAE = 5.0  # marks (0-70 scale)
BASELINE_INSUFFICIENT_R2 = 0.70

# Ablation acceptance rule (validated, leakage-free improvement):
# mean MAE must improve by >= these amounts and >= 4 of 5 folds must improve.
ABLATION_MIN_MAE_DELTA = 0.25  # marks
ABLATION_MIN_RMSE_DELTA = 0.50  # marks
ABLATION_MIN_FOLDS_IMPROVED = 4

# ---- Columns that must never appear as features (leakage / target-derived).
FORBIDDEN_FEATURES = [
    "total_marks",
    "percentage",
    "grade",
    "grade_point",
    "result_status",
    "performance_category",
    "ct1_marks",
    "ct2_marks",
    "attempt_number",
    "latest_sgpa",
    "overall_cgpa",
    "overall_percentage",
    "overall_attendance_percentage",
    "total_backlogs",
    "academic_standing",
]

CATEGORICAL_FEATURES = ["subject_type", "department_name"]
BINARY_FEATURES = ["gender"]

MODEL_ALGORITHMS = ["ridge", "hist_gbm", "xgboost"]

TARGET_MIN = 0.0
TARGET_MAX = 70.0
