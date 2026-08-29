"""Live (READ-ONLY) verification of SECOND-COHORT INGESTION READINESS / ETL GAP.

Verifies against the real PostgreSQL database (asyncpg, ssl=require):

- current admission years (authoritative chronology: students.admission_year)
- current student count / departments
- absence of any later (admission_year > 2023) cohort
- ETL-required master columns exist
- existing grain integrity (students unique, (student, semester) unique)
- M3-compatible target source columns present and populated
- classification of the ETL-gap audit (expect ETL_BLOCKED today)
- artifact hashes for M1/M2/M3 remain unchanged

No database writes of any kind.
"""
import asyncio
import hashlib
import os
import sys
from pathlib import Path

import pandas as pd

_SRC = str(Path(__file__).resolve().parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from features.v1_etl_second_cohort_readiness import (  # noqa: E402
    ETL_BLOCKED,
    audit_etl_second_cohort_readiness,
)

DB_HOST = "aws-1-ap-south-1.pooler.supabase.com"
DB_PORT = 6543
DB_NAME = "postgres"
DB_USER = "postgres.rtaqkxqdejelxsamnesm"
DB_PASSWORD = "KenexAI@*195"

ARTIFACTS = {
    "m1": ("m1_subject_endmarks.joblib", "3404d29e"),
    "m3": ("m3_next_semester_at_risk.joblib", "99d845fe"),
    "m2": ("m2_next_semester_performance.joblib", "6cac9a88"),
}

passed = 0
failed = 0
failures = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        failures.append(name)
        print(f"  [FAIL] {name} {detail}")


async def fetch(f, sql):
    async with f.pool.acquire() as conn:
        rows = await conn.fetch(sql)
        return [dict(r) for r in rows]


async def main():
    import asyncpg

    pool = await asyncpg.create_pool(
        host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER,
        password=DB_PASSWORD, ssl="require", min_size=1, max_size=2,
        statement_cache_size=0,
    )
    f = type("F", (), {"pool": pool})()

    print("=== 1. Admission-year census (students.admission_year) ===")
    rows = await fetch(f, "SELECT admission_year, count(*) n FROM students GROUP BY 1 ORDER BY 1")
    years = sorted(int(r["admission_year"]) for r in rows)
    print(f"  Admission years: {years}")
    check("admission_year populated", bool(years), str(rows))
    check("only current 2023 cohort (no later)", years == [2023], str(years))
    later = [y for y in years if y is not None and y > 2023]
    check("no later cohort present", len(later) == 0, str(later))

    print("=== 2. Student population ===")
    n_students = (await fetch(f, "SELECT count(*) n FROM students"))[0]["n"]
    n_distinct = (await fetch(f, "SELECT count(distinct student_id) n FROM students"))[0]["n"]
    check("student count == 80", n_students == 80, str(n_students))
    check("students unique (no duplicates)", n_distinct == n_students, f"{n_distinct}/{n_students}")

    print("=== 3. Departments ===")
    depts = await fetch(f, "SELECT department_name, count(*) n FROM students GROUP BY 1 ORDER BY 1")
    dept_map = {r["department_name"]: r["n"] for r in depts}
    print(f"  {dept_map}")
    check("departments CSE + BBA only", set(dept_map) == {"CSE", "BBA"}, str(dept_map))
    check("CSE 50 / BBA 30", dept_map.get("CSE") == 50 and dept_map.get("BBA") == 30, str(dept_map))

    print("=== 4. ETL-required master columns present ===")
    info = await fetch(
        f,
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name IN ('students','student_semester_summary')",
    )
    cols = {(r["table_name"], r["column_name"]) for r in info}
    required = [
        ("students", "student_id"), ("students", "enrollment_no"),
        ("students", "admission_year"), ("students", "department_name"),
        ("students", "gender"),
        ("student_semester_summary", "student_id"),
        ("student_semester_summary", "semester_no"),
        ("student_semester_summary", "academic_year"),
        ("student_semester_summary", "semester_result"),
        ("student_semester_summary", "backlog_count"),
    ]
    for t, c in required:
        check(f"col {t}.{c}", (t, c) in cols)

    print("=== 5. Grain integrity (student_semester_summary) ===")
    total = (await fetch(f, "SELECT count(*) n FROM student_semester_summary"))[0]["n"]
    grains = (await fetch(
        f, "SELECT count(*) n FROM (SELECT 1 FROM student_semester_summary GROUP BY student_id, semester_no) x"
    ))[0]["n"]
    check("summary rows == distinct grains", total == grains, f"{total}/{grains}")

    print("=== 6. M3-compatible target sources populated ===")
    res = (await fetch(
        f, "SELECT count(*) n, count(semester_result) with_res, count(backlog_count) with_bk "
           "FROM student_semester_summary"
    ))[0]
    check("semester_result populated", res["with_res"] == res["n"], str(res))
    check("backlog_count populated", res["with_bk"] == res["n"], str(res))

    print("=== 7. ETL-gap audit classification ===")
    audit = audit_etl_second_cohort_readiness(provenance="live")
    print(f"  classification={audit.classification} blockers={audit.summary['structural_blockers']}")
    check("ETL audit == ETL_BLOCKED", audit.classification == ETL_BLOCKED)

    print("=== 8. Artifact integrity (unchanged hashes) ===")
    artifacts_dir = Path(__file__).resolve().parent / "artifacts" / "models"
    for tag, (fname, prefix) in ARTIFACTS.items():
        p = artifacts_dir / fname
        if not p.exists():
            check(f"artifact {tag} present", False)
            continue
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        check(f"artifact {tag} hash {prefix}...", digest.startswith(prefix), digest[:12])

    await pool.close()

    print("=" * 60)
    print(f"LIVE VERIFICATION: {passed} passed, {failed} failed, {passed + failed} total")
    print("DB side effects: NONE (read-only)")
    if failures:
        print("Failures:", failures)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
