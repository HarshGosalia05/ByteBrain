"""Check what attendance/learning data exists for the real cohort."""
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
        print("ALL TABLES IN DATABASE")
        print("=" * 80)
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        for t in tables:
            print(f"  {t['table_name']}")

        print("\n" + "=" * 80)
        print("ATTENDANCE-RELATED TABLES FOR STU000001")
        print("=" * 80)
        for tbl in ["attendance", "attendance_weekly", "daily_attendance_07", "weekly_timetable_07"]:
            try:
                row = await conn.fetchrow(f"SELECT COUNT(*) AS cnt FROM {tbl}")
                print(f"  {tbl}: {row['cnt']} total rows")
                if row['cnt']:
                    if 'student_id' in [c['column_name'] for c in await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = $1", tbl)]:
                        srow = await conn.fetchrow(f"SELECT COUNT(*) AS cnt FROM {tbl} WHERE student_id = 'STU000001'")
                        print(f"    STU000001 rows: {srow['cnt']}")
            except Exception as e:
                print(f"  {tbl}: ERROR {e}")

        print("\nColumns of attendance table:")
        cols = await conn.fetch("""
            SELECT column_name, data_type FROM information_schema.columns 
            WHERE table_name = 'attendance' ORDER BY ordinal_position
        """)
        for c in cols:
            print(f"  {c['column_name']} ({c['data_type']})")

        print("\nSample attendance data for STU000001:")
        rows = await conn.fetch("SELECT * FROM attendance WHERE student_id = 'STU000001' LIMIT 5")
        for r in rows:
            print(f"  {dict(r)}")

        print("\nColumns of daily_attendance_07 table:")
        try:
            cols = await conn.fetch("""
                SELECT column_name, data_type FROM information_schema.columns 
                WHERE table_name = 'daily_attendance_07' ORDER BY ordinal_position
            """)
            for c in cols:
                print(f"  {c['column_name']} ({c['data_type']})")
            print("\nSample daily_attendance_07 data for STU000001:")
            rows = await conn.fetch("SELECT * FROM daily_attendance_07 WHERE student_id = 'STU000001' LIMIT 5")
            for r in rows:
                print(f"  {dict(r)}")
        except Exception as e:
            print(f"  ERROR {e}")

        print("\n\nColumns of weekly_timetable_07:")
        try:
            cols = await conn.fetch("""
                SELECT column_name, data_type FROM information_schema.columns 
                WHERE table_name = 'weekly_timetable_07' ORDER BY ordinal_position
            """)
            for c in cols:
                print(f"  {c['column_name']} ({c['data_type']})")
        except Exception as e:
            print(f"  ERROR {e}")

        # learning activity tables
        print("\n\nLEARNING ACTIVITY TABLES:")
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            AND (table_name ILIKE '%learning%' OR table_name ILIKE '%activity%' OR table_name ILIKE '%lifestyle%' OR table_name ILIKE '%survey%')
            ORDER BY table_name
        """)
        for t in tables:
            tbl = t['table_name']
            try:
                row = await conn.fetchrow(f"SELECT COUNT(*) AS cnt FROM {tbl}")
                print(f"  {tbl}: {row['cnt']} total rows")
                if row['cnt']:
                    scol = await conn.fetchrow("""
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_name = $1 AND column_name = 'student_id'
                    """, tbl)
                    if scol:
                        srow = await conn.fetchrow(f"SELECT COUNT(*) AS cnt FROM {tbl} WHERE student_id = 'STU000001'")
                        print(f"    STU000001 rows: {srow['cnt']}")
            except Exception as e:
                print(f"  {tbl}: ERROR {e}")

        # Check what's in lifestyle_survey for real cohort
        print("\n\nLegacy lifestyle_survey columns and sample:")
        cols = await conn.fetch("""
            SELECT column_name, data_type FROM information_schema.columns 
            WHERE table_name = 'lifestyle_survey' ORDER BY ordinal_position
        """)
        for c in cols:
            print(f"  {c['column_name']} ({c['data_type']})")
        rows = await conn.fetch("SELECT * FROM lifestyle_survey WHERE student_id = 'STU000001' LIMIT 2")
        for r in rows:
            print(f"  {dict(r)}")

    finally:
        await conn.close()

asyncio.run(run())
