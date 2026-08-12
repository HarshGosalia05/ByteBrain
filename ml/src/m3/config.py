"""M3 - Next-Semester At-Risk / ATKT Predictor: configuration."""
from __future__ import annotations

from pathlib import Path

ML_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ML_ROOT / "data" / "raw"
ARTIFACT_DIR = ML_ROOT / "artifacts" / "models"
REPORT_DIR = ML_ROOT / "reports"

MODEL_NAME = "m3_next_semester_at_risk"
MODEL_FILE = ARTIFACT_DIR / f"{MODEL_NAME}.joblib"
REPORT_FILE = REPORT_DIR / "m3_report.md"

RANDOM_STATE = 42
N_FOLDS = 5

TARGET = "is_at_risk_next_sem"

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

MODEL_ALGORITHMS = ["logistic_regression", "random_forest", "hist_gbm"]
