"""M3 v3 — Same-Semester End-Term Risk Prediction: configuration.

Predicts whether a student will enter an academic-risk state in the SAME
semester's end-term, using features available at mid-semester.

Task:
    INPUT:  Student information available after Mid-Sem examination
    TARGET: Whether the SAME semester's final/end-term outcome is at-risk

Label definition:
    is_at_risk_end_sem = 1 if semester_result(T) in ('FAIL','ATKT')
                         OR backlog_count(T) > 0
    (applied to the SAME semester T, NOT T+1)

Temporal contract:
    Features: mid-semester data at T + prior history
    Target:   end-semester outcome at T (same semester)
    FORBIDDEN: any end-semester marks, SGPA, percentage, total_marks at T

Business requirement:
    BBA: Semester 5 Mid-Sem → Semester 5 End-Term
    CSE: Semester 7 Mid-Sem → Semester 7 End-Term
"""
from __future__ import annotations

from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Root paths
# ──────────────────────────────────────────────────────────────────────────────
V3_ROOT = Path(__file__).resolve().parent            # ml/v3/m3_endterm_risk/
ML_ROOT = V3_ROOT.parent.parent                       # ml/
ARTIFACT_DIR = V3_ROOT / "artifacts" / "models"
REPORT_DIR = V3_ROOT / "reports"
DATA_CACHE_DIR = V3_ROOT / "data" / "cache"

# ──────────────────────────────────────────────────────────────────────────────
# Model artifact
# ──────────────────────────────────────────────────────────────────────────────
MODEL_NAME = "m3_v3_endterm_risk"
MODEL_FILE = ARTIFACT_DIR / f"{MODEL_NAME}.joblib"
MODEL_VERSION = "3.0"

# ──────────────────────────────────────────────────────────────────────────────
# Reproducibility
# ──────────────────────────────────────────────────────────────────────────────
RANDOM_STATE = 42
N_FOLDS = 5            # GroupKFold by student_id
N_SEEDS = 3            # model selection seeds

# ──────────────────────────────────────────────────────────────────────────────
# Target (binary classification)
# ──────────────────────────────────────────────────────────────────────────────
TARGET_AT_RISK = "is_at_risk_end_sem"
TARGETS = [TARGET_AT_RISK]

# Academic-risk result codes that flag at-risk
AT_RISK_RESULTS = frozenset({"FAIL", "ATKT"})

# ──────────────────────────────────────────────────────────────────────────────
# Cohort / temporal contract
# ──────────────────────────────────────────────────────────────────────────────
# Training uses the 6A cohort (1200 CSE students), semesters 1-7
COHORT_ID_PREFIX = "STU6A"
COHORT_DIVISION = "6A"

# Observation semesters T for which same-semester end-term data is available.
# In the 6A cohort, semesters 1-7 have complete end-semester marks.
# Semester 8 is internship-only (all PASS) and excluded.
VALID_OBSERVATION_SEMESTERS = [1, 2, 3, 4, 5, 6, 7]
TRAINING_SEMESTERS = [1, 2, 3, 4, 5, 6, 7]
TEMPORAL_HOLDOUT_SEMESTER = 7    # hold out T=7 for temporal validation
MAX_ACADEMIC_SEMESTER = 8        # CSE total semesters (semester 8 = internship)

# ──────────────────────────────────────────────────────────────────────────────
# Prediction point
# ──────────────────────────────────────────────────────────────────────────────
PREDICTION_POINT = (
    "After the student's mid-semester examinations at semester T, "
    "estimate the probability they enter an academic-risk state "
    "(backlog/ATKT) in the SAME semester's end-term. "
    "No end-semester information is used in features."
)

# ──────────────────────────────────────────────────────────────────────────────
# Feature tiers — MID-SEMESTER ONLY (end-semester FORBIDDEN)
# ──────────────────────────────────────────────────────────────────────────────

# Tier 1A: Mid-semester subject-level marks (available at prediction point)
TIER1_MIDSEM_SUBJECT = [
    "subj_mid_sem_marks_mean",       # average mid-sem marks across subjects
    "subj_mid_sem_marks_std",        # variability of mid-sem marks
    "subj_internal_marks_mean",      # average internal marks (pre mid-sem)
    "subj_internal_marks_std",       # variability of internal marks
]

# Tier 1B: Assessment & engagement signals available at mid-semester
TIER1_MIDSEM_ASSESSMENT = [
    "subj_assignment_score_mean",    # assignment scores (ongoing)
    "subj_quiz_avg_marks_mean",      # quiz marks (ongoing)
    "subj_submission_delay_mean",    # submission delays (ongoing)
    "subj_pre_endsem_pct_mean",      # pre-endsem assessment (mid-sem proxy)
]

# Tier 1C: Attendance at prediction point (mid-semester)
TIER1_MIDSEM_ATTENDANCE = [
    "semester_attendance_percentage",    # T attendance up to mid-sem
    "att_tsem_total_pct",               # computed attendance ratio
    "att_tsem_low_pct_weeks",           # fraction of low-attendance weeks
]

# Tier 1D: Learning activity (if available)
TIER1_MIDSEM_LEARNING = [
    "learn_tsem_volume_total",
    "learn_tsem_engagement_mean",
    "learn_tsem_completion_mean",
    "learn_tsem_late_mean",
]

# Tier 1E: Prior history (completed semesters before T)
TIER1_PRIOR_HISTORY = [
    "previous_sem_sgpa",            # SGPA at T-1
    "sgpa_drift",                   # SGPA(T-1) - SGPA(T-2); drift in recent trend
    "sgpa_rolling_mean_3",          # trailing 3-semester SGPA mean (up to T-1)
    "previous_sem_backlog_count",   # backlogs at T-1
    "backlog_change",               # backlog(T-1) - backlog(T-2)
    "cumulative_backlog_events",    # cumulative backlogs up to T-1
    "attendance_aggregate_pct",     # aggregate attendance up to T-1
]

# Tier 1F: Structural / enrollment signals (known at semester start)
TIER1_STRUCTURAL = [
    "credits_registered",           # T credits (enrollment load, known at start)
    "subjects_registered",          # T subject count (known at start)
]

# Tier 1G: Student metadata
TIER1_STUDENT_META = [
    "semester_no",                  # observation semester T
    "is_male",                      # encoded from gender
    "stress_ordinal",               # encoded from mental_stress_level
]

# Combined feature names (order matters for artifact)
ALL_FEATURE_NAMES = (
    TIER1_MIDSEM_SUBJECT
    + TIER1_MIDSEM_ASSESSMENT
    + TIER1_MIDSEM_ATTENDANCE
    + TIER1_MIDSEM_LEARNING
    + TIER1_PRIOR_HISTORY
    + TIER1_STRUCTURAL
    + TIER1_STUDENT_META
)

N_FEATURES = len(ALL_FEATURE_NAMES)

# ──────────────────────────────────────────────────────────────────────────────
# LEAKAGE POLICY — FORBIDDEN FEATURES (end-semester outcomes)
#
# These columns MUST NEVER appear in the feature matrix because they
# encode end-semester information that is not available at mid-semester.
# ──────────────────────────────────────────────────────────────────────────────
FORBIDDEN_FEATURES = frozenset([
    # Same-semester end-semester outcomes (the TARGET domain)
    "is_at_risk_end_sem",           # the target itself
    "semester_sgpa",                # T end-term SGPA
    "semester_percentage",          # T end-term percentage
    "semester_total_marks",         # T end-term total marks
    "semester_result",              # T end-term result
    "end_semester_grade",           # T end-term grade
    # Current-semester backlog count (= label definition, NOT a feature)
    "backlog_count",
    "credits_earned",               # end-semester outcome
    # Subject-level end-semester marks
    "subj_end_sem_marks_mean",
    "subj_end_sem_marks_std",
    "subj_failed_subjects_count",   # computed from end-term results
    # T+1 / next-semester (not applicable)
    "is_at_risk_next_sem",
    "next_semester_sgpa",
    "next_semester_percentage",
    "next_semester_marks",
    "next_semester_total_marks",
    "next_semester_grade",
    "next_semester_result",
    "next_semester_attendance_percentage",
    "next_semester_backlog_count",
    "next_backlog_count",
    "next_result",
    "next_sem_sgpa_shift",
    "next_sem_attendance",
    "next_cumulative_backlog_events",
    # Post-graduation (future leakage)
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

PRIOR_BACKLOG_RULE_SOURCE = "backlog_count"

# ──────────────────────────────────────────────────────────────────────────────
# Model candidates + selection
# ──────────────────────────────────────────────────────────────────────────────
MODEL_ALGORITHMS = ["logistic_regression", "random_forest", "hist_gbm", "xgboost"]

IMBALANCE_HANDLING = "class_weight=balanced"

THRESHOLD_TARGET_RECALL = 0.50
THRESHOLD_MIN_PRECISION = 0.10
