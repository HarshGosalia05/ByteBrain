import asyncpg
import json
from typing import List, Optional, Dict, Any, Callable

from app.core.config import settings
from app.repositories.student_repo import insert_student_messages
from app.services.notification_rules import (
    build_attendance_warnings,
    build_eligibility_warnings,
    build_faculty_attendance_warnings,
    build_faculty_performance_notifications,
    build_performance_change_notifications,
    build_performance_notifications,
)

class FacultyScopeError(Exception):
    """Scope gate failure (subject/term/faculty mismatch or invalid lecture)."""

class DuplicateLectureError(Exception):
    """A daily_attendance set already exists for the requested lecture."""


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
            ORDER BY academic_year DESC, semester_no DESC
            LIMIT 1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, faculty_id)
            return dict(row) if row else None

    async def get_term_sequence(self, faculty_id: str) -> List[Dict[str, Any]]:
        """Distinct terms taught by the faculty in chronological order
        (oldest first). Used to resolve the term immediately preceding the
        current term without hardcoding semester/year values."""
        query = """
            SELECT DISTINCT semester_no, academic_year
            FROM student_subject_enrollment
            WHERE faculty_id = $1 AND enrollment_status = 'Active'
            ORDER BY academic_year ASC, semester_no ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, faculty_id)
            return [dict(row) for row in rows]

    async def get_term_overview(self, faculty_id: str, semester_no: int, academic_year: Optional[str] = None) -> Dict[str, Any]:
        params: List[Any] = [faculty_id, semester_no]
        extra = ""
        if academic_year is not None:
            params.append(academic_year)
            extra = f" AND sse.academic_year = ${len(params)}"
        query = f"""
            SELECT 
                count(DISTINCT sse.subject_id) AS subjects,
                count(DISTINCT sse.student_id) AS students
            FROM student_subject_enrollment sse
            WHERE sse.faculty_id = $1 AND sse.semester_no = $2
                AND sse.enrollment_status = 'Active'{extra}
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            return dict(row) if row else {"subjects": 0, "students": 0}

    async def get_term_subjects(self, faculty_id: str, semester_no: int, academic_year: Optional[str] = None) -> List[Dict[str, Any]]:
        params: List[Any] = [faculty_id, semester_no]
        extra = ""
        if academic_year is not None:
            params.append(academic_year)
            extra = f" AND sse.academic_year = ${len(params)}"
        query = f"""
            SELECT 
                sse.subject_id, sse.subject_code, sse.subject_name, sse.credits,
                count(DISTINCT sse.student_id) AS students,
                CASE
                    WHEN SUM(aw.classes_held) > 0
                        THEN ROUND((100.0 * SUM(aw.classes_attended) / SUM(aw.classes_held))::numeric, 2)
                    WHEN SUM(a.total_classes) > 0
                        THEN ROUND((100.0 * SUM(a.attended_classes) / SUM(a.total_classes))::numeric, 2)
                    ELSE NULL
                END AS average_attendance,
                AVG(sp.percentage) AS average_performance
            FROM student_subject_enrollment sse
            LEFT JOIN attendance_weekly aw 
                ON aw.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            WHERE sse.faculty_id = $1 AND sse.semester_no = $2
                AND sse.enrollment_status = 'Active'{extra}
            GROUP BY sse.subject_id, sse.subject_code, sse.subject_name, sse.credits
            ORDER BY sse.subject_name ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
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

    async def get_classes_summary(self, faculty_id: str) -> Dict[str, Any]:
        query = """
            SELECT 
                count(DISTINCT (subject_id, semester_no)) AS total_classes,
                count(DISTINCT subject_id) AS total_subjects,
                count(DISTINCT student_id) AS total_students
            FROM student_subject_enrollment
            WHERE faculty_id = $1 AND enrollment_status = 'Active'
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, faculty_id)
            return dict(row) if row else {
                "total_classes": 0, "total_subjects": 0, "total_students": 0,
            }

    async def get_class_filters(self, faculty_id: str, semester_no: Optional[int], academic_year: Optional[str]) -> Dict[str, Any]:
        async with self.pool.acquire() as conn:
            semesters = await conn.fetch(
                """
                SELECT DISTINCT semester_no
                FROM student_subject_enrollment
                WHERE faculty_id = $1 AND enrollment_status = 'Active'
                ORDER BY semester_no ASC
                """,
                faculty_id,
            )
            years = await conn.fetch(
                """
                SELECT DISTINCT academic_year
                FROM student_subject_enrollment
                WHERE faculty_id = $1 AND enrollment_status = 'Active'
                ORDER BY academic_year ASC
                """,
                faculty_id,
            )
            
            subject_where = "faculty_id = $1 AND enrollment_status = 'Active'"
            subject_params = [faculty_id]
            if semester_no is not None:
                subject_params.append(semester_no)
                subject_where += f" AND semester_no = ${len(subject_params)}"
            if academic_year is not None:
                subject_params.append(academic_year)
                subject_where += f" AND academic_year = ${len(subject_params)}"
                
            subjects = await conn.fetch(
                f"""
                SELECT DISTINCT subject_id, subject_code, subject_name
                FROM student_subject_enrollment
                WHERE {subject_where}
                ORDER BY subject_code ASC
                """,
                *subject_params
            )
            pairs = await conn.fetch(
                """
                SELECT DISTINCT semester_no, academic_year
                FROM student_subject_enrollment
                WHERE faculty_id = $1 AND enrollment_status = 'Active'
                ORDER BY academic_year ASC, semester_no ASC
                """,
                faculty_id,
            )
            
            filter_enums = await conn.fetchrow(
                """
                SELECT 
                    array_agg(DISTINCT sp.grade) FILTER (WHERE sp.grade IS NOT NULL) AS grades,
                    array_agg(DISTINCT sp.result_status) FILTER (WHERE sp.result_status IS NOT NULL) AS result_statuses,
                    array_agg(DISTINCT sse.enrollment_status) FILTER (WHERE sse.enrollment_status IS NOT NULL) AS enrollment_statuses
                FROM student_subject_enrollment sse
                LEFT JOIN student_subject_performance sp ON sp.enrollment_record_id = sse.enrollment_record_id
                WHERE sse.faculty_id = $1 AND sse.enrollment_status = 'Active'
                """,
                faculty_id
            )
            
        grades = sorted(filter_enums["grades"] or []) if filter_enums else []
        result_statuses = sorted(filter_enums["result_statuses"] or []) if filter_enums else []
        enrollment_statuses = sorted(filter_enums["enrollment_statuses"] or []) if filter_enums else []
            
        return {
            "semesters": [r["semester_no"] for r in semesters],
            "academic_years": [r["academic_year"] for r in years],
            "subjects": [dict(r) for r in subjects],
            "term_options": [dict(r) for r in pairs],
            "grades": grades,
            "result_statuses": result_statuses,
            "enrollment_statuses": enrollment_statuses,
            "attendance_ranges": ["< 75%", "75% - 85%", "> 85%"],
            "sgpa_ranges": ["< 5.0", "5.0 - 7.0", "> 7.0"],
        }

    async def get_class_cards(
        self,
        faculty_id: str,
        semester_no: int,
        academic_year: str,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                sse.subject_id, sse.subject_code, sse.subject_name, sse.credits,
                sse.semester_no, sse.academic_year,
                count(DISTINCT sse.student_id) AS class_strength,
                AVG(COALESCE(a.attendance_percentage, sss.semester_attendance_percentage)) AS average_attendance,
                AVG(sp.percentage) AS average_percentage,
                MAX(sp.total_marks) AS highest_marks,
                MIN(sp.total_marks) AS lowest_marks,
                AVG(sp.grade_point) AS average_grade_point,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(sp.result_status) AS performed_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_semester_summary sss
                ON sss.student_id = sse.student_id AND sss.semester_no = sse.semester_no
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            WHERE sse.faculty_id = $1 AND sse.semester_no = $2 AND sse.academic_year = $3
                AND sse.enrollment_status = 'Active'
            GROUP BY sse.subject_id, sse.subject_code, sse.subject_name, sse.credits,
                sse.semester_no, sse.academic_year
            ORDER BY sse.subject_name ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, faculty_id, semester_no, academic_year)
            return [dict(row) for row in rows]

    async def count_class_students(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        attendance_range: Optional[str] = None,
        sgpa_range: Optional[str] = None,
        grade: Optional[str] = None,
        result_status: Optional[str] = None,
        student_status: Optional[str] = None,
    ) -> int:
        where, params = self._class_students_where(
            faculty_id, semester_no, academic_year, subject_id, search,
            attendance_range, sgpa_range, grade, result_status, student_status
        )
        query = f"""
            SELECT count(DISTINCT sse.enrollment_record_id)
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_semester_summary sss
                ON sss.student_id = sse.student_id AND sss.semester_no = sse.semester_no
            LEFT JOIN student_subject_performance sp ON sp.enrollment_record_id = sse.enrollment_record_id
            {where}
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *params)

    async def get_class_students(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        attendance_range: Optional[str],
        sgpa_range: Optional[str],
        grade: Optional[str],
        result_status: Optional[str],
        student_status: Optional[str],
        order_by: str,
        limit: int,
        offset: int,
    ) -> List[Dict[str, Any]]:
        where, params = self._class_students_where(
            faculty_id, semester_no, academic_year, subject_id, search,
            attendance_range, sgpa_range, grade, result_status, student_status
        )
        params.extend([limit, offset])
        query = f"""
            SELECT 
                sse.enrollment_record_id, sse.student_id, sse.enrollment_no, sse.semester_no,
                sse.subject_id, sse.subject_code, sse.subject_name, sse.enrollment_status,
                st.first_name, st.last_name, st.email,
                sp.internal_marks, sp.end_sem_marks AS external_marks, sp.total_marks, sp.grade,
                COALESCE(a.attendance_percentage, sss.semester_attendance_percentage) AS attendance_percentage,
                st.latest_sgpa, st.academic_standing
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_semester_summary sss
                ON sss.student_id = sse.student_id AND sss.semester_no = sse.semester_no
            LEFT JOIN student_subject_performance sp ON sp.enrollment_record_id = sse.enrollment_record_id
            {where}
            ORDER BY {order_by}
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    def _class_students_where(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        attendance_range: Optional[str] = None,
        sgpa_range: Optional[str] = None,
        grade: Optional[str] = None,
        result_status: Optional[str] = None,
        student_status: Optional[str] = None,
    ) -> tuple:
        clauses = ["sse.faculty_id = $1"]
        params: List[Any] = [faculty_id]
        
        if student_status:
            params.append(student_status)
            clauses.append(f"sse.enrollment_status = ${len(params)}")
        else:
            clauses.append("sse.enrollment_status = 'Active'")
        
        if semester_no is not None:
            params.append(semester_no)
            clauses.append(f"sse.semester_no = ${len(params)}")
        if academic_year is not None:
            params.append(academic_year)
            clauses.append(f"sse.academic_year = ${len(params)}")
        if subject_id is not None:
            params.append(subject_id)
            clauses.append(f"sse.subject_id = ${len(params)}")
            
        if grade is not None:
            params.append(grade)
            clauses.append(f"sp.grade = ${len(params)}")
        if result_status is not None:
            params.append(result_status)
            clauses.append(f"sp.result_status = ${len(params)}")
        if student_status is not None:
            params.append(student_status)
            clauses.append(f"sse.enrollment_status = ${len(params)}")
            
        if attendance_range is not None:
            att_expr = "COALESCE(a.attendance_percentage, sss.semester_attendance_percentage)"
            if attendance_range == "< 75%":
                clauses.append(f"{att_expr} < 75")
            elif attendance_range == "75% - 85%":
                clauses.append(f"{att_expr} >= 75 AND {att_expr} <= 85")
            elif attendance_range == "> 85%":
                clauses.append(f"{att_expr} > 85")
                
        if sgpa_range is not None:
            if sgpa_range == "< 5.0":
                clauses.append("st.latest_sgpa < 5.0")
            elif sgpa_range == "5.0 - 7.0":
                clauses.append("st.latest_sgpa >= 5.0 AND st.latest_sgpa <= 7.0")
            elif sgpa_range == "> 7.0":
                clauses.append("st.latest_sgpa > 7.0")
                
        if search:
            params.append(f"%{search}%")
            clauses.append(
                f"(st.enrollment_no::text ILIKE ${len(params)} "
                f"OR st.first_name ILIKE ${len(params)} "
                f"OR st.last_name ILIKE ${len(params)} "
                f"OR st.email ILIKE ${len(params)})"
            )
            
        return f"WHERE {' AND '.join(clauses)}", params

    async def get_mentees_raw(self, faculty_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                fsm.student_id, st.first_name, st.last_name, st.email, st.enrollment_no,
                st.current_semester AS semester,
                st.overall_attendance_percentage AS attendance_percentage,
                st.latest_sgpa, st.total_backlogs AS backlogs, st.academic_standing
            FROM faculty_student_map fsm
            JOIN students st ON st.student_id = fsm.student_id
            WHERE fsm.faculty_id = $1 AND fsm.status = 'Active'
            ORDER BY st.first_name ASC, st.last_name ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, faculty_id)
            return [dict(row) for row in rows]

    async def get_mentee_filters(self, faculty_id: str) -> Dict[str, Any]:
        query = """
            SELECT DISTINCT st.current_semester AS semester, st.academic_standing
            FROM faculty_student_map fsm
            JOIN students st ON st.student_id = fsm.student_id
            WHERE fsm.faculty_id = $1 AND fsm.status = 'Active'
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, faculty_id)
        semesters = sorted({r["semester"] for r in rows if r["semester"] is not None})
        standings = sorted(
            {r["academic_standing"] for r in rows if r["academic_standing"] is not None},
            key=str,
        )
        return {"semesters": semesters, "standings": standings}

    async def student_is_reachable(self, faculty_id: str, student_id: str) -> Optional[str]:
        """Returns 'class', 'mentee' or None depending on how the student is linked to this faculty."""
        async with self.pool.acquire() as conn:
            in_class = await conn.fetchval(
                """
                SELECT 1 FROM student_subject_enrollment
                WHERE faculty_id = $1 AND student_id = $2 LIMIT 1
                """,
                faculty_id, student_id,
            )
            is_mentee = await conn.fetchval(
                """
                SELECT 1 FROM faculty_student_map
                WHERE faculty_id = $1 AND student_id = $2 AND status = 'Active' LIMIT 1
                """,
                faculty_id, student_id,
            )
        if in_class:
            return "class"
        if is_mentee:
            return "mentee"
        return None

    async def get_student_overview(self, student_id: str) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            profile = await conn.fetchrow(
                """
                SELECT student_id, first_name, last_name, email, enrollment_no,
                    current_semester, latest_sgpa, overall_attendance_percentage,
                    total_backlogs, academic_standing
                FROM students
                WHERE student_id = $1
                """,
                student_id,
            )
            if not profile:
                return None
            summaries = await conn.fetch(
                """
                SELECT semester_no, semester_sgpa, semester_attendance_percentage,
                    backlog_count, academic_standing
                FROM student_semester_summary
                WHERE student_id = $1
                ORDER BY semester_no ASC
                """,
                student_id,
            )
            subjects = await conn.fetch(
                """
                SELECT sse.semester_no, subj.subject_code, subj.subject_name,
                    sp.internal_marks, sp.end_sem_marks AS external_marks, sp.total_marks, sp.grade,
                    a.attendance_percentage
                FROM student_subject_enrollment sse
                JOIN subjects subj ON subj.subject_id = sse.subject_id
                LEFT JOIN student_subject_performance sp ON sp.enrollment_record_id = sse.enrollment_record_id
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                WHERE sse.student_id = $1
                ORDER BY sse.semester_no ASC, subj.subject_name ASC
                """,
                student_id,
            )
        return {
            **dict(profile),
            "semester_summaries": [dict(r) for r in summaries],
            "subject_performance": [dict(r) for r in subjects],
        }

    async def get_student_profile_view(self, student_id: str) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            profile = await conn.fetchrow(
                """
                SELECT student_id, enrollment_no, university_roll_no, first_name, last_name,
                    COALESCE(NULLIF(full_name, ''), first_name || ' ' || last_name) AS full_name,
                    gender, date_of_birth, category, admission_year, admission_date,
                    admission_type, admission_quota, department_name, current_semester,
                    current_academic_year, city, email, student_phone_number,
                    guardian_name, guardian_phone, student_status,
                    latest_sgpa, overall_cgpa, overall_percentage, overall_attendance_percentage,
                    total_credits_registered, total_credits_earned, total_backlogs, academic_standing
                FROM students
                WHERE student_id = $1
                """,
                student_id,
            )
            if not profile:
                return None

            mentor = await conn.fetchrow(
                """
                SELECT fsm.mentor_role, fsm.mentor_since,
                    f.full_name AS faculty_name, f.designation
                FROM faculty_student_map fsm
                LEFT JOIN faculty f ON f.faculty_id = fsm.faculty_id
                WHERE fsm.student_id = $1
                ORDER BY fsm.mentor_since DESC NULLS LAST
                LIMIT 1
                """,
                student_id,
            )
            rank_row = await conn.fetchrow(
                """
                SELECT rk, total FROM (
                    SELECT student_id,
                        RANK() OVER (
                            PARTITION BY department_name
                            ORDER BY overall_percentage DESC NULLS LAST
                        ) AS rk,
                        COUNT(*) OVER (PARTITION BY department_name) AS total
                    FROM students
                ) ranked
                WHERE ranked.student_id = $1
                """,
                student_id,
            )
            career = await conn.fetchrow(
                """
                SELECT preferred_domain, dream_job_role, preferred_industry,
                    preferred_work_mode, target_package_lpa, higher_studies_interest,
                    entrepreneurship_interest, certification_interest,
                    internship_completed, placement_readiness_level
                FROM career_preferences
                WHERE student_id = $1
                ORDER BY survey_date DESC NULLS LAST
                LIMIT 1
                """,
                student_id,
            )
            message_count = await conn.fetchval(
                "SELECT count(*) FROM student_messages WHERE student_id = $1", student_id
            )
            summaries = await conn.fetch(
                """
                SELECT semester_no, academic_year, subjects_registered, credits_registered,
                    credits_earned, semester_percentage, semester_sgpa, semester_grade,
                    semester_attendance_percentage, backlog_count, semester_result,
                    academic_standing
                FROM student_semester_summary
                WHERE student_id = $1
                ORDER BY semester_no ASC
                """,
                student_id,
            )
            subjects = await conn.fetch(
                """
                SELECT sse.semester_no, sse.academic_year, sse.subject_id, subj.subject_code,
                    subj.subject_name, sse.credits, sse.subject_type, sse.faculty_id,
                    f.full_name AS faculty_name,
                    sp.internal_marks, sp.mid_sem_marks, sp.end_sem_marks AS external_marks,
                    sp.total_marks, sp.percentage, sp.grade, sp.grade_point, sp.result_status,
                    sp.attempt_number,
                    a.total_classes, a.attended_classes, a.attendance_percentage,
                    a.attendance_status, a.eligibility_status, a.shortage_flag
                FROM student_subject_enrollment sse
                JOIN subjects subj ON subj.subject_id = sse.subject_id
                LEFT JOIN faculty f ON f.faculty_id = sse.faculty_id
                LEFT JOIN student_subject_performance sp ON sp.enrollment_record_id = sse.enrollment_record_id
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                WHERE sse.student_id = $1
                ORDER BY sse.semester_no ASC, subj.subject_name ASC
                """,
                student_id,
            )
        return {
            "student": dict(profile),
            "mentor": dict(mentor) if mentor else None,
            "rank": int(rank_row["rk"]) if rank_row else None,
            "rank_total": int(rank_row["total"]) if rank_row else None,
            "message_count": int(message_count or 0),
            "semester_summaries": [dict(r) for r in summaries],
            "subject_performance": [dict(r) for r in subjects],
            "career": dict(career) if career else None,
        }

    async def get_subjects_summary(
        self,
        faculty_id: str,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
        batch: Optional[str] = None,
    ) -> Dict[str, Any]:
        clauses = ["sse.faculty_id = $1", "sse.enrollment_status = 'Active'"]
        params: List[Any] = [faculty_id]
        if semester_no is not None:
            params.append(semester_no)
            clauses.append(f"sse.semester_no = ${len(params)}")
        if academic_year is not None:
            params.append(academic_year)
            clauses.append(f"sse.academic_year = ${len(params)}")
        batch_year = self.batch_to_year(batch)
        if batch_year is not None:
            params.append(batch_year)
            clauses.append(f"st.admission_year = ${len(params)}")
        query = f"""
            SELECT 
                count(DISTINCT (sse.subject_id, sse.semester_no, sse.academic_year)) AS total_subjects,
                count(DISTINCT sse.student_id) AS total_students
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            WHERE {' AND '.join(clauses)}
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            return dict(row) if row else {"total_subjects": 0, "total_students": 0}

    async def get_subjects_weighted_attendance(
        self,
        faculty_id: str,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
        batch: Optional[str] = None,
    ) -> Optional[float]:
        """Weighted attendance across the filtered subject-offering population.

        Uses the same weekly-primary / legacy fallback as the subject cards so
        the KPI and the cards are computed over the identical filtered dataset.
        attendance % = 100 * SUM(classes_attended) / SUM(classes_held), never
        averaging already-averaged subject percentages.
        """
        clauses = ["sse.faculty_id = $1", "sse.enrollment_status = 'Active'"]
        params: List[Any] = [faculty_id]
        if semester_no is not None:
            params.append(semester_no)
            clauses.append(f"sse.semester_no = ${len(params)}")
        if academic_year is not None:
            params.append(academic_year)
            clauses.append(f"sse.academic_year = ${len(params)}")
        batch_year = self.batch_to_year(batch)
        if batch_year is not None:
            params.append(batch_year)
            clauses.append(f"st.admission_year = ${len(params)}")
        query = f"""
            SELECT
                CASE
                    WHEN COALESCE(SUM(aw.classes_held), 0) > 0
                        THEN ROUND((100.0 * SUM(aw.classes_attended) / SUM(aw.classes_held))::numeric, 2)
                    WHEN COALESCE(SUM(a.total_classes), 0) > 0
                        THEN ROUND((100.0 * SUM(a.attended_classes) / SUM(a.total_classes))::numeric, 2)
                    ELSE NULL
                END AS average_attendance
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance_weekly aw
                ON aw.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN attendance a
                ON a.enrollment_record_id = sse.enrollment_record_id
            WHERE {' AND '.join(clauses)}
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            if not row or row["average_attendance"] is None:
                return None
            return float(row["average_attendance"])

    async def get_subject_filters(self, faculty_id: str) -> Dict[str, Any]:
        async with self.pool.acquire() as conn:
            semesters = await conn.fetch(
                """
                SELECT DISTINCT semester_no
                FROM student_subject_enrollment
                WHERE faculty_id = $1 AND enrollment_status = 'Active'
                ORDER BY semester_no ASC
                """,
                faculty_id,
            )
            years = await conn.fetch(
                """
                SELECT DISTINCT academic_year
                FROM student_subject_enrollment
                WHERE faculty_id = $1 AND enrollment_status = 'Active'
                ORDER BY academic_year ASC
                """,
                faculty_id,
            )
            batches = await conn.fetch(
                """
                SELECT DISTINCT st.admission_year
                FROM student_subject_enrollment sse
                JOIN students st ON st.student_id = sse.student_id
                WHERE sse.faculty_id = $1 AND sse.enrollment_status = 'Active'
                    AND st.admission_year IS NOT NULL
                ORDER BY st.admission_year ASC
                """,
                faculty_id,
            )
        return {
            "semesters": [r["semester_no"] for r in semesters],
            "academic_years": [r["academic_year"] for r in years],
            "batches": [self.year_to_batch(r["admission_year"]) for r in batches],
        }

    @staticmethod
    def batch_to_year(batch: Optional[str]) -> Optional[int]:
        """Parse a batch label ("2021-22") into the admission_year int (2021)."""
        if not batch:
            return None
        try:
            return int(str(batch)[:4])
        except (ValueError, TypeError):
            return None

    @staticmethod
    def year_to_batch(year: Optional[int]) -> Optional[str]:
        """Format an admission_year int (2021) into the project batch label ("2021-22")."""
        if year is None:
            return None
        return f"{year}-{str(year + 1)[-2:]}"

    def _subject_cards_where(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        search: Optional[str],
        batch: Optional[str] = None,
    ) -> tuple:
        clauses = ["sse.faculty_id = $1", "sse.enrollment_status = 'Active'"]
        params: List[Any] = [faculty_id]
        if semester_no is not None:
            params.append(semester_no)
            clauses.append(f"sse.semester_no = ${len(params)}")
        if academic_year is not None:
            params.append(academic_year)
            clauses.append(f"sse.academic_year = ${len(params)}")
        batch_year = self.batch_to_year(batch)
        if batch_year is not None:
            params.append(batch_year)
            clauses.append(f"st.admission_year = ${len(params)}")
        if search:
            params.append(f"%{search}%")
            clauses.append(
                f"(sse.subject_code ILIKE ${len(params)} OR sse.subject_name ILIKE ${len(params)})"
            )
        return f"WHERE {' AND '.join(clauses)}", params

    async def count_subject_cards(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        search: Optional[str],
        batch: Optional[str] = None,
    ) -> int:
        where, params = self._subject_cards_where(faculty_id, semester_no, academic_year, search, batch)
        query = f"""
            SELECT count(DISTINCT (sse.subject_id, sse.semester_no, sse.academic_year))
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            {where}
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *params)

    async def get_subject_cards(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        search: Optional[str],
        order_by: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        batch: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        where, params = self._subject_cards_where(faculty_id, semester_no, academic_year, search, batch)
        query = f"""
            SELECT 
                sse.subject_id, sse.subject_code, sse.subject_name, sse.credits,
                sse.semester_no, sse.academic_year,
                count(DISTINCT sse.student_id) AS class_strength,
                CASE
                    WHEN SUM(aw.classes_held) > 0
                        THEN ROUND((100.0 * SUM(aw.classes_attended) / SUM(aw.classes_held))::numeric, 2)
                    WHEN SUM(a.total_classes) > 0
                        THEN ROUND((100.0 * SUM(a.attended_classes) / SUM(a.total_classes))::numeric, 2)
                    ELSE NULL
                END AS average_attendance,
                AVG(sp.percentage) AS average_percentage,
                MAX(sp.total_marks) AS highest_marks,
                MIN(sp.total_marks) AS lowest_marks,
                AVG(sp.grade_point) AS average_grade_point,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(sp.result_status) AS performed_count
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance_weekly aw 
                ON aw.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            {where}
            GROUP BY sse.subject_id, sse.subject_code, sse.subject_name, sse.credits,
                sse.semester_no, sse.academic_year
            ORDER BY {order_by}
        """
        if limit is not None:
            params.append(limit)
            query += f" LIMIT ${len(params)}"
            if offset is not None:
                params.append(offset)
                query += f" OFFSET ${len(params)}"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_subject_term(self, faculty_id: str, subject_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT semester_no, academic_year
            FROM student_subject_enrollment
            WHERE faculty_id = $1 AND subject_id = $2 AND enrollment_status = 'Active'
            ORDER BY academic_year DESC, semester_no DESC
            LIMIT 1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, faculty_id, subject_id)
            return dict(row) if row else None

    async def get_subject_detail(
        self,
        faculty_id: str,
        subject_id: str,
        semester_no: int,
        academic_year: str,
    ) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            scope = await conn.fetchval(
                """
                SELECT 1 FROM student_subject_enrollment
                WHERE faculty_id = $1 AND subject_id = $2 AND semester_no = $3
                    AND academic_year = $4 AND enrollment_status = 'Active'
                LIMIT 1
                """,
                faculty_id, subject_id, semester_no, academic_year,
            )
            if not scope:
                return None

            meta = await conn.fetchrow(
                """
                SELECT subject_id, subject_code, subject_name, credits, semester_no,
                    subject_type, assessment_type, department_name
                FROM subjects
                WHERE subject_id = $1
                """,
                subject_id,
            )

            agg = await conn.fetchrow(
                """
                SELECT 
                    count(DISTINCT sse.student_id) AS total_enrolled,
                    AVG(sp.percentage) AS average_percentage,
                    CASE
                        WHEN SUM(aw.classes_held) > 0
                            THEN ROUND((100.0 * SUM(aw.classes_attended) / SUM(aw.classes_held))::numeric, 2)
                        WHEN SUM(a.total_classes) > 0
                            THEN ROUND((100.0 * SUM(a.attended_classes) / SUM(a.total_classes))::numeric, 2)
                        ELSE NULL
                    END AS average_attendance,
                    count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                    count(sp.result_status) AS performed_count,
                    AVG(sp.grade_point) AS average_grade_point
                FROM student_subject_enrollment sse
                LEFT JOIN attendance_weekly aw 
                    ON aw.enrollment_record_id = sse.enrollment_record_id
                LEFT JOIN attendance a 
                    ON a.enrollment_record_id = sse.enrollment_record_id
                LEFT JOIN student_subject_performance sp 
                    ON sp.enrollment_record_id = sse.enrollment_record_id
                WHERE sse.faculty_id = $1 AND sse.subject_id = $2
                    AND sse.semester_no = $3 AND sse.academic_year = $4
                    AND sse.enrollment_status = 'Active'
                """,
                faculty_id, subject_id, semester_no, academic_year,
            )

            grades = await conn.fetch(
                """
                SELECT sp.grade, count(*) AS count
                FROM student_subject_enrollment sse
                JOIN student_subject_performance sp ON sp.enrollment_record_id = sse.enrollment_record_id
                WHERE sse.faculty_id = $1 AND sse.subject_id = $2
                    AND sse.semester_no = $3 AND sse.academic_year = $4
                    AND sse.enrollment_status = 'Active' AND sp.grade IS NOT NULL
                GROUP BY sp.grade
                ORDER BY MAX(sp.grade_point) DESC
                """,
                faculty_id, subject_id, semester_no, academic_year,
            )

            attendance = await conn.fetch(
                """
                WITH student_att AS (
                    SELECT sse.student_id,
                           COALESCE(
                               CASE WHEN SUM(aw.classes_held) > 0
                                    THEN 100.0 * SUM(aw.classes_attended) / SUM(aw.classes_held)
                                    ELSE NULL END,
                               CASE WHEN SUM(a.total_classes) > 0
                                    THEN 100.0 * SUM(a.attended_classes) / SUM(a.total_classes)
                                    ELSE NULL END
                           ) AS att_pct
                    FROM student_subject_enrollment sse
                    LEFT JOIN attendance_weekly aw ON aw.enrollment_record_id = sse.enrollment_record_id
                    LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                    WHERE sse.faculty_id = $1 AND sse.subject_id = $2
                        AND sse.semester_no = $3 AND sse.academic_year = $4
                        AND sse.enrollment_status = 'Active'
                    GROUP BY sse.student_id
                )
                SELECT
                    CASE
                        WHEN att_pct < 75 THEN '< 75%'
                        WHEN att_pct <= 85 THEN '75% - 85%'
                        ELSE '> 85%'
                    END AS band,
                    count(*) AS count
                FROM student_att
                WHERE att_pct IS NOT NULL
                GROUP BY band
                ORDER BY MIN(att_pct) ASC
                """,
                faculty_id, subject_id, semester_no, academic_year,
            )

            students = await conn.fetch(
                """
                SELECT sse.student_id, sse.enrollment_no, st.first_name, st.last_name,
                    COALESCE(wk_att.attendance_percentage, lg_att.attendance_percentage) AS attendance_percentage,
                    sp.total_marks, sp.grade
                FROM student_subject_enrollment sse
                JOIN students st ON st.student_id = sse.student_id
                LEFT JOIN (
                    SELECT enrollment_record_id,
                           ROUND((100.0 * SUM(classes_attended) / NULLIF(SUM(classes_held), 0))::numeric, 2) AS attendance_percentage
                    FROM attendance_weekly
                    GROUP BY enrollment_record_id
                ) wk_att ON wk_att.enrollment_record_id = sse.enrollment_record_id
                LEFT JOIN (
                    SELECT enrollment_record_id,
                           ROUND((100.0 * SUM(attended_classes) / NULLIF(SUM(total_classes), 0))::numeric, 2) AS attendance_percentage
                    FROM attendance
                    GROUP BY enrollment_record_id
                ) lg_att ON lg_att.enrollment_record_id = sse.enrollment_record_id
                LEFT JOIN student_subject_performance sp ON sp.enrollment_record_id = sse.enrollment_record_id
                WHERE sse.faculty_id = $1 AND sse.subject_id = $2
                    AND sse.semester_no = $3 AND sse.academic_year = $4
                    AND sse.enrollment_status = 'Active'
                ORDER BY st.first_name ASC, st.last_name ASC
                """,
                faculty_id, subject_id, semester_no, academic_year,
            )

        return {
            "meta": dict(meta),
            "agg": dict(agg),
            "grades": [dict(r) for r in grades],
            "attendance": [dict(r) for r in attendance],
            "students": [dict(r) for r in students],
        }

    async def get_subject_meta(self, subject_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT subject_id, subject_code, subject_name
            FROM subjects
            WHERE subject_id = $1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, subject_id)
            return dict(row) if row else None

    async def get_subject_history(self, faculty_id: str, subject_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                sse.semester_no, sse.academic_year,
                count(DISTINCT sse.student_id) AS students,
                AVG(sp.percentage) AS average_performance,
                CASE
                    WHEN SUM(aw.classes_held) > 0
                        THEN ROUND((100.0 * SUM(aw.classes_attended) / SUM(aw.classes_held))::numeric, 2)
                    WHEN SUM(a.total_classes) > 0
                        THEN ROUND((100.0 * SUM(a.attended_classes) / SUM(a.total_classes))::numeric, 2)
                    ELSE NULL
                END AS average_attendance,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(sp.result_status) AS performed_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance_weekly aw 
                ON aw.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            WHERE sse.faculty_id = $1 AND sse.subject_id = $2
                AND sse.enrollment_status = 'Active'
            GROUP BY sse.semester_no, sse.academic_year
            ORDER BY sse.academic_year ASC, sse.semester_no ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, faculty_id, subject_id)
            return [dict(row) for row in rows]

    async def get_performance_filters(self, faculty_id: str) -> Dict[str, Any]:
        async with self.pool.acquire() as conn:
            semesters = await conn.fetch(
                """
                SELECT DISTINCT semester_no
                FROM student_subject_enrollment
                WHERE faculty_id = $1 AND enrollment_status = 'Active'
                ORDER BY semester_no ASC
                """,
                faculty_id,
            )
            years = await conn.fetch(
                """
                SELECT DISTINCT academic_year
                FROM student_subject_enrollment
                WHERE faculty_id = $1 AND enrollment_status = 'Active'
                ORDER BY academic_year ASC
                """,
                faculty_id,
            )
            subjects = await conn.fetch(
                """
                SELECT DISTINCT subject_id, subject_code, subject_name
                FROM student_subject_enrollment
                WHERE faculty_id = $1 AND enrollment_status = 'Active'
                ORDER BY subject_code ASC
                """,
                faculty_id,
            )
            pairs = await conn.fetch(
                """
                SELECT DISTINCT semester_no, academic_year
                FROM student_subject_enrollment
                WHERE faculty_id = $1 AND enrollment_status = 'Active'
                ORDER BY academic_year ASC, semester_no ASC
                """,
                faculty_id,
            )
        return {
            "semesters": [r["semester_no"] for r in semesters],
            "academic_years": [r["academic_year"] for r in years],
            "subjects": [dict(r) for r in subjects],
            "term_options": [dict(r) for r in pairs],
        }

    async def get_taught_terms(self, faculty_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT DISTINCT semester_no, academic_year
            FROM student_subject_enrollment
            WHERE faculty_id = $1 AND enrollment_status = 'Active'
            ORDER BY semester_no ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, faculty_id)
            return [dict(row) for row in rows]

    def _analytics_where(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> tuple:
        clauses = ["sse.faculty_id = $1", "sse.enrollment_status = 'Active'"]
        params: List[Any] = [faculty_id]
        if semester_no is not None:
            params.append(semester_no)
            clauses.append(f"sse.semester_no = ${len(params)}")
        if academic_year is not None:
            params.append(academic_year)
            clauses.append(f"sse.academic_year = ${len(params)}")
        if subject_id is not None:
            params.append(subject_id)
            clauses.append(f"sse.subject_id = ${len(params)}")
        return f"WHERE {' AND '.join(clauses)}", params

    def _performance_where(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> tuple:
        return self._analytics_where(faculty_id, semester_no, academic_year, subject_id)

    async def get_performance_aggregates(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        perf_threshold: float,
        distinction_point: float,
    ) -> Dict[str, Any]:
        where, params = self._performance_where(faculty_id, semester_no, academic_year, subject_id)
        params.extend([perf_threshold, distinction_point])
        query = f"""
            SELECT 
                count(DISTINCT (sse.subject_id, sse.semester_no, sse.academic_year)) AS subjects,
                count(*) AS enrollments,
                AVG(sp.percentage) AS avg_performance,
                AVG(COALESCE(a.attendance_percentage, sss.semester_attendance_percentage)) AS avg_attendance,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(sp.result_status) AS performed_count,
                count(*) FILTER (WHERE sp.grade_point >= ${len(params)}) AS distinction_count,
                count(*) FILTER (WHERE sp.percentage < ${len(params) - 1}) AS below_count,
                count(*) FILTER (WHERE a.eligibility_status = 'Not Eligible') AS ineligible_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_semester_summary sss
                ON sss.student_id = sse.student_id AND sss.semester_no = sse.semester_no
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            {where}
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            return dict(row) if row else {
                "subjects": 0, "enrollments": 0, "avg_performance": None,
                "avg_attendance": None, "pass_count": 0, "performed_count": 0,
                "distinction_count": 0, "below_count": 0, "ineligible_count": 0,
            }

    async def get_grade_distribution(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        where, params = self._performance_where(faculty_id, semester_no, academic_year, subject_id)
        query = f"""
            SELECT sp.grade, count(*) AS count
            FROM student_subject_enrollment sse
            JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            {where}
            AND sp.grade IS NOT NULL
            GROUP BY sp.grade
            ORDER BY MAX(sp.grade_point) DESC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_performance_bands(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        where, params = self._performance_where(faculty_id, semester_no, academic_year, subject_id)
        query = f"""
            SELECT
                CASE
                    WHEN sp.percentage < 35 THEN '< 35%'
                    WHEN sp.percentage < 45 THEN '35% - 45%'
                    WHEN sp.percentage < 60 THEN '45% - 60%'
                    WHEN sp.percentage < 75 THEN '60% - 75%'
                    WHEN sp.percentage < 90 THEN '75% - 90%'
                    ELSE '>= 90%'
                END AS band,
                count(DISTINCT sse.enrollment_record_id) AS count
            FROM student_subject_enrollment sse
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            {where}
            AND sp.percentage IS NOT NULL
            GROUP BY band
            ORDER BY MIN(sp.percentage) ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_attendance_bands(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        where, params = self._performance_where(faculty_id, semester_no, academic_year, subject_id)
        query = f"""
            SELECT
                CASE
                    WHEN a.attendance_percentage < 60 THEN '< 60%'
                    WHEN a.attendance_percentage < 75 THEN '60% - 75%'
                    WHEN a.attendance_percentage < 90 THEN '75% - 90%'
                    ELSE '>= 90%'
                END AS band,
                count(DISTINCT sse.enrollment_record_id) AS count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            {where}
            AND a.attendance_percentage IS NOT NULL
            GROUP BY band
            ORDER BY MIN(a.attendance_percentage) ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_attempt_analysis(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        where, params = self._performance_where(faculty_id, semester_no, academic_year, subject_id)
        query = f"""
            SELECT
                CASE WHEN sp.attempt_number > 1 THEN 'Repeat' ELSE 'First' END AS attempt,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(*) FILTER (WHERE sp.result_status = 'Fail') AS fail_count
            FROM student_subject_enrollment sse
            JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            {where}
            AND sp.result_status IS NOT NULL
            GROUP BY attempt
            ORDER BY attempt ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_category_distribution(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        where, params = self._performance_where(faculty_id, semester_no, academic_year, subject_id)
        query = f"""
            SELECT sp.performance_category AS category, count(*) AS count
            FROM student_subject_enrollment sse
            JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            {where}
            AND sp.performance_category IS NOT NULL
            GROUP BY sp.performance_category
            ORDER BY count(*) DESC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_subject_breakdown(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        where, params = self._performance_where(faculty_id, semester_no, academic_year, subject_id)
        query = f"""
            SELECT 
                sse.subject_id, sse.subject_code, sse.subject_name,
                sse.semester_no, sse.academic_year,
                count(DISTINCT sse.student_id) AS enrollments,
                AVG(sp.percentage) AS average_performance,
                AVG(COALESCE(a.attendance_percentage, sss.semester_attendance_percentage)) AS average_attendance,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(sp.result_status) AS performed_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_semester_summary sss
                ON sss.student_id = sse.student_id AND sss.semester_no = sse.semester_no
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            {where}
            GROUP BY sse.subject_id, sse.subject_code, sse.subject_name,
                sse.semester_no, sse.academic_year
            ORDER BY sse.subject_name ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_performance_trends(
        self,
        faculty_id: str,
        subject_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        clauses = ["sse.faculty_id = $1", "sse.enrollment_status = 'Active'"]
        params: List[Any] = [faculty_id]
        if subject_id is not None:
            params.append(subject_id)
            clauses.append(f"sse.subject_id = ${len(params)}")
        query = f"""
            SELECT 
                sse.semester_no, sse.academic_year,
                AVG(sp.percentage) AS average_performance,
                AVG(COALESCE(a.attendance_percentage, sss.semester_attendance_percentage)) AS average_attendance,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(sp.result_status) AS performed_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_semester_summary sss
                ON sss.student_id = sse.student_id AND sss.semester_no = sse.semester_no
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            WHERE {' AND '.join(clauses)}
            GROUP BY sse.semester_no, sse.academic_year
            ORDER BY sse.academic_year ASC, sse.semester_no ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_learning_gap_rows(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        perf_threshold: float,
    ) -> List[Dict[str, Any]]:
        where, params = self._performance_where(faculty_id, semester_no, academic_year, subject_id)
        params.append(perf_threshold)
        query = f"""
            SELECT 
                sse.subject_id, sse.subject_code, sse.subject_name,
                sse.semester_no, sse.academic_year,
                count(DISTINCT sse.student_id) AS enrollments,
                AVG(sp.percentage) AS average_performance,
                AVG(COALESCE(a.attendance_percentage, sss.semester_attendance_percentage)) AS average_attendance,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(sp.result_status) AS performed_count,
                count(*) FILTER (WHERE sp.percentage < ${len(params)}) AS below_count,
                count(*) FILTER (WHERE a.eligibility_status = 'Not Eligible') AS ineligible_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_semester_summary sss
                ON sss.student_id = sse.student_id AND sss.semester_no = sse.semester_no
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            {where}
            GROUP BY sse.subject_id, sse.subject_code, sse.subject_name,
                sse.semester_no, sse.academic_year
            ORDER BY sse.subject_name ASC, sse.semester_no ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_subject_offering_history(self, faculty_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                sse.subject_id, sse.semester_no, sse.academic_year,
                AVG(sp.percentage) AS average_performance
            FROM student_subject_enrollment sse
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            WHERE sse.faculty_id = $1 AND sse.enrollment_status = 'Active'
            GROUP BY sse.subject_id, sse.semester_no, sse.academic_year
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, faculty_id)
            return [dict(row) for row in rows]

    def _performance_students_where(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        gap_status: Optional[str],
        perf_threshold: float,
    ) -> tuple:
        clauses = ["sse.faculty_id = $1", "sse.enrollment_status = 'Active'"]
        params: List[Any] = [faculty_id]
        if semester_no is not None:
            params.append(semester_no)
            clauses.append(f"sse.semester_no = ${len(params)}")
        if academic_year is not None:
            params.append(academic_year)
            clauses.append(f"sse.academic_year = ${len(params)}")
        if subject_id is not None:
            params.append(subject_id)
            clauses.append(f"sse.subject_id = ${len(params)}")
        if gap_status == "Below Baseline":
            params.append(perf_threshold)
            clauses.append(f"sp.percentage IS NOT NULL AND sp.percentage < ${len(params)}")
        elif gap_status == "On Track":
            params.append(perf_threshold)
            clauses.append(f"(sp.percentage IS NULL OR sp.percentage >= ${len(params)})")
        if search:
            params.append(f"%{search}%")
            clauses.append(
                f"(st.enrollment_no::text ILIKE ${len(params)} "
                f"OR st.first_name ILIKE ${len(params)} "
                f"OR st.last_name ILIKE ${len(params)})"
            )
        return f"WHERE {' AND '.join(clauses)}", params

    async def count_performance_students(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        gap_status: Optional[str],
        perf_threshold: float,
    ) -> int:
        where, params = self._performance_students_where(
            faculty_id, semester_no, academic_year, subject_id, search, gap_status, perf_threshold
        )
        query = f"""
            SELECT count(DISTINCT sse.enrollment_record_id)
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            {where}
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *params)

    async def get_performance_students(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        gap_status: Optional[str],
        perf_threshold: float,
        order_by: str,
        limit: int,
        offset: int,
    ) -> List[Dict[str, Any]]:
        where, params = self._performance_students_where(
            faculty_id, semester_no, academic_year, subject_id, search, gap_status, perf_threshold
        )
        params.extend([limit, offset])
        query = f"""
            SELECT 
                sse.enrollment_record_id, sse.student_id, sse.enrollment_no, sse.semester_no,
                sse.subject_id, sse.subject_code, sse.subject_name,
                st.first_name, st.last_name,
                COALESCE(a.attendance_percentage, sss.semester_attendance_percentage) AS attendance_percentage,
                sp.total_marks, sp.grade, sp.result_status, sp.percentage
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_semester_summary sss
                ON sss.student_id = sse.student_id AND sss.semester_no = sse.semester_no
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            {where}
            ORDER BY {order_by}
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    def _attendance_where(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> tuple:
        return self._analytics_where(faculty_id, semester_no, academic_year, subject_id)

    async def get_attendance_filter_options(self, faculty_id: str) -> Dict[str, Any]:
        async with self.pool.acquire() as conn:
            statuses = await conn.fetch(
                """
                SELECT DISTINCT a.attendance_status
                FROM student_subject_enrollment sse
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                WHERE sse.faculty_id = $1 AND sse.enrollment_status = 'Active'
                    AND a.attendance_status IS NOT NULL
                ORDER BY a.attendance_status ASC
                """,
                faculty_id,
            )
            student_statuses = await conn.fetch(
                """
                SELECT DISTINCT sse.enrollment_status
                FROM student_subject_enrollment sse
                WHERE sse.faculty_id = $1 AND sse.enrollment_status IS NOT NULL
                ORDER BY sse.enrollment_status ASC
                """,
                faculty_id,
            )
        return {
            "attendance_statuses": [r["attendance_status"] for r in statuses],
            "student_statuses": [r["enrollment_status"] for r in student_statuses],
        }

    async def get_attendance_aggregates(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        attendance_threshold: float,
    ) -> Dict[str, Any]:
        where, params = self._attendance_where(faculty_id, semester_no, academic_year, subject_id)
        params.append(attendance_threshold)
        query = f"""
            SELECT 
                count(DISTINCT (sse.subject_id, sse.semester_no, sse.academic_year)) AS subjects,
                count(*) AS enrollments,
                count(a.attendance_id) AS attendance_records,
                AVG(COALESCE(a.attendance_percentage, sss.semester_attendance_percentage)) AS avg_attendance,
                CASE WHEN SUM(a.total_classes) > 0
                    THEN ROUND(SUM(a.attended_classes) * 100.0 / SUM(a.total_classes), 2)
                END AS overall_attendance,
                AVG(a.total_classes) AS avg_total_classes,
                count(*) FILTER (WHERE COALESCE(a.attendance_percentage, sss.semester_attendance_percentage) >= ${len(params)}) AS above_count,
                count(*) FILTER (WHERE COALESCE(a.attendance_percentage, sss.semester_attendance_percentage) < ${len(params)}) AS below_count,
                count(*) FILTER (WHERE a.eligibility_status = 'Not Eligible') AS ineligible_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_semester_summary sss
                ON sss.student_id = sse.student_id AND sss.semester_no = sse.semester_no
            {where}
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            return dict(row) if row else {
                "subjects": 0, "enrollments": 0, "attendance_records": 0,
                "avg_attendance": None, "overall_attendance": None,
                "avg_total_classes": None, "above_count": 0, "below_count": 0,
                "ineligible_count": 0,
            }

    async def get_attendance_subject_breakdown(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        attendance_threshold: float,
    ) -> List[Dict[str, Any]]:
        where, params = self._attendance_where(faculty_id, semester_no, academic_year, subject_id)
        params.append(attendance_threshold)
        query = f"""
            SELECT 
                sse.subject_id, sse.subject_code, sse.subject_name,
                sse.semester_no, sse.academic_year,
                count(DISTINCT sse.student_id) AS enrollments,
                AVG(COALESCE(a.attendance_percentage, sss.semester_attendance_percentage)) AS average_attendance,
                count(*) FILTER (WHERE COALESCE(a.attendance_percentage, sss.semester_attendance_percentage) >= ${len(params)}) AS above_count,
                count(*) FILTER (WHERE COALESCE(a.attendance_percentage, sss.semester_attendance_percentage) < ${len(params)}) AS below_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_semester_summary sss
                ON sss.student_id = sse.student_id AND sss.semester_no = sse.semester_no
            {where}
            GROUP BY sse.subject_id, sse.subject_code, sse.subject_name,
                sse.semester_no, sse.academic_year
            ORDER BY sse.subject_name ASC, sse.semester_no ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_attendance_status_distribution(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        where, params = self._attendance_where(faculty_id, semester_no, academic_year, subject_id)
        query = f"""
            SELECT a.attendance_status AS status, count(DISTINCT sse.enrollment_record_id) AS count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            {where}
            AND a.attendance_status IS NOT NULL
            GROUP BY a.attendance_status
            ORDER BY MIN(a.attendance_percentage) DESC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_attendance_heatmap(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        where, params = self._attendance_where(faculty_id, semester_no, academic_year, subject_id)
        query = f"""
            SELECT 
                sse.student_id, st.first_name, st.last_name,
                sse.subject_id, sse.subject_code,
                a.attendance_percentage
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            {where}
            AND a.attendance_percentage IS NOT NULL
            ORDER BY st.first_name ASC, st.last_name ASC, sse.subject_code ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_attendance_above_below(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        attendance_threshold: float,
    ) -> List[Dict[str, Any]]:
        where, params = self._attendance_where(faculty_id, semester_no, academic_year, subject_id)
        params.append(attendance_threshold)
        query = f"""
            SELECT
                CASE WHEN a.attendance_percentage >= ${len(params)} 
                    THEN 'Above Threshold' ELSE 'Below Threshold' END AS band,
                count(DISTINCT sse.enrollment_record_id) AS count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            {where}
            AND a.attendance_percentage IS NOT NULL
            GROUP BY band
            ORDER BY band ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_attendance_trends(
        self,
        faculty_id: str,
        subject_id: Optional[str],
    ) -> Dict[str, Any]:
        clauses = ["sse.faculty_id = $1", "sse.enrollment_status = 'Active'"]
        params: List[Any] = [faculty_id]
        if subject_id is not None:
            params.append(subject_id)
            clauses.append(f"sse.subject_id = ${len(params)}")
        where = f"WHERE {' AND '.join(clauses)}"
        term_query = f"""
            SELECT 
                sse.semester_no, sse.academic_year,
                AVG(COALESCE(a.attendance_percentage, sss.semester_attendance_percentage)) AS average_attendance
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_semester_summary sss
                ON sss.student_id = sse.student_id AND sss.semester_no = sse.semester_no
            {where}
            GROUP BY sse.semester_no, sse.academic_year
            ORDER BY sse.academic_year ASC, sse.semester_no ASC
        """
        subject_query = f"""
            SELECT 
                sse.subject_id, sse.subject_code, sse.subject_name,
                sse.semester_no, sse.academic_year,
                AVG(COALESCE(a.attendance_percentage, sss.semester_attendance_percentage)) AS average_attendance
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_semester_summary sss
                ON sss.student_id = sse.student_id AND sss.semester_no = sse.semester_no
            {where}
            GROUP BY sse.subject_id, sse.subject_code, sse.subject_name,
                sse.semester_no, sse.academic_year
            ORDER BY sse.academic_year ASC, sse.semester_no ASC, sse.subject_name ASC
        """
        async with self.pool.acquire() as conn:
            terms = await conn.fetch(term_query, *params)
            by_subject = await conn.fetch(subject_query, *params)
        return {
            "terms": [dict(r) for r in terms],
            "by_subject": [dict(r) for r in by_subject],
        }

    async def get_attendance_governance(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        where, params = self._attendance_where(faculty_id, semester_no, academic_year, subject_id)
        query = f"""
            SELECT 
                sse.enrollment_record_id, sse.student_id, sse.enrollment_no, sse.semester_no,
                sse.subject_id, sse.subject_code, sse.subject_name,
                st.first_name, st.last_name,
                a.attendance_percentage, a.attendance_status, a.eligibility_status, a.shortage_flag,
                a.total_classes, a.attended_classes
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            {where}
            ORDER BY a.attendance_percentage ASC NULLS LAST, st.first_name ASC, st.last_name ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_attendance_history(self, faculty_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                sse.enrollment_record_id, sse.student_id, sse.subject_id,
                sse.semester_no, sse.academic_year,
                a.attendance_percentage
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            WHERE sse.faculty_id = $1 AND sse.enrollment_status = 'Active'
                AND a.attendance_percentage IS NOT NULL
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, faculty_id)
            return [dict(row) for row in rows]

    async def get_attendance_health_score(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> Dict[str, Any]:
        where, params = self._attendance_where(faculty_id, semester_no, academic_year, subject_id)
        subject_query = f"""
            SELECT 
                sse.subject_id, sse.subject_code, sse.subject_name,
                AVG(COALESCE(a.attendance_percentage, sss.semester_attendance_percentage)) AS average_attendance,
                count(DISTINCT sse.student_id) AS enrollments
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_semester_summary sss
                ON sss.student_id = sse.student_id AND sss.semester_no = sse.semester_no
            {where}
            GROUP BY sse.subject_id, sse.subject_code, sse.subject_name
            ORDER BY sse.subject_name ASC
        """
        student_query = f"""
            SELECT 
                sse.student_id, sse.enrollment_no, st.first_name, st.last_name,
                sse.subject_id, sse.subject_code, sse.subject_name,
                a.attendance_percentage, a.eligibility_status, a.shortage_flag
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            {where}
            ORDER BY st.first_name ASC, st.last_name ASC, sse.subject_name ASC
        """
        async with self.pool.acquire() as conn:
            subjects = await conn.fetch(subject_query, *params)
            students = await conn.fetch(student_query, *params)
        return {
            "subjects": [dict(r) for r in subjects],
            "students": [dict(r) for r in students],
        }

    async def get_attendance_correlation(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        where, params = self._attendance_where(faculty_id, semester_no, academic_year, subject_id)
        query = f"""
            SELECT a.attendance_percentage, sp.percentage AS performance_percentage
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            {where}
            AND a.attendance_percentage IS NOT NULL AND sp.percentage IS NOT NULL
            ORDER BY a.attendance_percentage ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    def _attendance_students_where(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        attendance_range: Optional[str],
        attendance_status: Optional[str],
        defaulter_status: Optional[str],
        student_status: Optional[str],
        critical_threshold: float,
        attendance_threshold: float,
        excellent_threshold: float,
    ) -> tuple:
        clauses = ["sse.faculty_id = $1"]
        params: List[Any] = [faculty_id]

        if student_status:
            params.append(student_status)
            clauses.append(f"sse.enrollment_status = ${len(params)}")
        else:
            clauses.append("sse.enrollment_status = 'Active'")

        if semester_no is not None:
            params.append(semester_no)
            clauses.append(f"sse.semester_no = ${len(params)}")
        if academic_year is not None:
            params.append(academic_year)
            clauses.append(f"sse.academic_year = ${len(params)}")
        if subject_id is not None:
            params.append(subject_id)
            clauses.append(f"sse.subject_id = ${len(params)}")

        if attendance_status is not None:
            params.append(attendance_status)
            clauses.append(f"a.attendance_status = ${len(params)}")

        if attendance_range is not None:
            if attendance_range == f"< {critical_threshold:.0f}%":
                params.append(critical_threshold)
                clauses.append(
                    f"a.attendance_percentage IS NOT NULL AND a.attendance_percentage < ${len(params)}"
                )
            elif attendance_range == f"{critical_threshold:.0f}% - {attendance_threshold:.0f}%":
                params.append(critical_threshold)
                params.append(attendance_threshold)
                clauses.append(
                    f"a.attendance_percentage IS NOT NULL "
                    f"AND a.attendance_percentage >= ${len(params) - 1} "
                    f"AND a.attendance_percentage < ${len(params)}"
                )
            elif attendance_range == f"{attendance_threshold:.0f}% - {excellent_threshold:.0f}%":
                params.append(attendance_threshold)
                params.append(excellent_threshold)
                clauses.append(
                    f"a.attendance_percentage IS NOT NULL "
                    f"AND a.attendance_percentage >= ${len(params) - 1} "
                    f"AND a.attendance_percentage < ${len(params)}"
                )
            elif attendance_range == f">= {excellent_threshold:.0f}%":
                params.append(excellent_threshold)
                clauses.append(
                    f"a.attendance_percentage IS NOT NULL AND a.attendance_percentage >= ${len(params)}"
                )

        if defaulter_status is not None:
            if defaulter_status == "Defaulter":
                params.append(attendance_threshold)
                clauses.append(
                    f"a.attendance_percentage IS NOT NULL AND a.attendance_percentage < ${len(params)}"
                )
            elif defaulter_status == "Non-Defaulter":
                params.append(attendance_threshold)
                clauses.append(
                    f"(a.attendance_percentage IS NULL OR a.attendance_percentage >= ${len(params)})"
                )

        if search:
            params.append(f"%{search}%")
            clauses.append(
                f"(st.enrollment_no::text ILIKE ${len(params)} "
                f"OR st.first_name ILIKE ${len(params)} "
                f"OR st.last_name ILIKE ${len(params)})"
            )

        return f"WHERE {' AND '.join(clauses)}", params

    async def count_attendance_students(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        attendance_range: Optional[str],
        attendance_status: Optional[str],
        defaulter_status: Optional[str],
        student_status: Optional[str],
        critical_threshold: float,
        attendance_threshold: float,
        excellent_threshold: float,
    ) -> int:
        where, params = self._attendance_students_where(
            faculty_id, semester_no, academic_year, subject_id, search,
            attendance_range, attendance_status, defaulter_status, student_status,
            critical_threshold, attendance_threshold, excellent_threshold,
        )
        query = f"""
            SELECT count(DISTINCT sse.enrollment_record_id)
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            {where}
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *params)

    async def get_attendance_students(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        attendance_range: Optional[str],
        attendance_status: Optional[str],
        defaulter_status: Optional[str],
        student_status: Optional[str],
        critical_threshold: float,
        attendance_threshold: float,
        excellent_threshold: float,
        order_by: str,
        limit: int,
        offset: int,
    ) -> List[Dict[str, Any]]:
        where, params = self._attendance_students_where(
            faculty_id, semester_no, academic_year, subject_id, search,
            attendance_range, attendance_status, defaulter_status, student_status,
            critical_threshold, attendance_threshold, excellent_threshold,
        )
        params.extend([limit, offset])
        query = f"""
            SELECT 
                sse.enrollment_record_id, sse.student_id, sse.enrollment_no, sse.semester_no,
                sse.subject_id, sse.subject_code, sse.subject_name,
                st.first_name, st.last_name,
                a.attendance_percentage, a.attended_classes, a.total_classes,
                a.attendance_status, a.eligibility_status, a.shortage_flag
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            {where}
            ORDER BY {order_by}
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_attendance_export_rows(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        student_ids: Optional[List[str]],
        critical_threshold: float,
        attendance_threshold: float,
        excellent_threshold: float,
    ) -> List[Dict[str, Any]]:
        where, params = self._attendance_students_where(
            faculty_id, semester_no, academic_year, subject_id, search,
            None, None, None, None, critical_threshold, attendance_threshold, excellent_threshold,
        )
        if student_ids:
            params.append(tuple(student_ids))
            where += f" AND sse.enrollment_record_id = ANY(${len(params)})"
        query = f"""
            SELECT 
                sse.enrollment_no, st.first_name, st.last_name, sse.semester_no,
                sse.academic_year, sse.subject_code, sse.subject_name,
                a.attendance_percentage, a.attended_classes, a.total_classes,
                a.attendance_status, a.eligibility_status
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            {where}
            ORDER BY st.first_name ASC, st.last_name ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_performance_export_rows(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        search: Optional[str],
        student_ids: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        where, params = self._performance_students_where(
            faculty_id, semester_no, academic_year, subject_id, search, None, 0.0
        )
        if student_ids:
            params.append(tuple(student_ids))
            where += f" AND sse.enrollment_record_id = ANY(${len(params)})"
        query = f"""
            SELECT 
                sse.enrollment_no, st.first_name, st.last_name, sse.semester_no,
                sse.academic_year, sse.subject_code, sse.subject_name,
                a.attendance_percentage,
                sp.total_marks, sp.grade, sp.result_status
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_subject_performance sp 
                ON sp.enrollment_record_id = sse.enrollment_record_id
            {where}
            ORDER BY st.first_name ASC, st.last_name ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_workload_filter_options(self, faculty_id: str) -> Dict[str, Any]:
        async with self.pool.acquire() as conn:
            types = await conn.fetch(
                """
                SELECT DISTINCT subject_type
                FROM student_subject_enrollment
                WHERE faculty_id = $1 AND enrollment_status = 'Active'
                    AND subject_type IS NOT NULL
                ORDER BY subject_type ASC
                """,
                faculty_id,
            )
        return {"subject_types": [r["subject_type"] for r in types]}

    async def get_workload_department_students(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
    ) -> int:
        query = """
            SELECT COUNT(DISTINCT sse.student_id)
            FROM student_subject_enrollment sse
            JOIN faculty f ON f.faculty_id = $1
            WHERE sse.department_code = f.department_code
                AND sse.enrollment_status = 'Active'
                AND ($2::int IS NULL OR sse.semester_no = $2)
                AND ($3::text IS NULL OR sse.academic_year = $3)
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, faculty_id, semester_no, academic_year)

    async def get_workload_mentee_overlap(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
    ) -> int:
        where, params = self._analytics_where(faculty_id, semester_no, academic_year, subject_id)
        query = f"""
            SELECT COUNT(DISTINCT fsm.student_id)
            FROM faculty_student_map fsm
            JOIN student_subject_enrollment sse ON sse.student_id = fsm.student_id
            {where}
            AND fsm.faculty_id = $1
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *params)

    async def get_workload_subject_breakdown(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        weeks: float,
        subject_type: Optional[str] = None,
        credits_min: Optional[int] = None,
        credits_max: Optional[int] = None,
        hours_min: Optional[float] = None,
        hours_max: Optional[float] = None,
        students_min: Optional[int] = None,
        students_max: Optional[int] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        where, params = self._analytics_where(faculty_id, semester_no, academic_year, subject_id)
        if subject_type is not None:
            params.append(subject_type)
            where += f" AND sse.subject_type = ${len(params)}"
        if search:
            params.append(f"%{search}%")
            where += f" AND (sse.subject_code ILIKE ${len(params)} OR sse.subject_name ILIKE ${len(params)})"
        params.append(weeks)
        weeks_idx = len(params)
        outer = []
        if credits_min is not None:
            params.append(credits_min)
            outer.append(f"credits >= ${len(params)}")
        if credits_max is not None:
            params.append(credits_max)
            outer.append(f"credits <= ${len(params)}")
        if hours_min is not None:
            params.append(hours_min)
            outer.append(f"weekly_hours >= ${len(params)}")
        if hours_max is not None:
            params.append(hours_max)
            outer.append(f"weekly_hours <= ${len(params)}")
        if students_min is not None:
            params.append(students_min)
            outer.append(f"students >= ${len(params)}")
        if students_max is not None:
            params.append(students_max)
            outer.append(f"students <= ${len(params)}")
        outer_sql = f" WHERE {' AND '.join(outer)}" if outer else ""
        query = f"""
            WITH offering AS (
                SELECT
                    sse.subject_id, sse.subject_code, sse.subject_name,
                    sse.semester_no, sse.academic_year,
                    MAX(sse.credits) AS credits,
                    MAX(sse.subject_type) AS subject_type,
                    COUNT(DISTINCT sse.student_id) AS students,
                    MAX(a.total_classes) AS classes,
                    CASE WHEN MAX(a.total_classes) > 0
                        THEN ROUND(MAX(a.total_classes) * 1.0 / ${weeks_idx}, 2)
                    END AS weekly_hours
                FROM student_subject_enrollment sse
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                {where}
                GROUP BY sse.subject_id, sse.subject_code, sse.subject_name,
                    sse.semester_no, sse.academic_year
            )
            SELECT *
            FROM offering{outer_sql}
            ORDER BY offering.subject_name ASC, offering.semester_no ASC, offering.academic_year ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_workload_aggregates(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        weeks: float,
    ) -> Dict[str, Any]:
        where, params = self._analytics_where(faculty_id, semester_no, academic_year, subject_id)
        params.append(weeks)
        weeks_idx = len(params)
        query = f"""
            WITH offering AS (
                SELECT
                    sse.subject_id, sse.semester_no, sse.academic_year,
                    MAX(sse.credits) AS credits,
                    COUNT(DISTINCT sse.student_id) AS students,
                    MAX(a.total_classes) AS classes
                FROM student_subject_enrollment sse
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                {where}
                GROUP BY sse.subject_id, sse.semester_no, sse.academic_year
            ),
            scope_students AS (
                SELECT COUNT(DISTINCT sse.student_id) AS total
                FROM student_subject_enrollment sse
                {where}
            )
            SELECT
                COUNT(*) AS offerings,
                COALESCE(SUM(offering.credits), 0) AS credits,
                COALESCE(SUM(offering.students), 0) AS student_slots,
                COALESCE(SUM(offering.classes), 0) AS classes,
                ROUND(COALESCE(SUM(offering.classes), 0) * 1.0 / ${weeks_idx}, 2) AS weekly_hours,
                (SELECT total FROM scope_students) AS students
            FROM offering
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            if row:
                return dict(row)
            return {
                "offerings": 0, "credits": 0, "student_slots": 0,
                "classes": 0, "weekly_hours": 0.0, "students": 0,
            }

    async def get_workload_trends(
        self,
        faculty_id: str,
        subject_id: Optional[str],
        weeks: float,
    ) -> Dict[str, Any]:
        where, params = self._analytics_where(faculty_id, None, None, subject_id)
        params.append(weeks)
        weeks_idx = len(params)
        term_query = f"""
            WITH offering AS (
                SELECT
                    sse.subject_id, sse.semester_no, sse.academic_year,
                    MAX(sse.credits) AS credits,
                    COUNT(DISTINCT sse.student_id) AS students,
                    MAX(a.total_classes) AS classes
                FROM student_subject_enrollment sse
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                {where}
                GROUP BY sse.subject_id, sse.semester_no, sse.academic_year
            )
            SELECT semester_no, academic_year,
                   COUNT(*) AS offerings,
                   SUM(credits) AS credits,
                   SUM(students) AS student_slots,
                   COALESCE(SUM(classes), 0) AS classes,
                   ROUND(COALESCE(SUM(classes), 0) * 1.0 / ${weeks_idx}, 2) AS weekly_hours
            FROM offering
            GROUP BY semester_no, academic_year
            ORDER BY semester_no ASC, academic_year ASC
        """
        subject_query = f"""
            WITH offering AS (
                SELECT
                    sse.subject_id, sse.subject_code, sse.subject_name,
                    sse.semester_no, sse.academic_year,
                    MAX(a.total_classes) AS classes
                FROM student_subject_enrollment sse
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                {where}
                GROUP BY sse.subject_id, sse.subject_code, sse.subject_name,
                    sse.semester_no, sse.academic_year
            )
            SELECT subject_id, subject_code, subject_name, semester_no, academic_year,
                   ROUND(COALESCE(classes, 0) * 1.0 / ${weeks_idx}, 2) AS weekly_hours
            FROM offering
            ORDER BY semester_no ASC, academic_year ASC, subject_name ASC
        """
        async with self.pool.acquire() as conn:
            terms = await conn.fetch(term_query, *params)
            by_subject = await conn.fetch(subject_query, *params)
        return {
            "terms": [dict(r) for r in terms],
            "by_subject": [dict(r) for r in by_subject],
        }

    async def get_workload_timeline(
        self,
        faculty_id: str,
        weeks: float,
    ) -> List[Dict[str, Any]]:
        params: List[Any] = [faculty_id, weeks]
        query = f"""
            WITH offering AS (
                SELECT
                    sse.subject_id, sse.semester_no, sse.academic_year,
                    MAX(sse.credits) AS credits,
                    COUNT(DISTINCT sse.student_id) AS students,
                    MAX(a.total_classes) AS classes
                FROM student_subject_enrollment sse
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                WHERE sse.faculty_id = $1 AND sse.enrollment_status = 'Active'
                GROUP BY sse.subject_id, sse.semester_no, sse.academic_year
            ),
            term_agg AS (
                SELECT semester_no, academic_year,
                       COUNT(*) AS subjects,
                       SUM(credits) AS credits,
                       SUM(students) AS student_slots,
                       COALESCE(SUM(classes), 0) AS classes,
                       ROUND(COALESCE(SUM(classes), 0) * 1.0 / $2, 2) AS weekly_hours
                FROM offering
                GROUP BY semester_no, academic_year
            ),
            term_students AS (
                SELECT sse.semester_no, sse.academic_year,
                       COUNT(DISTINCT sse.student_id) AS students
                FROM student_subject_enrollment sse
                WHERE sse.faculty_id = $1 AND sse.enrollment_status = 'Active'
                GROUP BY sse.semester_no, sse.academic_year
            )
            SELECT ta.semester_no, ta.academic_year, ta.subjects, ta.credits, ta.classes,
                   ta.weekly_hours, ts.students
            FROM term_agg ta
            JOIN term_students ts ON ts.semester_no = ta.semester_no
                AND ts.academic_year = ta.academic_year
            ORDER BY ta.semester_no ASC, ta.academic_year ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_workload_forecast_source(
        self,
        faculty_id: str,
        weeks: float,
    ) -> List[Dict[str, Any]]:
        params: List[Any] = [faculty_id, weeks]
        query = f"""
            SELECT sse.subject_id, sse.subject_code, sse.subject_name,
                   sse.semester_no, sse.academic_year,
                   MAX(sse.credits) AS credits,
                   COUNT(DISTINCT sse.student_id) AS students,
                   MAX(a.total_classes) AS classes,
                   CASE WHEN MAX(a.total_classes) > 0
                       THEN ROUND(MAX(a.total_classes) * 1.0 / $2, 2)
                   END AS weekly_hours
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
            WHERE sse.faculty_id = $1 AND sse.enrollment_status = 'Active'
            GROUP BY sse.subject_id, sse.subject_code, sse.subject_name,
                sse.semester_no, sse.academic_year
            ORDER BY sse.semester_no ASC, sse.academic_year ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_department_resource_summary(
        self,
        faculty_id: str,
        weeks: float,
        capacity_weekly_hours: float,
    ) -> Dict[str, Any]:
        params: List[Any] = [faculty_id, weeks, capacity_weekly_hours]
        query = f"""
            WITH dept AS (
                SELECT f.department_code, f.department_name
                FROM faculty f
                WHERE f.faculty_id = $1
            ),
            offering AS (
                SELECT sse.subject_id, sse.semester_no, sse.academic_year,
                       MAX(sse.credits) AS credits,
                       COUNT(DISTINCT sse.student_id) AS students,
                       MAX(a.total_classes) AS classes
                FROM student_subject_enrollment sse
                JOIN dept d ON d.department_code = sse.department_code
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                WHERE sse.enrollment_status = 'Active'
                GROUP BY sse.subject_id, sse.semester_no, sse.academic_year
            )
            SELECT
                (SELECT COUNT(*) FROM faculty f
                    JOIN dept d ON d.department_code = f.department_code) AS faculty_count,
                (SELECT COUNT(*) FROM offering) AS total_offerings,
                (SELECT COALESCE(SUM(credits), 0) FROM offering) AS total_credits,
                (SELECT COALESCE(SUM(students), 0) FROM offering) AS total_student_slots,
                (SELECT COALESCE(SUM(classes), 0) FROM offering) AS total_classes,
                (SELECT COUNT(DISTINCT sse.student_id) FROM student_subject_enrollment sse
                    JOIN dept d ON d.department_code = sse.department_code
                    WHERE sse.enrollment_status = 'Active') AS total_students,
                ROUND((SELECT COALESCE(AVG(classes), 0) FROM offering) * 1.0 / $2, 2)
                    AS mean_weekly_hours,
                ROUND((SELECT COALESCE(AVG(classes), 0) FROM offering) * 1.0 / $2 / $3 * 100, 2)
                    AS mean_capacity_utilization
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            if row:
                return dict(row)
            return {
                "faculty_count": 0, "total_offerings": 0, "total_students": 0,
                "total_credits": 0, "total_classes": 0,
                "mean_weekly_hours": 0.0, "mean_capacity_utilization": 0.0,
            }

    def _workload_students_base(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        subject_type: Optional[str],
        weeks: float,
        capacity_weekly_hours: float,
        overload_threshold: float,
        underutilized_threshold: float,
        credit_imbalance_ratio: float,
        student_imbalance_ratio: float,
    ) -> tuple:
        where, params = self._analytics_where(faculty_id, semester_no, academic_year, subject_id)
        if subject_type is not None:
            params.append(subject_type)
            where += f" AND sse.subject_type = ${len(params)}"
        params.extend([
            weeks,
            capacity_weekly_hours * overload_threshold,
            capacity_weekly_hours * underutilized_threshold,
            credit_imbalance_ratio,
            student_imbalance_ratio,
        ])
        weeks_i = len(params) - 4
        overload_cap_i = len(params) - 3
        underutil_cap_i = len(params) - 2
        credit_ratio_i = len(params) - 1
        student_ratio_i = len(params)
        cte = f"""
            WITH offering AS (
                SELECT
                    sse.subject_id, sse.subject_code, sse.subject_name,
                    sse.semester_no, sse.academic_year,
                    MAX(sse.credits) AS credits,
                    COUNT(DISTINCT sse.student_id) AS students,
                    MAX(a.total_classes) AS classes,
                    CASE WHEN MAX(a.total_classes) > 0
                        THEN ROUND(MAX(a.total_classes) * 1.0 / ${weeks_i}, 2)
                    END AS weekly_hours
                FROM student_subject_enrollment sse
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                {where}
                GROUP BY sse.subject_id, sse.subject_code, sse.subject_name,
                    sse.semester_no, sse.academic_year
            ),
            means AS (
                SELECT AVG(offering.credits) AS mean_credits,
                       AVG(offering.students) AS mean_students
                FROM offering
            ),
            offering_status AS (
                SELECT o.subject_id, o.subject_code, o.subject_name, o.semester_no, o.academic_year,
                       o.credits, o.students, o.classes, o.weekly_hours,
                       CASE
                           WHEN o.weekly_hours IS NULL THEN 'No Data'
                           WHEN o.weekly_hours >= ${overload_cap_i} THEN 'Overloaded'
                           WHEN o.weekly_hours < ${underutil_cap_i} THEN 'Underutilized'
                           WHEN o.credits > ${credit_ratio_i} * m.mean_credits THEN 'Credit Imbalance'
                           WHEN o.students > ${student_ratio_i} * m.mean_students THEN 'Student Imbalance'
                           ELSE 'Balanced'
                       END AS workload_status
                FROM offering o, means m
            )
        """
        return cte, params

    async def count_workload_students(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        subject_type: Optional[str],
        credits_min: Optional[int],
        credits_max: Optional[int],
        hours_min: Optional[float],
        hours_max: Optional[float],
        students_min: Optional[int],
        students_max: Optional[int],
        search: Optional[str],
        workload_status: Optional[str],
        weeks: float,
        capacity_weekly_hours: float,
        overload_threshold: float,
        underutilized_threshold: float,
        credit_imbalance_ratio: float,
        student_imbalance_ratio: float,
    ) -> int:
        cte, params = self._workload_students_base(
            faculty_id, semester_no, academic_year, subject_id, subject_type,
            weeks, capacity_weekly_hours, overload_threshold, underutilized_threshold,
            credit_imbalance_ratio, student_imbalance_ratio,
        )
        outer = []
        if search:
            params.append(f"%{search}%")
            outer.append(
                f"(st.enrollment_no::text ILIKE ${len(params)} "
                f"OR st.first_name ILIKE ${len(params)} "
                f"OR st.last_name ILIKE ${len(params)})"
            )
        if credits_min is not None:
            params.append(credits_min)
            outer.append(f"os.credits >= ${len(params)}")
        if credits_max is not None:
            params.append(credits_max)
            outer.append(f"os.credits <= ${len(params)}")
        if hours_min is not None:
            params.append(hours_min)
            outer.append(f"os.weekly_hours >= ${len(params)}")
        if hours_max is not None:
            params.append(hours_max)
            outer.append(f"os.weekly_hours <= ${len(params)}")
        if students_min is not None:
            params.append(students_min)
            outer.append(f"os.students >= ${len(params)}")
        if students_max is not None:
            params.append(students_max)
            outer.append(f"os.students <= ${len(params)}")
        if workload_status:
            params.append(workload_status)
            outer.append(f"os.workload_status = ${len(params)}")
        outer_sql = f" AND {' AND '.join(outer)}" if outer else ""
        query = f"""
            {cte}
            SELECT count(DISTINCT sse.enrollment_record_id)
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            JOIN offering_status os ON os.subject_id = sse.subject_id
                AND os.semester_no = sse.semester_no AND os.academic_year = sse.academic_year
            WHERE sse.faculty_id = $1 AND sse.enrollment_status = 'Active'{outer_sql}
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *params)

    async def get_workload_students(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        subject_id: Optional[str],
        subject_type: Optional[str],
        credits_min: Optional[int],
        credits_max: Optional[int],
        hours_min: Optional[float],
        hours_max: Optional[float],
        students_min: Optional[int],
        students_max: Optional[int],
        search: Optional[str],
        workload_status: Optional[str],
        weeks: float,
        capacity_weekly_hours: float,
        overload_threshold: float,
        underutilized_threshold: float,
        credit_imbalance_ratio: float,
        student_imbalance_ratio: float,
        order_by: str,
        limit: int,
        offset: int,
    ) -> List[Dict[str, Any]]:
        cte, params = self._workload_students_base(
            faculty_id, semester_no, academic_year, subject_id, subject_type,
            weeks, capacity_weekly_hours, overload_threshold, underutilized_threshold,
            credit_imbalance_ratio, student_imbalance_ratio,
        )
        outer = []
        if search:
            params.append(f"%{search}%")
            outer.append(
                f"(st.enrollment_no::text ILIKE ${len(params)} "
                f"OR st.first_name ILIKE ${len(params)} "
                f"OR st.last_name ILIKE ${len(params)})"
            )
        if credits_min is not None:
            params.append(credits_min)
            outer.append(f"os.credits >= ${len(params)}")
        if credits_max is not None:
            params.append(credits_max)
            outer.append(f"os.credits <= ${len(params)}")
        if hours_min is not None:
            params.append(hours_min)
            outer.append(f"os.weekly_hours >= ${len(params)}")
        if hours_max is not None:
            params.append(hours_max)
            outer.append(f"os.weekly_hours <= ${len(params)}")
        if students_min is not None:
            params.append(students_min)
            outer.append(f"os.students >= ${len(params)}")
        if students_max is not None:
            params.append(students_max)
            outer.append(f"os.students <= ${len(params)}")
        if workload_status:
            params.append(workload_status)
            outer.append(f"os.workload_status = ${len(params)}")
        outer_sql = f" AND {' AND '.join(outer)}" if outer else ""
        params.extend([limit, offset])
        query = f"""
            {cte}
            SELECT
                sse.enrollment_record_id, sse.student_id, sse.enrollment_no, sse.semester_no,
                os.academic_year, sse.subject_id, sse.subject_code, sse.subject_name,
                st.first_name, st.last_name,
                sse.credits, os.classes AS classes_conducted, os.weekly_hours, os.workload_status
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            JOIN offering_status os ON os.subject_id = sse.subject_id
                AND os.semester_no = sse.semester_no AND os.academic_year = sse.academic_year
            WHERE sse.faculty_id = $1 AND sse.enrollment_status = 'Active'{outer_sql}
            ORDER BY {order_by}
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    # =========================================================================
    # Marks Entry (plan 14)
    # =========================================================================

    def _jsonb(self, value: Any) -> Optional[str]:
        """Encode a scalar as a jsonb-typed parameter (None -> SQL NULL)."""
        if value is None:
            return None
        return json.dumps(value)

    async def get_subject_marks_grid(
        self,
        faculty_id: str,
        subject_id: str,
        semester_no: int,
        academic_year: str,
        order_by: str,
        limit: int,
        offset: int,
    ) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            scope = await conn.fetchval(
                """
                SELECT 1 FROM student_subject_enrollment
                WHERE faculty_id = $1 AND subject_id = $2 AND semester_no = $3
                    AND academic_year = $4 AND enrollment_status = 'Active'
                LIMIT 1
                """,
                faculty_id, subject_id, semester_no, academic_year,
            )
            if not scope:
                return None

            meta = await conn.fetchrow(
                """
                SELECT subject_id, subject_code, subject_name, credits, semester_no,
                    assessment_type, department_name
                FROM subjects
                WHERE subject_id = $1
                """,
                subject_id,
            )

            total = await conn.fetchval(
                """
                SELECT count(*) FROM student_subject_enrollment
                WHERE faculty_id = $1 AND subject_id = $2 AND semester_no = $3
                    AND academic_year = $4 AND enrollment_status = 'Active'
                """,
                faculty_id, subject_id, semester_no, academic_year,
            )

            rows = await conn.fetch(
                f"""
                SELECT sse.enrollment_record_id, sse.student_id, sse.enrollment_no,
                    st.first_name, st.last_name,
                    sp.internal_marks, sp.mid_sem_marks, sp.end_sem_marks,
                    sp.total_marks, sp.percentage, sp.grade, sp.grade_point,
                    sp.result_status, sp.performance_category, sp.remarks
                FROM student_subject_enrollment sse
                JOIN students st ON st.student_id = sse.student_id
                LEFT JOIN student_subject_performance sp
                    ON sp.enrollment_record_id = sse.enrollment_record_id
                WHERE sse.faculty_id = $1 AND sse.subject_id = $2
                    AND sse.semester_no = $3 AND sse.academic_year = $4
                    AND sse.enrollment_status = 'Active'
                ORDER BY {order_by}
                LIMIT ${5} OFFSET ${6}
                """,
                faculty_id, subject_id, semester_no, academic_year, limit, offset,
            )

        return {
            "meta": dict(meta) if meta else None,
            "total": int(total) if total else 0,
            "rows": [dict(r) for r in rows],
        }

    async def upsert_subject_marks(
        self,
        faculty_id: str,
        subject_id: str,
        semester_no: int,
        academic_year: str,
        entries: List[Dict[str, Any]],
        changed_by: str,
        derive_marks: Callable[[Optional[int], Optional[int], Optional[int]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        # Remarks is a derived field (like total/percentage/grade): it is never
        # accepted from the client. Only the three raw marks are editable.
        editable = ["internal_marks", "mid_sem_marks", "end_sem_marks"]
        results: List[Dict[str, Any]] = []
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                subject_name = await conn.fetchval(
                    "SELECT subject_name FROM subjects WHERE subject_id = $1",
                    subject_id,
                )
                enrolled = await conn.fetch(
                    """
                    SELECT enrollment_record_id, student_id, enrollment_no
                    FROM student_subject_enrollment
                    WHERE faculty_id = $1 AND subject_id = $2 AND semester_no = $3
                        AND academic_year = $4 AND enrollment_status = 'Active'
                    """,
                    faculty_id, subject_id, semester_no, academic_year,
                )
                enrolled_by_enr = {r["enrollment_record_id"]: r for r in enrolled}
                enrolled_ids = [r["enrollment_record_id"] for r in enrolled]
                if not enrolled_ids:
                    raise FacultyScopeError("No authorized enrollment for this subject/term")

                # MD-05: student display names for faculty-facing fail alerts.
                student_ids = [r["student_id"] for r in enrolled]
                name_by_sid: Dict[str, str] = {}
                if student_ids:
                    name_rows = await conn.fetch(
                        """
                        SELECT student_id, first_name, last_name
                        FROM students WHERE student_id = ANY($1::text[])
                        """,
                        student_ids,
                    )
                    name_by_sid = {
                        r["student_id"]: (r["first_name"] + " " + r["last_name"]).strip()
                        for r in name_rows
                    }

                existing_rows = await conn.fetch(
                    """
                    SELECT * FROM student_subject_performance
                    WHERE enrollment_record_id = ANY($1::text[])
                    FOR UPDATE
                    """,
                    enrolled_ids,
                )
                existing_by_enr = {r["enrollment_record_id"]: r for r in existing_rows}

                next_perf_id = await conn.fetchval(
                    """
                    SELECT max(substring(performance_id from 4)::bigint)
                    FROM student_subject_performance
                    """
                )

                # MD-05 notification events collected while auditing; materialized
                # after the loop, inside the same transaction (event_id dedups).
                publish_events: List[Dict[str, Any]] = []
                field_events: List[Dict[str, Any]] = []

                for entry in entries:
                    enr = entry["enrollment_record_id"]
                    scope_row = enrolled_by_enr.get(enr)
                    if scope_row is None:
                        raise FacultyScopeError(
                            f"enrollment {enr} is not in the authorized Active scope"
                        )
                    existing = existing_by_enr.get(enr)
                    operation = "insert" if existing is None else "update"

                    merged: Dict[str, Any] = {}
                    changed: List[str] = []
                    for field in editable:
                        old_val = existing[field] if existing is not None else None
                        if field not in entry:
                            # Field omitted from the request -> leave DB value untouched.
                            merged[field] = old_val
                            continue
                        new_val = entry[field]
                        if new_val == old_val:
                            merged[field] = old_val
                        else:
                            # Includes explicit null (clear) -> null differs from a
                            # populated old value, so the field is written as NULL and
                            # the change is recorded for the audit log.
                            merged[field] = new_val
                            changed.append(field)

                    if existing is not None and not changed:
                        results.append({
                            "enrollment_record_id": enr,
                            "student_id": scope_row["student_id"],
                            "operation": "unchanged",
                            "fields_changed": [],
                        })
                        continue

                    derived = derive_marks(
                        merged["internal_marks"], merged["mid_sem_marks"], merged["end_sem_marks"]
                    )

                    if existing is None:
                        next_perf_id = (next_perf_id or 0) + 1
                        performance_id = f"PER{next_perf_id:06d}"
                        await conn.execute(
                            """
                            INSERT INTO student_subject_performance (
                                performance_id, enrollment_record_id, enrollment_no,
                                student_id, subject_id, semester_no,
                                internal_marks, mid_sem_marks, end_sem_marks,
                                total_marks, percentage, grade, grade_point,
                                result_status, attempt_number, performance_category,
                                remarks, updated_at, updated_by
                            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,1,$15,$16,now(),$17)
                            """,
                            performance_id, enr, scope_row["enrollment_no"],
                            scope_row["student_id"], subject_id, semester_no,
                            merged["internal_marks"], merged["mid_sem_marks"], merged["end_sem_marks"],
                            derived["total_marks"], derived["percentage"], derived["grade"],
                            derived["grade_point"], derived["result_status"],
                            derived["performance_category"], derived["remarks"], changed_by,
                        )
                        publish_fields: List[Dict[str, Any]] = []
                        first_change_id = None
                        for field in editable:
                            new_val = merged[field]
                            if new_val is None:
                                continue
                            change_id = await conn.fetchval(
                                """
                                INSERT INTO performance_change_log (
                                    performance_id, enrollment_record_id, student_id, subject_id,
                                    field_name, old_value, new_value, operation_type,
                                    changed_by, changed_at
                                ) VALUES ($1,$2,$3,$4,$5,NULL,$6,$7,$8,now())
                                RETURNING change_id
                                """,
                                performance_id, enr, scope_row["student_id"], subject_id,
                                field, self._jsonb(new_val), operation, changed_by,
                            )
                            if first_change_id is None:
                                first_change_id = change_id
                            publish_fields.append({"name": field, "value": new_val})
                        if publish_fields:
                            publish_events.append({
                                "kind": "publish",
                                "student_id": scope_row["student_id"],
                                "student_name": name_by_sid.get(scope_row["student_id"])
                                or scope_row["student_id"],
                                "subject_id": subject_id,
                                "subject_name": subject_name,
                                "change_id": first_change_id,
                                "fields": publish_fields,
                                "result_status": derived["result_status"],
                                "percentage": derived["percentage"],
                            })
                        results.append({
                            "enrollment_record_id": enr,
                            "student_id": scope_row["student_id"],
                            "operation": "insert",
                            "fields_changed": [f for f in editable if merged[f] is not None],
                        })
                        continue

                    await conn.execute(
                        """
                        UPDATE student_subject_performance
                        SET internal_marks = $1, mid_sem_marks = $2, end_sem_marks = $3,
                            total_marks = $4, percentage = $5, grade = $6, grade_point = $7,
                            result_status = $8, performance_category = $9, remarks = $10,
                            updated_at = now(), updated_by = $11
                        WHERE enrollment_record_id = $12
                        """,
                        merged["internal_marks"], merged["mid_sem_marks"], merged["end_sem_marks"],
                        derived["total_marks"], derived["percentage"], derived["grade"],
                        derived["grade_point"], derived["result_status"],
                        derived["performance_category"], derived["remarks"], changed_by, enr,
                    )
                    for field in changed:
                        change_id = await conn.fetchval(
                            """
                            INSERT INTO performance_change_log (
                                performance_id, enrollment_record_id, student_id, subject_id,
                                field_name, old_value, new_value, operation_type,
                                changed_by, changed_at
                            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,now())
                            RETURNING change_id
                            """,
                            existing["performance_id"], enr, scope_row["student_id"], subject_id,
                            field, self._jsonb(existing[field]), self._jsonb(merged[field]),
                            "update", changed_by,
                        )
                        field_events.append({
                            "kind": "field",
                            "student_id": scope_row["student_id"],
                            "student_name": name_by_sid.get(scope_row["student_id"])
                            or scope_row["student_id"],
                            "subject_id": subject_id,
                            "subject_name": subject_name,
                            "field_name": field,
                            "old_value": existing[field],
                            "new_value": merged[field],
                            "change_id": change_id,
                            "result_status": derived["result_status"],
                            "percentage": derived["percentage"],
                        })
                    results.append({
                        "enrollment_record_id": enr,
                        "student_id": scope_row["student_id"],
                        "operation": "updated",
                        "fields_changed": changed,
                    })

                if publish_events or field_events:
                    events = publish_events + field_events
                    notifications = build_performance_notifications(events)
                    notifications += build_performance_change_notifications(events)
                    notifications += build_faculty_performance_notifications(events, faculty_id)
                    if notifications:
                        await insert_student_messages(conn, notifications)

        summary = {
            "saved": sum(1 for r in results if r["operation"] in ("insert", "updated")),
            "inserted": sum(1 for r in results if r["operation"] == "insert"),
            "updated": sum(1 for r in results if r["operation"] == "updated"),
            "unchanged": sum(1 for r in results if r["operation"] == "unchanged"),
            "rejected": 0,
        }
        return {"results": results, "summary": summary}

    async def get_marks_change_log(
        self,
        subject_id: str,
        page: int,
        page_size: int,
    ) -> Dict[str, Any]:
        async with self.pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT count(*) FROM performance_change_log WHERE subject_id = $1",
                subject_id,
            )
            rows = await conn.fetch(
                """
                SELECT cl.change_id, cl.performance_id, cl.enrollment_record_id,
                    cl.student_id, cl.subject_id, cl.field_name, cl.old_value,
                    cl.new_value, cl.operation_type, cl.changed_by, cl.changed_at,
                    st.first_name, st.last_name
                FROM performance_change_log cl
                LEFT JOIN students st ON st.student_id = cl.student_id
                WHERE cl.subject_id = $1
                ORDER BY cl.changed_at DESC, cl.change_id DESC
                LIMIT $2 OFFSET $3
                """,
                subject_id, page_size, (page - 1) * page_size,
            )
        return {
            "total": int(total) if total else 0,
            "items": [dict(r) for r in rows],
        }

    # =========================================================================
    # Attendance Entry (plan 15)
    # =========================================================================

    async def get_attendance_meta(
        self,
        faculty_id: str,
        subject_id: str,
        semester_no: int,
        academic_year: str,
    ) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            scope = await conn.fetchval(
                """
                SELECT 1 FROM student_subject_enrollment
                WHERE faculty_id = $1 AND subject_id = $2 AND semester_no = $3
                    AND academic_year = $4 AND enrollment_status = 'Active'
                LIMIT 1
                """,
                faculty_id, subject_id, semester_no, academic_year,
            )
            if not scope:
                return None

            meta = await conn.fetchrow(
                """
                SELECT subject_id, subject_code, subject_name, semester_no,
                    department_code, department_name
                FROM subjects
                WHERE subject_id = $1
                """,
                subject_id,
            )

            sessions = await conn.fetch(
                """
                SELECT day_name, slot_no, start_time, end_time, subject_id,
                    subject_name, faculty_id, lecture_type
                FROM weekly_timetable_07
                WHERE semester_no = $1 AND subject_id = $2 AND faculty_id = $3
                ORDER BY day_name, start_time
                """,
                semester_no, subject_id, faculty_id,
            )
            recorded_lectures = await conn.fetchval(
                """
                SELECT COALESCE(max(lecture_number), 0)
                FROM daily_attendance_07 WHERE subject_id = $1
                """,
                subject_id,
            )

            students = await conn.fetch(
                """
                SELECT sse.enrollment_record_id, sse.student_id, sse.enrollment_no,
                    st.first_name, st.last_name,
                    a.attendance_percentage, a.attendance_status,
                    a.eligibility_status, a.shortage_flag
                FROM student_subject_enrollment sse
                JOIN students st ON st.student_id = sse.student_id
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                WHERE sse.faculty_id = $1 AND sse.subject_id = $2
                    AND sse.semester_no = $3 AND sse.academic_year = $4
                    AND sse.enrollment_status = 'Active'
                ORDER BY sse.enrollment_no ASC
                """,
                faculty_id, subject_id, semester_no, academic_year,
            )

        return {
            "meta": dict(meta) if meta else None,
            "sessions": [dict(r) for r in sessions],
            "recorded_lectures": int(recorded_lectures or 0),
            "students": [dict(r) for r in students],
        }

    async def get_lecture_attendance(
        self,
        faculty_id: str,
        subject_id: str,
        semester_no: int,
        academic_year: str,
        lecture_date: Any,
        slot_no: int,
    ) -> Optional[Dict[str, Any]]:
        day_name = lecture_date.strftime("%A")
        async with self.pool.acquire() as conn:
            scope = await conn.fetchval(
                """
                SELECT 1 FROM student_subject_enrollment
                WHERE faculty_id = $1 AND subject_id = $2 AND semester_no = $3
                    AND academic_year = $4 AND enrollment_status = 'Active'
                LIMIT 1
                """,
                faculty_id, subject_id, semester_no, academic_year,
            )
            if not scope:
                return None

            timetable = await conn.fetchrow(
                """
                SELECT wt.day_name, wt.slot_no, wt.start_time, wt.end_time,
                    wt.subject_id, wt.subject_name, wt.faculty_id, wt.lecture_type,
                    wt.department_code, wt.semester_no, wt.academic_year, s.subject_code
                FROM weekly_timetable_07 wt
                JOIN subjects s ON s.subject_id = wt.subject_id
                WHERE wt.semester_no = $1 AND wt.subject_id = $2 AND wt.faculty_id = $3
                    AND wt.day_name = $4 AND wt.slot_no = $5
                ORDER BY wt.academic_year DESC
                LIMIT 1
                """,
                semester_no, subject_id, faculty_id, day_name, slot_no,
            )
            if not timetable:
                raise FacultyScopeError("No timetable session matches the requested lecture")

            lecture_number = await self._resolve_lecture_number(
                conn, subject_id, lecture_date, day_name, slot_no, semester_no
            )
            recorded = lecture_number is not None
            if not recorded:
                lecture_number = await conn.fetchval(
                    """
                    SELECT COALESCE(max(lecture_number), 0) + 1
                    FROM daily_attendance_07 WHERE subject_id = $1
                    """,
                    subject_id,
                )

            lecture_number = int(lecture_number or 1)
            daily = {}
            if recorded:
                rows = await conn.fetch(
                    """
                    SELECT student_id, attendance_id, attendance_status
                    FROM daily_attendance_07
                    WHERE subject_id = $1 AND lecture_date = $2 AND lecture_number = $3
                    """,
                    subject_id, lecture_date, lecture_number,
                )
                daily = {r["student_id"]: r for r in rows}

            students = await conn.fetch(
                """
                SELECT sse.enrollment_record_id, sse.student_id, sse.enrollment_no,
                    st.first_name, st.last_name,
                    a.attendance_percentage, a.attendance_status AS band,
                    a.eligibility_status, a.shortage_flag
                FROM student_subject_enrollment sse
                JOIN students st ON st.student_id = sse.student_id
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                WHERE sse.faculty_id = $1 AND sse.subject_id = $2
                    AND sse.semester_no = $3 AND sse.academic_year = $4
                    AND sse.enrollment_status = 'Active'
                ORDER BY sse.enrollment_no ASC
                """,
                faculty_id, subject_id, semester_no, academic_year,
            )

        return {
            "timetable": dict(timetable),
            "lecture_number": lecture_number,
            "recorded": recorded,
            "daily": daily,
            "students": [dict(r) for r in students],
        }

    async def _resolve_lecture_number(
        self,
        conn: asyncpg.Connection,
        subject_id: str,
        lecture_date: Any,
        day_name: str,
        slot_no: int,
        semester_no: int,
    ) -> Optional[int]:
        rows = await conn.fetch(
            """
            SELECT DISTINCT lecture_number
            FROM daily_attendance_07
            WHERE subject_id = $1 AND lecture_date = $2
            ORDER BY lecture_number
            """,
            subject_id, lecture_date,
        )
        if not rows:
            return None
        numbers = [int(r["lecture_number"]) for r in rows]
        if len(numbers) == 1:
            return numbers[0]
        slot_order = await conn.fetch(
            """
            SELECT slot_no FROM weekly_timetable_07
            WHERE subject_id = $1 AND day_name = $2 AND semester_no = $3
            ORDER BY start_time
            """,
            subject_id, day_name, semester_no,
        )
        slots = [int(s["slot_no"]) for s in slot_order]
        idx = slots.index(slot_no) if slot_no in slots else 0
        return numbers[idx] if idx < len(numbers) else numbers[0]

    async def upsert_lecture_attendance(
        self,
        faculty_id: str,
        subject_id: str,
        semester_no: int,
        academic_year: str,
        lecture_date: Any,
        slot_no: int,
        student_statuses: Dict[str, str],
        allow_correction: bool,
        changed_by: str,
        aggregate_fields: Callable[[Optional[float]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        day_name = lecture_date.strftime("%A")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                timetable = await conn.fetchrow(
                    """
                    SELECT wt.day_name, wt.slot_no, wt.start_time, wt.end_time,
                        wt.subject_id, wt.subject_name, wt.faculty_id, wt.lecture_type,
                        wt.department_code, wt.semester_no, wt.academic_year, s.subject_code
                    FROM weekly_timetable_07 wt
                    JOIN subjects s ON s.subject_id = wt.subject_id
                    WHERE wt.semester_no = $1 AND wt.subject_id = $2 AND wt.faculty_id = $3
                        AND wt.day_name = $4 AND wt.slot_no = $5
                    ORDER BY wt.academic_year DESC
                    LIMIT 1
                    """,
                    semester_no, subject_id, faculty_id, day_name, slot_no,
                )
                if not timetable:
                    raise FacultyScopeError("No timetable session matches the requested lecture")

                enrolled = await conn.fetch(
                    """
                    SELECT enrollment_record_id, student_id, enrollment_no
                    FROM student_subject_enrollment
                    WHERE faculty_id = $1 AND subject_id = $2 AND semester_no = $3
                        AND academic_year = $4 AND enrollment_status = 'Active'
                    """,
                    faculty_id, subject_id, semester_no, academic_year,
                )
                enrolled_by_sid = {r["student_id"]: r for r in enrolled}

                lecture_number = await self._resolve_lecture_number(
                    conn, subject_id, lecture_date, day_name, slot_no, semester_no
                )
                recorded = lecture_number is not None
                if not recorded:
                    lecture_number = await conn.fetchval(
                        """
                        SELECT COALESCE(max(lecture_number), 0) + 1
                        FROM daily_attendance_07 WHERE subject_id = $1
                        """,
                        subject_id,
                    )
                lecture_number = int(lecture_number or 1)

                existing_rows = await conn.fetch(
                    """
                    SELECT attendance_id, student_id, attendance_status
                    FROM daily_attendance_07
                    WHERE subject_id = $1 AND lecture_date = $2 AND lecture_number = $3
                    FOR UPDATE
                    """,
                    subject_id, lecture_date, lecture_number,
                )
                existing_by_sid = {r["student_id"]: r for r in existing_rows}
                already_recorded = bool(existing_rows)

                if already_recorded and not allow_correction:
                    raise DuplicateLectureError(
                        f"Lecture {lecture_number} on {lecture_date} is already recorded"
                    )

                if already_recorded:
                    unknown = [sid for sid in student_statuses if sid not in enrolled_by_sid]
                    if unknown:
                        raise FacultyScopeError(
                            f"Student(s) {', '.join(unknown)} are not in the authorized Active scope"
                        )
                    process_ids = [sid for sid in student_statuses if sid in enrolled_by_sid]
                else:
                    process_ids = list(enrolled_by_sid.keys())

                next_id = await conn.fetchval(
                    "SELECT COALESCE(max(attendance_id), 0) FROM daily_attendance_07"
                )

                results: List[Dict[str, Any]] = []
                summary = {"inserted": 0, "updated": 0, "unchanged": 0}
                for sid in process_ids:
                    status = student_statuses.get(sid, "A")
                    existing = existing_by_sid.get(sid)
                    if existing is not None:
                        if existing["attendance_status"] == status:
                            operation = "unchanged"
                            summary["unchanged"] += 1
                        else:
                            await conn.execute(
                                """
                                UPDATE daily_attendance_07
                                SET attendance_status = $1, updated_at = now()
                                WHERE attendance_id = $2
                                """,
                                status, existing["attendance_id"],
                            )
                            operation = "updated"
                            summary["updated"] += 1
                        results.append({
                            "student_id": sid,
                            "enrollment_no": enrolled_by_sid[sid]["enrollment_no"],
                            "operation": operation,
                            "attendance_status": status,
                            "audit": (operation == "updated", existing["attendance_status"], status),
                        })
                    else:
                        next_id = int(next_id or 0) + 1
                        await conn.execute(
                            """
                            INSERT INTO daily_attendance_07 (
                                attendance_id, student_id, enrollment_no, subject_id,
                                subject_name, faculty_id, lecture_date, lecture_number,
                                day_name, department_code, semester_no, academic_year,
                                attendance_status, created_at, updated_at
                            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,now(),now())
                            """,
                            next_id, sid, enrolled_by_sid[sid]["enrollment_no"],
                            subject_id, timetable["subject_name"], faculty_id,
                            lecture_date, lecture_number, day_name,
                            timetable["department_code"], semester_no,
                            timetable["academic_year"], status,
                        )
                        summary["inserted"] += 1
                        results.append({
                            "student_id": sid,
                            "enrollment_no": enrolled_by_sid[sid]["enrollment_no"],
                            "operation": "insert",
                            "attendance_status": status,
                            "audit": (True, None, status),
                        })

                affected_ids = process_ids
                prev_by_sid = await self._capture_prev_attendance(
                    conn, subject_id, semester_no, affected_ids
                )
                agg_by_sid, sem_by_sid, overall_by_sid = await self._recompute_attendance(
                    conn, subject_id, semester_no, academic_year,
                    affected_ids, enrolled_by_sid, aggregate_fields,
                )

                # MD-05: attendance warnings + eligibility flips (same transaction).
                await self._insert_attendance_notifications(
                    conn,
                    prev_by_sid,
                    agg_by_sid,
                    subject_id,
                    timetable["subject_name"],
                    semester_no,
                    affected_ids,
                    faculty_id,
                )

                # Audit appends (inside the same transaction).
                for res in results:
                    audit = res.pop("audit", None)
                    if audit is None or not audit[0]:
                        continue
                    _, old_status, new_status = audit
                    await conn.execute(
                        """
                        INSERT INTO attendance_change_log (
                            lecture_date, slot_no, student_id, subject_id,
                            field_name, old_value, new_value, operation_type,
                            changed_by, changed_at
                        ) VALUES ($1,$2,$3,$4,'attendance_status',$5,$6,$7,$8,now())
                        """,
                        lecture_date, slot_no, res["student_id"], subject_id,
                        self._jsonb(old_status), self._jsonb(new_status),
                        res["operation"], changed_by,
                    )

        for res in results:
            sid = res["student_id"]
            agg = agg_by_sid.get(sid, {})
            res["attendance_percentage"] = agg.get("attendance_percentage")
            res["attendance_status_band"] = agg.get("attendance_status")
            res["eligibility_status"] = agg.get("eligibility_status")
            res["shortage_flag"] = agg.get("shortage_flag")
            res["semester_attendance_percentage"] = sem_by_sid.get(sid)
            res["overall_attendance_percentage"] = overall_by_sid.get(sid)

        sem_means = [float(v) for v in sem_by_sid.values() if v is not None]
        overall_means = [float(v) for v in overall_by_sid.values() if v is not None]
        return {
            "lecture_number": lecture_number,
            "recorded": already_recorded or summary["inserted"] > 0,
            "results": results,
            "summary": summary,
            "semester_attendance_percentage": round(sum(sem_means) / len(sem_means), 2) if sem_means else None,
            "overall_attendance_percentage": round(sum(overall_means) / len(overall_means), 2) if overall_means else None,
        }

    async def _capture_prev_attendance(
        self,
        conn: asyncpg.Connection,
        subject_id: str,
        semester_no: int,
        student_ids: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Pre-write aggregate attendance state (baseline for MD-05 crossings)."""
        if not student_ids:
            return {}
        rows = await conn.fetch(
            """
            SELECT a.student_id, a.attendance_percentage, a.eligibility_status
            FROM attendance a
            JOIN student_subject_enrollment e
                ON e.enrollment_record_id = a.enrollment_record_id
            WHERE e.subject_id = $1 AND e.semester_no = $2
                AND e.student_id = ANY($3::text[])
            """,
            subject_id, semester_no, student_ids,
        )
        return {
            r["student_id"]: {
                "attendance_percentage": r["attendance_percentage"],
                "eligibility_status": r["eligibility_status"],
            }
            for r in rows
        }

    async def _insert_attendance_notifications(
        self,
        conn: asyncpg.Connection,
        prev_by_sid: Dict[str, Dict[str, Any]],
        agg_by_sid: Dict[str, Dict[str, Any]],
        subject_id: str,
        subject_name: str,
        semester_no: int,
        affected_ids: List[str],
        faculty_id: str,
    ) -> None:
        """Materialize attendance + eligibility notifications.

        Students receive ATTENDANCE_WARNING / ELIGIBILITY_WARNING rows; the
        owning faculty member receives STUDENT_ATTENDANCE_WARNING /
        STUDENT_ELIGIBILITY_WARNING rows for the same events. Only students
        with a pre-existing aggregate baseline are compared, so the first-ever
        lecture recording never floods the inbox. A recovery above target then
        a re-crossing is still deduplicated because the direction is part of
        the event identity.
        """
        names: Dict[str, str] = {}
        if affected_ids:
            name_rows = await conn.fetch(
                """
                SELECT student_id, first_name, last_name
                FROM students WHERE student_id = ANY($1::text[])
                """,
                affected_ids,
            )
            names = {
                r["student_id"]: (r["first_name"] + " " + r["last_name"]).strip()
                for r in name_rows
            }
        crossings: List[Dict[str, Any]] = []
        flips: List[Dict[str, Any]] = []
        for sid in affected_ids:
            prev = prev_by_sid.get(sid)
            new = agg_by_sid.get(sid)
            if not prev or not new:
                continue
            old_pct = prev.get("attendance_percentage")
            new_pct = new.get("attendance_percentage")
            if old_pct is not None and new_pct is not None:
                if (
                    old_pct >= settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD
                    and new_pct < settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD
                ):
                    crossings.append({
                        "student_id": sid,
                        "student_name": names.get(sid) or sid,
                        "subject_id": subject_id,
                        "subject_name": subject_name,
                        "semester_no": semester_no,
                        "old_pct": old_pct,
                        "new_pct": new_pct,
                        "direction": "below-critical",
                    })
                elif (
                    old_pct >= settings.FACULTY_ATTENDANCE_THRESHOLD
                    and new_pct < settings.FACULTY_ATTENDANCE_THRESHOLD
                ):
                    crossings.append({
                        "student_id": sid,
                        "student_name": names.get(sid) or sid,
                        "subject_id": subject_id,
                        "subject_name": subject_name,
                        "semester_no": semester_no,
                        "old_pct": old_pct,
                        "new_pct": new_pct,
                        "direction": "below-target",
                    })
            if (
                prev.get("eligibility_status") != "Not Eligible"
                and new.get("eligibility_status") == "Not Eligible"
            ):
                flips.append({
                    "student_id": sid,
                    "student_name": names.get(sid) or sid,
                    "subject_id": subject_id,
                    "subject_name": subject_name,
                    "semester_no": semester_no,
                })
        notifications = build_attendance_warnings(
            crossings,
            below_target_threshold=settings.FACULTY_ATTENDANCE_THRESHOLD,
            critical_threshold=settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD,
        )
        notifications += build_eligibility_warnings(flips)
        notifications += build_faculty_attendance_warnings(
            crossings,
            flips,
            faculty_id,
            below_target_threshold=settings.FACULTY_ATTENDANCE_THRESHOLD,
            critical_threshold=settings.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD,
        )
        if notifications:
            await insert_student_messages(conn, notifications)

    async def _recompute_attendance(
        self,
        conn: asyncpg.Connection,
        subject_id: str,
        semester_no: int,
        academic_year: str,
        student_ids: List[str],
        enrolled_by_sid: Dict[str, Dict[str, Any]],
        aggregate_fields: Callable[[Optional[float]], Dict[str, Any]],
    ) -> tuple:
        """Recompute aggregate attendance + semester/overall summaries (plan 15 §6.2-6.4)."""
        if not student_ids:
            return {}, {}, {}

        agg_rows = await conn.fetch(
            """
            SELECT student_id,
                count(DISTINCT (lecture_date, lecture_number)) AS total_classes,
                count(*) FILTER (WHERE attendance_status = 'P') AS attended_classes
            FROM daily_attendance_07
            WHERE subject_id = $1 AND semester_no = $2
                AND student_id = ANY($3::text[])
            GROUP BY student_id
            """,
            subject_id, semester_no, student_ids,
        )
        agg_by_sid = {}
        for ar in agg_rows:
            total = int(ar["total_classes"])
            attended = int(ar["attended_classes"])
            pct = round(attended / total * 100, 2) if total else None
            bands = aggregate_fields(pct)
            agg_by_sid[ar["student_id"]] = {
                "total_classes": total,
                "attended_classes": attended,
                "attendance_percentage": pct,
                "attendance_status": bands["attendance_status"],
                "eligibility_status": bands["eligibility_status"],
                "shortage_flag": bands["shortage_flag"],
            }

        for sid in student_ids:
            er = enrolled_by_sid[sid]
            agg = agg_by_sid.get(sid)
            if agg is None:
                continue
            existing_agg = await conn.fetchrow(
                "SELECT 1 FROM attendance WHERE enrollment_record_id = $1",
                er["enrollment_record_id"],
            )
            if existing_agg:
                await conn.execute(
                    """
                    UPDATE attendance
                    SET total_classes = $1, attended_classes = $2,
                        attendance_percentage = $3, attendance_status = $4,
                        eligibility_status = $5, shortage_flag = $6
                    WHERE enrollment_record_id = $7
                    """,
                    agg["total_classes"], agg["attended_classes"],
                    agg["attendance_percentage"], agg["attendance_status"],
                    agg["eligibility_status"], agg["shortage_flag"],
                    er["enrollment_record_id"],
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO attendance (
                        attendance_id, enrollment_record_id, enrollment_no,
                        student_id, subject_id, semester_no, total_classes,
                        attended_classes, attendance_percentage,
                        attendance_status, eligibility_status, shortage_flag
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                    """,
                    "ATT" + er["enrollment_record_id"][3:],
                    er["enrollment_record_id"], er["enrollment_no"],
                    sid, subject_id, semester_no,
                    agg["total_classes"], agg["attended_classes"],
                    agg["attendance_percentage"], agg["attendance_status"],
                    agg["eligibility_status"], agg["shortage_flag"],
                )

        sem_rows = await conn.fetch(
            """
            SELECT e.student_id, round(avg(a.attendance_percentage)::numeric, 2) AS mean
            FROM attendance a
            JOIN student_subject_enrollment e ON e.enrollment_record_id = a.enrollment_record_id
            WHERE e.student_id = ANY($1::text[]) AND e.semester_no = $2
            GROUP BY e.student_id
            """,
            student_ids, semester_no,
        )
        overall_rows = await conn.fetch(
            """
            SELECT student_id, round(avg(attendance_percentage)::numeric, 2) AS mean
            FROM attendance
            WHERE student_id = ANY($1::text[])
            GROUP BY student_id
            """,
            student_ids,
        )
        sem_by_sid = {r["student_id"]: r["mean"] for r in sem_rows}
        overall_by_sid = {r["student_id"]: r["mean"] for r in overall_rows}

        if sem_rows:
            await conn.execute(
                """
                UPDATE student_semester_summary s
                SET semester_attendance_percentage = agg.mean
                FROM (
                    SELECT e.student_id, round(avg(a.attendance_percentage)::numeric, 2) AS mean
                    FROM attendance a
                    JOIN student_subject_enrollment e
                        ON e.enrollment_record_id = a.enrollment_record_id
                    WHERE e.student_id = ANY($1::text[]) AND e.semester_no = $2
                    GROUP BY e.student_id
                ) agg
                WHERE s.student_id = agg.student_id AND s.semester_no = $2
                """,
                student_ids, semester_no,
            )
            existing_summary_ids = {
                r["student_id"]
                for r in await conn.fetch(
                    """
                    SELECT student_id FROM student_semester_summary
                    WHERE student_id = ANY($1::text[]) AND semester_no = $2
                    """,
                    student_ids, semester_no,
                )
            }
            for sid in student_ids:
                if sid in existing_summary_ids:
                    continue
                mean = sem_by_sid.get(sid)
                if mean is None:
                    continue
                next_sum_id = await conn.fetchval(
                    """
                    SELECT COALESCE(max(substring(semester_summary_id from 4)::bigint), 0) + 1
                    FROM student_semester_summary
                    """
                )
                await conn.execute(
                    """
                    INSERT INTO student_semester_summary (
                        semester_summary_id, student_id, enrollment_no,
                        semester_no, academic_year, semester_attendance_percentage
                    ) VALUES ($1,$2,$3,$4,$5,$6)
                    """,
                    f"SEM{int(next_sum_id):06d}", sid,
                    enrolled_by_sid[sid]["enrollment_no"], semester_no,
                    academic_year, mean,
                )

        if overall_rows:
            await conn.execute(
                """
                UPDATE students s
                SET overall_attendance_percentage = sub.mean
                FROM (
                    SELECT student_id, round(avg(attendance_percentage)::numeric, 2) AS mean
                    FROM attendance
                    WHERE student_id = ANY($1::text[])
                    GROUP BY student_id
                ) sub
                WHERE s.student_id = sub.student_id
                """,
                student_ids,
            )

        return agg_by_sid, sem_by_sid, overall_by_sid

    async def correct_daily_attendance(
        self,
        faculty_id: str,
        attendance_id: int,
        status: str,
        changed_by: str,
        aggregate_fields: Callable[[Optional[float]], Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Single-student correction of a recorded daily row (plan 15 §8.4)."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT d.attendance_id, d.student_id, d.enrollment_no, d.subject_id,
                        d.lecture_date, d.lecture_number, d.attendance_status,
                        d.semester_no, d.academic_year
                    FROM daily_attendance_07 d
                    JOIN student_subject_enrollment e
                        ON e.student_id = d.student_id AND e.subject_id = d.subject_id
                            AND e.semester_no = d.semester_no
                    WHERE d.attendance_id = $1 AND e.faculty_id = $2
                        AND e.enrollment_status = 'Active'
                    LIMIT 1
                    FOR UPDATE
                    """,
                    attendance_id, faculty_id,
                )
                if not row:
                    raise FacultyScopeError("No authorized attendance record matches this id")

                old_status = row["attendance_status"]
                if old_status == status:
                    return {
                        "attendance_id": int(attendance_id),
                        "student_id": row["student_id"],
                        "subject_id": row["subject_id"],
                        "lecture_date": row["lecture_date"],
                        "lecture_number": row["lecture_number"],
                        "operation": "unchanged",
                        "attendance_status": status,
                    }

                await conn.execute(
                    """
                    UPDATE daily_attendance_07
                    SET attendance_status = $1, updated_at = now()
                    WHERE attendance_id = $2
                    """,
                    status, attendance_id,
                )

                await conn.execute(
                    """
                    INSERT INTO attendance_change_log (
                        lecture_date, slot_no, student_id, subject_id,
                        field_name, old_value, new_value, operation_type,
                        changed_by, changed_at
                    ) VALUES ($1,0,$2,$3,'attendance_status',$4,$5,'update',$6,now())
                    """,
                    row["lecture_date"], row["student_id"],
                    row["subject_id"], self._jsonb(old_status), self._jsonb(status),
                    changed_by,
                )

                enrolled = await conn.fetch(
                    """
                    SELECT enrollment_record_id, student_id, enrollment_no
                    FROM student_subject_enrollment
                    WHERE student_id = $1 AND subject_id = $2 AND semester_no = $3
                        AND enrollment_status = 'Active'
                    """,
                    row["student_id"], row["subject_id"], row["semester_no"],
                )
                if not enrolled:
                    raise FacultyScopeError("No authorized enrollment for this attendance record")
                enrolled_by_sid = {r["student_id"]: r for r in enrolled}
                prev_by_sid = await self._capture_prev_attendance(
                    conn, row["subject_id"], row["semester_no"], [row["student_id"]]
                )
                agg_by_sid, sem_by_sid, overall_by_sid = await self._recompute_attendance(
                    conn, row["subject_id"], row["semester_no"], row["academic_year"],
                    [row["student_id"]], enrolled_by_sid, aggregate_fields,
                )
                subject_name = await conn.fetchval(
                    "SELECT subject_name FROM subjects WHERE subject_id = $1",
                    row["subject_id"],
                )
                await self._insert_attendance_notifications(
                    conn,
                    prev_by_sid,
                    agg_by_sid,
                    row["subject_id"],
                    subject_name,
                    row["semester_no"],
                    [row["student_id"]],
                    faculty_id,
                )

        agg = agg_by_sid.get(row["student_id"], {})
        return {
            "attendance_id": int(attendance_id),
            "student_id": row["student_id"],
            "subject_id": row["subject_id"],
            "lecture_date": row["lecture_date"],
            "lecture_number": row["lecture_number"],
            "operation": "updated",
            "attendance_status": status,
            "attendance_percentage": agg.get("attendance_percentage"),
            "attendance_status_band": agg.get("attendance_status"),
            "eligibility_status": agg.get("eligibility_status"),
            "shortage_flag": agg.get("shortage_flag"),
            "semester_attendance_percentage": sem_by_sid.get(row["student_id"]),
            "overall_attendance_percentage": overall_by_sid.get(row["student_id"]),
        }

    async def get_attendance_change_log(
        self,
        subject_id: str,
        page: int,
        page_size: int,
        lecture_date: Any = None,
        slot_no: Optional[int] = None,
    ) -> Dict[str, Any]:
        async with self.pool.acquire() as conn:
            conditions = ["cl.subject_id = $1"]
            params: List[Any] = [subject_id]
            if lecture_date is not None:
                params.append(lecture_date)
                conditions.append(f"cl.lecture_date = ${len(params)}")
            if slot_no is not None:
                params.append(int(slot_no))
                conditions.append(f"cl.slot_no = ${len(params)}")
            where = " AND ".join(conditions)
            count_query = f"SELECT count(*) FROM attendance_change_log cl WHERE {where}"
            total = await conn.fetchval(count_query, *params)
            page_query = f"""
                SELECT cl.change_id, cl.lecture_date, cl.slot_no, cl.student_id,
                    cl.subject_id, cl.field_name, cl.old_value, cl.new_value,
                    cl.operation_type, cl.changed_by, cl.changed_at,
                    st.first_name, st.last_name
                FROM attendance_change_log cl
                LEFT JOIN students st ON st.student_id = cl.student_id
                WHERE {where}
                ORDER BY cl.changed_at DESC, cl.change_id DESC
                LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
            """
            rows = await conn.fetch(page_query, *params, page_size, (page - 1) * page_size)
        return {
            "total": int(total) if total else 0,
            "items": [dict(r) for r in rows],
        }

    async def get_faculty_timetable(
        self,
        faculty_id: str,
        semester_no: int,
    ) -> Dict[str, Any]:
        query = """
            SELECT
                wt.timetable_id, wt.day_name, wt.slot_no, wt.start_time, wt.end_time,
                wt.subject_id, wt.subject_name, wt.faculty_id, wt.lecture_type,
                wt.department_code,
                s.subject_code, s.credits
            FROM weekly_timetable_07 wt
            LEFT JOIN subjects s ON s.subject_id = wt.subject_id
            WHERE wt.faculty_id = $1
                AND wt.semester_no = $2
            ORDER BY wt.slot_no, wt.start_time
        """
        slots_query = """
            SELECT DISTINCT slot_no, start_time, end_time
            FROM weekly_timetable_07
            WHERE semester_no = $1
            ORDER BY slot_no, start_time
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, faculty_id, semester_no)
            slots = await conn.fetch(slots_query, semester_no)
            return {
                "sessions": [dict(row) for row in rows],
                "slots": [dict(row) for row in slots],
            }

    async def get_full_timetable(
        self,
        semester_no: int,
        academic_year: str,
    ) -> Dict[str, Any]:
        query = """
            SELECT
                wt.timetable_id, wt.day_name, wt.slot_no, wt.start_time, wt.end_time,
                wt.subject_id, wt.subject_name, wt.faculty_id, wt.lecture_type,
                wt.department_code, wt.academic_year,
                s.subject_code, s.credits
            FROM weekly_timetable_07 wt
            LEFT JOIN subjects s ON s.subject_id = wt.subject_id
            WHERE wt.semester_no = $1
                AND wt.academic_year = $2
            ORDER BY wt.day_name, wt.slot_no, wt.start_time
        """
        semester_query = """
            SELECT
                wt.timetable_id, wt.day_name, wt.slot_no, wt.start_time, wt.end_time,
                wt.subject_id, wt.subject_name, wt.faculty_id, wt.lecture_type,
                wt.department_code, wt.academic_year,
                s.subject_code, s.credits
            FROM weekly_timetable_07 wt
            LEFT JOIN subjects s ON s.subject_id = wt.subject_id
            WHERE wt.semester_no = $1
            ORDER BY wt.day_name, wt.slot_no, wt.start_time
        """
        slots_query = """
            SELECT DISTINCT slot_no, start_time, end_time
            FROM weekly_timetable_07
            WHERE semester_no = $1
            ORDER BY slot_no, start_time
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, semester_no, academic_year)
            year = academic_year
            if not rows:
                rows = await conn.fetch(semester_query, semester_no)
                if rows:
                    year = rows[0]["academic_year"]
            slots = await conn.fetch(slots_query, semester_no)
            return {
                "sessions": [dict(row) for row in rows],
                "slots": [dict(row) for row in slots],
                "academic_year": year,
            }

    # ------------------------------------------------------------------
    # MD-05 faculty notifications (student_messages, recipient_type='faculty')
    # ------------------------------------------------------------------

    @staticmethod
    def _faculty_notification(row: asyncpg.Record) -> Dict[str, Any]:
        return {
            "message_id": str(row["message_id"]),
            "message_type": row["message_type"],
            "title": row["title"],
            "message_body": row["message_body"],
            "subject": row["subject"],
            "priority": row["priority"],
            "status": row["status"],
            "created_at": row["created_at"],
        }

    async def get_faculty_notifications(
        self,
        faculty_id: str,
        message_type: Optional[str] = None,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Faculty-scoped notification feed (recipient_type='faculty')."""
        params: List[Any] = [faculty_id]
        filters = ["faculty_recipient_id = $1", "recipient_type = 'faculty'"]
        if message_type:
            params.append(message_type)
            filters.append(f"message_type = ${len(params)}")
        if unread_only:
            filters.append("status = 'Unread'")
        where = " AND ".join(filters)
        params.append(page_size)
        params.append((page - 1) * page_size)

        async with self.pool.acquire() as conn:
            total = await conn.fetchval(
                f"SELECT count(*) FROM student_messages WHERE {where}",
                *params[:-2],
            )
            rows = await conn.fetch(
                f"""
                SELECT message_id, message_type, title, message_body,
                       subject, priority, status, created_at
                FROM student_messages
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT ${len(params) - 1} OFFSET ${len(params)}
                """,
                *params,
            )
            unread_count = await conn.fetchval(
                """
                SELECT count(*) FROM student_messages
                WHERE faculty_recipient_id = $1 AND recipient_type = 'faculty'
                    AND status = 'Unread'
                """,
                faculty_id,
            )
        return {
            "items": [self._faculty_notification(row) for row in rows],
            "total": int(total),
            "unread_count": int(unread_count),
        }

    async def get_faculty_unread_count(self, faculty_id: str) -> int:
        async with self.pool.acquire() as conn:
            value = await conn.fetchval(
                """
                SELECT count(*) FROM student_messages
                WHERE faculty_recipient_id = $1 AND recipient_type = 'faculty'
                    AND status = 'Unread'
                """,
                faculty_id,
            )
            return int(value)

    async def mark_faculty_notification_read(
        self, faculty_id: str, message_id: str
    ) -> Optional[Dict[str, Any]]:
        """Ownership-scoped read toggle. Returns None for unknown/foreign ids."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE student_messages
                SET status = 'Read'
                WHERE faculty_recipient_id = $1 AND recipient_type = 'faculty'
                    AND message_id = $2::uuid
                RETURNING message_id, message_type, title, message_body,
                          subject, priority, status, created_at
                """,
                faculty_id, message_id,
            )
            return self._faculty_notification(row) if row else None

    async def mark_all_faculty_notifications_read(self, faculty_id: str) -> int:
        """Mark every unread faculty notification read; returns rows affected."""
        async with self.pool.acquire() as conn:
            value = await conn.fetchval(
                """
                WITH upd AS (
                    UPDATE student_messages
                    SET status = 'Read'
                    WHERE faculty_recipient_id = $1 AND recipient_type = 'faculty'
                        AND status = 'Unread'
                    RETURNING 1
                )
                SELECT count(*) FROM upd
                """,
                faculty_id,
            )
            return int(value)

    async def delete_faculty_notification(
        self, faculty_id: str, message_id: str
    ) -> Optional[Dict[str, Any]]:
        """Ownership-scoped clear (hard delete). Returns None for unknown ids."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                DELETE FROM student_messages
                WHERE faculty_recipient_id = $1 AND recipient_type = 'faculty'
                    AND message_id = $2::uuid
                RETURNING message_id, message_type, title, message_body,
                          subject, priority, status, created_at
                """,
                faculty_id, message_id,
            )
            return self._faculty_notification(row) if row else None

    async def delete_all_faculty_notifications(self, faculty_id: str) -> int:
        """Clear every faculty notification; returns rows deleted."""
        async with self.pool.acquire() as conn:
            value = await conn.fetchval(
                """
                WITH del AS (
                    DELETE FROM student_messages
                    WHERE faculty_recipient_id = $1 AND recipient_type = 'faculty'
                    RETURNING 1
                )
                SELECT count(*) FROM del
                """,
                faculty_id,
            )
            return int(value)
