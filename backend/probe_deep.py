"""Deep data probe for M1 v2 - understanding the deployment boundary and data structure."""
import asyncio
import asyncpg
from pathlib import Path
from decimal import Decimal


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

    # is_m1_deployment_boundary distribution in student_semester_summary
    print("=== is_m1_deployment_boundary (student_semester_summary, 6A) ===")
    rows = await conn.fetch(
        "SELECT is_m1_deployment_boundary, COUNT(*) AS n "
        "FROM student_semester_summary WHERE student_id LIKE 'STU6A%' "
        "GROUP BY is_m1_deployment_boundary"
    )
    for r in rows:
        print(f"  is_m1_deployment_boundary={r['is_m1_deployment_boundary']}: {r['n']} rows")

    # target_available_if_completed distribution
    print("\n=== target_available_if_completed (student_semester_summary, 6A) ===")
    rows = await conn.fetch(
        "SELECT target_available_if_completed, COUNT(*) AS n "
        "FROM student_semester_summary WHERE student_id LIKE 'STU6A%' "
        "GROUP BY target_available_if_completed"
    )
    for r in rows:
        print(f"  target_available_if_completed={r['target_available_if_completed']}: {r['n']} rows")

    # Semester breakdown of is_m1_deployment_boundary
    print("\n=== is_m1_deployment_boundary by semester (6A) ===")
    rows = await conn.fetch(
        "SELECT semester_no, is_m1_deployment_boundary, COUNT(*) AS n "
        "FROM student_semester_summary WHERE student_id LIKE 'STU6A%' "
        "GROUP BY semester_no, is_m1_deployment_boundary ORDER BY semester_no"
    )
    for r in rows:
        print(f"  sem {r['semester_no']}, deploy_boundary={r['is_m1_deployment_boundary']}: {r['n']} rows")

    # Sample student_semester_summary for a 6A student
    print("\n=== Sample student_semester_summary for STU6A0001 ===")
    rows = await conn.fetch(
        "SELECT student_id, semester_no, semester_sgpa, semester_percentage, "
        "sgpa_drift, sgpa_rolling_mean_3, backlog_count, cumulative_backlog_events, "
        "is_m1_deployment_boundary, target_available_if_completed "
        "FROM student_semester_summary WHERE student_id='STU6A0001' ORDER BY semester_no"
    )
    for r in rows:
        print(dict(r))

    # Check the deployment boundary marker linking to semester 8
    print("\n=== Students in semester 8 (deployment boundary) ===")
    row = await conn.fetchrow(
        "SELECT COUNT(DISTINCT student_id) AS n FROM student_subject_performance "
        "WHERE student_id LIKE 'STU6A%' AND semester_no=8"
    )
    print(f"  Distinct students with sem 8 performance: {row['n']}")

    # Correlation check: internal/mid vs end_sem for feature insight
    print("\n=== Correlation proxy: mean end_sem by internal decile (6A, all sems) ===")
    rows = await conn.fetch(
        "SELECT "
        "NTILE(5) OVER (ORDER BY internal_marks) AS decile_internal, "
        "AVG(end_sem_marks) AS mean_end_sem "
        "FROM student_subject_performance WHERE student_id LIKE 'STU6A%' "
        "GROUP BY decile_internal ORDER BY decile_internal"
    )
    for r in rows:
        print(f"  decile {r['decile_internal']}: mean end_sem = {float(r['mean_end_sem']):.2f}")

    # Range of key marks
    print("\n=== Key marks ranges (6A performance) ===")
    row = await conn.fetchrow(
        "SELECT MIN(internal_marks) AS int_min, MAX(internal_marks) AS int_max, "
        "MIN(mid_sem_marks) AS mid_min, MAX(mid_sem_marks) AS mid_max, "
        "MIN(end_sem_marks) AS end_min, MAX(end_sem_marks) AS end_max, "
        "MIN(assignment_score) AS assign_min, MAX(assignment_score) AS assign_max, "
        "MIN(quiz_avg_marks) AS quiz_min, MAX(quiz_avg_marks) AS quiz_max "
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
    print("\n=== Weeks per enrollment in attendance_weekly (6A, sample) ===")
    rows = await conn.fetch(
        "SELECT enrollment_record_id, semester_no, COUNT(DISTINCT week_number) AS weeks, "
        "SUM(classes_held) AS total_held, SUM(classes_attended) AS total_attended "
        "FROM attendance_weekly WHERE student_id LIKE 'STU6A%' AND semester_no=1 "
        "GROUP BY enrollment_record_id, semester_no LIMIT 5"
    )
    for r in rows:
        print(dict(r))

    # Learning activity: aggregate per enrollment for sem 1 sample
    print("\n=== Learning activity aggregate per enrollment (6A, sem 1, sample 3) ===")
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
        print(dict(r))

    # Lifestyle survey - semester distribution for 6A
    print("\n=== student_lifestyle_survey by semester (6A) ===")
    rows = await conn.fetch(
        "SELECT semester_no, COUNT(*) AS n FROM student_lifestyle_survey "
        "WHERE student_id LIKE 'STU6A%' GROUP BY semester_no ORDER BY semester_no"
    )
    for r in rows:
        print(f"  sem {r['semester_no']}: {r['n']} rows")

    # Student_skill_profile - domain distribution
    print("\n=== student_skill_profile - skill_domain distribution (6A) ===")
    rows = await conn.fetch(
        "SELECT skill_domain, COUNT(*) AS n FROM student_skill_profile "
        "WHERE student_id LIKE 'STU6A%' GROUP BY skill_domain ORDER BY n DESC LIMIT 10"
    )
    for r in rows:
        print(f"  {r['skill_domain']}: {r['n']}")

    # Prior history - max semester for each 6A student
    print("\n=== Current semester distribution (students table, 6A) ===")
    rows = await conn.fetch(
        "SELECT current_semester, COUNT(*) AS n FROM students "
        "WHERE student_id LIKE 'STU6A%' GROUP BY current_semester ORDER BY current_semester"
    )
    for r in rows:
        print(f"  current_semester={r['current_semester']}: {r['n']} students")

    # Check the student_semester_summary rows for the prior-history aggregation
    print("\n=== student_semester_summary sample for 6A (semester 1 to 4, first student) ===")
    rows = await conn.fetch(
        "SELECT * FROM student_semester_summary "
        "WHERE student_id='STU6A0001' ORDER BY semester_no LIMIT 5"
    )
    for r in rows:
        print(dict(r))

    # Division-specific analysis
    print("\n=== 6A vs non-6A student count breakdown ===")
    rows = await conn.fetch(
        "SELECT division, COUNT(*) AS n FROM students GROUP BY division ORDER BY n DESC"
    )
    for r in rows:
        print(f"  division={r['division']}: {r['n']}")

    # Subjects: how many per semester
    print("\n=== Subjects per semester ===")
    rows = await conn.fetch(
        "SELECT semester_no, COUNT(*) AS n FROM subjects "
        "GROUP BY semester_no ORDER BY semester_no"
    )
    for r in rows:
        print(f"  sem {r['semester_no']}: {r['n']} subjects")

    await conn.close()
    print("\n=== Done ===")


asyncio.run(main())
