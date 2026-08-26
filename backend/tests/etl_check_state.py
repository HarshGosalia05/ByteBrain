"""Quick check: verify database state after aborted ETL run."""
import asyncio
from urllib.parse import quote_plus
import asyncpg

DB_DSN = (
    "postgresql://postgres.rtaqkxqdejelxsamnesm:"
    + quote_plus("KenexAI@*195")
    + "@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"
)

async def check():
    conn = await asyncpg.connect(dsn=DB_DSN)
    
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
