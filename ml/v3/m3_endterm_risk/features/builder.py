"""M3 v3 — Feature Builder: point-in-time same-semester features.

Builds features from MID-SEMESTER data only. The label is derived from
the SAME semester's end-term outcome (not T+1).

Grain: (student_id, observation_semester T) — one row per student-semester.

Point-in-time contract:
  - Features: mid-semester marks, internal assessments, attendance at T,
    prior history (semesters < T). NO end-semester marks/SGPA at T.
  - Label: is_at_risk_end_sem(T) from semester_result(T) and backlog_count(T).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .. import config


def _normalize_result(v):
    if v is None:
        return None
    s = str(v).strip().upper()
    return s if s else None


def check_joins(tables: dict[str, pd.DataFrame]) -> dict:
    """Verify per-student·semester completeness before building features."""
    results = []
    ss = tables["semester_summary"]
    ok = True

    # Grain uniqueness
    dup = ss.duplicated(subset=["student_id", "semester_no"]).sum()
    results.append({"check": "grain_uniqueness_semester_summary", "pass": int(dup) == 0})
    if dup:
        ok = False

    # 6A student count
    n_stu = int((tables["students"]["student_id"].str.startswith("STU6A")).sum())
    results.append({"check": "6a_student_count", "expected": 1200, "actual": n_stu, "pass": n_stu >= 1190})
    if n_stu < 1190:
        ok = False

    # Row counts
    for tbl in ["students", "semester_summary", "performance"]:
        results.append({"check": f"row_count_{tbl}", "count": int(len(tables[tbl]))})

    out = {"pass": ok, "checks": results}
    if not ok:
        import json
        raise ValueError(f"M3 v3 integrity check FAILED: {json.dumps(out, indent=2)}")
    return out


def _aggregate_subjects_midsem(performance: pd.DataFrame) -> pd.DataFrame:
    """Aggregate subject performance to (student_id, semester_no) using MID-SEM data only.

    Uses internal_marks and mid_sem_marks (available at mid-semester).
    Does NOT use end_sem_marks (forbidden at prediction time).
    """
    p = performance.copy()
    for col in ["internal_marks", "mid_sem_marks", "assignment_score",
                "quiz_avg_marks", "submission_delay_days", "pre_endsem_assessment_pct"]:
        p[col] = pd.to_numeric(p[col], errors="coerce")

    g = p.groupby(["student_id", "semester_no"])
    agg = pd.DataFrame({
        "subj_mid_sem_marks_mean": g["mid_sem_marks"].mean(),
        "subj_mid_sem_marks_std": g["mid_sem_marks"].std(),
        "subj_internal_marks_mean": g["internal_marks"].mean(),
        "subj_internal_marks_std": g["internal_marks"].std(),
        "subj_assignment_score_mean": g["assignment_score"].mean(),
        "subj_quiz_avg_marks_mean": g["quiz_avg_marks"].mean(),
        "subj_submission_delay_mean": g["submission_delay_days"].mean(),
        "subj_pre_endsem_pct_mean": g["pre_endsem_assessment_pct"].mean(),
    })
    return agg.reset_index()


def _aggregate_attendance(attendance_weekly: pd.DataFrame) -> pd.DataFrame:
    """Aggregate weekly attendance to (student_id, semester_no) at T."""
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


def _compute_prior_history(ss: pd.DataFrame) -> pd.DataFrame:
    """Compute Tier 1E prior-history features from semester_summary.

    For each observation semester T, prior-history features use data from
    semesters < T only (point-in-time safe).
    """
    ss = ss.sort_values(["student_id", "semester_no"]).copy()

    for col in ["semester_sgpa", "backlog_count", "semester_attendance_percentage",
                "cumulative_backlog_events"]:
        if col in ss.columns:
            ss[col] = pd.to_numeric(ss[col], errors="coerce")

    # Per-student rolling computations
    results = []
    for sid, grp in ss.groupby("student_id"):
        grp = grp.sort_values("semester_no").copy()
        sgpa = grp["semester_sgpa"]
        bc = grp["backlog_count"].fillna(0)
        att = grp["semester_attendance_percentage"]

        # Previous semester SGPA
        prev_sgpa = sgpa.shift(1)
        # SGPA drift (T-1 minus T-2)
        sgpa_drift = (sgpa.shift(1) - sgpa.shift(2)).round(2)
        # Rolling mean of completed semesters (min_periods=1)
        sgpa_completed = sgpa.mask(sgpa <= 0).ffill()
        roll3 = sgpa_completed.shift(1).rolling(3, min_periods=1).mean().round(3)
        # Previous backlog
        prev_bc = bc.shift(1).fillna(0)
        # Backlog change
        bc_change = (bc.shift(1) - bc.shift(2)).fillna(0).round(1)
        # Cumulative backlog events up to T-1
        cum_bc = bc.shift(1).cumsum().fillna(0)
        # Attendance aggregate (T-1)
        att_agg = att.shift(1).round(3)

        grp["previous_sem_sgpa"] = prev_sgpa
        grp["sgpa_drift"] = sgpa_drift
        grp["sgpa_rolling_mean_3"] = roll3
        grp["previous_sem_backlog_count"] = prev_bc
        grp["backlog_change"] = bc_change
        grp["cumulative_backlog_events"] = cum_bc
        grp["attendance_aggregate_pct"] = att_agg

        results.append(grp)

    return pd.concat(results, ignore_index=True)


def build_feature_matrix(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build the M3 v3 feature matrix.

    Returns a DataFrame at grain (student_id, observation_semester T) with all
    feature columns PLUS the label column `is_at_risk_end_sem`.
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

    # ── Construct same-semester label ──────────────────────────────────────
    ss = ss.sort_values(["student_id", "semester_no"]).copy()

    def _risk_end_sem(row):
        r = _normalize_result(row.get("semester_result"))
        bc = row.get("backlog_count")
        bc = None if bc is None else float(bc)
        if r is None and bc is None:
            return None
        return int((r in config.AT_RISK_RESULTS) or (bc is not None and bc > 0))

    ss[config.TARGET_AT_RISK] = ss.apply(_risk_end_sem, axis=1)

    n_total = len(ss)
    print(f"  semester_summary rows: {n_total:,}")

    # Keep only training semesters
    base = ss[ss["semester_no"].isin(config.TRAINING_SEMESTERS)].copy()
    print(f"  eligible semesters T={config.TRAINING_SEMESTERS}: {len(base):,}")

    # Drop rows with no label
    base = base.dropna(subset=[config.TARGET_AT_RISK])
    print(f"  after dropping missing labels: {len(base):,}")

    n_start = len(base)

    # ── Compute prior history features ─────────────────────────────────────
    base = _compute_prior_history(base)

    # ── Join subject mid-semester aggregates ────────────────────────────────
    subj_agg = _aggregate_subjects_midsem(perf)
    base = base.merge(subj_agg, on=["student_id", "semester_no"], how="left", validate="many_to_one")
    assert len(base) == n_start

    # ── Join attendance aggregate ───────────────────────────────────────────
    if len(att) > 0:
        att_agg = _aggregate_attendance(att)
        base = base.merge(att_agg, on=["student_id", "semester_no"], how="left", validate="many_to_one")
    else:
        for c in ["att_tsem_total_pct", "att_tsem_low_pct_weeks"]:
            base[c] = float("nan")
    assert len(base) == n_start

    # ── Join learning aggregate ─────────────────────────────────────────────
    if len(learn) > 0:
        learn_agg = _aggregate_learning(learn)
        base = base.merge(learn_agg, on=["student_id", "semester_no"], how="left", validate="many_to_one")
    else:
        for c in ["learn_tsem_volume_total", "learn_tsem_engagement_mean",
                   "learn_tsem_completion_mean", "learn_tsem_late_mean"]:
            base[c] = float("nan")
    assert len(base) == n_start

    # ── Join lifestyle ──────────────────────────────────────────────────────
    if len(life) > 0:
        life_c = life[["student_id", "semester_no", "study_hours_per_week", "mental_stress_level"]].copy()
        life_c["study_hours_per_week"] = pd.to_numeric(life_c["study_hours_per_week"], errors="coerce")
        base = base.merge(life_c, on=["student_id", "semester_no"], how="left", validate="many_to_one")
    else:
        base["study_hours_per_week"] = float("nan")
        base["mental_stress_level"] = "Medium"
    assert len(base) == n_start

    # ── Join student gender ─────────────────────────────────────────────────
    stu_c = stu[["student_id", "gender"]].copy()
    base = base.merge(stu_c, on="student_id", how="left", validate="many_to_one")
    assert len(base) == n_start

    # ── Drop forbidden end-semester columns from the base ──────────────────
    # These come from semester_summary but are NOT legitimate features for
    # same-semester mid-sem → end-term prediction.
    # Keep the target column (needed for y) — it's excluded by select_features.
    _keep = {config.TARGET_AT_RISK}
    cols_to_drop = [c for c in config.FORBIDDEN_FEATURES if c in base.columns and c not in _keep]
    if cols_to_drop:
        base = base.drop(columns=cols_to_drop)
        print(f"  Dropped forbidden end-semester columns: {cols_to_drop}")

    # ── Leakage check ───────────────────────────────────────────────────────
    _allowed = {config.TARGET_AT_RISK}
    forbidden_found = [c for c in config.FORBIDDEN_FEATURES
                       if c in base.columns and c not in _allowed]
    if forbidden_found:
        raise ValueError(f"M3 v3 LEAKAGE DETECTED: {forbidden_found}")
    print(f"  Leakage check: PASS — no forbidden end-semester columns")

    # ── Grain uniqueness ────────────────────────────────────────────────────
    dup = base.duplicated(subset=["student_id", "semester_no"]).sum()
    if dup > 0:
        raise ValueError(f"M3 v3 duplicate grains: {dup}")
    print(f"  Grain uniqueness: PASS")

    print(f"  Final M3 v3 feature matrix: {len(base):,} rows x {len(base.columns)} columns")
    return base


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
        "training_semesters": config.TRAINING_SEMESTERS,
        "temporal_holdout_semester": config.TEMPORAL_HOLDOUT_SEMESTER,
        "target": config.TARGET_AT_RISK,
    }
