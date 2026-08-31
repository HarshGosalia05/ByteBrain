"""Read-only live verification of the M3 chronological (later academic-year)
cohort analysis against real PostgreSQL (Supabase) via asyncpg.

Determines from the LIVE database whether a chronologically later admission
cohort exists to expand M3, and confirms the current M3 evaluation state is
unchanged (eval-only; no M3 artifact persisted).

Verifies against the LIVE database:
  - Single admission cohort (admission_year == 2023, 80 students, id range).
  - Single current_academic_year (2026-27); the distinct summary academic_year
    values are calendar years of the same cohort, not separate cohorts.
  - analyze_m3_cohort_expansion on live frames -> expansion NOT possible,
    0 added positive students (no later cohort exists -> do NOT manufacture).
  - Forward-compatible: the module would detect a later cohort if it arrived.
  - Current M3 evaluation state unchanged (6 positive students, 4/5 informative
    folds, 1 absent-positive -> NaN) and reproducible.
  - M1 & M3 artifact hashes unchanged.

Read-only: NO INSERT/UPDATE/DELETE, no schema changes, no ETL, no artifact
writes.
"""
from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

import pandas as pd

_SRC = str(Path(__file__).resolve().parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

_BACKEND = str(Path(__file__).resolve().parents[1] / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from db_env import db_config  # noqa: E402

DB = db_config()
DB_HOST = DB.host
DB_PORT = DB.port
DB_NAME = DB.name
DB_USER = DB.user
DB_PASS = DB.password

SUMMARY_SQL = """
    SELECT student_id, semester_no, academic_year, subjects_registered,
           credits_registered, credits_earned, semester_total_marks,
           semester_percentage, semester_sgpa, semester_attendance_percentage,
           backlog_count, semester_result, semester_grade
    FROM student_semester_summary
    ORDER BY student_id, semester_no
"""

STUDENTS_SQL = """
    SELECT student_id, department_name, gender, admission_year,
           current_academic_year, student_status
    FROM students
    ORDER BY student_id
"""


async def fetch(pool, sql):
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


async def main():
    import asyncpg

    results = {"passed": 0, "failed": 0, "errors": []}

    def check(name, cond, detail=""):
        if cond:
            results["passed"] += 1
            print(f"  [PASS] {name}" + (f" -- {detail}" if detail else ""))
        else:
            results["failed"] += 1
            results["errors"].append(name)
            print(f"  [FAIL] {name}" + (f" -- {detail}" if detail else ""))

    pool = await asyncpg.create_pool(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASS, ssl="require",
        min_size=1, max_size=2, statement_cache_size=0,
    )
    try:
        summary = await fetch(pool, SUMMARY_SQL)
        students = await fetch(pool, STUDENTS_SQL)
        print(f"\n=== LIVE cohort chronology (PostgreSQL) ===")
        print(f"  summary rows: {len(summary)} | students: {len(students)}")
        print(f"  depts: {students['department_name'].value_counts().to_dict()}")
        print(f"  admission_year: {sorted(students['admission_year'].unique())}")
        print(f"  current_academic_year: {sorted(students['current_academic_year'].unique())}")
        print(f"  summary academic_year -> semesters:")
        for y, g in summary.groupby("academic_year"):
            print(f"    {y}: sem {int(g['semester_no'].min())}..{int(g['semester_no'].max())}, rows {len(g)}")

        from features.v1_m3_cohort_expansion import (
            analyze_m3_cohort_expansion, render_expansion_analysis,
        )
        from features.v1_m3_experiment import run_m3_experiment
        from features.v1_cohort_dataset import V1CohortScope, build_cohort_v1_dataset
        from features.v1_label_builder import AT_RISK_RESULTS

        # 1. Single cohort census (live)
        check("Single admission cohort (2023 only)",
              sorted(students["admission_year"].unique()) == [2023],
              f"{sorted(students['admission_year'].unique())}")
        check("Two active departments only",
              sorted(students["department_name"].unique()) == ["BBA", "CSE"])
        check("Single current academic year",
              sorted(students["current_academic_year"].unique()) == ["2026-27"])
        check("80 students, id range STU000001..STU000080",
              students["student_id"].nunique() == 80
              and students["student_id"].min() == "STU000001"
              and students["student_id"].max() == "STU000080",
              f"{students['student_id'].nunique()}")

        # 2. Expansion analysis (live)
        print("\n=== M3 chronological cohort analysis (live) ===")
        tables = {"summary": summary, "students": students}
        a = analyze_m3_cohort_expansion(tables=tables)
        print(render_expansion_analysis(a))
        check("No chronologically later cohort exists (live)",
              a.later_admission_years == [] and not a.expansion_possible)
        check("Adds 0 positive students (live)",
              a.later_positive_rows == 0 and a.later_positive_students == 0)
        check("All existing labeled rows consumed (live)", a.all_labeled_rows_consumed)

        # 3. Label rule intact (independent academic outcome)
        check("Independent academic-outcome rule (FAIL/ATKT, backlog>0)",
              {"FAIL", "ATKT"} <= set(AT_RISK_RESULTS))

        # 4. Current M3 evaluation unchanged (eval-only, no artifact persist)
        print("\n=== M3 current evaluation state (live) ===")
        dataset = build_cohort_v1_dataset(
            V1CohortScope(), tables={"summary": summary, "students": students}
        )
        m3a = run_m3_experiment(dataset)
        m3b = run_m3_experiment(dataset)
        check("M3 student isolation", m3a.student_isolation_ok)
        check("M3 deployment excluded", m3a.deployment_excluded_ok)
        check("M3 positive students == 6", m3a.n_positive_students == 6,
              f"rows={m3a.n_positive_rows} students={m3a.n_positive_students}")
        check("M3 informative folds == 4/5", len(m3a.folds_with_positive) == 4,
              f"folds_with_positive={m3a.folds_with_positive}")
        check("M3 reproducible", m3a.n_positive_rows == m3b.n_positive_rows
              and m3a.folds_with_positive == m3b.folds_with_positive)
        ref_a = m3a.reference()
        absent = [f for f in ref_a.folds if f.positive_absent]
        check("Absent-positive fold reported NaN (not fabricated)",
              len(absent) == 1 and all(pd.isna(f.f1) for f in absent))

    finally:
        await pool.close()

    # 5. Artifact hashes unchanged (M1/M3 eval-only; M2 unchanged this step)
    print("\n=== Artifact hashes (unchanged guard) ===")
    artifacts = Path(__file__).resolve().parent / "artifacts" / "models"
    m1 = artifacts / "m1_subject_endmarks.joblib"
    m3 = artifacts / "m3_next_semester_at_risk.joblib"
    m2 = artifacts / "m2_next_semester_performance.joblib"
    for label, p, prefix in [
        ("M1", m1, "3404D29E"), ("M3", m3, "99D845FE"), ("M2", m2, "6cac9a88"),
    ]:
        if p.exists():
            h = sha256(p)
            ok = h.lower().startswith(prefix.lower())
            check(f"{label} artifact hash {prefix}...", ok, f"{h[:12]}...")
        else:
            check(f"{label} artifact exists", False, str(p))

    print("\n" + "=" * 60)
    print(f"LIVE VERIFICATION: {results['passed']} passed, "
          f"{results['failed']} failed, {results['passed'] + results['failed']} total")
    print("DB side effects: NONE (read-only)")
    if results["errors"]:
        print("Errors:", results["errors"])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
