"""M1 v2 — Feature Builder: point-in-time feature engineering.

Constructs the M1 feature matrix from the raw Supabase tables using
correct multi-table joins. All joins use foreign keys, not positional
alignment.

Grain: (student_id, subject_id, semester_no) — one row per prediction target.

Point-in-time contract:
  - Only information available BEFORE the end-semester exam is used.
  - internal_marks, mid_sem_marks: recorded before end-exam ✅
  - assignment_score, quiz_avg_marks: recorded during semester ✅
  - attendance_weekly: all 8 weeks recorded before end-exam ✅
  - learning_activity: all 8 weeks recorded before end-exam ✅
  - prior semester aggregates: from completed semesters < T ✅
  - lifestyle survey: recorded at semester start/during ✅

Forbidden columns are explicitly excluded and verified.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .. import config


# ──────────────────────────────────────────────────────────────────────────────
# Join integrity checks
# ──────────────────────────────────────────────────────────────────────────────

def check_joins(tables: dict[str, pd.DataFrame]) -> dict:
    """Verify join integrity before building features.

    Returns a dict with 'pass' (bool) and 'checks' (list of findings).
    Raises ValueError if any critical check fails.
    """
    findings = []
    ok = True

    perf = tables["performance"]
    enr = tables["enrollment"]
    stu = tables["students"]

    # 1. FK: performance → enrollment (enrollment_record_id)
    perf_enr_ids = set(perf["enrollment_record_id"])
    enr_ids = set(enr["enrollment_record_id"])
    orphans = perf_enr_ids - enr_ids
    findings.append({
        "check": "fk_performance_enrollment",
        "pass": len(orphans) == 0,
        "orphan_count": len(orphans),
    })
    if orphans:
        ok = False

    # 2. Grain: no duplicate (student_id, subject_id, semester_no) in performance
    dup = perf.duplicated(subset=["student_id", "subject_id", "semester_no"]).sum()
    findings.append({
        "check": "grain_uniqueness_performance",
        "pass": int(dup) == 0,
        "duplicate_count": int(dup),
    })
    if dup:
        ok = False

    # 3. Student coverage: all performance students exist in students table
    perf_students = set(perf["student_id"])
    stu_students = set(stu["student_id"])
    missing = perf_students - stu_students
    findings.append({
        "check": "fk_performance_students",
        "pass": len(missing) == 0,
        "missing_count": len(missing),
    })
    if missing:
        ok = False

    # 4. Row counts
    findings.append({"check": "row_count_performance", "count": len(perf)})
    findings.append({"check": "row_count_enrollment", "count": len(enr)})
    findings.append({"check": "row_count_students", "count": len(stu)})

    # 5. Expected 6A count
    expected_6a = perf[perf["student_id"].str.startswith("STU6A")].shape[0]
    findings.append({
        "check": "6a_performance_rows",
        "expected_approx": 68400,
        "actual": expected_6a,
        "pass": expected_6a >= 60000,
    })

    result = {"pass": ok, "checks": findings}
    if not ok:
        raise ValueError(f"Join integrity check FAILED: {json.dumps(result, indent=2)}")
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Attendance weekly aggregation (per enrollment_record_id)
# ──────────────────────────────────────────────────────────────────────────────

def _aggregate_attendance(attendance_weekly: pd.DataFrame) -> pd.DataFrame:
    """Aggregate weekly attendance to per-enrollment level.

    Produces:
        att_total_pct         : 100 * SUM(classes_attended) / SUM(classes_held)
        att_rolling_4w_mean   : mean of attendance_rolling_4w across all weeks
        att_velocity_latest   : attendance_velocity of the last available week
        att_low_pct_weeks     : fraction of weeks with low_attendance_flag=True

    Uses SUM(attended)/SUM(held) — not average of percentages — to avoid
    weighting bias from weeks with few classes.
    """
    aw = attendance_weekly.copy()
    # Ensure numerics
    for col in ["classes_held", "classes_attended", "attendance_percentage",
                "attendance_velocity", "attendance_rolling_4w"]:
        aw[col] = pd.to_numeric(aw[col], errors="coerce")

    # Aggregate by enrollment_record_id
    grp = aw.groupby("enrollment_record_id")

    # Compute latest velocity separately (pandas 3.x: no include_groups in apply)
    latest_velocity = (
        aw.sort_values("week_number")
          .groupby("enrollment_record_id")["attendance_velocity"]
          .last()
    )

    att_agg = pd.DataFrame({
        "att_classes_held": grp["classes_held"].sum(),
        "att_classes_attended": grp["classes_attended"].sum(),
        "att_rolling_4w_sum": grp["attendance_rolling_4w"].sum(),
        "att_rolling_4w_count": grp["attendance_rolling_4w"].count(),
        "att_low_flag_count": grp["low_attendance_flag"].sum(),
        "att_total_weeks": grp["week_number"].count(),
    }).reset_index()

    att_agg = att_agg.merge(
        latest_velocity.rename("att_velocity_latest").reset_index(),
        on="enrollment_record_id", how="left"
    )

    att_agg["att_total_pct"] = (
        100.0 * att_agg["att_classes_attended"] / att_agg["att_classes_held"].clip(lower=1)
    )
    att_agg["att_rolling_4w_mean"] = (
        att_agg["att_rolling_4w_sum"] / att_agg["att_rolling_4w_count"].clip(lower=1)
    )
    att_agg["att_low_pct_weeks"] = (
        att_agg["att_low_flag_count"] / att_agg["att_total_weeks"].clip(lower=1)
    )

    return att_agg[[
        "enrollment_record_id",
        "att_total_pct",
        "att_rolling_4w_mean",
        "att_velocity_latest",
        "att_low_pct_weeks",
    ]]


# ──────────────────────────────────────────────────────────────────────────────
# Learning activity aggregation (per enrollment_record_id)
# ──────────────────────────────────────────────────────────────────────────────

def _aggregate_learning(learning_activity: pd.DataFrame) -> pd.DataFrame:
    """Aggregate weekly learning activity to per-enrollment level.

    Produces:
        activity_volume_total          : SUM(activity_volume) across weeks
        avg_engagement_consistency     : AVG(engagement_consistency)
        avg_assessment_completion_rate : AVG(assessment_completion_rate)
        avg_late_submission_rate       : AVG(late_submission_rate)

    These are OULAD-inspired behavioral features adapted to KenexAI data.
    No OULAD student IDs or labels are used.
    Mathematical definition:
        activity_volume_total = sum of weekly activity_volume counts
        engagement_consistency = from DB; pre-computed per-week 0–1
        assessment_completion_rate = from DB; pre-computed per-week 0–1
        late_submission_rate = from DB; pre-computed per-week 0–1
    """
    la = learning_activity.copy()
    for col in ["activity_volume", "engagement_consistency",
                "assessment_completion_rate", "late_submission_rate"]:
        la[col] = pd.to_numeric(la[col], errors="coerce")

    grp = la.groupby("enrollment_record_id")
    learn_agg = pd.DataFrame({
        "activity_volume_total": grp["activity_volume"].sum(),
        "avg_engagement_consistency": grp["engagement_consistency"].mean(),
        "avg_assessment_completion_rate": grp["assessment_completion_rate"].mean(),
        "avg_late_submission_rate": grp["late_submission_rate"].mean(),
    }).reset_index()

    return learn_agg


# ──────────────────────────────────────────────────────────────────────────────
# Prior semester aggregates (from student_semester_summary, sems < T)
# ──────────────────────────────────────────────────────────────────────────────

def _build_prior_aggregates(semester_summary: pd.DataFrame) -> pd.DataFrame:
    """Build per (student_id, semester_no) prior-history features.

    For each (student_id, semester_no=T), aggregates from semesters < T.

    Features:
        prior_avg_sgpa         : mean SGPA from completed sems < T
        sgpa_drift_latest      : sgpa_drift from the most recent completed sem < T
        prior_backlog_cumulative : cumulative_backlog_events at sem T-1
        prior_avg_attendance   : mean semester_attendance_percentage < T
        prior_n_sems           : number of completed prior semesters

    NaN is produced for semester 1 (no prior history) — handled by imputer.
    """
    ss = semester_summary.copy()
    for col in ["semester_sgpa", "semester_percentage", "semester_attendance_percentage",
                "sgpa_drift", "cumulative_backlog_events"]:
        ss[col] = pd.to_numeric(ss[col], errors="coerce")

    # A semester counts as completed only when its result is published
    # (sgpa > 0 AND percentage > 0). Placeholder rows for in-progress
    # semesters use 0.0 for both and must not pollute prior-history features.
    ss["_completed"] = (ss["semester_sgpa"] > 0) & (ss["semester_percentage"] > 0)

    results = []
    for student_id, grp in ss.sort_values("semester_no").groupby("student_id"):
        semesters = sorted(grp["semester_no"].unique())
        for sem_t in semesters:
            prior = grp[(grp["semester_no"] < sem_t) & grp["_completed"]]
            n_prior = len(prior)
            if n_prior == 0:
                row = {
                    "student_id": student_id,
                    "semester_no": sem_t,
                    "prior_avg_sgpa": float("nan"),
                    "sgpa_drift_latest": float("nan"),
                    "prior_backlog_cumulative": float("nan"),
                    "prior_avg_attendance": float("nan"),
                    "prior_n_sems": 0,
                }
            else:
                last_row = prior.sort_values("semester_no").iloc[-1]
                row = {
                    "student_id": student_id,
                    "semester_no": sem_t,
                    "prior_avg_sgpa": float(prior["semester_sgpa"].mean()),
                    "sgpa_drift_latest": float(last_row.get("sgpa_drift", float("nan"))
                                               if pd.notna(last_row.get("sgpa_drift"))
                                               else float("nan")),
                    "prior_backlog_cumulative": float(last_row.get("cumulative_backlog_events", 0)
                                                      if pd.notna(last_row.get("cumulative_backlog_events"))
                                                      else 0.0),
                    "prior_avg_attendance": float(
                        prior["semester_attendance_percentage"].mean()
                        if "semester_attendance_percentage" in prior.columns
                        else float("nan")
                    ),
                    "prior_n_sems": n_prior,
                }
            results.append(row)

    return pd.DataFrame(results)


# ──────────────────────────────────────────────────────────────────────────────
# Lifestyle features (current semester)
# ──────────────────────────────────────────────────────────────────────────────

def _prepare_lifestyle(lifestyle: pd.DataFrame) -> pd.DataFrame:
    """Select and clean lifestyle survey features for join."""
    ls = lifestyle[["student_id", "semester_no",
                    "study_hours_per_week", "mental_stress_level"]].copy()
    ls["study_hours_per_week"] = pd.to_numeric(ls["study_hours_per_week"], errors="coerce")
    return ls


# ──────────────────────────────────────────────────────────────────────────────
# Main feature builder
# ──────────────────────────────────────────────────────────────────────────────

def build_feature_matrix(tables: dict[str, pd.DataFrame],
                          include_tier2: bool = True) -> pd.DataFrame:
    """Build the M1 v2 feature matrix from raw tables.

    Grain: (student_id, subject_id, semester_no) — one row per performance record.

    Join sequence:
        performance (fact table, 68,400 rows)
          → LEFT JOIN enrollment (1:1 via enrollment_record_id)
          → LEFT JOIN students (many:1 via student_id)
          → LEFT JOIN att_agg (1:1 via enrollment_record_id)
          → LEFT JOIN learn_agg (1:1 via enrollment_record_id)
          → LEFT JOIN lifestyle (many:1 via student_id + semester_no) [optional]
          → LEFT JOIN prior_aggregates (many:1 via student_id + semester_no) [tier2]

    Returns a DataFrame with all feature columns + target + student_id + identifiers.
    DOES NOT include forbidden/leakage columns.
    """
    perf = tables["performance"].copy()
    enr = tables["enrollment"].copy()
    stu = tables["students"].copy()
    att_weekly = tables["attendance_weekly"].copy()
    learn_act = tables["learning_activity"].copy()
    sem_summary = tables["semester_summary"].copy()
    lifestyle = tables["lifestyle"].copy()

    # Ensure numeric types for key columns
    for col in ["internal_marks", "mid_sem_marks", "end_sem_marks",
                "assignment_score", "quiz_avg_marks", "submission_delay_days",
                "pre_endsem_assessment_pct"]:
        if col in perf.columns:
            perf[col] = pd.to_numeric(perf[col], errors="coerce")

    n_start = len(perf)
    print(f"  Starting rows (performance): {n_start:,}")

    # ── Step 1: Join enrollment for credits, subject_type ──────────────────────
    enr_cols = ["enrollment_record_id", "credits", "subject_type"]
    fact = perf.merge(
        enr[enr_cols],
        on="enrollment_record_id",
        how="left",
        validate="many_to_one",
    )
    assert len(fact) == n_start, f"Row count changed after enrollment join: {len(fact)} != {n_start}"
    print(f"  After enrollment join: {len(fact):,} rows (expected {n_start:,})")

    # ── Step 2: Join student metadata ─────────────────────────────────────────
    stu_cols = ["student_id", "gender", "admission_type", "admission_quota", "category"]
    fact = fact.merge(
        stu[stu_cols],
        on="student_id",
        how="left",
        validate="many_to_one",
    )
    assert len(fact) == n_start, f"Row count changed after students join: {len(fact)} != {n_start}"
    print(f"  After students join: {len(fact):,} rows")

    # ── Step 3: Aggregate attendance_weekly ────────────────────────────────────
    att_agg = _aggregate_attendance(att_weekly)
    fact = fact.merge(att_agg, on="enrollment_record_id", how="left")
    assert len(fact) == n_start, f"Row count changed after attendance join: {len(fact)} != {n_start}"
    print(f"  After attendance_weekly join: {len(fact):,} rows")

    # ── Step 4: Aggregate learning activity ────────────────────────────────────
    learn_agg = _aggregate_learning(learn_act)
    fact = fact.merge(learn_agg, on="enrollment_record_id", how="left")
    assert len(fact) == n_start, f"Row count changed after learning join: {len(fact)} != {n_start}"
    print(f"  After learning_activity join: {len(fact):,} rows")

    # ── Step 5: Lifestyle survey (current semester) ────────────────────────────
    ls = _prepare_lifestyle(lifestyle)
    fact = fact.merge(ls, on=["student_id", "semester_no"], how="left")
    assert len(fact) == n_start, f"Row count changed after lifestyle join: {len(fact)} != {n_start}"
    print(f"  After lifestyle join: {len(fact):,} rows")

    # ── Step 6: Prior semester aggregates (Tier 2) ────────────────────────────
    if include_tier2:
        prior_agg = _build_prior_aggregates(sem_summary)
        fact = fact.merge(prior_agg, on=["student_id", "semester_no"], how="left")
        assert len(fact) == n_start, f"Row count changed after prior_agg join: {len(fact)} != {n_start}"
        print(f"  After prior_aggregates join: {len(fact):,} rows")

    # ── Step 7: Verify no forbidden columns (except target) leaked in ─────────
    # The fact table legitimately contains the TARGET column (end_sem_marks) for
    # training purposes. Only DERIVED/result columns are forbidden at this stage.
    # The feature selection step (select_features) enforces that the target is
    # never included in X.
    non_target_forbidden = config.FORBIDDEN_FEATURES - {config.TARGET}
    forbidden_found = [c for c in non_target_forbidden if c in fact.columns]
    if forbidden_found:
        raise ValueError(f"LEAKAGE DETECTED — derived/forbidden columns present: {forbidden_found}")
    print(f"  Leakage check: PASS — no derived/forbidden columns in fact table")

    # ── Step 8: Duplicate-grain check ─────────────────────────────────────────
    dup = fact.duplicated(subset=["student_id", "subject_id", "semester_no"]).sum()
    if dup > 0:
        raise ValueError(f"Duplicate (student, subject, semester) grains: {dup}")
    print(f"  Grain uniqueness check: PASS — 0 duplicates")

    print(f"  Final feature matrix: {len(fact):,} rows × {len(fact.columns)} columns")
    return fact


# ──────────────────────────────────────────────────────────────────────────────
# Dataset fingerprint (for artifact metadata)
# ──────────────────────────────────────────────────────────────────────────────

def fingerprint(df: pd.DataFrame) -> str:
    """Deterministic fingerprint of a DataFrame for provenance tracking."""
    h = hashlib.md5(
        pd.util.hash_pandas_object(df, index=True).values.tobytes()
    ).hexdigest()
    return h


def dataset_provenance(tables: dict[str, pd.DataFrame]) -> dict:
    """Record dataset provenance for artifact metadata."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "row_counts": {k: len(v) for k, v in tables.items()},
        "fingerprints": {k: fingerprint(v) for k, v in tables.items()},
        "cohort": "CSE_6A_1200",
        "student_prefix": config.COHORT_ID_PREFIX,
        "temporal_holdout_semester": config.TEMPORAL_HOLDOUT_SEMESTER,
        "training_semesters": config.TRAINING_SEMESTERS,
        "target": config.TARGET,
    }
