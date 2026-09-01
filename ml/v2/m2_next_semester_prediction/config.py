"""M2 v2 — Next-Semester Performance Predictor: configuration.

Predicts a student's NEXT-semester academic performance (`semester_sgpa` and
`semester_percentage` at observation semester T+1) from features available at
(the just-completed) observation semester T.

Temporal contract: features from semester T only; target from semester T+1.
No T+1 information ever appears in `X`.

CRITICAL: The M1 v2 `FORBIDDEN_FEATURES` list is NOT reused. In M1 the current
semester's outcome columns (sgpa/percentage/marks) are forbidden because they
are outcome-like for the same-grain `end_sem_marks` target. In M2 the CURRENT-T
outcome columns ARE legitimate predictors (T is complete); what is forbidden are
the T+1 (next-semester) outcome columns that a naive `shift()` would leak.

DO NOT import any ml/src/m2 code. Isolated v2 implementation.
Supabase is READ-ONLY. No database modifications.
"""
from __future__ import annotations

from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Root paths
# ──────────────────────────────────────────────────────────────────────────────
V2_ROOT = Path(__file__).resolve().parent              # ml/v2/m2_next_semester_prediction/
ML_ROOT = V2_ROOT.parent.parent                         # ml/
ARTIFACT_DIR = V2_ROOT / "artifacts" / "models"
REPORT_DIR = V2_ROOT / "reports"
DATA_CACHE_DIR = V2_ROOT / "data" / "cache"

# ──────────────────────────────────────────────────────────────────────────────
# Model artifact
# ──────────────────────────────────────────────────────────────────────────────
MODEL_NAME = "m2_v2_next_semester"
MODEL_FILE = ARTIFACT_DIR / f"{MODEL_NAME}.joblib"
MODEL_VERSION = "2.0"

# ──────────────────────────────────────────────────────────────────────────────
# Reproducibility
# ──────────────────────────────────────────────────────────────────────────────
RANDOM_STATE = 42
N_FOLDS = 5          # GroupKFold by student_id
N_SEEDS = 3          # model selection seeds

# ──────────────────────────────────────────────────────────────────────────────
# Targets (two independent regression targets, matching legacy M2 contract)
# ──────────────────────────────────────────────────────────────────────────────
TARGET_SGPA = "next_semester_sgpa"
TARGET_PERCENTAGE = "next_semester_percentage"
TARGETS = [TARGET_SGPA, TARGET_PERCENTAGE]

# Target bounds (clip)
SGPA_MIN, SGPA_MAX = 0.0, 10.0
PERCENTAGE_MIN, PERCENTAGE_MAX = 0.0, 100.0
TARGET_BOUNDS = {
    TARGET_SGPA: (SGPA_MIN, SGPA_MAX),
    TARGET_PERCENTAGE: (PERCENTAGE_MIN, PERCENTAGE_MAX),
}

# ──────────────────────────────────────────────────────────────────────────────
# Cohort / temporal contract
# ──────────────────────────────────────────────────────────────────────────────
COHORT_ID_PREFIX = "STU6A"
COHORT_DIVISION = "6A"

# Observation semesters T whose next-semester T+1 target is a NORMAL academic
# semester (semesters 2..7). Semester 8 (target for T=7) is a 1-subject
# internship/project term with a compressed SGPA distribution — excluded as a
# target so the model predicts comparable full academic semesters.
TRAINING_TRANSITIONS = [1, 2, 3, 4, 5, 6]       # observation T -> target T+1 in {2..7}
TEMPORAL_HOLDOUT_TRANSITION = 6                # hold out T=6 -> predict semester 7

# All semesters that can serve as a valid observation T (those followed by a
# normal academic semester T+1). A student at T=8 (final/internship) has NO
# valid T+1 -> readiness NO_DATA.
VALID_OBSERVATION_SEMESTERS = [1, 2, 3, 4, 5, 6]
MAX_ACADEMIC_SEMESTER = 7                      # last semester whose outcome is a comparable target

# Deployment: observation T must satisfy  T in VALID_OBSERVATION_SEMESTERS
# (equivalently T+1 in 2..7, i.e. a real upcoming normal academic semester).

# ──────────────────────────────────────────────────────────────────────────────
# Prediction point
# ──────────────────────────────────────────────────────────────────────────────
PREDICTION_POINT = (
    "After the student's semester T has completed (all T outcomes known), "
    "predict their NEXT academic semester T+1 semester_sgpa and "
    "semester_percentage. No T+1 information is used in features."
)

# ──────────────────────────────────────────────────────────────────────────────
# Feature tiers
# ──────────────────────────────────────────────────────────────────────────────

# Tier 1: Current-semester (T) outcome + structural signals from semester_summary.
# These are T-completed outcomes (legitimate predictors of T+1).
TIER1_SEM_SUMMARY = [
    "semester_sgpa",              # T outcome — predictor of T+1
    "semester_percentage",        # T outcome — predictor of T+1
    "semester_total_marks",       # T outcome — predictor of T+1
    "semester_attendance_percentage",  # T attendance
    "backlog_count",              # T backlogs
    "cumulative_backlog_events",  # T cumulative backlogs
    "credits_registered",         # T credits
    "credits_earned",             # T earned credits
    "subjects_registered",        # T subjects
]

# Tier 1: Point-in-time prior history (from semester_summary, semesters <= T)
TIER1_PRIOR_HISTORY = [
    "previous_sem_sgpa",          # SGPA at T-1
    "sgpa_drift",                 # SGPA(T) - SGPA(T-1)
    "sgpa_rolling_mean_3",        # trailing 3-semester SGPA mean
    "previous_sem_backlog_count", # backlogs at T-1
    "backlog_change",             # backlog_count(T) - backlog_count(T-1)
    "attendance_aggregate_pct",   # attendance aggregate percentage
]

# Tier 1: Subject-level aggregates at T (from performance/enrollment)
TIER1_SUBJECT_AGG = [
    "subj_internal_marks_mean",   # mean internal marks across T subjects
    "subj_internal_marks_std",    # std of internal marks across T subjects
    "subj_mid_sem_marks_mean",    # mean mid-sem marks across T subjects
    "subj_end_sem_marks_mean",    # mean end_sem marks across T subjects (T outcome)
    "subj_assignment_score_mean", # mean assignment score across T subjects
    "subj_quiz_avg_marks_mean",   # mean quiz avg across T subjects
    "subj_submission_delay_mean", # mean submission delay across T subjects
    "subj_pre_endsem_pct_mean",   # mean pre-endsem assessment pct across T subjects
    "subj_end_sem_marks_std",     # std of end_sem marks across T subjects
]

# Tier 1: Attendance aggregate at T (from attendance_weekly)
TIER1_ATTENDANCE_AGG = [
    "att_tsem_total_pct",         # 100 * SUM(attended)/SUM(held) across T subject-weeks
    "att_tsem_low_pct_weeks",     # fraction of (subject,week) rows with low flag
    "att_tsem_velocity_mean",     # mean attendance_velocity across rows
]

# Tier 1: Learning activity aggregate at T (from student_learning_activity)
TIER1_LEARNING_AGG = [
    "learn_tsem_volume_total",    # SUM(activity_volume) across T subject-weeks
    "learn_tsem_engagement_mean", # AVG(engagement_consistency) across rows
    "learn_tsem_completion_mean", # AVG(assessment_completion_rate) across rows
    "learn_tsem_late_mean",       # AVG(late_submission_rate) across rows
]

# Tier 1: Categorical / binary student metadata
TIER1_STUDENT_META = [
    "gender",                     # -> is_male
    "semester_no",                # observation semester T (1..6)
    "mental_stress_level",        # -> stress_ordinal
    "study_hours_per_week",       # lifestyle survey at T
]

# Raw feature names (pre-encoding) — used for leakage checks and feature selection
ALL_FEATURE_NAMES = (
    TIER1_SEM_SUMMARY
    + TIER1_PRIOR_HISTORY
    + TIER1_SUBJECT_AGG
    + TIER1_ATTENDANCE_AGG
    + TIER1_LEARNING_AGG
    + TIER1_STUDENT_META
)

# ──────────────────────────────────────────────────────────────────────────────
# Leakage policy (M2-SPECIFIC, NOT M1's list)
#
# Forbids any column that encodes T+1 (next-semester) outcome information.
# The target columns themselves are moved into `y` separately and never in `X`.
# Current-T outcome columns are NOT in this list — they are legitimate features.
# ──────────────────────────────────────────────────────────────────────────────
FORBIDDEN_FEATURES = frozenset([
    # Targets (T+1 outcomes)
    "next_semester_sgpa",
    "next_semester_percentage",
    "next_semester_marks",
    "next_semester_total_marks",
    "next_semester_grade",
    "next_semester_result",
    "next_semester_attendance_percentage",
    "next_semester_backlog_count",
    "next_semester_rank",
    # Any lagged/derived T+1 signal
    "next_sem_sgpa_shift",
    "next_sem_attendance",
    "next_backlog_count",
    "next_cumulative_backlog_events",
    # Placement (post-degree future) — leakage by definition for a T+1 target
    "placement_status",
    "package_lpa",
    "package_tier",
    "placement_domain",
    "placement_date",
])

# ──────────────────────────────────────────────────────────────────────────────
# Categorical encoding specification
# ──────────────────────────────────────────────────────────────────────────────
ORDINAL_FEATURES = {
    "mental_stress_level": {"Low": 0, "Medium": 1, "High": 2},
}
BINARY_FEATURES = {"gender": {"Male": 1, "Female": 0}}
CATEGORICAL_FEATURES = []   # M2 has no subject-level categorical at this grain

# ──────────────────────────────────────────────────────────────────────────────
# Baselines
# ──────────────────────────────────────────────────────────────────────────────
BASELINE_NAMES = ["mean_predictor", "prior_semester_carryforward", "ridge"]

# ──────────────────────────────────────────────────────────────────────────────
# Model candidates + selection thresholds
# ──────────────────────────────────────────────────────────────────────────────
MODEL_ALGORITHMS = ["ridge", "random_forest", "hist_gbm", "xgboost"]

# Honest-skill thresholds (SGPA + percentage targets)
BASELINE_INSUFFICIENT_R2 = 0.50   # if CV R² < this, relationship is weak
ABLATION_MIN_MAE_DELTA_RATIO = 0.02  # min relative MAE improvement to accept a feature