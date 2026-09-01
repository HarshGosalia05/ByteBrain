"""Verify attendance data for STU000% production students."""
import asyncio
import asyncpg
from pathlib import Path

env = {}
for f in ['.env.local', '.env']:
    p = Path(f)
    if p.exists():
        with open(p, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        break

host = env.get('DB_HOST', 'localhost')
port = int(env.get('DB_PORT', '5432'))
dbname = env.get('DB_NAME', 'postgres')
user = env.get('DB_USER', 'postgres')
password = env.get('DB_PASSWORD', 'password')
ssl_mode = 'require' if ('supabase' in host or port == 6543) else None


async def check():
    conn = await asyncpg.connect(host=host, port=port, database=dbname,
                                user=user, password=password, ssl=ssl_mode)
    try:
        # 1. Attendance table structure
        print("=== ATTENDANCE TABLE COLUMNS ===")
        rows = await conn.fetch(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'attendance' ORDER BY ordinal_position"
        )
        for r in rows:
            print(f"  {r['column_name']}: {r['data_type']}")

        # 2. Attendance data for STU000%
        print("\n=== ATTENDANCE DATA FOR STU000% ===")
        r = await conn.fetchrow(
            "SELECT COUNT(*) as total, COUNT(attendance_percentage) as att_nn "
            "FROM attendance WHERE student_id LIKE 'STU000%'"
        )
        print(f"  Total rows: {r['total']}, attendance_percentage non-null: {r['att_nn']}")

        # 3. Sample sem 7 data
        print("\n=== SAMPLE SEM 7 ATTENDANCE ===")
        rows = await conn.fetch(
            "SELECT student_id, subject_id, semester_no, attendance_percentage, "
            "total_classes, attended_classes "
            "FROM attendance WHERE student_id LIKE 'STU000%' AND semester_no = 7 "
            "LIMIT 10"
        )
        for r in rows:
            print(f"  {r['student_id']} {r['subject_id']} sem={r['semester_no']} "
                  f"att={r['attendance_percentage']} total={r['total_classes']} "
                  f"attended={r['attended_classes']}")

        # 4. Students with sem 7 attendance
        r = await conn.fetchrow(
            "SELECT COUNT(DISTINCT student_id) as students "
            "FROM attendance WHERE student_id LIKE 'STU000%' AND semester_no = 7"
        )
        print(f"\n  Students with sem 7 attendance: {r['students']}")

        # 5. Attendance percentage range
        rows = await conn.fetch(
            "SELECT MIN(attendance_percentage) as mn, MAX(attendance_percentage) as mx, "
            "AVG(attendance_percentage) as avg "
            "FROM attendance WHERE student_id LIKE 'STU000%'"
        )
        print(f"  Attendance range: {rows[0]['mn']:.2f} - {rows[0]['mx']:.2f}, "
              f"avg: {rows[0]['avg']:.2f}")

        # 6. Performance sem 7 data
        print("\n=== PERFORMANCE SEM 7 DATA ===")
        r = await conn.fetchrow(
            "SELECT COUNT(*) as total, "
            "COUNT(internal_marks) as internal_nn, "
            "COUNT(mid_sem_marks) as mid_nn "
            "FROM student_subject_performance "
            "WHERE student_id LIKE 'STU000%' AND semester_no = 7"
        )
        print(f"  Sem 7 rows: {r['total']}, internal_nn: {r['internal_nn']}, mid_nn: {r['mid_nn']}")

        # 7. Enrollment sem 7
        print("\n=== ENROLLMENT SEM 7 ===")
        r = await conn.fetchrow(
            "SELECT COUNT(*) as total, COUNT(credits) as credits_nn, "
            "COUNT(subject_type) as type_nn "
            "FROM student_subject_enrollment "
            "WHERE student_id LIKE 'STU000%' AND semester_no = 7"
        )
        print(f"  Sem 7 rows: {r['total']}, credits_nn: {r['credits_nn']}, type_nn: {r['type_nn']}")

        # 8. Students table - department_name
        print("\n=== STUDENTS TABLE ===")
        rows = await conn.fetch(
            "SELECT department_name, COUNT(*) as cnt "
            "FROM students WHERE student_id LIKE 'STU000%' "
            "GROUP BY department_name"
        )
        for r in rows:
            print(f"  {r['department_name']}: {r['cnt']} students")

        # 9. Join check: performance + attendance + enrollment for sem 7
        print("\n=== FULL JOIN CHECK (sem 7) ===")
        r = await conn.fetchrow("""
            SELECT COUNT(*) as total
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON p.enrollment_record_id = e.enrollment_record_id
            JOIN students s ON p.student_id = s.student_id
            LEFT JOIN attendance a
              ON p.student_id = a.student_id
              AND p.subject_id = a.subject_id
              AND p.semester_no = a.semester_no
            WHERE p.student_id LIKE 'STU000%' AND p.semester_no = 7
        """)
        print(f"  Total sem 7 rows with all joins: {r['total']}")

        # 10. Check how many sem 7 rows have attendance
        r = await conn.fetchrow("""
            SELECT
              COUNT(*) as total,
              COUNT(a.attendance_percentage) as with_att
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON p.enrollment_record_id = e.enrollment_record_id
            LEFT JOIN attendance a
              ON p.student_id = a.student_id
              AND p.subject_id = a.subject_id
              AND p.semester_no = a.semester_no
            WHERE p.student_id LIKE 'STU000%' AND p.semester_no = 7
        """)
        print(f"  Rows with attendance: {r['with_att']}/{r['total']}")

    finally:
        await conn.close()


asyncio.run(check())
