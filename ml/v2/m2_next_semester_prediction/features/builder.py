"""M2 v2 — Feature Builder: point-in-time T → T+1 feature engineering.

Grain: (student_id, observation_semester T) — one row per student-semester
transition for which a next-semester target (T+1 in {2..7}) exists.

Point-in-time contract:
  - Features derive ONLY from semester T (and prior history at T).
  - T is a COMPLETED semester, so its SGPA/percentage/marks are legitimate
    predictors (unlike M1, where the current semester's outcome was the target
    and therefore forbidden).
  - The target is semester T+1's semester_sgpa / semester_percentage. It is
    computed by a within-student forward shift and moved to `y` — it never
    appears in `X`.

Forbidden/leakage contract:
  - T+1 outcome columns (next_semester_*) must NEVER be in features.
  - The M1 v2 forbidden list is deliberately NOT reused (M2's feature domain
    includes current-T outcomes).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .. import config


# ──────────────────────────────────────────────────────────────────────────────
# Join / integrity checks
# ──────────────────────────────────────────────────────────────────────────────

def check_joins(tables: dict[str, pd.DataFrame]) -> dict:
    """Verify per-student·semester completeness before building features.

    Asserts every 6A student has a semester_summary row for every semester
    1..8 and no grain duplicates. Returns dict with 'pass' and 'checks'.
    """
    results = []
    ss = tables["semester_summary"]
    ok = True

    # 1. Grain uniqueness in semester_summary
    dup = ss.duplicated(subset=["student_id", "semester_no"]).sum()
    results.append({"check": "grain_uniqueness_semester_summary", "pass": int(dup) == 0, "n": int(dup)})
    if dup:
        ok = False

    # 2. Full coverage: 8 semesters per student
    counts = ss.groupby("student_id")["semester_no"].nunique()
    incomplete = (counts < 8).sum()
    results.append({"check": "all_students_reach_8_semesters", "pass": int(incomplete) == 0, "incomplete": int(incomplete)})
    if incomplete:
        ok = False

    # 3. Target availability rows
    n_target_avail = int((ss["target_available_if_completed"].astype(str).str.upper() == "TRUE").sum())
    results.append({"check": "target_available_rows", "count": n_target_avail})

    # 4. Row counts
    for tbl in ["students", "semester_summary", "performance", "attendance_weekly", "learning_activity", "lifestyle"]:
        results.append({"check": f"row_count_{tbl}", "count": int(len(tables[tbl]))})

    # 5. 6A coverage
    n_stu = int((tables["students"]["student_id"].str.startswith("STU6A")).sum())
    results.append({"check": "6a_student_count", "expected": 1200, "actual": n_stu, "pass": n_stu >= 1190})

    out = {"pass": ok, "checks": results}
    if not ok:
        raise ValueError(f"M2 v2 integrity check FAILED: {json.dumps(out, indent=2)}")
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Subject-level aggregates at semester T (per student)
# ──────────────────────────────────────────────────────────────────────────────

def _aggregate_subjects(performance: pd.DataFrame) -> pd.DataFrame:
    """Aggregate subject performance to (student_id, semester_no) at T.

    For each student·semester the mean (and std where meaningful) of the
    subject marks across that semester's subjects.
    """
    p = performance.copy()
    for col in ["internal_marks", "mid_sem_marks", "end_sem_marks",
                "assignment_score", "quiz_avg_marks", "submission_delay_days",
                "pre_endsem_assessment_pct"]:
        p[col] = pd.to_numeric(p[col], errors="coerce")

    g = p.groupby(["student_id", "semester_no"])
    agg = pd.DataFrame({
        "subj_internal_marks_mean": g["internal_marks"].mean(),
        "subj_internal_marks_std": g["internal_marks"].std(),
        "subj_mid_sem_marks_mean": g["mid_sem_marks"].mean(),
        "subj_end_sem_marks_mean": g["end_sem_marks"].mean(),
        "subj_end_sem_marks_std": g["end_sem_marks"].std(),
        "subj_assignment_score_mean": g["assignment_score"].mean(),
        "subj_quiz_avg_marks_mean": g["quiz_avg_marks"].mean(),
        "subj_submission_delay_mean": g["submission_delay_days"].mean(),
        "subj_pre_endsem_pct_mean": g["pre_endsem_assessment_pct"].mean(),
    })
    return agg.reset_index()


def _aggregate_attendance(attendance_weekly: pd.DataFrame) -> pd.DataFrame:
    """Aggregate weekly attendance to (student_id, semester_no) at T.

    att_tsem_total_pct     : 100 * SUM(attended)/SUM(held) across subject-weeks
    att_tsem_low_pct_weeks : fraction of subject-week rows flagged low
    att_tsem_velocity_mean : mean attendance_velocity across subject-weeks
    """
    a = attendance_weekly.copy()
    for col in ["classes_held", "classes_attended", "attendance_velocity"]:
        a[col] = pd.to_numeric(a[col], errors="coerce")
    a["low_flag"] = a["low_attendance_flag"].astype(str).str.upper() == "TRUE"

    g = a.groupby(["student_id", "semester_no"])
    held = g["classes_held"].sum()
    attended = g["classes_attended"].sum()
    agg = pd.DataFrame({
        "att_tsem_total_pct": 100.0 * attended / held.clip(lower=1),
        "att_tsem_low_pct_weeks": g["low_flag"].mean(),
        "att_tsem_velocity_mean": g["attendance_velocity"].mean(),
    }).reset_index()
    return agg


def _aggregate_learning(learning_activity: pd.DataFrame) -> pd.DataFrame:
    """Aggregate weekly learning activity to (student_id, semester_no) at T."""
    la = learning_activity.copy()
    for col in ["activity_volume", "engagement_consistency",
                "assessment_completion_rate", "late_submission_rate"]:
        la[col] = pd.to_numeric(la[col], errors="coerce")

    g = la.groupby(["student_id", "semester_no"])
    agg = pd.DataFrame({
        "learn_tsem_volume_total": g["activity_volume"].sum(),
        "learn_tsem_engagement_mean": g["engagement_consistency"].mean(),
        "learn_tsem_completion_mean": g["assessment_completion_rate"].mean(),
        "learn_tsem_late_mean": g["late_submission_rate"].mean(),
    })
    return agg.reset_index()


# ──────────────────────────────────────────────────────────────────────────────
# Main feature builder
# ──────────────────────────────────────────────────────────────────────────────

def build_feature_matrix(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build the M2 v2 feature matrix.

    Returns a DataFrame at grain (student_id, observation_semester T) with all
    feature columns PLUS the target columns `next_semester_sgpa` and
    `next_semester_percentage`. The targets are separated out in
    `select_features` (never in X).
    """
    ss = tables["semester_summary"].copy()
    stu = tables["students"].copy()
    perf = tables["performance"].copy()
    att = tables["attendance_weekly"].copy()
    learn = tables["learning_activity"].copy()
    life = tables["lifestyle"].copy()

    for col in ["semester_sgpa", "semester_percentage", "semester_total_marks",
                "semester_attendance_percentage", "backlog_count",
                "cumulative_backlog_events", "credits_registered", "credits_earned",
                "subjects_registered", "previous_sem_sgpa", "sgpa_drift",
                "sgpa_rolling_mean_3", "previous_sem_backlog_count",
                "backlog_change", "attendance_aggregate_pct"]:
        if col in ss.columns:
            ss[col] = pd.to_numeric(ss[col], errors="coerce")

    # Sort by student then semester and compute the T -> T+1 targets within student.
    ss = ss.sort_values(["student_id", "semester_no"]).copy()
    ss[config.TARGET_SGPA] = ss.groupby("student_id")["semester_sgpa"].shift(-1)
    ss[config.TARGET_PERCENTAGE] = ss.groupby("student_id")["semester_percentage"].shift(-1)
    ss["next_semester_no"] = ss["semester_no"] + 1

    n_total = len(ss)
    print(f"  semester_summary rows (students x sems): {n_total:,}")

    # Keep only eligible observation semesters T (those whose T+1 is a normal
    # academic semester, i.e. T in TRAINING_TRANSITIONS = 1..6).
    base = ss[ss["semester_no"].isin(config.TRAINING_TRANSITIONS)].copy()
    print(f"  eligible transitions (T=1..6): {len(base):,}")

    # Drop rows with no next-semester target (shouldn't happen for T<=6 but be safe)
    base = base.dropna(subset=[config.TARGET_SGPA, config.TARGET_PERCENTAGE])
    print(f"  after dropping missing targets: {len(base):,} (expected 7,200 = 1200x6)")

    n_start = len(base)

    # ── Join subject aggregates (many:1 via student_id + semester_no) ─────────
    subj_agg = _aggregate_subjects(perf)
    base = base.merge(subj_agg, on=["student_id", "semester_no"], how="left", validate="many_to_one")
    assert len(base) == n_start

    # ── Join attendance aggregate ─────────────────────────────────────────────
    att_agg = _aggregate_attendance(att)
    base = base.merge(att_agg, on=["student_id", "semester_no"], how="left", validate="many_to_one")
    assert len(base) == n_start

    # ── Join learning aggregate ───────────────────────────────────────────────
    learn_agg = _aggregate_learning(learn)
    base = base.merge(learn_agg, on=["student_id", "semester_no"], how="left", validate="many_to_one")
    assert len(base) == n_start

    # ── Join lifestyle (many:1 via student_id + semester_no) ──────────────────
    life_c = life[["student_id", "semester_no", "study_hours_per_week", "mental_stress_level"]].copy()
    life_c["study_hours_per_week"] = pd.to_numeric(life_c["study_hours_per_week"], errors="coerce")
    base = base.merge(life_c, on=["student_id", "semester_no"], how="left", validate="many_to_one")
    assert len(base) == n_start

    # ── Join student gender (many:1 via student_id) ───────────────────────────
    stu_c = stu[["student_id", "gender"]].copy()
    base = base.merge(stu_c, on="student_id", how="left", validate="many_to_one")
    assert len(base) == n_start

    # ── Forbidden-feature check (M2-specific) ─────────────────────────────────
    # The target columns are legitimately carried on the fact rows for `y`; they
    # are excluded from X by select_features + the leakage gate. Any OTHER
    # forbidden/derived column is a hard failure.
    _allowed_in_fact = set(config.TARGETS)
    forbidden_found = [c for c in config.FORBIDDEN_FEATURES
                       if c in base.columns and c not in _allowed_in_fact]
    if forbidden_found:
        raise ValueError(f"M2 LEAKAGE DETECTED — forbidden T+1 columns present: {forbidden_found}")
    print(f"  Leakage check (T+1 forbidden columns, targets excluded): PASS — none present")

    # ── Grain uniqueness check ────────────────────────────────────────────────
    dup = base.duplicated(subset=["student_id", "semester_no"]).sum()
    if dup > 0:
        raise ValueError(f"M2 duplicate (student, semester) grains: {dup}")
    print(f"  Grain uniqueness (student, observation_semester): PASS — 0 duplicates")

    print(f"  Final M2 v2 feature matrix: {len(base):,} rows x {len(base.columns)} columns")
    return base


# ──────────────────────────────────────────────────────────────────────────────
# Dataset fingerprint / provenance
# ──────────────────────────────────────────────────────────────────────────────

def fingerprint(df: pd.DataFrame) -> str:
    """Deterministic MD5 fingerprint for provenance tracking."""
    return hashlib.md5(
        pd.util.hash_pandas_object(df, index=True).values.tobytes()
    ).hexdigest()


def dataset_provenance(tables: dict[str, pd.DataFrame]) -> dict:
    """Record dataset provenance for artifact metadata."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "row_counts": {k: len(v) for k, v in tables.items()},
        "fingerprints": {k: fingerprint(v) for k, v in tables.items()},
        "cohort": "CSE_6A_1200",
        "student_prefix": config.COHORT_ID_PREFIX,
        "training_transitions": config.TRAINING_TRANSITIONS,
        "temporal_holdout_transition": config.TEMPORAL_HOLDOUT_TRANSITION,
        "targets": config.TARGETS,
    }