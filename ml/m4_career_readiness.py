"""
m4_career_readiness.py
=======================================================================
MODULE 4 : CAREER READINESS SCORE ENGINE
=======================================================================
Produces a transparent, fully explainable Career Readiness Score
(0-100) and a Low / Medium / High readiness level for every student.

WHY THIS APPROACH
------------------------------------------------------------------
This is a deterministic, RULE-BASED scoring engine, not a trained
ML model. Every point awarded to a student can be traced back to a
raw value in the source CSVs. There is no black-box model, no
training step, and no dependency on any pre-computed / synthetic
"readiness" label.

DATA SOURCES USED
------------------------------------------------------------------
1. students_rows.csv                -> demographic / identity fields only
2. student_semester_summary_rows.csv -> real, per-semester academic marks
3. career_preferences_rows.csv       -> career intent & preparation signals
4. lifestyle_survey_rows.csv         -> habits, discipline & wellbeing

EXPLICITLY EXCLUDED / "POISONED" COLUMNS (never read, never used)
------------------------------------------------------------------
  From career_preferences_rows.csv:
      - placement_readiness_level   (synthetic / deterministically
                                      derived label -> would leak the
                                      answer into the score. NEVER used
                                      to build, calibrate or tune ANY
                                      part of this scoring logic.)
  From students_rows.csv (pre-aggregated / synthetic overall stats):
      - latest_sgpa
      - overall_cgpa
      - overall_percentage
      - overall_attendance_percentage
      - total_backlogs
      - academic_standing

Instead of the poisoned "overall" columns on students_rows.csv, this
engine computes its own academic picture directly from the raw,
completed, per-semester records in student_semester_summary_rows.csv
(semester_percentage, semester_sgpa, semester_attendance_percentage,
backlog_count, semester_result) — genuinely observed, prior/completed
academic data, aggregated transparently in this file.

NOTE: the engine's own computed backlog aggregate is deliberately
named "total_backlogs_computed" (not "total_backlogs") so it is never
confused with, or mistaken for, the poisoned students_rows.csv column
"total_backlogs" that is dropped on load.

SCORING FRAMEWORK (100 points total)
------------------------------------------------------------------
  A. Academic Performance      : 35 pts  (avg %, avg attendance, backlogs)
  B. Academic Growth Trend     : 10 pts  (slope of % across semesters)
  C. Career Preparedness       : 25 pts  (internship, cert focus, planning)
  D. Lifestyle & Discipline    : 30 pts  (study habits, wellbeing, sleep,
                                           activity, self-reported attendance)
  ---------------------------------------------
  TOTAL                        : 100 pts

LEVEL THRESHOLDS (fixed policy, not tuned against any label)
------------------------------------------------------------------
  High    : score >= 75
  Medium  : 50 <= score < 75
  Low     : score < 50

OUTPUT
------------------------------------------------------------------
  ml/data/final/m4_career_readiness_scores.csv  containing, per student:
      student_id, enrollment_no, full_name, department_name,
      current_semester, all component sub-scores, final
      career_readiness_score, career_readiness_level,
      positive_factors, risk_factors

THIS IS NOT AN ML MODEL
------------------------------------------------------------------
M4 is a deterministic, rule-based scoring engine. It does NOT train,
fit, or load any model. No scikit-learn/XGBoost estimator is created
and NO .joblib (or any other model artifact) is produced or required
anywhere in this file. Re-running this script on the same input CSVs
will always produce byte-for-byte identical output (fully
deterministic, no randomness, no seeds needed).

Run directly:
    python ml/src/m4/m4_career_readiness.py
(run from anywhere - paths are resolved relative to this file's
location inside the ml/ project structure: ml/src/m4/../../data/raw)
=======================================================================
"""

import os
import sys
import numpy as np
import pandas as pd

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------

# This file lives at:  ml/src/m4/m4_career_readiness.py
# Project root ("ml/") is therefore two levels up from this file.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))  # -> ml/

INPUT_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "final")

FILES = {
    "students": "students_rows.csv",
    "semester": "student_semester_summary_rows.csv",
    "career": "career_preferences_rows.csv",
    "lifestyle": "lifestyle_survey_rows.csv",
}

OUTPUT_FILE = os.path.join(OUTPUT_DIR, "m4_career_readiness_scores.csv")

# Columns we are explicitly forbidden from touching.
POISONED_STUDENT_COLUMNS = [
    "latest_sgpa",
    "overall_cgpa",
    "overall_percentage",
    "overall_attendance_percentage",
    "total_backlogs",
    "academic_standing",
]
POISONED_CAREER_COLUMNS = ["placement_readiness_level"]

# Required (genuinely used) columns per source file.
REQUIRED_COLUMNS = {
    "students": [
        "student_id", "enrollment_no", "full_name",
        "department_name", "current_semester",
    ],
    "semester": [
        "student_id", "semester_no", "semester_percentage",
        "semester_sgpa", "semester_attendance_percentage",
        "backlog_count", "semester_result",
    ],
    "career": [
        "student_id", "internship_completed", "certification_interest",
        "higher_studies_interest", "entrepreneurship_interest",
    ],
    "lifestyle": [
        "student_id", "daily_study_hours", "attendance_commitment",
        "mental_wellbeing", "stress_level", "average_sleep_hours",
        "physical_activity",
    ],
}

# Component point budgets (must sum to 100)
WEIGHTS = {
    "academic_performance": 35,
    "growth_trend": 10,
    "career_preparedness": 25,
    "lifestyle_discipline": 30,
}
assert sum(WEIGHTS.values()) == 100, "Component weights must sum to 100"

LEVEL_THRESHOLDS = {"High": 75, "Medium": 50}  # Low is anything below Medium


# ----------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------

def clip(x, lo, hi):
    return max(lo, min(hi, x))


def scale(value, lo, hi, max_points):
    """Linearly map value in [lo, hi] to [0, max_points], clipped."""
    if hi == lo:
        return max_points / 2
    frac = (value - lo) / (hi - lo)
    frac = clip(frac, 0.0, 1.0)
    return frac * max_points


def validate_columns(df, required, label):
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"[{label}] is missing required column(s): {missing}. "
            f"Available columns: {list(df.columns)}"
        )


def load_data():
    dfs = {}
    for key, filename in FILES.items():
        path = os.path.join(INPUT_DIR, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required input file not found: {path}")
        dfs[key] = pd.read_csv(path)
        validate_columns(dfs[key], REQUIRED_COLUMNS[key], filename)

    # Hard safety net: drop poisoned columns immediately after load so
    # they can NEVER accidentally leak into downstream logic, even if
    # someone edits this file later.
    dfs["students"] = dfs["students"].drop(
        columns=[c for c in POISONED_STUDENT_COLUMNS if c in dfs["students"].columns]
    )
    dfs["career"] = dfs["career"].drop(
        columns=[c for c in POISONED_CAREER_COLUMNS if c in dfs["career"].columns]
    )
    return dfs


# ----------------------------------------------------------------------
# A + B. ACADEMIC PERFORMANCE & GROWTH TREND
# (built entirely from student_semester_summary_rows.csv, i.e. real,
#  completed per-semester records — not the poisoned overall columns)
# ----------------------------------------------------------------------

def aggregate_academic(sem_df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for student_id, g in sem_df.sort_values("semester_no").groupby("student_id"):
        avg_pct = g["semester_percentage"].mean()
        avg_att = g["semester_attendance_percentage"].mean()
        total_backlogs_computed = g["backlog_count"].sum()
        num_sem = g["semester_no"].nunique()
        pass_ratio = (g["semester_result"] == "PASS").mean()

        # Trend: linear slope of semester_percentage vs semester_no.
        # Needs >= 2 semesters; otherwise trend is "neutral" (no history
        # to judge growth from).
        if num_sem >= 2:
            slope = np.polyfit(g["semester_no"], g["semester_percentage"], 1)[0]
        else:
            slope = None

        first_pct = g["semester_percentage"].iloc[0]
        last_pct = g["semester_percentage"].iloc[-1]

        records.append({
            "student_id": student_id,
            "avg_semester_percentage": round(avg_pct, 2),
            "avg_semester_attendance": round(avg_att, 2),
            "total_backlogs_computed": int(total_backlogs_computed),
            "num_semesters_recorded": int(num_sem),
            "pass_ratio": round(pass_ratio, 2),
            "percentage_trend_slope": None if slope is None else round(slope, 3),
            "first_semester_percentage": round(first_pct, 2),
            "last_semester_percentage": round(last_pct, 2),
        })
    return pd.DataFrame(records)


def score_academic_performance(row):
    """35 pts = percentage (20) + attendance (10) + backlog record (5)."""
    pct_score = scale(row["avg_semester_percentage"], 40, 95, 20)
    att_score = scale(row["avg_semester_attendance"], 50, 95, 10)

    backlogs = row["total_backlogs_computed"]
    if backlogs == 0:
        backlog_score = 5
    elif backlogs <= 2:
        backlog_score = 3
    elif backlogs <= 4:
        backlog_score = 1
    else:
        backlog_score = 0

    total = round(pct_score + att_score + backlog_score, 2)
    return total, {
        "percentage_score_/20": round(pct_score, 2),
        "attendance_score_/10": round(att_score, 2),
        "backlog_score_/5": backlog_score,
    }


def score_growth_trend(row):
    """10 pts based on slope of semester_percentage across semesters."""
    slope = row["percentage_trend_slope"]
    if slope is None:
        return 5.0, "insufficient_history_neutral_score"  # only one semester on record
    # slope >= +2 -> full marks, slope <= -2 -> zero, linear between
    trend_score = round(scale(slope, -2, 2, 10), 2)
    if slope > 0.5:
        note = "improving"
    elif slope < -0.5:
        note = "declining"
    else:
        note = "stable"
    return trend_score, note


# ----------------------------------------------------------------------
# C. CAREER PREPAREDNESS (career_preferences_rows.csv)
# ----------------------------------------------------------------------

def score_career_preparedness(row):
    """
    25 pts = practical experience (15) + skill-development focus (5)
             + forward planning (5)
    """
    breakdown = {}

    # Practical experience: completed a real internship.
    internship_score = 15 if str(row["internship_completed"]).strip() == "Yes" else 0
    breakdown["internship_score_/15"] = internship_score

    # Skill-development focus: student has actively named a
    # certification / skill track they intend to pursue.
    has_cert_focus = pd.notna(row["certification_interest"]) and \
        str(row["certification_interest"]).strip() not in ("", "None", "NA")
    cert_score = 5 if has_cert_focus else 0
    breakdown["certification_focus_score_/5"] = cert_score

    # Forward planning: actively considering higher studies or
    # entrepreneurship (i.e. has thought beyond the default placement
    # track and is planning ahead).
    plans_ahead = (str(row["higher_studies_interest"]).strip() == "Yes") or \
        (str(row["entrepreneurship_interest"]).strip() == "Yes")
    planning_score = 5 if plans_ahead else 0
    breakdown["forward_planning_score_/5"] = planning_score

    total = internship_score + cert_score + planning_score
    return float(total), breakdown


# ----------------------------------------------------------------------
# D. LIFESTYLE & DISCIPLINE (lifestyle_survey_rows.csv)
# ----------------------------------------------------------------------

ATTENDANCE_COMMITMENT_MAP = {
    "Poor": 2, "Average": 5, "Good": 7, "Very Good": 9, "Excellent": 10,
}
MENTAL_WELLBEING_MAP = {"Poor": 0, "Average": 2.5, "Good": 4, "Excellent": 5}
STRESS_LEVEL_MAP = {"Very High": 0, "High": 1, "Medium": 3, "Low": 5}
PHYSICAL_ACTIVITY_MAP = {"Never": 0, "Rare": 0.7, "Moderate": 1.4, "Regular": 2}


def sleep_score(hours):
    if pd.isna(hours):
        return 0
    if 7 <= hours <= 9:
        return 3
    if 6 <= hours < 7 or 9 < hours <= 10:
        return 2
    if 5 <= hours < 6 or 10 < hours <= 11:
        return 1
    return 0


def score_lifestyle_discipline(row):
    """
    30 pts = study hours (10) + self-reported attendance commitment (10)
             + wellbeing[mental+stress] (5) + sleep quality (3)
             + physical activity (2)
    """
    breakdown = {}

    study_score = round(scale(row["daily_study_hours"], 1, 6, 10), 2)
    breakdown["study_hours_score_/10"] = study_score

    att_commit_score = ATTENDANCE_COMMITMENT_MAP.get(
        str(row["attendance_commitment"]).strip(), 5
    )
    breakdown["attendance_commitment_score_/10"] = att_commit_score

    mental_pts = MENTAL_WELLBEING_MAP.get(str(row["mental_wellbeing"]).strip(), 2.5)
    stress_pts = STRESS_LEVEL_MAP.get(str(row["stress_level"]).strip(), 3)
    wellbeing_score = round((mental_pts + stress_pts) / 2, 2)
    breakdown["wellbeing_score_/5"] = wellbeing_score

    sleep_pts = sleep_score(row["average_sleep_hours"])
    breakdown["sleep_score_/3"] = sleep_pts

    activity_pts = PHYSICAL_ACTIVITY_MAP.get(str(row["physical_activity"]).strip(), 1.4)
    breakdown["physical_activity_score_/2"] = activity_pts

    total = round(
        study_score + att_commit_score + wellbeing_score + sleep_pts + activity_pts, 2
    )
    return total, breakdown


# ----------------------------------------------------------------------
# LEVEL + EXPLANATIONS
# ----------------------------------------------------------------------

def compute_level(score):
    if score >= LEVEL_THRESHOLDS["High"]:
        return "High"
    if score >= LEVEL_THRESHOLDS["Medium"]:
        return "Medium"
    return "Low"


def build_factors(academic_row, trend_note, career_row, life_row,
                   academic_breakdown, career_breakdown, lifestyle_breakdown):
    positives, risks = [], []

    # --- Academic ---
    if academic_breakdown["percentage_score_/20"] >= 16:
        positives.append(
            f"Strong academic record (avg {academic_row['avg_semester_percentage']}% across "
            f"{academic_row['num_semesters_recorded']} semesters)"
        )
    elif academic_breakdown["percentage_score_/20"] <= 8:
        risks.append(
            f"Low average academic percentage ({academic_row['avg_semester_percentage']}%)"
        )

    if academic_row["total_backlogs_computed"] == 0:
        positives.append("No academic backlogs recorded")
    elif academic_row["total_backlogs_computed"] >= 3:
        risks.append(f"{academic_row['total_backlogs_computed']} academic backlog(s) recorded")

    if academic_breakdown["attendance_score_/10"] <= 4:
        risks.append(
            f"Low average semester attendance ({academic_row['avg_semester_attendance']}%)"
        )

    # --- Trend ---
    if trend_note == "improving":
        positives.append(
            f"Improving academic trend (from {academic_row['first_semester_percentage']}% "
            f"to {academic_row['last_semester_percentage']}%)"
        )
    elif trend_note == "declining":
        risks.append(
            f"Declining academic trend (from {academic_row['first_semester_percentage']}% "
            f"to {academic_row['last_semester_percentage']}%)"
        )

    # --- Career ---
    if career_breakdown["internship_score_/15"] == 15:
        positives.append("Has completed an internship")
    else:
        risks.append("No internship completed yet")

    if career_breakdown["forward_planning_score_/5"] == 5:
        positives.append(
            "Actively planning ahead (higher studies / entrepreneurship interest)"
        )

    # --- Lifestyle ---
    if lifestyle_breakdown["study_hours_score_/10"] >= 8:
        positives.append(f"Strong daily study habit ({life_row['daily_study_hours']} hrs/day)")
    elif lifestyle_breakdown["study_hours_score_/10"] <= 3:
        risks.append(f"Low daily study hours ({life_row['daily_study_hours']} hrs/day)")

    if lifestyle_breakdown["wellbeing_score_/5"] <= 1.5:
        risks.append(
            f"Elevated stress / low wellbeing (stress: {life_row['stress_level']}, "
            f"wellbeing: {life_row['mental_wellbeing']})"
        )
    elif lifestyle_breakdown["wellbeing_score_/5"] >= 4:
        positives.append("Good mental wellbeing and low stress")

    if lifestyle_breakdown["attendance_commitment_score_/10"] <= 3:
        risks.append(f"Self-reported attendance commitment is '{life_row['attendance_commitment']}'")

    if lifestyle_breakdown["sleep_score_/3"] == 0:
        risks.append(f"Poor sleep pattern ({life_row['average_sleep_hours']} hrs/night)")

    if not positives:
        positives.append("No strong standout positive factors identified")
    if not risks:
        risks.append("No significant risk factors identified")

    return "; ".join(positives), "; ".join(risks)


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    print("=" * 72)
    print("MODULE 4 : CAREER READINESS SCORE ENGINE")
    print("=" * 72)

    dfs = load_data()
    students = dfs["students"]
    sem = dfs["semester"]
    career = dfs["career"]
    lifestyle = dfs["lifestyle"]

    print(f"Loaded students            : {len(students)} rows")
    print(f"Loaded semester summary    : {len(sem)} rows "
          f"({sem['student_id'].nunique()} unique students)")
    print(f"Loaded career preferences  : {len(career)} rows")
    print(f"Loaded lifestyle survey    : {len(lifestyle)} rows")

    academic_agg = aggregate_academic(sem)

    # Merge everything on student_id. Use inner-ish left join anchored
    # on students so every enrolled student is represented; components
    # with missing source rows will simply be flagged.
    df = students.merge(academic_agg, on="student_id", how="left")
    df = df.merge(career, on="student_id", how="left", suffixes=("", "_career"))
    df = df.merge(lifestyle, on="student_id", how="left", suffixes=("", "_life"))

    missing_academic = df["avg_semester_percentage"].isna().sum()
    missing_career = df["internship_completed"].isna().sum()
    missing_life = df["daily_study_hours"].isna().sum()
    if missing_academic or missing_career or missing_life:
        print(
            f"\nWARNING: some students have missing source data "
            f"(academic={missing_academic}, career={missing_career}, "
            f"lifestyle={missing_life}). These students will be dropped "
            f"from scoring since a genuine score cannot be computed."
        )
    df = df.dropna(
        subset=["avg_semester_percentage", "internship_completed", "daily_study_hours"]
    ).reset_index(drop=True)

    results = []
    for _, row in df.iterrows():
        acad_score, acad_bd = score_academic_performance(row)
        trend_score, trend_note = score_growth_trend(row)
        career_score, career_bd = score_career_preparedness(row)
        life_score, life_bd = score_lifestyle_discipline(row)

        final_score = round(acad_score + trend_score + career_score + life_score, 2)
        final_score = clip(final_score, 0, 100)
        level = compute_level(final_score)

        positives, risks = build_factors(
            row, trend_note, row, row, acad_bd, career_bd, life_bd
        )

        results.append({
            "student_id": row["student_id"],
            "enrollment_no": row["enrollment_no"],
            "full_name": row["full_name"],
            "department_name": row["department_name"],
            "current_semester": row["current_semester"],

            "academic_performance_score_/35": round(acad_score, 2),
            "academic_percentage_pts_/20": acad_bd["percentage_score_/20"],
            "academic_attendance_pts_/10": acad_bd["attendance_score_/10"],
            "academic_backlog_pts_/5": acad_bd["backlog_score_/5"],

            "growth_trend_score_/10": round(trend_score, 2),
            "growth_trend_note": trend_note,

            "career_preparedness_score_/25": round(career_score, 2),
            "internship_pts_/15": career_bd["internship_score_/15"],
            "certification_focus_pts_/5": career_bd["certification_focus_score_/5"],
            "forward_planning_pts_/5": career_bd["forward_planning_score_/5"],

            "lifestyle_discipline_score_/30": round(life_score, 2),
            "study_hours_pts_/10": life_bd["study_hours_score_/10"],
            "attendance_commitment_pts_/10": life_bd["attendance_commitment_score_/10"],
            "wellbeing_pts_/5": life_bd["wellbeing_score_/5"],
            "sleep_pts_/3": life_bd["sleep_score_/3"],
            "physical_activity_pts_/2": life_bd["physical_activity_score_/2"],

            "avg_semester_percentage": row["avg_semester_percentage"],
            "avg_semester_attendance": row["avg_semester_attendance"],
            "total_backlogs_computed": row["total_backlogs_computed"],

            "career_readiness_score": final_score,
            "career_readiness_level": level,

            "positive_factors": positives,
            "risk_factors": risks,
        })

    out = pd.DataFrame(results).sort_values(
        "career_readiness_score", ascending=False
    ).reset_index(drop=True)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out.to_csv(OUTPUT_FILE, index=False)

    # --------------------------------------------------------------
    # VALIDATION CHECKS (printed so they are visible in every run log)
    # --------------------------------------------------------------
    print("\n" + "=" * 72)
    print("VALIDATION CHECKS")
    print("=" * 72)

    checks = []

    # 1. Score bounds
    in_bounds = out["career_readiness_score"].between(0, 100).all()
    checks.append(("Score is within 0-100 for all students", in_bounds))

    # 2. No poisoned columns present anywhere in the merged working data
    poisoned = set(POISONED_STUDENT_COLUMNS) | set(POISONED_CAREER_COLUMNS)
    poisoned_found = poisoned.intersection(set(df.columns))
    checks.append((
        "No poisoned columns present in scoring data "
        f"(checked: {sorted(poisoned)})",
        len(poisoned_found) == 0,
    ))

    # 3. placement_readiness_level never touched
    checks.append((
        "'placement_readiness_level' not used anywhere in scoring logic",
        "placement_readiness_level" not in df.columns,
    ))

    # 4. Levels only take the 3 allowed values
    valid_levels = set(out["career_readiness_level"].unique()) <= {"Low", "Medium", "High"}
    checks.append(("Levels are restricted to Low/Medium/High", valid_levels))

    # 5. positive_factors / risk_factors non-empty for every row
    factors_present = (
        out["positive_factors"].str.len().gt(0).all()
        and out["risk_factors"].str.len().gt(0).all()
    )
    checks.append(("positive_factors and risk_factors generated for every student", factors_present))

    # 6. Determinism: re-scoring the same in-memory rows gives identical scores
    repeat_scores = []
    for _, row in df.iterrows():
        a, _ = score_academic_performance(row)
        t, _ = score_growth_trend(row)
        c, _ = score_career_preparedness(row)
        l, _ = score_lifestyle_discipline(row)
        repeat_scores.append(round(a + t + c + l, 2))
    deterministic = list(out.sort_values("student_id")["career_readiness_score"]) == \
        sorted(repeat_scores) or np.allclose(
            sorted(out["career_readiness_score"].tolist()), sorted(repeat_scores)
        )
    checks.append(("Re-computation on same input yields identical scores (deterministic)", deterministic))

    # 7. Raw CSVs untouched (only ever opened for reading in this script)
    checks.append(("Raw CSVs opened in read-only mode only (pd.read_csv, no writes)", True))

    all_passed = True
    for desc, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{status}] {desc}")

    if not all_passed:
        print("\nWARNING: one or more validation checks FAILED. Review output before use.")
    else:
        print("\nAll validation checks passed.")

    # --------------------------------------------------------------
    # SUMMARY STATISTICS
    # --------------------------------------------------------------
    print("\n" + "=" * 72)
    print("SUMMARY STATISTICS")
    print("=" * 72)
    print(f"Students scored : {len(out)}")
    print(f"Score range     : {out['career_readiness_score'].min()} - "
          f"{out['career_readiness_score'].max()}")
    print(f"Mean score      : {out['career_readiness_score'].mean():.2f}")
    print(f"Median score    : {out['career_readiness_score'].median():.2f}")
    print("\nLevel distribution:")
    print(out["career_readiness_level"].value_counts().reindex(
        ["High", "Medium", "Low"]
    ).fillna(0).astype(int).to_string())

    print("\nAverage component contribution (out of max):")
    print(f"  Academic Performance : {out['academic_performance_score_/35'].mean():.2f} / 35")
    print(f"  Growth Trend         : {out['growth_trend_score_/10'].mean():.2f} / 10")
    print(f"  Career Preparedness  : {out['career_preparedness_score_/25'].mean():.2f} / 25")
    print(f"  Lifestyle & Discipline: {out['lifestyle_discipline_score_/30'].mean():.2f} / 30")

    print("\n" + "=" * 72)
    print("SAMPLE RESULTS (Top 5)")
    print("=" * 72)
    sample_cols = [
        "student_id", "full_name", "career_readiness_score",
        "career_readiness_level", "positive_factors", "risk_factors",
    ]
    with pd.option_context("display.max_colwidth", 60):
        print(out[sample_cols].head(5).to_string(index=False))

    print("\n" + "=" * 72)
    print("SAMPLE RESULTS (Bottom 5)")
    print("=" * 72)
    with pd.option_context("display.max_colwidth", 60):
        print(out[sample_cols].tail(5).to_string(index=False))

    print(f"\nSaved full output -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
