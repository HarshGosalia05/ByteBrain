"""Read-only Supabase schema probe for M1 v2 implementation."""
import asyncio
import asyncpg
import os
import sys
from pathlib import Path

# Load from .env.local first, then .env
def load_env():
    env = {}
    for fname in [".env.local", ".env"]:
        p = Path(__file__).parent.parent / fname
        if p.exists():
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        env[k.strip()] = v.strip().strip('"').strip("'")
    return env

env = load_env()
DB_HOST = env.get("DB_HOST", "localhost")
DB_PORT = int(env.get("DB_PORT", 5432))
DB_NAME = env.get("DB_NAME", "postgres")
DB_USER = env.get("DB_USER", "postgres")
DB_PASS = env.get("DB_PASSWORD", "password")


async def main():
    print(f"Connecting to {DB_HOST}:{DB_PORT}/{DB_NAME} as {DB_USER}")
    ssl_mode = "require" if ("supabase" in DB_HOST or DB_PORT == 6543) else None
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASS, ssl=ssl_mode
    )
    print("Connected OK.")

    # List all tables
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name"
    )
    print("\nALL PUBLIC TABLES:")
    for r in rows:
        print(f"  {r['table_name']}")

    # Row counts for key tables
    target_tables = [
        "students", "subjects", "student_subject_enrollment",
        "student_subject_performance", "attendance_weekly",
        "student_semester_summary", "student_learning_activity",
        "student_lifestyle_survey", "student_skill_profile",
        "career_preferences_v2", "placement", "faculty_student_map",
    ]
    print("\nROW COUNTS (key tables):")
    for tbl in target_tables:
        try:
            row = await conn.fetchrow(f"SELECT COUNT(*) AS n FROM {tbl}")
            print(f"  {tbl}: {row['n']}")
        except Exception as e:
            print(f"  {tbl}: ERROR - {e}")

    # Columns for student_subject_performance
    print("\nCOLUMNS: student_subject_performance")
    cols = await conn.fetch(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='student_subject_performance' ORDER BY ordinal_position"
    )
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']}, nullable={c['is_nullable']})")

    # Columns for attendance_weekly
    print("\nCOLUMNS: attendance_weekly")
    cols = await conn.fetch(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='attendance_weekly' ORDER BY ordinal_position"
    )
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']}, nullable={c['is_nullable']})")

    # Columns for student_learning_activity
    print("\nCOLUMNS: student_learning_activity")
    cols = await conn.fetch(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='student_learning_activity' ORDER BY ordinal_position"
    )
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']}, nullable={c['is_nullable']})")

    # Columns for students
    print("\nCOLUMNS: students")
    cols = await conn.fetch(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='students' ORDER BY ordinal_position"
    )
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']}, nullable={c['is_nullable']})")

    # Columns for student_semester_summary
    print("\nCOLUMNS: student_semester_summary")
    cols = await conn.fetch(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='student_semester_summary' ORDER BY ordinal_position"
    )
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']}, nullable={c['is_nullable']})")

    # Columns for student_subject_enrollment
    print("\nCOLUMNS: student_subject_enrollment")
    cols = await conn.fetch(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='student_subject_enrollment' ORDER BY ordinal_position"
    )
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']}, nullable={c['is_nullable']})")

    # Columns for subjects
    print("\nCOLUMNS: subjects")
    cols = await conn.fetch(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='subjects' ORDER BY ordinal_position"
    )
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']}, nullable={c['is_nullable']})")

    # Columns for student_lifestyle_survey
    print("\nCOLUMNS: student_lifestyle_survey")
    cols = await conn.fetch(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='student_lifestyle_survey' ORDER BY ordinal_position"
    )
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']}, nullable={c['is_nullable']})")

    # Columns for student_skill_profile
    print("\nCOLUMNS: student_skill_profile")
    cols = await conn.fetch(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='student_skill_profile' ORDER BY ordinal_position"
    )
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']}, nullable={c['is_nullable']})")

    # Columns for placement
    print("\nCOLUMNS: placement")
    cols = await conn.fetch(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='placement' ORDER BY ordinal_position"
    )
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']}, nullable={c['is_nullable']})")

    # Sample of performance table for 6A students (STU6A*)
    print("\nSAMPLE student_subject_performance (6A students, 3 rows):")
    rows = await conn.fetch(
        "SELECT * FROM student_subject_performance WHERE student_id LIKE 'STU6A%' LIMIT 3"
    )
    for r in rows:
        print(dict(r))

    # Check end_sem_marks nulls for 6A
    print("\nend_sem_marks NULL distribution (6A cohort):")
    row = await conn.fetchrow(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN end_sem_marks IS NULL THEN 1 ELSE 0 END) AS nulls, "
        "SUM(CASE WHEN end_sem_marks IS NOT NULL THEN 1 ELSE 0 END) AS non_nulls "
        "FROM student_subject_performance WHERE student_id LIKE 'STU6A%'"
    )
    print(dict(row))

    # Distinct semesters in performance for 6A
    row = await conn.fetchrow(
        "SELECT ARRAY_AGG(DISTINCT semester_no ORDER BY semester_no) AS sems "
        "FROM student_subject_performance WHERE student_id LIKE 'STU6A%'"
    )
    print(f"Distinct semester_no values (6A): {row['sems']}")

    # Check is_current_semester column
    try:
        row = await conn.fetchrow(
            "SELECT ARRAY_AGG(DISTINCT is_current_semester ORDER BY is_current_semester) AS vals "
            "FROM student_subject_performance WHERE student_id LIKE 'STU6A%'"
        )
        print(f"is_current_semester values (6A): {row['vals']}")
    except Exception as e:
        print(f"is_current_semester column: NOT FOUND - {e}")

    # Check boundary / deployment markers
    try:
        row = await conn.fetchrow(
            "SELECT ARRAY_AGG(DISTINCT target_not_available ORDER BY target_not_available) AS vals "
            "FROM student_subject_performance WHERE student_id LIKE 'STU6A%'"
        )
        print(f"target_not_available values (6A): {row['vals']}")
    except Exception as e:
        print(f"target_not_available column: NOT FOUND - {e}")

    # Performance NULL analysis
    print("\nPerformance NULL analysis for 6A:")
    row = await conn.fetchrow(
        "SELECT "
        "COUNT(*) AS total, "
        "SUM(CASE WHEN internal_marks IS NULL THEN 1 ELSE 0 END) AS internal_marks_null, "
        "SUM(CASE WHEN mid_sem_marks IS NULL THEN 1 ELSE 0 END) AS mid_sem_marks_null, "
        "SUM(CASE WHEN end_sem_marks IS NULL THEN 1 ELSE 0 END) AS end_sem_marks_null, "
        "SUM(CASE WHEN total_marks IS NULL THEN 1 ELSE 0 END) AS total_marks_null "
        "FROM student_subject_performance WHERE student_id LIKE 'STU6A%'"
    )
    print(dict(row))

    # Distinct departments in 6A cohort
    rows = await conn.fetch(
        "SELECT DISTINCT department_name FROM students WHERE student_id LIKE 'STU6A%'"
    )
    print(f"\nDepartments in 6A cohort: {[r['department_name'] for r in rows]}")

    # Total students in 6A
    row = await conn.fetchrow(
        "SELECT COUNT(DISTINCT student_id) AS n FROM students WHERE student_id LIKE 'STU6A%'"
    )
    print(f"Total 6A students: {row['n']}")

    # attendance_weekly sample
    print("\nSAMPLE attendance_weekly (6A students, 2 rows):")
    try:
        rows = await conn.fetch(
            "SELECT * FROM attendance_weekly WHERE student_id LIKE 'STU6A%' LIMIT 2"
        )
        for r in rows:
            print(dict(r))
    except Exception as e:
        print(f"  ERROR: {e}")

    # student_learning_activity sample
    print("\nSAMPLE student_learning_activity (6A students, 2 rows):")
    try:
        rows = await conn.fetch(
            "SELECT * FROM student_learning_activity WHERE student_id LIKE 'STU6A%' LIMIT 2"
        )
        for r in rows:
            print(dict(r))
    except Exception as e:
        print(f"  ERROR: {e}")

    # career_preferences_v2 columns
    print("\nCOLUMNS: career_preferences_v2")
    try:
        cols = await conn.fetch(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='career_preferences_v2' ORDER BY ordinal_position"
        )
        for c in cols:
            print(f"  {c['column_name']} ({c['data_type']}, nullable={c['is_nullable']})")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Check semester_no distribution for 6A in performance
    print("\nSemester distribution in performance (6A):")
    rows = await conn.fetch(
        "SELECT semester_no, COUNT(*) AS n, "
        "SUM(CASE WHEN end_sem_marks IS NOT NULL THEN 1 ELSE 0 END) AS labeled "
        "FROM student_subject_performance WHERE student_id LIKE 'STU6A%' "
        "GROUP BY semester_no ORDER BY semester_no"
    )
    for r in rows:
        print(f"  sem {r['semester_no']}: {r['n']} rows, {r['labeled']} labeled")

    # Check join between performance and enrollment
    print("\nFK check: performance rows without matching enrollment:")
    row = await conn.fetchrow(
        "SELECT COUNT(*) AS orphans FROM student_subject_performance p "
        "LEFT JOIN student_subject_enrollment e ON p.enrollment_record_id = e.enrollment_record_id "
        "WHERE e.enrollment_record_id IS NULL AND p.student_id LIKE 'STU6A%'"
    )
    print(f"  Orphan performance rows (6A): {row['orphans']}")

    # Check attendance_weekly nulls and structure
    try:
        print("\nattendance_weekly NULL distribution (6A, sample cols):")
        row = await conn.fetchrow(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN week_number IS NULL THEN 1 ELSE 0 END) AS week_null "
            "FROM attendance_weekly WHERE student_id LIKE 'STU6A%'"
        )
        print(dict(row))
    except Exception as e:
        print(f"attendance_weekly NULL check: {e}")

    # Check student_learning_activity structure
    try:
        print("\nstudent_learning_activity NULL check (6A):")
        row = await conn.fetchrow(
            "SELECT COUNT(*) AS total FROM student_learning_activity WHERE student_id LIKE 'STU6A%'"
        )
        print(f"  Total learning activity rows (6A): {row['total']}")
    except Exception as e:
        print(f"  ERROR: {e}")

    await conn.close()
    print("\n=== Done ===")


asyncio.run(main())
