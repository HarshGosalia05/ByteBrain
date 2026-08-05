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
            ORDER BY academic_year DESC, semester_no DESC
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
                AVG(a.attendance_percentage) AS average_attendance,
                AVG(sp.percentage) AS average_percentage,
                MAX(sp.total_marks) AS highest_marks,
                MIN(sp.total_marks) AS lowest_marks,
                AVG(sp.grade_point) AS average_grade_point,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(sp.result_status) AS performed_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
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
                a.attendance_percentage,
                st.latest_sgpa, st.academic_standing
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
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
            if attendance_range == "< 75%":
                clauses.append("a.attendance_percentage < 75")
            elif attendance_range == "75% - 85%":
                clauses.append("a.attendance_percentage >= 75 AND a.attendance_percentage <= 85")
            elif attendance_range == "> 85%":
                clauses.append("a.attendance_percentage > 85")
                
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

    async def get_subjects_summary(
        self,
        faculty_id: str,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
    ) -> Dict[str, Any]:
        clauses = ["faculty_id = $1", "enrollment_status = 'Active'"]
        params: List[Any] = [faculty_id]
        if semester_no is not None:
            params.append(semester_no)
            clauses.append(f"semester_no = ${len(params)}")
        if academic_year is not None:
            params.append(academic_year)
            clauses.append(f"academic_year = ${len(params)}")
        query = f"""
            SELECT 
                count(DISTINCT (subject_id, semester_no, academic_year)) AS total_subjects,
                count(DISTINCT student_id) AS total_students
            FROM student_subject_enrollment
            WHERE {' AND '.join(clauses)}
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            return dict(row) if row else {"total_subjects": 0, "total_students": 0}

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
        return {
            "semesters": [r["semester_no"] for r in semesters],
            "academic_years": [r["academic_year"] for r in years],
        }

    def _subject_cards_where(
        self,
        faculty_id: str,
        semester_no: Optional[int],
        academic_year: Optional[str],
        search: Optional[str],
    ) -> tuple:
        clauses = ["sse.faculty_id = $1", "sse.enrollment_status = 'Active'"]
        params: List[Any] = [faculty_id]
        if semester_no is not None:
            params.append(semester_no)
            clauses.append(f"sse.semester_no = ${len(params)}")
        if academic_year is not None:
            params.append(academic_year)
            clauses.append(f"sse.academic_year = ${len(params)}")
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
    ) -> int:
        where, params = self._subject_cards_where(faculty_id, semester_no, academic_year, search)
        query = f"""
            SELECT count(DISTINCT (sse.subject_id, sse.semester_no, sse.academic_year))
            FROM student_subject_enrollment sse
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
    ) -> List[Dict[str, Any]]:
        where, params = self._subject_cards_where(faculty_id, semester_no, academic_year, search)
        query = f"""
            SELECT 
                sse.subject_id, sse.subject_code, sse.subject_name, sse.credits,
                sse.semester_no, sse.academic_year,
                count(DISTINCT sse.student_id) AS class_strength,
                AVG(a.attendance_percentage) AS average_attendance,
                AVG(sp.percentage) AS average_percentage,
                MAX(sp.total_marks) AS highest_marks,
                MIN(sp.total_marks) AS lowest_marks,
                AVG(sp.grade_point) AS average_grade_point,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(sp.result_status) AS performed_count
            FROM student_subject_enrollment sse
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
                    AVG(a.attendance_percentage) AS average_attendance,
                    count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                    count(sp.result_status) AS performed_count,
                    AVG(sp.grade_point) AS average_grade_point
                FROM student_subject_enrollment sse
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
                SELECT
                    CASE
                        WHEN a.attendance_percentage < 75 THEN '< 75%'
                        WHEN a.attendance_percentage <= 85 THEN '75% - 85%'
                        ELSE '> 85%'
                    END AS band,
                    count(DISTINCT sse.student_id) AS count
                FROM student_subject_enrollment sse
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                WHERE sse.faculty_id = $1 AND sse.subject_id = $2
                    AND sse.semester_no = $3 AND sse.academic_year = $4
                    AND sse.enrollment_status = 'Active'
                    AND a.attendance_percentage IS NOT NULL
                GROUP BY band
                ORDER BY MIN(a.attendance_percentage) ASC
                """,
                faculty_id, subject_id, semester_no, academic_year,
            )

            students = await conn.fetch(
                """
                SELECT sse.student_id, sse.enrollment_no, st.first_name, st.last_name,
                    a.attendance_percentage, sp.total_marks, sp.grade
                FROM student_subject_enrollment sse
                JOIN students st ON st.student_id = sse.student_id
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
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
                AVG(a.attendance_percentage) AS average_attendance,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(sp.result_status) AS performed_count
            FROM student_subject_enrollment sse
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
                AVG(a.attendance_percentage) AS avg_attendance,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(sp.result_status) AS performed_count,
                count(*) FILTER (WHERE sp.grade_point >= ${len(params)}) AS distinction_count,
                count(*) FILTER (WHERE sp.percentage < ${len(params) - 1}) AS below_count,
                count(*) FILTER (WHERE a.eligibility_status = 'Not Eligible') AS ineligible_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
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
                AVG(a.attendance_percentage) AS average_attendance,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(sp.result_status) AS performed_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
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
                AVG(a.attendance_percentage) AS average_attendance,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(sp.result_status) AS performed_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
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
                AVG(a.attendance_percentage) AS average_attendance,
                count(*) FILTER (WHERE sp.result_status = 'Pass') AS pass_count,
                count(sp.result_status) AS performed_count,
                count(*) FILTER (WHERE sp.percentage < ${len(params)}) AS below_count,
                count(*) FILTER (WHERE a.eligibility_status = 'Not Eligible') AS ineligible_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
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
                a.attendance_percentage,
                sp.total_marks, sp.grade, sp.result_status, sp.percentage
            FROM student_subject_enrollment sse
            JOIN students st ON st.student_id = sse.student_id
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
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
                AVG(a.attendance_percentage) AS avg_attendance,
                CASE WHEN SUM(a.total_classes) > 0
                    THEN ROUND(SUM(a.attended_classes) * 100.0 / SUM(a.total_classes), 2)
                END AS overall_attendance,
                AVG(a.total_classes) AS avg_total_classes,
                count(*) FILTER (WHERE a.attendance_percentage >= ${len(params)}) AS above_count,
                count(*) FILTER (WHERE a.attendance_percentage < ${len(params)}) AS below_count,
                count(*) FILTER (WHERE a.eligibility_status = 'Not Eligible') AS ineligible_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
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
                AVG(a.attendance_percentage) AS average_attendance,
                count(*) FILTER (WHERE a.attendance_percentage >= ${len(params)}) AS above_count,
                count(*) FILTER (WHERE a.attendance_percentage < ${len(params)}) AS below_count
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
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
                AVG(a.attendance_percentage) AS average_attendance
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
            {where}
            GROUP BY sse.semester_no, sse.academic_year
            ORDER BY sse.academic_year ASC, sse.semester_no ASC
        """
        subject_query = f"""
            SELECT 
                sse.subject_id, sse.subject_code, sse.subject_name,
                sse.semester_no, sse.academic_year,
                AVG(a.attendance_percentage) AS average_attendance
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
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
                AVG(a.attendance_percentage) AS average_attendance,
                count(DISTINCT sse.student_id) AS enrollments
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a 
                ON a.enrollment_record_id = sse.enrollment_record_id
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
                           WHEN o.weekly_hours IS NOT NULL
                                AND o.weekly_hours >= ${overload_cap_i} THEN 'Overloaded'
                           WHEN o.weekly_hours IS NOT NULL
                                AND o.weekly_hours < ${underutil_cap_i} THEN 'Underutilized'
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
