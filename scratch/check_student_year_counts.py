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

    print("=== DISTINCT STUDENTS PER ACADEMIC YEAR IN student_semester_summary ===")
    rows = await conn.fetch("""
        SELECT 
            CASE WHEN academic_year = '2026-2027' THEN '2026-27' ELSE academic_year END as norm_year,
            COUNT(DISTINCT student_id) as student_count
        FROM student_semester_summary
        GROUP BY norm_year
        ORDER BY norm_year;
    """)
    for r in rows:
        print(dict(r))

    print("\n=== DISTINCT STUDENTS PER ACADEMIC YEAR IN student_subject_enrollment ===")
    rows2 = await conn.fetch("""
        SELECT academic_year, COUNT(DISTINCT student_id) as student_count
        FROM student_subject_enrollment
        GROUP BY academic_year
        ORDER BY academic_year;
    """)
    for r in rows2:
        print(dict(r))

    print("\n=== STUDENTS PER ADMISSION_YEAR in students ===")
    rows3 = await conn.fetch("""
        SELECT admission_year, COUNT(DISTINCT student_id) as student_count
        FROM students
        GROUP BY admission_year
        ORDER BY admission_year;
    """)
    for r in rows3:
        print(dict(r))

    print("\n=== COMBINATIONS IN student_semester_summary: ACADEMIC_YEAR + DEPARTMENT + SEMESTER ===")
    rows4 = await conn.fetch("""
        SELECT 
            CASE WHEN sem.academic_year = '2026-2027' THEN '2026-27' ELSE sem.academic_year END as year,
            s.department_code,
            sem.semester_no,
            COUNT(DISTINCT s.student_id) as student_count
        FROM student_semester_summary sem
        JOIN students s ON s.student_id = sem.student_id
        GROUP BY year, s.department_code, sem.semester_no
        ORDER BY year, s.department_code, sem.semester_no;
    """)
    for r in rows4:
        print(dict(r))

    print("\n=== TOTAL STUDENTS IN students TABLE ===")
    t_stu = await conn.fetchval("SELECT COUNT(*) FROM students;")
    print("Total students in DB:", t_stu)

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
