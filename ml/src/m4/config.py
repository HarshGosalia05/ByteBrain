"""M4 - Career Readiness Estimate: configuration."""
from __future__ import annotations

from pathlib import Path

ML_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ML_ROOT / "data" / "raw"
ARTIFACT_DIR = ML_ROOT / "artifacts" / "models"
REPORT_DIR = ML_ROOT / "reports"

MODEL_NAME = "m4_career_readiness"
MODEL_FILE = ARTIFACT_DIR / f"{MODEL_NAME}.joblib"
REPORT_FILE = REPORT_DIR / "m4_report.md"

RANDOM_STATE = 42
N_FOLDS = 5

TARGET = "placement_readiness_level"

# Excluded target_package_lpa as it may encode the label.
BASELINE_RAW_FEATURES = [
    "preferred_domain",
    "dream_job_role",
    "preferred_industry",
    "preferred_work_mode",
    "higher_studies_interest",
    "entrepreneurship_interest",
    "certification_interest",
    "internship_completed",
    # Academic features from prior semesters
    "avg_prior_percentage",
    "avg_prior_sgpa",
    "avg_prior_attendance",
    "total_prior_backlogs",
]

CATEGORICAL_FEATURES = [
    "preferred_domain",
    "dream_job_role",
    "preferred_industry",
    "preferred_work_mode",
    "certification_interest",
]

BINARY_FEATURES = [
    "higher_studies_interest",
    "entrepreneurship_interest",
    "internship_completed",
]

MODEL_ALGORITHMS = ["logistic_regression", "random_forest", "hist_gbm"]
