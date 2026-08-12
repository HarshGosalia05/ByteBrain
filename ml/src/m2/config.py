"""M2 - Next-Semester Academic Performance Predictor: configuration."""
from __future__ import annotations

from pathlib import Path

ML_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ML_ROOT / "data" / "raw"
ARTIFACT_DIR = ML_ROOT / "artifacts" / "models"
REPORT_DIR = ML_ROOT / "reports"

MODEL_NAME = "m2_next_semester_performance"
MODEL_FILE = ARTIFACT_DIR / f"{MODEL_NAME}.joblib"
REPORT_FILE = REPORT_DIR / "m2_report.md"

RANDOM_STATE = 42
N_FOLDS = 5

TARGETS = ["next_semester_percentage", "next_semester_sgpa"]

BASELINE_RAW_FEATURES = [
    "semester_no",
    "subjects_registered",
    "credits_registered",
    "credits_earned",
    "semester_total_marks",
    "semester_percentage",
    "semester_sgpa",
    "semester_attendance_percentage",
    "backlog_count",
    "department_name",
    "gender",
]

CATEGORICAL_FEATURES = ["department_name"]
BINARY_FEATURES = ["gender"]

MODEL_ALGORITHMS = ["ridge", "hist_gbm", "xgboost"]
