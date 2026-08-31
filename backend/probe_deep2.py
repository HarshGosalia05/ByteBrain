"""Supplementary data probe - part 2."""
import asyncio
import asyncpg
from pathlib import Path


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
    ssl_mode = "require" if ("supabase" in DB_HOST or DB_PORT == 6543) else None
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASS, ssl=ssl_mode,
        statement_cache_size=0
    )
    print("Connected OK.\n")

    # Range of key marks (corrected - no window function in GROUP BY)
    print("=== Key marks ranges (6A performance) ===")
    row = await conn.fetchrow(
        "SELECT MIN(internal_marks) AS int_min, MAX(internal_marks) AS int_max, "
        "MIN(mid_sem_marks) AS mid_min, MAX(mid_sem_marks) AS mid_max, "
        "MIN(end_sem_marks) AS end_min, MAX(end_sem_marks) AS end_max, "
        "MIN(assignment_score) AS assign_min, MAX(assignment_score) AS assign_max, "
        "MIN(quiz_avg_marks) AS quiz_min, MAX(quiz_avg_marks) AS quiz_max "
        "FROM student_subject_performance WHERE student_id LIKE 'STU6A%'"
    )
    print(dict(row))

    # Internal marks decile - step by step
    print("\n=== End_sem distribution by internal_marks range (6A) ===")
    rows = await conn.fetch(
        "SELECT CASE "
        "WHEN internal_marks <= 10 THEN '0-10' "
        "WHEN internal_marks <= 14 THEN '11-14' "
        "WHEN internal_marks <= 16 THEN '15-16' "
        "WHEN internal_marks <= 18 THEN '17-18' "
        "ELSE '19-20' END AS int_band, "
        "COUNT(*) AS n, AVG(end_sem_marks) AS mean_end "
        "FROM student_subject_performance WHERE student_id LIKE 'STU6A%' "
        "GROUP BY 1 ORDER BY 1"
    )
    for r in rows:
        print(f"  internal={r['int_band']}: n={r['n']}, mean_end={float(r['mean_end']):.2f}")

    # pre_endsem_assessment_pct distribution
    print("\n=== pre_endsem_assessment_pct stats (6A) ===")
    row = await conn.fetchrow(
        "SELECT MIN(pre_endsem_assessment_pct) AS pmin, MAX(pre_endsem_assessment_pct) AS pmax, "
        "AVG(pre_endsem_assessment_pct) AS pmean "
        "FROM student_subject_performance WHERE student_id LIKE 'STU6A%'"
    )
    print(dict(row))

    # assignment_score and quiz null count
    print("\n=== assignment_score / quiz_avg null counts (6A) ===")
    row = await conn.fetchrow(
        "SELECT "
        "SUM(CASE WHEN assignment_score IS NULL THEN 1 ELSE 0 END) AS assign_null, "
        "SUM(CASE WHEN quiz_avg_marks IS NULL THEN 1 ELSE 0 END) AS quiz_null, "
        "SUM(CASE WHEN submission_delay_days IS NULL THEN 1 ELSE 0 END) AS delay_null, "
        "SUM(CASE WHEN pre_endsem_assessment_pct IS NULL THEN 1 ELSE 0 END) AS preendsem_null "
        "FROM student_subject_performance WHERE student_id LIKE 'STU6A%'"
    )
    print(dict(row))

    # subject_type distribution
    print("\n=== Subject type distribution (subjects table) ===")
    rows = await conn.fetch(
        "SELECT subject_type, COUNT(*) AS n FROM subjects GROUP BY subject_type ORDER BY n DESC"
    )
    for r in rows:
        print(f"  {r['subject_type']}: {r['n']}")

    # Attendance weekly: weeks per enrollment record
    print("\n=== Weeks per enrollment in attendance_weekly (6A, sem 1, sample) ===")
    rows = await conn.fetch(
        "SELECT enrollment_record_id, semester_no, COUNT(DISTINCT week_number) AS weeks, "
        "SUM(classes_held) AS total_held, SUM(classes_attended) AS total_attended "
        "FROM attendance_weekly WHERE student_id LIKE 'STU6A%' AND semester_no=1 "
        "GROUP BY enrollment_record_id, semester_no LIMIT 5"
    )
    for r in rows:
        print(dict(r))

    # Learning activity: aggregate per enrollment for sem 1 sample
    print("\n=== Learning activity aggregate per enrollment (6A, sem 1, 3 samples) ===")
    rows = await conn.fetch(
        "SELECT enrollment_record_id, semester_no, "
        "SUM(activity_volume) AS total_activity, "
        "AVG(engagement_consistency) AS avg_engagement, "
        "AVG(assessment_completion_rate) AS avg_completion, "
        "AVG(late_submission_rate) AS avg_late_submit "
        "FROM student_learning_activity WHERE student_id LIKE 'STU6A%' AND semester_no=1 "
        "GROUP BY enrollment_record_id, semester_no LIMIT 3"
    )
    for r in rows:
        print({k: float(v) if hasattr(v, 'is_nan') else v for k, v in dict(r).items()})

    # Lifestyle survey - semester distribution for 6A
    print("\n=== student_lifestyle_survey by semester (6A) ===")
    rows = await conn.fetch(
        "SELECT semester_no, COUNT(*) AS n FROM student_lifestyle_survey "
        "WHERE student_id LIKE 'STU6A%' GROUP BY semester_no ORDER BY semester_no"
    )
    for r in rows:
        print(f"  sem {r['semester_no']}: {r['n']} rows")

    # Sample lifestyle survey for a 6A student
    print("\n=== Sample student_lifestyle_survey for STU6A0001 ===")
    rows = await conn.fetch(
        "SELECT * FROM student_lifestyle_survey WHERE student_id='STU6A0001' ORDER BY semester_no"
    )
    for r in rows:
        print(dict(r))

    # Current semester distribution for 6A students
    print("\n=== Current semester distribution (students, 6A) ===")
    rows = await conn.fetch(
        "SELECT current_semester, COUNT(*) AS n FROM students "
        "WHERE student_id LIKE 'STU6A%' GROUP BY current_semester ORDER BY current_semester"
    )
    for r in rows:
        print(f"  current_semester={r['current_semester']}: {r['n']} students")

    # Division breakdown
    print("\n=== Division breakdown (all students) ===")
    rows = await conn.fetch(
        "SELECT division, COUNT(*) AS n FROM students GROUP BY division ORDER BY n DESC"
    )
    for r in rows:
        print(f"  division={r['division']}: {r['n']}")

    # Subjects per semester
    print("\n=== Subjects per semester ===")
    rows = await conn.fetch(
        "SELECT semester_no, COUNT(*) AS n FROM subjects "
        "GROUP BY semester_no ORDER BY semester_no"
    )
    for r in rows:
        print(f"  sem {r['semester_no']}: {r['n']} subjects")

    # Student skill profile - null proficiency check
    print("\n=== student_skill_profile null check (6A) ===")
    row = await conn.fetchrow(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN proficiency_level IS NULL THEN 1 ELSE 0 END) AS prof_null "
        "FROM student_skill_profile WHERE student_id LIKE 'STU6A%'"
    )
    print(dict(row))

    # FK: enrollment-record-based join cardinality check
    print("\n=== Join cardinality: performance JOIN attendance_weekly (6A, sem 1, 5 records) ===")
    rows = await conn.fetch(
        "SELECT p.enrollment_record_id, COUNT(a.attendance_id) AS att_weekly_rows "
        "FROM student_subject_performance p "
        "LEFT JOIN attendance_weekly a ON p.enrollment_record_id = a.enrollment_record_id "
        "WHERE p.student_id LIKE 'STU6A%' AND p.semester_no=1 "
        "GROUP BY p.enrollment_record_id LIMIT 5"
    )
    for r in rows:
        print(dict(r))

    # Check attendance_weekly week range
    print("\n=== attendance_weekly week_number range (6A) ===")
    row = await conn.fetchrow(
        "SELECT MIN(week_number) AS wmin, MAX(week_number) AS wmax "
        "FROM attendance_weekly WHERE student_id LIKE 'STU6A%'"
    )
    print(dict(row))

    # Check learning_activity week range
    print("\n=== student_learning_activity week_number range (6A) ===")
    row = await conn.fetchrow(
        "SELECT MIN(week_number) AS wmin, MAX(week_number) AS wmax "
        "FROM student_learning_activity WHERE student_id LIKE 'STU6A%'"
    )
    print(dict(row))

    await conn.close()
    print("\n=== Done ===")


asyncio.run(main())
