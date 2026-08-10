import asyncpg
from typing import List, Optional, Dict, Any


class StudentRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_class_benchmark_averages(
        self,
        department_code: str,
        exclude_student_id: str,
        subject_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """Peer-only aggregate percentages for a subject/semester/year cohort.

        MD-03 feature 5: aggregates are computed over the authenticated
        student's department and explicitly EXCLUDE the student's own record so
        the benchmark stays a classmate average. Only aggregate statistics are
        returned — no peer identity ever crosses this boundary.
        """
        query = """
            SELECT
                sse.subject_id,
                sse.semester_no,
                sse.academic_year,
                COUNT(sp.percentage)::int AS cohort_size,
                ROUND(AVG(sp.percentage)::numeric, 2)::float8 AS class_average
            FROM student_subject_enrollment sse
            JOIN student_subject_performance sp
                ON sp.enrollment_record_id = sse.enrollment_record_id
            WHERE sse.department_code = $1
              AND sp.student_id <> $2
              AND sp.percentage IS NOT NULL
              AND sse.subject_id = ANY($3::text[])
            GROUP BY sse.subject_id, sse.semester_no, sse.academic_year
            ORDER BY sse.semester_no ASC, sse.subject_id ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, department_code, exclude_student_id, subject_ids)
            return [dict(row) for row in rows]

    async def get_student_profile(self, student_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT
                s.student_id, s.first_name, s.last_name,
                s.enrollment_no, s.admission_year, s.current_semester,
                s.department_name, s.department_code,
                s.current_academic_year, s.latest_sgpa, s.overall_cgpa,
                s.overall_percentage, s.total_credits_registered,
                s.total_credits_earned, s.total_backlogs, s.academic_standing
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
                backlog_count AS active_backlogs,
                academic_year,
                subjects_registered,
                credits_registered,
                semester_percentage,
                semester_grade,
                semester_result,
                academic_standing
            FROM student_semester_summary
            WHERE student_id = $1
            ORDER BY semester_no ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, student_id)
            return [dict(row) for row in rows]

    async def get_subject_performance(
        self, student_id: str, semester: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        params = [student_id]
        semester_filter = ""
        if semester is not None:
            params.append(semester)
            semester_filter = f" AND sse.semester_no = ${len(params)}"

        query = f"""
            SELECT
                sse.semester_no AS semester,
                sse.subject_id,
                sse.subject_code,
                sse.subject_name,
                sse.credits,
                sse.academic_year,
                sp.internal_marks,
                sp.mid_sem_marks,
                sp.end_sem_marks,
                sp.total_marks,
                sp.percentage,
                sp.grade,
                sp.grade_point,
                sp.result_status,
                sp.attempt_number,
                sp.performance_category,
                sp.remarks,
                sp.updated_at,
                a.attendance_percentage
            FROM student_subject_enrollment sse
            LEFT JOIN subjects subj ON subj.subject_id = sse.subject_id
            LEFT JOIN student_subject_performance sp
                ON sp.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN attendance a
                ON a.enrollment_record_id = sse.enrollment_record_id
            WHERE sse.student_id = $1
              AND (sp.student_id = $1 OR sp.student_id IS NULL)
              AND (a.student_id = $1 OR a.student_id IS NULL)
              {semester_filter}
            ORDER BY sse.semester_no ASC, sse.subject_name ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]