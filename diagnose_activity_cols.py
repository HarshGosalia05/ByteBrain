"""Exhaustive: find ANY column with activity/engagement/volume for the real cohort."""
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
        # Find all columns with activity / volume / engagement / session / attempt / resource / submission
        cols = await conn.fetch("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND (column_name ILIKE '%activ%' OR column_name ILIKE '%volume%'
                   OR column_name ILIKE '%engagement%' OR column_name ILIKE '%session%'
                   OR column_name ILIKE '%attempt%' OR column_name ILIKE '%resource%'
                   OR column_name ILIKE '%submission%' OR column_name ILIKE '%view%'
                   OR column_name ILIKE '%consist%')
            ORDER BY table_name, column_name
        """)
        print("Columns matching activity-related patterns:")
        for c in cols:
            print(f"  {c['table_name']}.{c['column_name']} ({c['data_type']})")

        # For each such column in any table, get non-null count for real cohort
        real_tables = set()
        for c in cols:
            tbl = c['table_name']
            col = c['column_name']
            try:
                has_sid = await conn.fetchrow("""
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name=$1 AND column_name='student_id'
                """, tbl)
                if not has_sid:
                    continue
                real_tables.add(tbl)
                q = f'SELECT COUNT(*) AS total, COUNT({col}) AS nn FROM "{tbl}" WHERE student_id LIKE \'STU000%\''
                r = await conn.fetchrow(q)
                if r['nn'] > 0:
                    print(f"  >>> {tbl}.{col}: {r['nn']}/{r['total']} non-null for STU000")
            except Exception as e:
                print(f"  err {tbl}.{col}: {e}")

        print("\nTables with student_id + activity-like columns checked:", sorted(real_tables))

    finally:
        await conn.close()

asyncio.run(run())