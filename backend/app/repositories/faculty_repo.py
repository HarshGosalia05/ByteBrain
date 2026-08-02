import asyncpg
from typing import List, Optional, Dict, Any

class FacultyRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_faculty_profile(self, faculty_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT 
                f.faculty_id, f.faculty_code, f.full_name, f.gender,
                f.department_code, f.department_name, f.designation,
                f.qualification, f.specialization, f.experience_years,
                f.email, f.phone_number, f.joining_date, f.employment_type, f.status,
                d.department_name AS department_full_name
            FROM faculty f
            LEFT JOIN departments d ON f.department_code = d.dept_code
            WHERE f.faculty_id = $1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, faculty_id)
            return dict(row) if row else None

    async def update_faculty_contact(
        self,
        faculty_id: str,
        email: Optional[str],
        phone_number: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        if email is None and phone_number is None:
            return await self.get_faculty_profile(faculty_id)

        updates = []
        params: List[Any] = []
        if email is not None:
            params.append(email)
            updates.append(f"email = ${len(params)}")
        if phone_number is not None:
            params.append(phone_number)
            updates.append(f"phone_number = ${len(params)}")

        params.append(faculty_id)
        query = f"UPDATE faculty SET {', '.join(updates)} WHERE faculty_id = ${len(params)}"
        async with self.pool.acquire() as conn:
            await conn.execute(query, *params)
        return await self.get_faculty_profile(faculty_id)

    async def get_current_term(self, faculty_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT semester_no, academic_year
            FROM student_subject_enrollment
            WHERE faculty_id = $1 AND enrollment_status = 'Active'
            ORDER BY semester_no DESC
            LIMIT 1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, faculty_id)
            return dict(row) if row else None

    async def get_term_overview(self, faculty_id: str, semester_no: int) -> Dict[str, Any]:
        query = """
            SELECT 
                count(DISTINCT sse.subject_id) AS subjects,
                count(DISTINCT sse.student_id) AS students
            FROM student_subject_enrollment sse
            WHERE sse.faculty_id = $1 AND sse.semester_no = $2
                AND sse.enrollment_status = 'Active'
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, faculty_id, semester_no)
            return dict(row) if row else {"subjects": 0, "students": 0}

    async def get_term_subjects(self, faculty_id: str, semester_no: int) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                sse.subject_id, sse.subject_code, sse.subject_name, sse.credits,
                count(DISTINCT sse.student_id) AS students,
                AVG(a.attendance_percentage) AS average_attendance,
                AVG(sp.percentage) AS average_performance
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            WHERE sse.faculty_id = $1 AND sse.semester_no = $2
                AND sse.enrollment_status = 'Active'
            GROUP BY sse.subject_id, sse.subject_code, sse.subject_name, sse.credits
            ORDER BY sse.subject_name ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, faculty_id, semester_no)
            return [dict(row) for row in rows]

    async def get_mentee_count(self, faculty_id: str) -> int:
        query = """
            SELECT count(*) AS mentees
            FROM faculty_student_map
            WHERE faculty_id = $1 AND status = 'Active'
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, faculty_id)
            return int(row["mentees"]) if row else 0
