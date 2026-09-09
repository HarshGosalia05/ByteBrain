"""Check mid-semester marks data for production students."""
import asyncio
import json
import sys

sys.path.insert(0, "backend")
from app.core.database import db


async def run():
    await db.connect()
    pool = db.pool
    async with pool.acquire() as conn:
        # Check what mid-semester data exists
        rows = await conn.fetch(
            """
            SELECT student_id, semester_no, subject_id, 
                   midsem_marks, assignment_marks, quiz_marks
            FROM student_subject_marks
            WHERE student_id IN ('STU000001', 'STU000051')
            AND semester_no IN (5, 7)
            ORDER BY student_id, semester_no, subject_id
            LIMIT 20
        """
        )
        print("Sample marks data:")
        for r in rows:
            print(f"  {r['student_id']} sem={r['semester_no']} subj={r['subject_id']} mid={r['midsem_marks']} assign={r['assignment_marks']} quiz={r['quiz_marks']}")

        # Check attendance data
        rows2 = await conn.fetch(
            """
            SELECT student_id, semester_no, subject_id, 
                   total_classes, classes_attended
            FROM student_attendance
            WHERE student_id IN ('STU000001', 'STU000051')
            AND semester_no IN (5, 7)
            ORDER BY student_id, semester_no, subject_id
            LIMIT 10
        """
        )
        print("\nSample attendance data:")
        for r in rows2:
            pct = (r['classes_attended'] / r['total_classes'] * 100) if r['total_classes'] > 0 else 0
            print(f"  {r['student_id']} sem={r['semester_no']} subj={r['subject_id']} {r['classes_attended']}/{r['total_classes']} ({pct:.1f}%)")

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
        print("\nSemester summary:")
        for r in rows3:
            print(f"  {r['student_id']} sem={r['semester_no']} sgpa={r['semester_sgpa']} backlogs={r['backlog_count']} att={r['semester_attendance_percentage']}")

    await db.disconnect()


asyncio.run(run())
