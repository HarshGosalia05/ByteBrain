"""M1 v2 — Subject Performance Predictor: configuration.

All paths, seeds, thresholds, and feature/target contracts for the
1200-student CSE 6A cohort implementation.

DO NOT import any ml/src/m1 code. This is an isolated v2 implementation.
Supabase is READ-ONLY. No modifications to the database.
"""
from __future__ import annotations

from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Root paths
# ──────────────────────────────────────────────────────────────────────────────
V2_ROOT = Path(__file__).resolve().parent            # ml/v2/m1_subject_prediction/
ML_ROOT = V2_ROOT.parent.parent                      # ml/
ARTIFACT_DIR = V2_ROOT / "artifacts" / "models"
REPORT_DIR = V2_ROOT / "reports"
DATA_CACHE_DIR = V2_ROOT / "data" / "cache"

# ──────────────────────────────────────────────────────────────────────────────
# Model artifact
# ──────────────────────────────────────────────────────────────────────────────
MODEL_NAME = "m1_v2_subject_endmarks"
MODEL_FILE = ARTIFACT_DIR / f"{MODEL_NAME}.joblib"
MODEL_VERSION = "2.0"

# ──────────────────────────────────────────────────────────────────────────────
# Reproducibility
# ──────────────────────────────────────────────────────────────────────────────
RANDOM_STATE = 42
N_FOLDS = 5          # GroupKFold by student_id
N_SEEDS = 3          # model selection seeds

# ──────────────────────────────────────────────────────────────────────────────
# Target
# ──────────────────────────────────────────────────────────────────────────────
TARGET = "end_sem_marks"
TARGET_MIN = 0.0
TARGET_MAX = 70.0

# ──────────────────────────────────────────────────────────────────────────────
# 6A cohort filter
# ──────────────────────────────────────────────────────────────────────────────
COHORT_ID_PREFIX = "STU6A"               # 6A student IDs start with STU6A
COHORT_DIVISION = "6A"
TEMPORAL_HOLDOUT_SEMESTER = 7           # Semester 7 = temporal validation set
TRAINING_SEMESTERS = list(range(1, 7))  # Semesters 1–6 for training

# ──────────────────────────────────────────────────────────────────────────────
# Prediction point
# ──────────────────────────────────────────────────────────────────────────────
PREDICTION_POINT = (
    "During semester T, after internal marks, mid-sem marks, weekly "
    "attendance (all 8 weeks), learning activity (all 8 weeks), and "
    "assignments/quizzes have been recorded — BEFORE the end-semester exam."
)
ATTENDANCE_WEEKS_AVAILABLE = 8    # all 8 weekly records are available at cutoff
LEARNING_WEEKS_AVAILABLE = 8      # same

# ──────────────────────────────────────────────────────────────────────────────
# Feature tiers
# ──────────────────────────────────────────────────────────────────────────────

# Tier 1: Current-semester pre-exam numeric signals (always included)
TIER1_NUMERIC = [
    "internal_marks",            # 0–20; internal assessment; available before end-exam
    "mid_sem_marks",             # 0–50; mid-semester exam; available before end-exam
    "pre_endsem_assessment_pct", # composite (internal+mid)/70 * 100; no leakage
    "assignment_score",          # 0–100; scored during semester; no leakage
    "quiz_avg_marks",            # 0–100; quiz average; no leakage
    "submission_delay_days",     # submission delay in days; behavioral signal
    "att_total_pct",             # 100 * SUM(classes_attended)/SUM(classes_held); point-in-time
    "att_rolling_4w_mean",       # attendance_weekly rolling 4-week mean; point-in-time
    "att_velocity_latest",       # latest week's attendance velocity; point-in-time
    "credits",                   # subject credits (1–5); constant within enrollment
    "semester_no",               # current semester (1–8)
]

# Tier 1: Behavioral signals from learning activity (current semester, pre-exam)
TIER1_BEHAVIORAL = [
    "activity_volume_total",     # SUM(activity_volume) across weeks; engagement proxy
    "avg_engagement_consistency", # AVG(engagement_consistency); 0–1
    "avg_assessment_completion_rate",  # AVG(assessment_completion_rate); 0–1
    "avg_late_submission_rate",  # AVG(late_submission_rate); 0–1
]

# Tier 1: Categorical features
TIER1_CATEGORICAL = [
    "subject_type",              # Theory / Laboratory / Project / Internship
    "subject_domain",            # Communication & General / Math & Statistics / etc.
]

# Tier 1: Student metadata (binary / demographic)
TIER1_STUDENT_META = [
    "gender",                    # Male / Female → is_male
    "mental_stress_level",       # High / Medium / Low → ordinal encoded
    "study_hours_per_week",      # lifestyle survey; self-reported at semester start
]

# Tier 2 (Ablation): Prior semester aggregates from student_semester_summary
TIER2_PRIOR_HISTORY = [
    "prior_avg_sgpa",            # mean SGPA from all completed semesters < T
    "sgpa_drift_latest",         # most recent sgpa_drift (sem T-1 vs T-2)
    "prior_backlog_cumulative",  # cumulative backlogs from completed semesters < T
    "prior_avg_attendance",      # mean semester attendance from completed sems < T
    "prior_n_sems",              # number of completed prior semesters
]

# All raw feature names (pre-encoding) — used for leakage checks
ALL_FEATURE_NAMES = (
    TIER1_NUMERIC
    + TIER1_BEHAVIORAL
    + TIER1_CATEGORICAL
    + TIER1_STUDENT_META
    + TIER2_PRIOR_HISTORY
)

# ──────────────────────────────────────────────────────────────────────────────
# Leakage policy: columns that must NEVER appear as features
# ──────────────────────────────────────────────────────────────────────────────
FORBIDDEN_FEATURES = frozenset([
    # Target-derived
    "end_sem_marks",
    "total_marks",
    "percentage",
    "grade",
    "grade_point",
    "result_status",
    "performance_category",
    "remarks",
    # Student-level aggregates that include current semester outcomes
    "latest_sgpa",
    "overall_cgpa",
    "overall_percentage",
    "overall_attendance_percentage",
    "total_backlogs",
    "academic_standing",
    # Post-outcome
    "placement_status",
    "package_lpa",
    "package_tier",
    "placement_domain",
    "placement_date",
    # Per-semester outcome fields
    "semester_total_marks",
    "semester_percentage",
    "semester_sgpa",
    "semester_grade",
    "semester_result",
    "credits_earned",
])

# ──────────────────────────────────────────────────────────────────────────────
# Categorical encoding specification
# ──────────────────────────────────────────────────────────────────────────────
OHE_FEATURES = ["subject_type", "subject_domain"]  # one-hot encoded
ORDINAL_FEATURES = {
    "mental_stress_level": {"Low": 0, "Medium": 1, "High": 2},
}
BINARY_FEATURES = {"gender": {"Male": 1, "Female": 0}}

# ──────────────────────────────────────────────────────────────────────────────
# Stage B (ablation) thresholds — same discipline as V1
# ──────────────────────────────────────────────────────────────────────────────
BASELINE_INSUFFICIENT_MAE = 5.0   # marks; if CV MAE > this → consider ablation
BASELINE_INSUFFICIENT_R2 = 0.70   # if R² < this → consider ablation
ABLATION_MIN_MAE_DELTA = 0.25     # minimum mean MAE improvement to accept a feature
ABLATION_MIN_FOLDS_IMPROVED = 4   # minimum folds (out of 5) that must improve

# ──────────────────────────────────────────────────────────────────────────────
# Model candidates
# ──────────────────────────────────────────────────────────────────────────────
MODEL_ALGORITHMS = ["ridge", "random_forest", "hist_gbm", "xgboost"]
# Note: xgboost must be installed in ml/.venv

# ──────────────────────────────────────────────────────────────────────────────
# Baselines
# ──────────────────────────────────────────────────────────────────────────────
BASELINE_NAMES = ["mean_predictor", "prior_mean_predictor", "ridge"]
