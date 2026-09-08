"""Verify learning activity derivability for real cohort + attendance ratio equivalence."""
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
        print("1. ANY learning-activity-like source for real cohort?")
        print("=" * 80)
        # Check all columns of student_subject_performance for real cohort null-status across all 80 students
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) AS total,
                COUNT(assignment_score) AS assignment_nonnull,
                COUNT(quiz_avg_marks) AS quiz_nonnull,
                COUNT(submission_delay_days) AS delay_nonnull,
                COUNT(pre_endsem_assessment_pct) AS pre_endsem_nonnull,
                COUNT(ct1_marks) AS ct1_nonnull,
                COUNT(ct2_marks) AS ct2_nonnull
            FROM student_subject_performance
            WHERE student_id LIKE 'STU000%'
        """)
        d = dict(row)
        print(f"  real cohort subject_performance: total={d['total']}, assignment={d['assignment_nonnull']}, quiz={d['quiz_nonnull']}, delay={d['delay_nonnull']}, pre_endsem={d['pre_endsem_nonnull']}, ct1={d['ct1_nonnull']}, ct2={d['ct2_nonnull']}")

        # Any learning-activity-like tables?
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        print("  All tables: ", [t['table_name'] for t in tables])

        # 2. Validate attendance table ratio == semester summary ratio for ALL completed sems
        print("\n" + "=" * 80)
        print("2. attendance table ratio vs semester_attendance_percentage (real cohort)")
        print("=" * 80)
        rows = await conn.fetch("""
            SELECT 
                ss.student_id, ss.semester_no,
                ss.semester_attendance_percentage AS summary_pct,
                SUM(a.total_classes) AS held,
                SUM(a.attended_classes) AS attended
            FROM student_semester_summary ss
            LEFT JOIN attendance a 
                ON a.student_id = ss.student_id AND a.semester_no = ss.semester_no
            WHERE ss.student_id LIKE 'STU000%'
            GROUP BY ss.student_id, ss.semester_no, ss.semester_attendance_percentage
            ORDER BY ss.student_id, ss.semester_no
            LIMIT 40
        """)
        mismatch = 0
        n = 0
        for r in rows:
            n += 1
            held = r['held']
            att = r['attended']
            if held is None or held == 0:
                ratio = None
            else:
                ratio = round(100.0 * att / held, 2)
            summary_pct = float(r['summary_pct']) if r['summary_pct'] is not None else None
            match = (ratio is not None and summary_pct is not None and abs(ratio - summary_pct) < 0.011)
            if ratio is not None and summary_pct is not None and abs(ratio - summary_pct) >= 0.011:
                mismatch += 1
                print(f"  MISMATCH {r['student_id']} sem {r['semester_no']}: ratio={ratio}, summary={summary_pct}")
            if n <= 16:
                print(f"  {r['student_id']} sem {r['semester_no']}: ratio={ratio}, summary={summary_pct}, match={match}")
        print(f"  Total sampled: {n}, mismatches: {mismatch}")

        # 3. Check the learning activity table empty for real cohort
        print("\n" + "=" * 80)
        print("3. student_learning_activity for real cohort")
        print("=" * 80)
        cnt = await conn.fetchrow("SELECT COUNT(*) AS c FROM student_learning_activity WHERE student_id LIKE 'STU000%'")
        print(f"  rows: {cnt['c']}")

        # 4. Check what ml_predictions stored for a real student (previous predictions with features?)
        print("\n" + "=" * 80)
        print("4. ml_predictions sample for STU000001")
        print("=" * 80)
        try:
            pred = await conn.fetchrow("SELECT * FROM ml_predictions WHERE student_id = 'STU000001' LIMIT 1")
            if pred:
                d = dict(pred)
                for k, v in d.items():
                    sv = str(v)
                    print(f"  {k}: {sv[:200]}{'...' if len(sv) > 200 else ''}")
            else:
                print("  no rows")
        except Exception as e:
            print(f"  ERROR: {e}")

    finally:
        await conn.close()

asyncio.run(run())