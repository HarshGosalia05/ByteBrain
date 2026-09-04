import asyncio
from app.core.database import db

async def t():
    await db.connect()
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT student_id, semester_no, semester_sgpa, semester_attendance_percentage, semester_total_marks
            FROM student_semester_summary
            WHERE student_total_marks > 0 OR semester_total_marks > 0
            ORDER BY student_id, semester_no
        """)
        for r in rows:
            d = dict(r)
            if d['semester_no'] >= 5:
                print(f"{d['student_id']} Sem {d['semester_no']}: sgpa={d['semester_sgpa']}, att={d['semester_attendance_percentage']}, marks={d['semester_total_marks']}")
    await db.disconnect()

asyncio.run(t())
