"""Compute sem-7 attendance from daily_attendance_07 for STU000001 and compare sources."""
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
        print("DAILY ATTENDANCE SEM 7 for STU000001")
        print("=" * 80)
        rows = await conn.fetch("""
            SELECT attendance_status, COUNT(*) AS cnt
            FROM daily_attendance_07
            WHERE student_id = 'STU000001' AND semester_no = 7
            GROUP BY attendance_status
        """)
        total = 0
        present = 0
        for r in rows:
            print(f"  status={r['attendance_status']}: {r['cnt']}")
            if r['attendance_status'] in ('P', 'Present'):
                present = r['cnt']
            total += r['cnt']
        print(f"  total={total}, present={present}, pct={100*present/total if total else None:.2f}")

        # Distinct lectures (held classes count)
        lec = await conn.fetchrow("""
            SELECT COUNT(*) AS lectures FROM (
                SELECT DISTINCT subject_id, lecture_date, lecture_number
                FROM daily_attendance_07 WHERE semester_no = 7
            ) x
        """)
        print(f"  total distinct lectures (held classes) for sem 7: {lec['lectures']}")

        # Per-subject held/present for STU000001 sem 7
        print("\nPer-subject detail (daily attendance):")
        rows = await conn.fetch("""
            SELECT subject_id,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE attendance_status = 'P') AS present
            FROM daily_attendance_07
            WHERE student_id = 'STU000001' AND semester_no = 7
            GROUP BY subject_id ORDER BY subject_id
        """)
        for r in rows:
            print(f"  {r['subject_id']}: total={r['total']}, present={r['present']}")

        print("\nAttendance table detail (sem 7):")
        rows = await conn.fetch("""
            SELECT subject_id, total_classes, attended_classes, attendance_percentage
            FROM attendance
            WHERE student_id = 'STU000001' AND semester_no = 7
            ORDER BY subject_id
        """)
        for r in rows:
            print(f"  {r['subject_id']}: held={r['total_classes']}, att={r['attended_classes']}, pct={r['attendance_percentage']}")

        # Week-based derivation: how many weeks?
        weeks = await conn.fetchrow("""
            SELECT COUNT(DISTINCT lecture_date) FROM daily_attendance_07 WHERE student_id='STU000001' AND semester_no=7
        """)
        print(f"\n  distinct lecture dates for STU000001 sem 7: {weeks['count']}")

    finally:
        await conn.close()

asyncio.run(run())