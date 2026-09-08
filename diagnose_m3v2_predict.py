"""Check which students can get M3 V2 predictions and verify feature values."""
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
        # Find students who would get a READY prediction (current_semester < 8)
        students = await conn.fetch("""
            SELECT student_id, current_semester, department_name 
            FROM students 
            WHERE student_id LIKE 'STU6A%' AND current_semester < 8
            ORDER BY student_id
            LIMIT 5
        """)
        print(f"6A students with current_semester < 8: {len(students)}")
        for s in students:
            print(f"  {s['student_id']} sem={s['current_semester']} dept={s['department_name']}")

        # Also check non-6A students
        non6a = await conn.fetch("""
            SELECT student_id, current_semester, department_name 
            FROM students 
            WHERE student_id NOT LIKE 'STU6A%'
            ORDER BY student_id
            LIMIT 5
        """)
        print(f"\nNon-6A students: {len(non6a)}")
        for s in non6a:
            print(f"  {s['student_id']} sem={s['current_semester']} dept={s['department_name']}")

        # Check if STU00 students have attendance/learning data
        for s in non6a[:3]:
            sid = s['student_id']
            cur_sem = s['current_semester']
            att = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM attendance_weekly WHERE student_id = $1", sid)
            lr = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM student_learning_activity WHERE student_id = $1", sid)
            ss = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM student_semester_summary WHERE student_id = $1", sid)
            print(f"  {sid}: att={att['cnt']}, lr={lr['cnt']}, ss={ss['cnt']}")

        # The actual production students with predictions are all current_semester=8
        # which means NO_DATA. Let's check what current_semester distribution looks like
        print("\n\nCurrent semester distribution for 6A students:")
        dist = await conn.fetch("""
            SELECT current_semester, COUNT(*) AS cnt
            FROM students
            WHERE student_id LIKE 'STU6A%'
            GROUP BY current_semester
            ORDER BY current_semester
        """)
        for d in dist:
            print(f"  semester {d['current_semester']}: {d['cnt']} students")

        # Simulate prediction for STU6A0001 at T=7 (if we force it)
        print("\n\nSimulated feature values for STU6A0001 at T=7:")
        T = 7
        sid = "STU6A0001"

        # att_tsem_total_pct
        att_agg = await conn.fetchrow("""
            SELECT SUM(classes_held) AS held, SUM(classes_attended) AS attended
            FROM attendance_weekly
            WHERE student_id = $1 AND semester_no = $2
        """, sid, T)
        if att_agg and att_agg['held']:
            pct = 100.0 * att_agg['attended'] / att_agg['held']
            print(f"  att_tsem_total_pct = 100 * {att_agg['attended']}/{att_agg['held']} = {pct:.4f}")
        else:
            print(f"  att_tsem_total_pct = NaN")

        # learn_tsem_volume_total
        lr_agg = await conn.fetchrow("""
            SELECT SUM(activity_volume) AS total_vol
            FROM student_learning_activity
            WHERE student_id = $1 AND semester_no = $2
        """, sid, T)
        if lr_agg and lr_agg['total_vol'] is not None:
            print(f"  learn_tsem_volume_total = {lr_agg['total_vol']}")
        else:
            print(f"  learn_tsem_volume_total = NaN")

        # attendance_aggregate_pct from summary
        ss_row = await conn.fetchrow("""
            SELECT semester_attendance_percentage, attendance_aggregate_pct
            FROM student_semester_summary
            WHERE student_id = $1 AND semester_no = $2
        """, sid, T)
        if ss_row:
            print(f"  semester_attendance_percentage = {ss_row['semester_attendance_percentage']}")
            print(f"  attendance_aggregate_pct = {ss_row['attendance_aggregate_pct']}")

        # Now check: for the NON-6A students, do they have attendance/learning data?
        print("\n\nNon-6A student attendance/learning check:")
        for s in non6a[:5]:
            sid = s['student_id']
            cur_sem = s['current_semester']
            att = await conn.fetchrow("""
                SELECT COUNT(*) AS cnt FROM attendance_weekly 
                WHERE student_id = $1 AND semester_no = $2
            """, sid, cur_sem)
            lr = await conn.fetchrow("""
                SELECT COUNT(*) AS cnt FROM student_learning_activity 
                WHERE student_id = $1 AND semester_no = $2
            """, sid, cur_sem)
            print(f"  {sid} (sem={cur_sem}): att_rows_T={att['cnt']}, lr_rows_T={lr['cnt']}")

    finally:
        await conn.close()

asyncio.run(run())
