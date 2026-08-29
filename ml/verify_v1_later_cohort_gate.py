"""Read-only live verification of the second later-cohort availability &
integration gate against real PostgreSQL (Supabase) via asyncpg.

Runs the SAME deterministic gate on the LIVE database frames and asserts:
  - chronological census (single 2023 admission cohort; no later year)
  - no candidate later cohort; verdict == NO_VALID_LATER_COHORT_FOUND
  - projection equals the current M3 population (added positives == 0)
  - determinism: run twice -> identical verdict/candidates/projection
  - authoritative chronology field == students.admission_year
  - artifact hashes unchanged (M1/M3 eval-only; M2 at prior hash)

Read-only: NO INSERT/UPDATE/DELETE, no schema change, no ETL, no artifact writes.
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

DB_HOST = "aws-1-ap-south-1.pooler.supabase.com"
DB_PORT = 6543
DB_NAME = "postgres"
DB_USER = "postgres.rtaqkxqdejelxsamnesm"
DB_PASS = "KenexAI@*195"

SUMMARY_SQL = """
    SELECT student_id, semester_no, academic_year, semester_result, backlog_count
    FROM student_semester_summary
    ORDER BY student_id, semester_no
"""

STUDENTS_SQL = """
    SELECT student_id, department_name, admission_year, current_academic_year
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
        from features.v1_later_cohort_gate import (
            run_later_cohort_gate, render_later_cohort_gate, NO_VALID,
        )

        students = await fetch(pool, STUDENTS_SQL)
        summary = await fetch(pool, SUMMARY_SQL)
        # Merge department_name into the summary frame (as the cohort loader does).
        summary = summary.merge(
            students[["student_id", "department_name"]], on="student_id", how="left"
        )
        tables = {"summary": summary, "students": students}

        print("\n=== LIVE later-cohort gate (PostgreSQL) ===")
        print(f"  students: {len(students)} | summary rows: {len(summary)}")
        print(f"  admission_years: {sorted(students['admission_year'].unique())}")
        print(f"  current_academic_year: {sorted(students['current_academic_year'].unique())}")

        # Deterministic rerun
        r1 = run_later_cohort_gate(tables=tables, provenance="live")
        r2 = run_later_cohort_gate(tables=tables, provenance="live")

        # Chronology / census
        check("authoritative field == students.admission_year",
              r1.authoritative_chronology_field == "students.admission_year")
        check("single admission year 2023", r1.all_admission_years == [2023],
              str(r1.all_admission_years))
        check("current cohort year 2023, 80 students",
              r1.current_cohort_year == 2023 and len(r1.current_student_ids) == 80)
        check("no later admission years", r1.later_admission_years == [])

        # Verdict
        check("verdict == NO_VALID_LATER_COHORT_FOUND", r1.verdict == NO_VALID,
              r1.verdict)
        check("no candidates", r1.candidates == [])
        check("reasons documented", bool(r1.reasons_for_no_valid))

        # Projection (live positive-row count is 26, not CSV 28)
        p = r1.projected
        check("projection: 0 later-new students", p["later_new_students"] == 0)
        check("projection: combined students 80", p["combined_total_students"] == 80)
        check("projection: added positives 0", p["added_positive_rows"] == 0
              and p["added_positive_students"] == 0)
        check("projection: live positives 26 / 6",
              p["combined_positive_rows"] == 26
              and p["combined_positive_students"] == 6,
              f"rows={p['combined_positive_rows']} stu={p['combined_positive_students']}")

        # Determinism
        check("identical verdict (2nd run)", r2.verdict == r1.verdict)
        check("identical candidates (2nd run)", r2.candidates == r1.candidates)
        check("identical projection (2nd run)", r2.projected == r1.projected)
        check("identical reasons (2nd run)", r2.reasons_for_no_valid == r1.reasons_for_no_valid)

        print(render_later_cohort_gate(r1))

    finally:
        await pool.close()

    # Artifact policy: nothing changed this step.
    print("\n=== Artifact status (unchanged guard) ===")
    artifacts = Path(__file__).resolve().parent / "artifacts" / "models"
    for label, fname, prefix in [
        ("M1", "m1_subject_endmarks.joblib", "3404D29E"),
        ("M3", "m3_next_semester_at_risk.joblib", "99D845FE"),
        ("M2", "m2_next_semester_performance.joblib", "6cac9a88"),
    ]:
        p = artifacts / fname
        if p.exists():
            h = sha256(p)
            check(f"{label} artifact hash {prefix}...", h.lower().startswith(prefix.lower()),
                  f"{h[:12]}...")
        else:
            check(f"{label} artifact exists", False, str(p))

    print("\n" + "=" * 60)
    print(f"LIVE VERIFICATION: {results['passed']} passed, {results['failed']} failed, "
          f"{results['passed'] + results['failed']} total")
    print("DB side effects: NONE (read-only)")
    if results["errors"]:
        print("Errors:", results["errors"])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
