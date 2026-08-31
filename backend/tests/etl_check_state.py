"""Quick check: verify database state after aborted ETL run."""
import asyncio
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db_env import db_config  # noqa: E402

async def check():
    db = db_config()
    conn = await asyncpg.connect(
        host=db.host, port=db.port, database=db.name, user=db.user,
        password=db.password, ssl="require", statement_cache_size=0,
    )
    
    tables = ["daily_attendance_07", "weekly_timetable_07", "attendance", 
              "student_semester_summary"]
    for t in tables:
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {t}")
        print(f"{t}: {count}")
    
    # Check students derived
    stu = await conn.fetch(
        "SELECT student_id, overall_attendance_percentage, full_name "
        "FROM students WHERE student_id IN ('STU000001','STU000032') ORDER BY student_id"
    )
    for r in stu:
        print(f"students {r['student_id']}: oap={r['overall_attendance_percentage']}, fn={r['full_name']}")
    
    await conn.close()

asyncio.run(check())