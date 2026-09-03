import asyncio
import sys
sys.path.insert(0, "backend")

from app.core.config import settings
import asyncpg

async def test_query(conn, dept_code, academic_year, semester):
    print(f"\n--- Testing: dept={dept_code}, year={academic_year}, sem={semester} ---")
    
    # Let's test the filtered students subquery:
    # A student is in scope if:
    # 1. Matches department_code (if provided)
    # 2. If academic_year or semester is provided, the student has a matching record in student_semester_summary
    #    (or student_subject_enrollment) for that academic_year and/or semester.
    # 3. If neither academic_year nor semester is provided, all students in students table matching department_code.
    
    sql = """
    WITH filtered_students AS (
        SELECT DISTINCT s.student_id
        FROM students s
        LEFT JOIN student_semester_summary sem ON sem.student_id = s.student_id
        WHERE ($1::int IS NULL OR s.department_code = $1)
          AND ($2::text IS NULL OR sem.academic_year = $2 OR (sem.academic_year = '2026-2027' AND $2 = '2026-27'))
          AND ($3::int IS NULL OR sem.semester_no = $3)
          AND (
              ($2::text IS NULL AND $3::int IS NULL)
              OR sem.semester_no IS NOT NULL
          )
    )
    SELECT
        (SELECT COUNT(*) FROM filtered_students) AS total_students,
        (SELECT COUNT(*) FROM faculty f WHERE ($1::int IS NULL OR f.department_code = $1)) AS total_faculty,
        (SELECT COUNT(*) FROM departments d WHERE ($1::int IS NULL OR d.dept_code = $1)) AS total_departments,
        (SELECT AVG(s.overall_cgpa) FROM students s WHERE s.student_id IN (SELECT student_id FROM filtered_students)) AS avg_cgpa,
        (SELECT COALESCE(SUM(s.total_backlogs), 0) FROM students s WHERE s.student_id IN (SELECT student_id FROM filtered_students)) AS total_backlogs
    """
    row = await conn.fetchrow(sql, dept_code, academic_year, semester)
    print("KPIs:", dict(row))

    # Test risk distribution for filtered students:
    risk_sql = """
    WITH filtered_students AS (
        SELECT DISTINCT s.student_id
        FROM students s
        LEFT JOIN student_semester_summary sem ON sem.student_id = s.student_id
        WHERE ($1::int IS NULL OR s.department_code = $1)
          AND ($2::text IS NULL OR sem.academic_year = $2 OR (sem.academic_year = '2026-2027' AND $2 = '2026-27'))
          AND ($3::int IS NULL OR sem.semester_no = $3)
          AND (
              ($2::text IS NULL AND $3::int IS NULL)
              OR sem.semester_no IS NOT NULL
          )
    )
    SELECT r.prediction_status AS risk_level, COUNT(DISTINCT r.student_id) AS count
    FROM risk_predictions r
    WHERE r.student_id IN (SELECT student_id FROM filtered_students)
    GROUP BY r.prediction_status
    """
    risk_rows = await conn.fetch(risk_sql, dept_code, academic_year, semester)
    print("Risk:", [dict(r) for r in risk_rows])

async def main():
    conn = await asyncpg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
    )

    # Test cases from user prompt:
    # TEST A: All Years, All Departments, All Semesters
    await test_query(conn, None, None, None)

    # TEST B: Academic Year = 2024-25
    await test_query(conn, None, "2024-25", None)

    # TEST C: Academic Year = 2025-26
    await test_query(conn, None, "2025-26", None)

    # TEST D: Academic Year = 2026-27
    await test_query(conn, None, "2026-27", None)

    # TEST E: 2024-25 + BBA (dept 2) + All Semesters
    await test_query(conn, 2, "2024-25", None)

    # TEST F: 2024-25 + BBA (dept 2) + Semester 3
    await test_query(conn, 2, "2024-25", 3)

    # TEST F2: 2024-25 + CSE (dept 1) + Semester 7
    await test_query(conn, 1, "2024-25", 7)

    # TEST F3: 2024-25 + CSE (dept 1) + Semester 3
    await test_query(conn, 1, "2024-25", 3)

    # TEST F4: BBA (dept 2) + Semester 7 (invalid semester for BBA)
    await test_query(conn, 2, None, 7)

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
