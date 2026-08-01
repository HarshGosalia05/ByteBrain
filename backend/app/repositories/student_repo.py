import asyncpg
from typing import List, Optional, Dict, Any

class StudentRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_student_profile(self, student_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT 
                s.student_id, s.first_name, s.last_name, 
                s.enrollment_no, s.admission_year, s.current_semester,
                s.department_name
            FROM students s
            WHERE s.student_id = $1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, student_id)
            return dict(row) if row else None

    async def get_semester_summaries(self, student_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                semester_no AS semester, 
                semester_sgpa AS sgpa, 
                credits_earned AS total_credits_earned, 
                semester_attendance_percentage AS attendance_percentage, 
                backlog_count AS active_backlogs
            FROM student_semester_summary
            WHERE student_id = $1
            ORDER BY semester_no ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, student_id)
            return [dict(row) for row in rows]

    async def get_subject_performance(self, student_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                sse.semester_no AS semester,
                subj.subject_code,
                subj.subject_name,
                sp.internal_marks,
                sp.end_sem_marks AS external_marks,
                sp.total_marks,
                sp.grade,
                a.attendance_percentage
            FROM student_subject_enrollment sse
            JOIN subjects subj ON sse.subject_id = subj.subject_id
            LEFT JOIN student_subject_performance sp 
                ON sse.student_id = sp.student_id AND sse.subject_id = sp.subject_id AND sse.semester_no = sp.semester_no
            LEFT JOIN attendance a 
                ON sse.student_id = a.student_id AND sse.subject_id = a.subject_id AND sse.semester_no = a.semester_no
            WHERE sse.student_id = $1
            ORDER BY sse.semester_no ASC, subj.subject_name ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, student_id)
            return [dict(row) for row in rows]
