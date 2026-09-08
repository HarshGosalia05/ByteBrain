"""M3 V2 Feature Diagnostic — Check DB data for attendance + learning activity."""
import asyncio
import asyncpg
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from db_env import db_config

cfg = db_config()
CONN = {
    "host": cfg.host,
    "port": cfg.port,
    "database": cfg.name,
    "user": cfg.user,
    "password": cfg.password,
}

# Get SSL settings same as the app
ssl_mode = "require" if ("supabase" in cfg.host or cfg.port == 6543) else None

async def run():
    conn = await asyncpg.connect(**CONN, ssl=ssl_mode)
    try:
        # 1. Check row counts
        print("=" * 80)
        print("ROW COUNTS")
        print("=" * 80)
        for tbl in ["students", "attendance_weekly", "student_learning_activity", "student_semester_summary"]:
            row = await conn.fetchrow(f"SELECT COUNT(*) AS cnt FROM {tbl}")
            print(f"  {tbl}: {row['cnt']:,}")

        # 2. Check how many STU6A students have attendance data
        print("\n" + "=" * 80)
        print("6A STUDENT DATA COVERAGE")
        print("=" * 80)
        row = await conn.fetchrow("""
            SELECT COUNT(DISTINCT student_id) AS cnt 
            FROM attendance_weekly WHERE student_id LIKE 'STU6A%'
        """)
        print(f"  Students with attendance_weekly data: {row['cnt']}")

        row = await conn.fetchrow("""
            SELECT COUNT(DISTINCT student_id) AS cnt 
            FROM student_learning_activity WHERE student_id LIKE 'STU6A%'
        """)
        print(f"  Students with learning_activity data: {row['cnt']}")

        row = await conn.fetchrow("""
            SELECT COUNT(DISTINCT student_id) AS cnt 
            FROM students WHERE student_id LIKE 'STU6A%'
        """)
        print(f"  Total 6A students: {row['cnt']}")

        # 3. Pick a specific student and check all data
        test_student = "STU6A0001"
        print(f"\n{'=' * 80}")
        print(f"DETAILED DATA FOR {test_student}")
        print("=" * 80)

        # Check student record
        stu = await conn.fetchrow("SELECT * FROM students WHERE student_id = $1", test_student)
        if stu:
            d = dict(stu)
            print(f"\n  Student: {d.get('student_id')}, sem={d.get('current_semester')}, dept={d.get('department_name')}")
        else:
            print(f"\n  Student {test_student} NOT FOUND")

        # Check semester summary
        ss = await conn.fetch("SELECT semester_no, semester_sgpa, semester_attendance_percentage, attendance_aggregate_pct FROM student_semester_summary WHERE student_id = $1 ORDER BY semester_no", test_student)
        print(f"\n  Semester summary rows: {len(ss)}")
        for r in ss:
            d = dict(r)
            print(f"    sem {d['semester_no']}: sgpa={d['semester_sgpa']}, att%={d['semester_attendance_percentage']}, att_agg={d['attendance_aggregate_pct']}")

        # Check attendance_weekly
        att = await conn.fetch("SELECT semester_no, subject_id, week_number, classes_held, classes_attended FROM attendance_weekly WHERE student_id = $1 ORDER BY semester_no, subject_id, week_number", test_student)
        print(f"\n  Attendance weekly rows: {len(att)}")
        if att:
            # Group by semester
            sems = {}
            for r in att:
                d = dict(r)
                s = d['semester_no']
                if s not in sems:
                    sems[s] = 0
                sems[s] += 1
            for s in sorted(sems.keys()):
                print(f"    semester {s}: {sems[s]} rows")
            # Show first few
            for r in att[:3]:
                d = dict(r)
                print(f"    sample: sem={d['semester_no']}, subj={d['subject_id']}, wk={d['week_number']}, held={d['classes_held']}, attended={d['classes_attended']}")
        else:
            print("    *** NO DATA ***")

        # Check learning activity
        learn = await conn.fetch("SELECT semester_no, subject_id, week_number, activity_volume, engagement_consistency, assessment_completion_rate, late_submission_rate FROM student_learning_activity WHERE student_id = $1 ORDER BY semester_no, subject_id, week_number", test_student)
        print(f"\n  Learning activity rows: {len(learn)}")
        if learn:
            sems = {}
            for r in learn:
                d = dict(r)
                s = d['semester_no']
                if s not in sems:
                    sems[s] = 0
                sems[s] += 1
            for s in sorted(sems.keys()):
                print(f"    semester {s}: {sems[s]} rows")
            for r in learn[:3]:
                d = dict(r)
                print(f"    sample: sem={d['semester_no']}, subj={d['subject_id']}, wk={d['week_number']}, vol={d['activity_volume']}, eng={d['engagement_consistency']}")
        else:
            print("    *** NO DATA ***")

        # 4. Manually compute features for the student
        print(f"\n{'=' * 80}")
        print(f"MANUAL FEATURE COMPUTATION FOR {test_student}")
        print("=" * 80)

        # Get the observation semester T (current_semester)
        if stu:
            T = dict(stu).get('current_semester')
            print(f"  Observation semester T = {T}")

            # att_tsem_total_pct = 100 * SUM(classes_attended) / SUM(classes_held)
            att_agg = await conn.fetchrow("""
                SELECT SUM(classes_held) AS held, SUM(classes_attended) AS attended
                FROM attendance_weekly
                WHERE student_id = $1 AND semester_no = $2
            """, test_student, T)
            if att_agg and att_agg['held']:
                pct = 100.0 * att_agg['attended'] / att_agg['held']
                print(f"  att_tsem_total_pct = 100 * {att_agg['attended']}/{att_agg['held']} = {pct:.2f}")
            else:
                print(f"  att_tsem_total_pct = NaN (no attendance data for sem {T})")

            # attendance_aggregate_pct from student_semester_summary
            ss_row = await conn.fetchrow("""
                SELECT semester_attendance_percentage, attendance_aggregate_pct
                FROM student_semester_summary
                WHERE student_id = $1 AND semester_no = $2
            """, test_student, T)
            if ss_row:
                print(f"  semester_attendance_percentage = {ss_row['semester_attendance_percentage']}")
                print(f"  attendance_aggregate_pct = {ss_row['attendance_aggregate_pct']}")
            else:
                print(f"  No semester summary for sem {T}")

            # learn_tsem_volume_total = SUM(activity_volume)
            lr_agg = await conn.fetchrow("""
                SELECT SUM(activity_volume) AS total_vol
                FROM student_learning_activity
                WHERE student_id = $1 AND semester_no = $2
            """, test_student, T)
            if lr_agg and lr_agg['total_vol'] is not None:
                print(f"  learn_tsem_volume_total = {lr_agg['total_vol']}")
            else:
                print(f"  learn_tsem_volume_total = NaN (no learning data for sem {T})")

        # 5. Check a few more students
        print(f"\n{'=' * 80}")
        print("MULTI-STUDENT ATTENDANCE + LEARNING CHECK")
        print("=" * 80)
        students = await conn.fetch("SELECT student_id, current_semester FROM students WHERE student_id LIKE 'STU6A%' ORDER BY student_id LIMIT 10")
        for s in students:
            sid = s['student_id']
            cur_sem = s['current_semester']
            att_row = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM attendance_weekly WHERE student_id = $1 AND semester_no = $2", sid, cur_sem)
            lr_row = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM student_learning_activity WHERE student_id = $1 AND semester_no = $2", sid, cur_sem)
            print(f"  {sid} (cur_sem={cur_sem}): att_rows={att_row['cnt']}, lr_rows={lr_row['cnt']}")

    finally:
        await conn.close()

asyncio.run(run())
