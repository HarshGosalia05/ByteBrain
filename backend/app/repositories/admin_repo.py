"""MD-02 Admin Dashboard — read-only aggregation repository.

Every query here is a SELECT against the canonical tables. The repository
never writes and never hardcodes academic values. Filters are applied only
where they are semantically meaningful:

  * ``department_code``  -> students / faculty / departments / summaries
                           (via students) / risk (via students) / attendance
                           / subject performance (via enrollment).
  * ``academic_year``    -> semester-scoped data only (summaries, attendance,
                           subject performance). Not applied to overall
                           student-level figures (CGPA, backlogs, risk) which
                           have no academic-year dimension.
  * ``semester``         -> semester-scoped data only.
"""

from typing import Any, Dict, List, Optional

import asyncpg


class AdminRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def _fetch(self, query: str, args: tuple = ()) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]

    async def _fetchrow(self, query: str, args: tuple) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def get_overall_counts(
        self, department_code: Optional[int]
    ) -> Dict[str, Any]:
        """Students / faculty / departments totals (department filter only)."""
        row = await self._fetchrow(
            """
            SELECT
                (SELECT COUNT(*) FROM students s
                    WHERE ($1::int IS NULL OR s.department_code = $1)) AS total_students,
                (SELECT COUNT(*) FROM faculty f
                    WHERE ($1::int IS NULL OR f.department_code = $1)) AS total_faculty,
                (SELECT COUNT(*) FROM departments d
                    WHERE ($1::int IS NULL OR d.dept_code = $1)) AS total_departments,
                (SELECT AVG(s.overall_cgpa) FROM students s
                    WHERE ($1::int IS NULL OR s.department_code = $1)) AS avg_cgpa,
                (SELECT COALESCE(SUM(s.total_backlogs), 0) FROM students s
                    WHERE ($1::int IS NULL OR s.department_code = $1)) AS total_backlogs
            """,
            (department_code,),
        )
        return row or {}

    async def get_semester_averages(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> Dict[str, Any]:
        """Average SGPA / percentage / attendance across semester summaries."""
        row = await self._fetchrow(
            """
            SELECT
                AVG(sem.semester_sgpa) AS avg_sgpa,
                AVG(sem.semester_percentage) AS avg_percentage,
                AVG(sem.semester_attendance_percentage) AS avg_attendance
            FROM student_semester_summary sem
            JOIN students s ON s.student_id = sem.student_id
            WHERE ($1::int IS NULL OR s.department_code = $1)
              AND ($2::text IS NULL OR sem.academic_year = $2)
              AND ($3::int IS NULL OR sem.semester_no = $3)
            """,
            (department_code, academic_year, semester),
        )
        return row or {}

    async def get_risk_distribution(
        self, department_code: Optional[int]
    ) -> List[Dict[str, Any]]:
        """Stored risk levels from risk_predictions (department filter only)."""
        return await self._fetch(
            """
            SELECT r.prediction_status AS risk_level, COUNT(*) AS count
            FROM risk_predictions r
            JOIN students s ON s.student_id = r.student_id
            WHERE ($1::int IS NULL OR s.department_code = $1)
            GROUP BY r.prediction_status
            """,
            (department_code,),
        )

    async def get_department_performance(
        self,
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Per-department average percentage + SGPA from semester summaries."""
        return await self._fetch(
            """
            SELECT
                s.department_code,
                COALESCE(d.department_name, s.department_name) AS department_name,
                AVG(sem.semester_percentage) AS avg_percentage,
                AVG(sem.semester_sgpa) AS avg_sgpa
            FROM student_semester_summary sem
            JOIN students s ON s.student_id = sem.student_id
            LEFT JOIN departments d ON d.dept_code = s.department_code
            WHERE ($1::text IS NULL OR sem.academic_year = $1)
              AND ($2::int IS NULL OR sem.semester_no = $2)
            GROUP BY s.department_code, d.department_name, s.department_name
            ORDER BY s.department_code
            """,
            (academic_year, semester),
        )

    async def get_academic_trend(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Average SGPA / percentage per semester, ordered numerically."""
        return await self._fetch(
            """
            SELECT
                sem.semester_no AS semester,
                AVG(sem.semester_sgpa) AS avg_sgpa,
                AVG(sem.semester_percentage) AS avg_percentage,
                AVG(sem.semester_attendance_percentage) AS avg_attendance
            FROM student_semester_summary sem
            JOIN students s ON s.student_id = sem.student_id
            WHERE ($1::int IS NULL OR s.department_code = $1)
              AND ($2::text IS NULL OR sem.academic_year = $2)
            GROUP BY sem.semester_no
            ORDER BY sem.semester_no
            """,
            (department_code, academic_year),
        )

    async def get_attendance_distribution(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Subject-level attendance status distribution (existing statuses).

        Scoping goes through ``student_subject_enrollment`` because the
        attendance table only carries ``enrollment_record_id`` + ``semester_no``.
        """
        return await self._fetch(
            """
            SELECT
                COALESCE(a.attendance_status, 'Unknown') AS status,
                COUNT(*) AS count
            FROM attendance a
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = a.enrollment_record_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND ($2::text IS NULL OR e.academic_year = $2)
              AND ($3::int IS NULL OR e.semester_no = $3)
            GROUP BY COALESCE(a.attendance_status, 'Unknown')
            """,
            (department_code, academic_year, semester),
        )

    async def get_attendance_shortage_count(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> int:
        """Count of subject-level attendance rows marked exam-ineligible."""
        row = await self._fetchrow(
            """
            SELECT COUNT(*) AS count
            FROM attendance a
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = a.enrollment_record_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND ($2::text IS NULL OR e.academic_year = $2)
              AND ($3::int IS NULL OR e.semester_no = $3)
              AND COALESCE(a.eligibility_status, 'Not Eligible') = 'Not Eligible'
            """,
            (department_code, academic_year, semester),
        )
        return int((row or {}).get("count") or 0)

    async def get_result_overview(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Pass / Fail / Pending from subject performance results.

        NULL ``result_status`` is Pending (never Fail); this reuses the
        canonical marks derivation where a missing end-sem keeps derived
        fields NULL. Scoping goes through ``enrollment_record_id``.
        """
        return await self._fetch(
            """
            SELECT
                CASE
                    WHEN p.result_status IS NULL THEN 'Pending'
                    WHEN UPPER(p.result_status) = 'FAIL' THEN 'Fail'
                    ELSE 'Pass'
                END AS status,
                COUNT(*) AS count
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = p.enrollment_record_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND ($2::text IS NULL OR e.academic_year = $2)
              AND ($3::int IS NULL OR e.semester_no = $3)
            GROUP BY 1
            """,
            (department_code, academic_year, semester),
        )

    async def get_weakest_subjects(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Subjects with the most Fail results (weak-subject indicator)."""
        return await self._fetch(
            """
            SELECT
                e.subject_code,
                e.subject_name,
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'FAIL') AS fail_count,
                AVG(p.percentage) AS avg_percentage
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = p.enrollment_record_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND ($2::text IS NULL OR e.academic_year = $2)
              AND ($3::int IS NULL OR e.semester_no = $3)
            GROUP BY e.subject_code, e.subject_name
            HAVING COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'FAIL') > 0
            ORDER BY fail_count DESC, e.subject_name
            LIMIT $4
            """,
            (department_code, academic_year, semester, limit),
        )

    async def get_risk_by_department(
        self, department_code: Optional[int]
    ) -> List[Dict[str, Any]]:
        """Per-department risk distribution for the highest-risk insight."""
        return await self._fetch(
            """
            SELECT
                s.department_code,
                COALESCE(d.department_name, s.department_name) AS department_name,
                r.prediction_status AS risk_level,
                COUNT(*) AS count
            FROM risk_predictions r
            JOIN students s ON s.student_id = r.student_id
            LEFT JOIN departments d ON d.dept_code = s.department_code
            WHERE ($1::int IS NULL OR s.department_code = $1)
            GROUP BY
                s.department_code,
                COALESCE(d.department_name, s.department_name),
                r.prediction_status
            """,
            (department_code,),
        )

    async def get_filter_options(self) -> Dict[str, Any]:
        """Available academic years / departments / semesters for the filters."""
        years = await self._fetch(
            "SELECT DISTINCT academic_year FROM student_semester_summary "
            "WHERE academic_year IS NOT NULL ORDER BY academic_year"
        )
        departments = await self._fetch(
            "SELECT dept_code AS department_code, department_name, "
            "department_short_name FROM departments ORDER BY dept_code"
        )
        semesters = await self._fetch(
            "SELECT DISTINCT semester_no FROM student_semester_summary "
            "WHERE semester_no IS NOT NULL ORDER BY semester_no"
        )
        return {
            "academic_years": [r["academic_year"] for r in years],
            "departments": departments,
            "semesters": [r["semester_no"] for r in semesters],
        }

    # --- MD-03 Academic / Department / Subject intelligence ------------------

    async def get_result_counts(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> Dict[str, Any]:
        """Scope-level Pass / Fail counts (Pending is neither).

        NULL ``result_status`` means Pending (end-sem not entered) and is
        excluded from both counts — a Pending row is never a Fail.
        """
        row = await self._fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'PASS') AS pass_count,
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'FAIL') AS fail_count
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = p.enrollment_record_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND ($2::text IS NULL OR e.academic_year = $2)
              AND ($3::int IS NULL OR e.semester_no = $3)
            """,
            (department_code, academic_year, semester),
        )
        return row or {}

    async def get_credits_earned(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> int:
        """Sum of credits on enrollments whose subject result is Pass."""
        row = await self._fetchrow(
            """
            SELECT COALESCE(SUM(e.credits), 0) AS credits_earned
            FROM student_subject_enrollment e
            JOIN student_subject_performance p
              ON p.enrollment_record_id = e.enrollment_record_id
            WHERE UPPER(p.result_status) = 'PASS'
              AND ($1::int IS NULL OR e.department_code = $1)
              AND ($2::text IS NULL OR e.academic_year = $2)
              AND ($3::int IS NULL OR e.semester_no = $3)
            """,
            (department_code, academic_year, semester),
        )
        return int((row or {}).get("credits_earned") or 0)

    async def get_pass_rate_trend(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Pass / Fail counts per semester for the pass-rate trend."""
        return await self._fetch(
            """
            SELECT
                e.semester_no AS semester,
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'PASS') AS pass_count,
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'FAIL') AS fail_count
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = p.enrollment_record_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND ($2::text IS NULL OR e.academic_year = $2)
              AND ($3::int IS NULL OR e.semester_no = $3)
            GROUP BY e.semester_no
            ORDER BY e.semester_no
            """,
            (department_code, academic_year, semester),
        )

    async def get_grade_distribution(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Stored grade counts; a NULL grade is Pending, never converted to F."""
        return await self._fetch(
            """
            SELECT
                COALESCE(p.grade, 'Pending') AS grade,
                COUNT(*) AS count
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = p.enrollment_record_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND ($2::text IS NULL OR e.academic_year = $2)
              AND ($3::int IS NULL OR e.semester_no = $3)
            GROUP BY COALESCE(p.grade, 'Pending')
            """,
            (department_code, academic_year, semester),
        )

    async def get_marks_component_averages(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> Dict[str, Any]:
        """Scope-level raw averages of the three marks components (NULL-safe).

        ``AVG`` ignores NULL marks, so an un-entered end-sem for a live
        semester never pulls the average down to zero — it is simply not
        counted.
        """
        row = await self._fetchrow(
            """
            SELECT
                AVG(p.internal_marks) AS avg_internal,
                AVG(p.mid_sem_marks) AS avg_mid_sem,
                AVG(p.end_sem_marks) AS avg_end_sem,
                COUNT(*) AS total_rows
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = p.enrollment_record_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND ($2::text IS NULL OR e.academic_year = $2)
              AND ($3::int IS NULL OR e.semester_no = $3)
            """,
            (department_code, academic_year, semester),
        )
        return row or {}

    async def get_department_summaries(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Per-department students + semester averages in the scope."""
        return await self._fetch(
            """
            SELECT
                s.department_code,
                COALESCE(d.department_name, s.department_name) AS department_name,
                d.department_short_name,
                COUNT(DISTINCT s.student_id) AS total_students,
                AVG(sem.semester_sgpa) AS avg_sgpa,
                AVG(sem.semester_percentage) AS avg_percentage,
                AVG(sem.semester_attendance_percentage) AS avg_attendance
            FROM students s
            LEFT JOIN departments d ON d.dept_code = s.department_code
            LEFT JOIN student_semester_summary sem ON sem.student_id = s.student_id
              AND ($2::text IS NULL OR sem.academic_year = $2)
              AND ($3::int IS NULL OR sem.semester_no = $3)
            WHERE ($1::int IS NULL OR s.department_code = $1)
            GROUP BY
                s.department_code,
                COALESCE(d.department_name, s.department_name),
                d.department_short_name
            ORDER BY s.department_code
            """,
            (department_code, academic_year, semester),
        )

    async def get_faculty_counts(
        self, department_code: Optional[int]
    ) -> List[Dict[str, Any]]:
        """Per-department faculty headcount (department filter only)."""
        return await self._fetch(
            """
            SELECT department_code, COUNT(*) AS total_faculty
            FROM faculty
            WHERE ($1::int IS NULL OR department_code = $1)
            GROUP BY department_code
            """,
            (department_code,),
        )

    async def get_department_backlogs(
        self, department_code: Optional[int]
    ) -> List[Dict[str, Any]]:
        """Per-department backlog total (department filter only)."""
        return await self._fetch(
            """
            SELECT s.department_code, COALESCE(SUM(s.total_backlogs), 0) AS total_backlogs
            FROM students s
            WHERE ($1::int IS NULL OR s.department_code = $1)
            GROUP BY s.department_code
            """,
            (department_code,),
        )

    async def get_department_pass_rates(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Per-department Pass / Fail counts (Pending excluded)."""
        return await self._fetch(
            """
            SELECT
                e.department_code,
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'PASS') AS pass_count,
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'FAIL') AS fail_count
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = p.enrollment_record_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND ($2::text IS NULL OR e.academic_year = $2)
              AND ($3::int IS NULL OR e.semester_no = $3)
            GROUP BY e.department_code
            """,
            (department_code, academic_year, semester),
        )

    async def get_subject_aggregates(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Per-subject aggregates via the canonical enrollment join.

        All metrics are NULL-safe (``AVG`` skips NULL components, pass rate
        excludes Pending) and the canonical
        ``student_subject_performance.enrollment_record_id`` relationship is
        the only join key used.
        """
        return await self._fetch(
            """
            SELECT
                e.subject_code,
                e.subject_name,
                e.department_code,
                COALESCE(d.department_name, e.department_name) AS department_name,
                e.semester_no AS semester,
                COUNT(DISTINCT e.enrollment_record_id) AS student_count,
                AVG(p.internal_marks) AS avg_internal,
                AVG(p.mid_sem_marks) AS avg_mid_sem,
                AVG(p.end_sem_marks) AS avg_end_sem,
                AVG(p.percentage) AS avg_percentage,
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'PASS') AS pass_count,
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'FAIL') AS fail_count,
                AVG(a.attendance_percentage) AS avg_attendance
            FROM student_subject_enrollment e
            JOIN student_subject_performance p
              ON p.enrollment_record_id = e.enrollment_record_id
            LEFT JOIN departments d ON d.dept_code = e.department_code
            LEFT JOIN attendance a ON a.enrollment_record_id = e.enrollment_record_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND ($2::text IS NULL OR e.academic_year = $2)
              AND ($3::int IS NULL OR e.semester_no = $3)
              AND ($4::text IS NULL
                   OR e.subject_name ILIKE '%' || $4 || '%'
                   OR e.subject_code ILIKE '%' || $4 || '%')
            GROUP BY
                e.subject_code,
                e.subject_name,
                e.department_code,
                COALESCE(d.department_name, e.department_name),
                e.semester_no
            ORDER BY e.subject_code, e.semester_no
            """,
            (department_code, academic_year, semester, search),
        )
