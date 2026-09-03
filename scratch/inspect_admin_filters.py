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
    
    print("=== DEPARTMENTS ===")
    dept_rows = await conn.fetch("SELECT * FROM departments ORDER BY dept_code;")
    for r in dept_rows:
        print(dict(r))

    print("\n=== STUDENTS TABLE COLUMNS ===")
    cols = await conn.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'students' 
        ORDER BY ordinal_position;
    """)
    print([r["column_name"] for r in cols])

    print("\n=== STUDENTS: ADMISSION_YEAR vs CURRENT_ACADEMIC_YEAR ===")
    stu_years = await conn.fetch("""
        SELECT admission_year, current_academic_year, current_semester, department_code, COUNT(*) 
        FROM students 
        GROUP BY admission_year, current_academic_year, current_semester, department_code 
        ORDER BY department_code, current_semester;
    """)
    for r in stu_years:
        print(dict(r))

    print("\n=== STUDENT_SEMESTER_SUMMARY: ACADEMIC_YEAR & SEMESTER_NO ===")
    sem_years = await conn.fetch("""
        SELECT academic_year, semester_no, COUNT(*), COUNT(DISTINCT student_id) as distinct_students
        FROM student_semester_summary 
        GROUP BY academic_year, semester_no 
        ORDER BY academic_year, semester_no;
    """)
    for r in sem_years:
        print(dict(r))

    print("\n=== BBA STUDENTS IN DATABASE ===")
    bba_info = await conn.fetch("""
        SELECT s.current_semester, COUNT(*) 
        FROM students s 
        WHERE s.department_code = 2 
        GROUP BY s.current_semester;
    """)
    for r in bba_info:
        print("Students current_semester for BBA (dept 2):", dict(r))

    bba_sem_info = await conn.fetch("""
        SELECT sem.semester_no, COUNT(*), COUNT(DISTINCT sem.student_id) as distinct_students 
        FROM student_semester_summary sem
        JOIN students s ON s.student_id = sem.student_id
        WHERE s.department_code = 2
        GROUP BY sem.semester_no
        ORDER BY sem.semester_no;
    """)
    for r in bba_sem_info:
        print("Semester summary semester_no for BBA:", dict(r))

    bba_enr_info = await conn.fetch("""
        SELECT semester_no, COUNT(*), COUNT(DISTINCT student_id) as distinct_students
        FROM student_subject_enrollment
        WHERE department_code = 2
        GROUP BY semester_no
        ORDER BY semester_no;
    """)
    for r in bba_enr_info:
        print("Enrollment semester_no for BBA:", dict(r))

    print("\n=== RISK PREDICTIONS TABLE ===")
    risk_cols = await conn.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'risk_predictions' 
        ORDER BY ordinal_position;
    """)
    print([r["column_name"] for r in risk_cols])

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
