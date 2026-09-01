"""Diagnostic script: audit data availability for 80 production students."""
import asyncio
import asyncpg
import os
from pathlib import Path

# Load env
env = {}
for env_file in ['.env.local', '.env']:
    p = Path(env_file)
    if p.exists():
        with open(p, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        break

host = env.get('DB_HOST', 'localhost')
port = int(env.get('DB_PORT', '5432'))
dbname = env.get('DB_NAME', 'postgres')
user = env.get('DB_USER', 'postgres')
password = env.get('DB_PASSWORD', 'password')
ssl_mode = 'require' if ('supabase' in host or port == 6543) else None


async def run():
    conn = await asyncpg.connect(host=host, port=port, database=dbname,
                                user=user, password=password, ssl=ssl_mode)
    try:
        # 1. Target availability
        print("=== TARGET AVAILABILITY (end_sem_marks) ===")
        rows = await conn.fetch("""
            SELECT semester_no,
                   COUNT(*) as total,
                   COUNT(end_sem_marks) as non_null,
                   COUNT(*) FILTER (WHERE end_sem_marks IS NULL) as null_count
            FROM student_subject_performance
            WHERE student_id LIKE 'STU000%'
            GROUP BY semester_no ORDER BY semester_no
        """)
        for r in rows:
            print(f"  Sem {r['semester_no']}: {r['total']} rows, {r['non_null']} labeled, {r['null_count']} NULL")

        # 2. Feature columns
        print("\n=== FEATURE COLUMNS IN student_subject_performance ===")
        for feat in ['internal_marks', 'mid_sem_marks', 'pre_endsem_assessment_pct',
                      'assignment_score', 'quiz_avg_marks', 'submission_delay_days']:
            r = await conn.fetchrow(f"""
                SELECT COUNT(*) as total, COUNT({feat}) as nn
                FROM student_subject_performance
                WHERE student_id LIKE 'STU000%'
            """)
            pct = 100 * r['nn'] / max(r['total'], 1)
            print(f"  {feat}: {r['nn']}/{r['total']} ({pct:.0f}%)")

        # 3. subject_domain
        r = await conn.fetchrow("""
            SELECT COUNT(*) as total, COUNT(subject_domain) as nn
            FROM student_subject_performance WHERE student_id LIKE 'STU000%'
        """)
        print(f"  subject_domain: {r['nn']}/{r['total']} ({100*r['nn']/max(r['total'],1):.0f}%)")

        # 4. student_learning_activity
        r = await conn.fetchrow("SELECT COUNT(*) as cnt FROM student_learning_activity WHERE student_id LIKE 'STU000%'")
        print(f"\n=== STUDENT LEARNING ACTIVITY: {r['cnt']} rows ===")

        # 5. attendance_weekly
        print("\n=== ATTENDANCE WEEKLY ===")
        rows = await conn.fetch("""
            SELECT semester_no, COUNT(DISTINCT student_id) as students, COUNT(*) as rows
            FROM attendance_weekly WHERE student_id LIKE 'STU000%'
            GROUP BY semester_no ORDER BY semester_no
        """)
        for r in rows:
            print(f"  Sem {r['semester_no']}: {r['students']} students, {r['rows']} rows")
        if not rows:
            print("  NO DATA")

        # 6. Lifestyle survey
        print("\n=== LIFESTYLE SURVEY ===")
        rows = await conn.fetch("""
            SELECT semester_no, COUNT(*) as cnt,
                   COUNT(mental_stress_level) as stress_nn,
                   COUNT(study_hours_per_week) as study_nn
            FROM student_lifestyle_survey WHERE student_id LIKE 'STU000%'
            GROUP BY semester_no ORDER BY semester_no
        """)
        for r in rows:
            print(f"  Sem {r['semester_no']}: {r['cnt']} rows, stress={r['stress_nn']}, study={r['study_nn']}")
        if not rows:
            print("  NO DATA")

        # 7. Semester summary
        print("\n=== STUDENT SEMESTER SUMMARY ===")
        rows = await conn.fetch("""
            SELECT semester_no, COUNT(*) as cnt,
                   COUNT(semester_sgpa) as sgpa_nn,
                   COUNT(semester_attendance_percentage) as att_nn,
                   COUNT(cumulative_backlog_events) as backlog_nn,
                   COUNT(sgpa_drift) as drift_nn,
                   COUNT(backlog_count) as backlog_count_nn
            FROM student_semester_summary WHERE student_id LIKE 'STU000%'
            GROUP BY semester_no ORDER BY semester_no
        """)
        for r in rows:
            print(f"  Sem {r['semester_no']}: {r['cnt']} rows, sgpa={r['sgpa_nn']}, att={r['att_nn']}, "
                  f"backlog_events={r['backlog_nn']}, backlog_count={r['backlog_count_nn']}, drift={r['drift_nn']}")
        if not rows:
            print("  NO DATA")

        # 8. Students
        print("\n=== STUDENTS TABLE ===")
        r = await conn.fetchrow("""
            SELECT COUNT(*) as total, COUNT(current_semester) as curr_sem_nn,
                   MIN(current_semester) as min_sem, MAX(current_semester) as max_sem
            FROM students WHERE student_id LIKE 'STU000%'
        """)
        print(f"  Total: {r['total']}, current_semester: {r['curr_sem_nn']}, range: {r['min_sem']}-{r['max_sem']}")

        # 9. Enrollment
        print("\n=== ENROLLMENT ===")
        rows = await conn.fetch("""
            SELECT semester_no, COUNT(DISTINCT student_id) as students, COUNT(*) as rows
            FROM student_subject_enrollment WHERE student_id LIKE 'STU000%'
            GROUP BY semester_no ORDER BY semester_no
        """)
        for r in rows:
            print(f"  Sem {r['semester_no']}: {r['students']} students, {r['rows']} rows")

        # 10. Specific check: which 80 students have end_sem_marks in any sem?
        print("\n=== STUDENTS WITH end_sem_marks (ANY semester) ===")
        r = await conn.fetchrow("""
            SELECT COUNT(DISTINCT student_id) as students
            FROM student_subject_performance
            WHERE student_id LIKE 'STU000%' AND end_sem_marks IS NOT NULL
        """)
        print(f"  Students with at least one labeled record: {r['students']}/80")

        # Which semesters have labels?
        rows = await conn.fetch("""
            SELECT semester_no, COUNT(DISTINCT student_id) as labeled_students,
                   COUNT(*) as labeled_rows
            FROM student_subject_performance
            WHERE student_id LIKE 'STU000%' AND end_sem_marks IS NOT NULL
            GROUP BY semester_no ORDER BY semester_no
        """)
        print("  Per-semester with labels:")
        for r in rows:
            print(f"    Sem {r['semester_no']}: {r['labeled_students']} students, {r['labeled_rows']} rows")

        # 11. M1 V2 column: pre_endsem_assessment_pct — check if it is ever populated for 80 students
        print("\n=== pre_endsem_assessment_pct for 80 students ===")
        r = await conn.fetchrow("""
            SELECT COUNT(*) as total,
                   COUNT(pre_endsem_assessment_pct) as nn
            FROM student_subject_performance
            WHERE student_id LIKE 'STU000%'
        """)
        print(f"  {r['nn']}/{r['total']} non-null")

        # Can we compute it as (internal + mid) / 70 * 100?
        r = await conn.fetchrow("""
            SELECT COUNT(*) as total,
                   COUNT(internal_marks) as internal_nn,
                   COUNT(mid_sem_marks) as mid_nn
            FROM student_subject_performance
            WHERE student_id LIKE 'STU000%'
        """)
        print(f"  internal_marks: {r['internal_nn']}/{r['total']}, mid_sem_marks: {r['mid_nn']}/{r['total']}")

        # 12. Check config.ORDINAL_FEATURES mismatch: v1 has "Very High"
        print("\n=== MENTAL STRESS LEVEL VALUES (80 students) ===")
        rows = await conn.fetch("""
            SELECT mental_stress_level, COUNT(*) as cnt
            FROM student_lifestyle_survey
            WHERE student_id LIKE 'STU000%'
            GROUP BY mental_stress_level
        """)
        for r in rows:
            print(f"  '{r['mental_stress_level']}': {r['cnt']}")
        if not rows:
            print("  NO DATA")

        # 13. Check study_hours_per_week values
        print("\n=== STUDY HOURS VALUES (80 students) ===")
        r = await conn.fetchrow("""
            SELECT MIN(study_hours_per_week) as min_h, MAX(study_hours_per_week) as max_h,
                   AVG(study_hours_per_week) as avg_h, COUNT(study_hours_per_week) as nn
            FROM student_lifestyle_survey WHERE student_id LIKE 'STU000%'
        """)
        if r and r['nn']:
            print(f"  min={r['min_h']}, max={r['max_h']}, avg={r['avg_h']:.2f}, nn={r['nn']}")
        else:
            print("  NO DATA (0 rows)")

        # 14. Check v1 lifestyle table structure
        print("\n=== LIFESTYLE SURVEY TABLE COLUMNS ===")
        rows = await conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'student_lifestyle_survey'
            ORDER BY ordinal_position
        """)
        for r in rows:
            print(f"  {r['column_name']}")

        # 15. Check actual sem5 label distribution by student
        print("\n=== SEM 5 LABEL DISTRIBUTION ===")
        rows = await conn.fetch("""
            SELECT student_id, COUNT(*) as total, COUNT(end_sem_marks) as labeled
            FROM student_subject_performance
            WHERE student_id LIKE 'STU000%' AND semester_no = 5
            GROUP BY student_id
            HAVING COUNT(end_sem_marks) < COUNT(*)
            ORDER BY student_id
        """)
        print(f"  Students with partial sem 5 labels: {len(rows)}")
        for r in rows[:5]:
            print(f"    {r['student_id']}: {r['labeled']}/{r['total']} labeled")
        if len(rows) > 5:
            print(f"    ... and {len(rows)-5} more")

        # 16. Total labeled rows available for training
        r = await conn.fetchrow("""
            SELECT COUNT(*) as total_labeled
            FROM student_subject_performance
            WHERE student_id LIKE 'STU000%' AND end_sem_marks IS NOT NULL
        """)
        print(f"\n=== TOTAL LABELED ROWS (all semesters): {r['total_labeled']} ===")

        # 17. Can we compute sgpa_drift from semester_summary?
        print("\n=== SGPA DRIFT COMPUTABLE? ===")
        rows = await conn.fetch("""
            SELECT student_id, semester_no, semester_sgpa
            FROM student_semester_summary
            WHERE student_id LIKE 'STU000%'
            ORDER BY student_id, semester_no
        """)
        # Check if there are multiple semesters per student
        students_with_mult = 0
        for sid in set(r['student_id'] for r in rows):
            sems = [r['semester_no'] for r in rows if r['student_id'] == sid]
            if len(sems) > 1:
                students_with_mult += 1
        print(f"  Students with >1 semester in summary: {students_with_mult}/80")

    finally:
        await conn.close()


asyncio.run(run())
