"""M3 v2 — At-Risk Student Prediction: configuration.

Predicts whether a student will enter a defined academic-risk state in the NEXT
semester (T+1) from features available at the just-completed observation
semester T. Binary classification.

Temporal contract: features from semester T only; the LABEL is computed from
academic outcomes in semester T+1. No T+1 information ever appears in `X`.

Target definition (legacy-canonical, data-supported):
    at_risk(T+1) =
        1 if semester_result(T+1) in ('FAIL','ATKT') OR backlog_count(T+1) > 0
        0 otherwise

In the 1200 CSE 6A cohort, `ATKT` ⟺ `backlog_count > 0` (verified), and no
`FAIL` value exists, so this reduces to `backlog_count(T+1) > 0`. The OR-form is
kept for contract fidelity and generality.

CRITICAL — M1/M2 forbidden lists are NOT reused. Current-T outcome columns
(semester_sgpa, semester_percentage, ...) are LEGITIMATE features here (T is
complete); what is forbidden is any T+1 / future / placement signal.

Supabase is READ-ONLY. No database modifications.
"""
from __future__ import annotations

from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Root paths
# ──────────────────────────────────────────────────────────────────────────────
V2_ROOT = Path(__file__).resolve().parent            # ml/v2/m3_at_risk_prediction/
ML_ROOT = V2_ROOT.parent.parent                       # ml/
ARTIFACT_DIR = V2_ROOT / "artifacts" / "models"
REPORT_DIR = V2_ROOT / "reports"
DATA_CACHE_DIR = V2_ROOT / "data" / "cache"

# ──────────────────────────────────────────────────────────────────────────────
# Model artifact
# ──────────────────────────────────────────────────────────────────────────────
MODEL_NAME = "m3_v2_at_risk"
MODEL_FILE = ARTIFACT_DIR / f"{MODEL_NAME}.joblib"
MODEL_VERSION = "2.0"

# ──────────────────────────────────────────────────────────────────────────────
# Reproducibility
# ──────────────────────────────────────────────────────────────────────────────
RANDOM_STATE = 42
N_FOLDS = 5            # GroupKFold by student_id
N_SEEDS = 3            # model selection seeds

# ──────────────────────────────────────────────────────────────────────────────
# Target (binary classification)
# ──────────────────────────────────────────────────────────────────────────────
TARGET_AT_RISK = "is_at_risk_next_sem"
TARGETS = [TARGET_AT_RISK]

# Academic-risk result codes that flag at-risk (the presence of ATKT/backlogs)
AT_RISK_RESULTS = frozenset({"FAIL", "ATKT"})

# ──────────────────────────────────────────────────────────────────────────────
# Cohort / temporal contract
# ──────────────────────────────────────────────────────────────────────────────
COHORT_ID_PREFIX = "STU6A"
COHORT_DIVISION = "6A"

# Observation semesters T whose next-semester T+1 is a NORMAL academic semester.
# T=7 -> semester 8 (internship, 1 subject, all PASS) is excluded as a target;
# T=8 has no T+1. So valid observation semesters are 1..6.
VALID_OBSERVATION_SEMESTERS = [1, 2, 3, 4, 5, 6]
TRAINING_TRANSITIONS = [1, 2, 3, 4, 5, 6]     # observation T -> target T+1 in {2..7}
TEMPORAL_HOLDOUT_TRANSITION = 6               # hold out T=6 -> predict semester 7
MAX_ACADEMIC_SEMESTER = 7                     # last semester whose outcome is a comparable target

# ──────────────────────────────────────────────────────────────────────────────
# Prediction point
# ──────────────────────────────────────────────────────────────────────────────
PREDICTION_POINT = (
    "After the student's semester T has completed (all T outcomes known), "
    "estimate the probability they enter an academic-risk state (backlog/ATKT) "
    "in their NEXT academic semester T+1. No T+1 information is used in features."
)

# ──────────────────────────────────────────────────────────────────────────────
# Feature tiers (all T-only; see m3_v2_feature_contract.md for rationale)
# ──────────────────────────────────────────────────────────────────────────────

# Tier 1A: Current-semester (T) outcomes + structural signals (semester_summary).
# T is complete, so these are legitimate predictors of T+1 risk.
TIER1_SEM_SUMMARY = [
    "semester_sgpa",                # T SGPA (lower -> more risk)
    "semester_percentage",          # T percentage
    "semester_total_marks",         # T marks
    "semester_attendance_percentage",  # T attendance
    "backlog_count",                # T backlogs (past attainment)
    "cumulative_backlog_events",    # T cumulative
    "credits_registered",           # T credits
    "credits_earned",               # T earned credits
    "subjects_registered",          # T subject load
]

# Tier 1B: Point-in-time prior history (semesters <= T)
TIER1_PRIOR_HISTORY = [
    "previous_sem_sgpa",            # SGPA at T-1
    "sgpa_drift",                   # SGPA(T) - SGPA(T-1); NaN at sem 1
    "sgpa_rolling_mean_3",          # trailing 3-semester SGPA mean
    "previous_sem_backlog_count",   # backlogs at T-1
    "backlog_change",               # backlog(T) - backlog(T-1)
    "attendance_aggregate_pct",     # aggregate attendance
]

# Tier 1C: Subject-level aggregates at T (performance/enrollment)
TIER1_SUBJECT_AGG = [
    "subj_internal_marks_mean",
    "subj_internal_marks_std",
    "subj_mid_sem_marks_mean",
    "subj_end_sem_marks_mean",
    "subj_end_sem_marks_std",
    "subj_assignment_score_mean",
    "subj_quiz_avg_marks_mean",
    "subj_submission_delay_mean",
    "subj_pre_endsem_pct_mean",
    "subj_failed_subjects_count",   # count of T subjects with grade F / poor end marks
]

# Tier 1D: Attendance aggregates at T (attendance_weekly)
TIER1_ATTENDANCE_AGG = [
    "att_tsem_total_pct",           # 100 * SUM(attended)/SUM(held) across T subject-weeks
    "att_tsem_low_pct_weeks",       # fraction of rows with low-attendance flag
    "att_tsem_velocity_mean",       # mean attendance_velocity
]

# Tier 1E: Learning-activity aggregates at T (student_learning_activity)
TIER1_LEARNING_AGG = [
    "learn_tsem_volume_total",
    "learn_tsem_engagement_mean",
    "learn_tsem_completion_mean",
    "learn_tsem_late_mean",
]

# Tier 1F: Student / lifestyle metadata (T-anchored)
TIER1_STUDENT_META = [
    "gender",                       # -> is_male
    "semester_no",                  # observation semester T (1..6)
    "mental_stress_level",          # -> stress_ordinal
    "study_hours_per_week",         # lifestyle survey at T
]

ALL_FEATURE_NAMES = (
    TIER1_SEM_SUMMARY
    + TIER1_PRIOR_HISTORY
    + TIER1_SUBJECT_AGG
    + TIER1_ATTENDANCE_AGG
    + TIER1_LEARNING_AGG
    + TIER1_STUDENT_META
)

# ──────────────────────────────────────────────────────────────────────────────
# Leakage policy (M3-SPECIFIC, NOT M1/M2's list)
#
# Forbids any T+1 (next-semester) outcome column, any future/derived signal,
# and any placement (post-graduation) column. Current-T outcome columns are
# legitimate features (T complete) and are NOT in this list.
# ──────────────────────────────────────────────────────────────────────────────
FORBIDDEN_FEATURES = frozenset([
    # T+1 outcome columns (the target domain)
    "is_at_risk_next_sem",         # the M3 target itself
    "next_semester_sgpa",
    "next_semester_percentage",
    "next_semester_marks",
    "next_semester_total_marks",
    "next_semester_grade",
    "next_semester_result",
    "next_semester_attendance_percentage",
    "next_semester_backlog_count",
    "next_semester_rank",
    "next_backlog_count",
    "next_result",
    # Any lagged/derived T+1 signal
    "next_sem_sgpa_shift",
    "next_sem_attendance",
    "next_cumulative_backlog_events",
    # Post-graduation (future leakage by definition)
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
CATEGORICAL_FEATURES = []

# ──────────────────────────────────────────────────────────────────────────────
# Baselines
# ──────────────────────────────────────────────────────────────────────────────
BASELINE_NAMES = ["majority_class", "prior_backlog_rule"]

# Simple, defensible academic-risk baseline: predict a student is at-risk if
# they already carry a backlog at T (prior attainment), mirrored against the
# true T+1 label. This is a strong, hard-to-beat naive prior — if ML cannot
# beat it on the held-out semester, M3 V2 is NOT READY.
PRIOR_BACKLOG_RULE_SOURCE = "backlog_count"   # current-T backlog

# ──────────────────────────────────────────────────────────────────────────────
# Model candidates + selection
# ──────────────────────────────────────────────────────────────────────────────
MODEL_ALGORITHMS = ["logistic_regression", "random_forest", "hist_gbm", "xgboost"]

# Classification-specific selection: maximize F1 on positive class from CV, with
# secondary preference for PR-AUC; threshold tuned on validation data only.
IMBALANCE_HANDLING = "class_weight=balanced"   # never global oversampling

# Positive-region decision: threshold is selected on GROUP-VALIDATION data to
# maximise recall subject to a precision floor, NOT on the final temporal holdout.
THRESHOLD_TARGET_RECALL = 0.50     # at-least recall floor for threshold search
THRESHOLD_MIN_PRECISION = 0.15     # precision floor to avoid junk positive deluge