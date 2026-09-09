"""Check actual data for production students."""
import asyncio
import sys

sys.path.insert(0, "backend")
from app.core.database import db


async def run():
    await db.connect()
    pool = db.pool
    async with pool.acquire() as conn:
        # Check student_subject_performance
        rows = await conn.fetch(
            """
            SELECT student_id, semester_no, subject_id, 
                   internal_marks, mid_sem_marks, end_sem_marks
            FROM student_subject_performance
            WHERE student_id IN ('STU000001', 'STU000051')
            AND semester_no IN (5, 7)
            ORDER BY student_id, semester_no, subject_id
            LIMIT 20
        """
        )
        print("student_subject_performance:")
        for r in rows:
            print(f"  {r['student_id']} sem={r['semester_no']} subj={r['subject_id']} internal={r['internal_marks']} mid={r['mid_sem_marks']} end={r['end_sem_marks']}")

        # Check attendance
        rows2 = await conn.fetch(
            """
            SELECT student_id, semester_no, subject_id, 
                   total_classes, attended_classes
            FROM attendance
            WHERE student_id IN ('STU000001', 'STU000051')
            AND semester_no IN (5, 7)
            ORDER BY student_id, semester_no, subject_id
            LIMIT 10
        """
        )
        print("\nattendance:")
        for r in rows2:
            pct = (r['attended_classes'] / r['total_classes'] * 100) if r['total_classes'] > 0 else 0
            print(f"  {r['student_id']} sem={r['semester_no']} subj={r['subject_id']} {r['attended_classes']}/{r['total_classes']} ({pct:.1f}%)")

        # Check semester summary
        rows3 = await conn.fetch(
            """
            SELECT student_id, semester_no, semester_sgpa, 
                   backlog_count, semester_attendance_percentage
            FROM student_semester_summary
            WHERE student_id IN ('STU000001', 'STU000051')
            AND semester_no IN (5, 7)
            ORDER BY student_id, semester_no
        """)
        print("\nstudent_semester_summary:")
        for r in rows3:
            print(f"  {r['student_id']} sem={r['semester_no']} sgpa={r['semester_sgpa']} backlogs={r['backlog_count']} att={r['semester_attendance_percentage']}")

    await db.disconnect()


asyncio.run(run())
