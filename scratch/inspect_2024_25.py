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

    print("=== student_semester_summary for 2024-25 ===")
    rows = await conn.fetch("""
        SELECT sem.semester_no, s.department_code, s.admission_year, COUNT(DISTINCT sem.student_id) as cnt
        FROM student_semester_summary sem
        JOIN students s ON s.student_id = sem.student_id
        WHERE sem.academic_year = '2024-25'
        GROUP BY sem.semester_no, s.department_code, s.admission_year
        ORDER BY sem.semester_no, s.department_code;
    """)
    for r in rows:
        print(dict(r))

    print("\n=== student_subject_enrollment for 2024-25 ===")
    rows2 = await conn.fetch("""
        SELECT e.semester_no, e.department_code, COUNT(DISTINCT e.student_id) as cnt
        FROM student_subject_enrollment e
        WHERE e.academic_year = '2024-25'
        GROUP BY e.semester_no, e.department_code
        ORDER BY e.semester_no, e.department_code;
    """)
    for r in rows2:
        print(dict(r))

    print("\n=== Check if students table has any other year columns or cohort mapping ===")
    sample_stu = await conn.fetchrow("SELECT * FROM students LIMIT 1;")
    print(dict(sample_stu))

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
