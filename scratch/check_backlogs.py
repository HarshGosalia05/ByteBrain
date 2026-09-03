import asyncio
import sys
sys.path.insert(0, "backend")

from app.core.config import settings
import asyncpg

async def main():
    conn = await asyncpg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
    )

    row1 = await conn.fetchrow("""
        SELECT 
            SUM(s.total_backlogs) as sum_stu_backlogs,
            AVG(s.overall_cgpa) as avg_cgpa
        FROM students s;
    """)
    print("All students:", dict(row1))

    # For 2025-26:
    row2 = await conn.fetchrow("""
        WITH filtered_students AS (
            SELECT DISTINCT s.student_id
            FROM students s
            JOIN student_semester_summary sem ON sem.student_id = s.student_id
            WHERE sem.academic_year = '2025-26'
        )
        SELECT 
            COUNT(*) as student_count,
            (SELECT SUM(s.total_backlogs) FROM students s WHERE s.student_id IN (SELECT student_id FROM filtered_students)) as sum_stu_backlogs,
            (SELECT AVG(s.overall_cgpa) FROM students s WHERE s.student_id IN (SELECT student_id FROM filtered_students)) as avg_cgpa,
            (SELECT SUM(sem.backlog_count) FROM student_semester_summary sem WHERE sem.academic_year = '2025-26') as sum_sem_backlogs
        FROM filtered_students;
    """)
    print("2025-26:", dict(row2))

    # For 2026-27:
    row3 = await conn.fetchrow("""
        WITH filtered_students AS (
            SELECT DISTINCT s.student_id
            FROM students s
            JOIN student_semester_summary sem ON sem.student_id = s.student_id
            WHERE sem.academic_year = '2026-27' OR sem.academic_year = '2026-2027'
        )
        SELECT 
            COUNT(*) as student_count,
            (SELECT SUM(s.total_backlogs) FROM students s WHERE s.student_id IN (SELECT student_id FROM filtered_students)) as sum_stu_backlogs,
            (SELECT AVG(s.overall_cgpa) FROM students s WHERE s.student_id IN (SELECT student_id FROM filtered_students)) as avg_cgpa,
            (SELECT SUM(sem.backlog_count) FROM student_semester_summary sem WHERE sem.academic_year = '2026-27' OR sem.academic_year = '2026-2027') as sum_sem_backlogs
        FROM filtered_students;
    """)
    print("2026-27:", dict(row3))

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
