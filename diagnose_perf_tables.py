"""Check student_subject_performance detail for real cohort — do assignment/quiz fields exist?"""
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
ssl_mode = "require" if ("supabase" in cfg.host or cfg.port == 6543) else None

async def run():
    conn = await asyncpg.connect(**CONN, ssl=ssl_mode, statement_cache_size=0)
    try:
        print("=" * 80)
        print("STUDENT_SUBJECT_PERFORMANCE COLS: STU000001 vs STU6A0001")
        print("=" * 80)
        for sid in ["STU000001", "STU6A0001"]:
            srow = await conn.fetchrow("""
                SELECT 
                    COUNT(*) AS total,
                    COUNT(assignment_score) AS assignment_nonnull,
                    COUNT(quiz_avg_marks) AS quiz_nonnull,
                    COUNT(submission_delay_days) AS delay_nonnull,
                    COUNT(pre_endsem_assessment_pct) AS pre_endsem_nonnull,
                    MIN(semester_no) AS min_sem, MAX(semester_no) AS max_sem
                FROM student_subject_performance
                WHERE student_id = $1
            """, sid)
            d = dict(srow)
            print(f"  {sid}: total={d['total']}, assignment_ok={d['assignment_nonnull']}, quiz_ok={d['quiz_nonnull']}, delay_ok={d['delay_nonnull']}, pre_endsem_ok={d['pre_endsem_nonnull']}, sems={d['min_sem']}..{d['max_sem']}")

            # Sample rows for sem 7
            rows = await conn.fetch("""
                SELECT semester_no, subject_id, internal_marks, mid_sem_marks, end_sem_marks, 
                       assignment_score, quiz_avg_marks, submission_delay_days, pre_endsem_assessment_pct,
                       result_status
                FROM student_subject_performance
                WHERE student_id = $1 AND semester_no = 7
                ORDER BY subject_id
                LIMIT 3
            """, sid)
            for r in rows:
                print(f"    sem7: {dict(r)}")

        print("\n" + "=" * 80)
        print("ATTENDANCE TABLE: columns + STU000001 all semesters")
        print("=" * 80)
        att_rows = await conn.fetch("""
            SELECT semester_no, SUM(total_classes) AS held, SUM(attended_classes) AS attended
            FROM attendance
            WHERE student_id = 'STU000001'
            GROUP BY semester_no
            ORDER BY semester_no
        """)
        for r in att_rows:
            d = dict(r)
            pct = 100.0 * d['attended'] / d['held'] if d['held'] else None
            print(f"  sem {d['semester_no']}: held={d['held']}, attended={d['attended']}, att%= {pct:.2f}")

        print("\n" + "=" * 80)
        print("STUDENT_SEMESTER_SUMMARY: semester_attendance_percentage vs attendance table for real cohort")
        print("=" * 80)
        ss_rows = await conn.fetch("""
            SELECT semester_no, semester_attendance_percentage, attendance_aggregate_pct
            FROM student_semester_summary
            WHERE student_id = 'STU000001'
            ORDER BY semester_no
        """)
        for r in ss_rows:
            print(f"  sem {r['semester_no']}: sem_att%={r['semester_attendance_percentage']}, aggregate_pct={r['attendance_aggregate_pct']}")

        # Check semester 7 total classes to understand why attendance table says 125 vs summary 87.35
        print("\n" + "=" * 80)
        print("ATTENDANCE TABLE SEM 7 DETAIL")
        print("=" * 80)
        rows = await conn.fetch("""
            SELECT subject_id, total_classes, attended_classes, attendance_percentage
            FROM attendance
            WHERE student_id = 'STU000001' AND semester_no = 7
            ORDER BY subject_id
        """)
        for r in rows:
            print(f"  {r['subject_id']}: held={r['total_classes']}, att={r['attended_classes']}, pct={r['attendance_percentage']}")

    finally:
        await conn.close()

asyncio.run(run())