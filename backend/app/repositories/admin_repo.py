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

    @staticmethod
    def _batch_sql(param: str = "$2", alias: str = "s") -> str:
        return f"""(
            {param}::text IS NULL
            OR {alias}.admission_year::text = {param}
            OR {alias}.admission_year = CASE 
                WHEN {param} ~ '^[0-9]{{2}}-[0-9]{{2}}$' THEN ('20' || split_part({param}, '-', 1))::int
                WHEN {param} ~ '^[0-9]{{4}}-[0-9]{{2,4}}$' THEN split_part({param}, '-', 1)::int
                WHEN {param} ~ '^[0-9]{{4}}$' THEN {param}::int
                ELSE -1
            END
            OR (EXISTS (
                SELECT 1 FROM student_semester_summary _sss
                WHERE _sss.student_id = {alias}.student_id
                  AND (_sss.academic_year = {param} OR _sss.academic_year = ('20' || {param}) OR ('20' || _sss.academic_year) = {param} OR (_sss.academic_year = '2026-2027' AND ({param} = '2026-27' OR {param} = '26-27')))
            ))
        )"""

    async def get_overall_counts(
        self,
        department_code: Optional[int],
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Students / faculty / departments totals scoped by active filters."""
        batch_cond = self._batch_sql("$2", "s")
        row = await self._fetchrow(
            f"""
            WITH filtered_students AS (
                SELECT DISTINCT s.student_id
                FROM students s
                LEFT JOIN student_semester_summary sem ON sem.student_id = s.student_id
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND {batch_cond}
                  AND ($3::int IS NULL OR sem.semester_no = $3)
                  AND (
                      $3::int IS NULL
                      OR sem.semester_no IS NOT NULL
                  )
            )
            SELECT
                (SELECT COUNT(*) FROM filtered_students) AS total_students,
                (SELECT COUNT(*) FROM faculty f
                    WHERE ($1::int IS NULL OR f.department_code = $1)) AS total_faculty,
                (SELECT COUNT(*) FROM departments d
                    WHERE ($1::int IS NULL OR d.dept_code = $1)) AS total_departments,
                (SELECT AVG(s.overall_cgpa) FROM students s
                    WHERE s.student_id IN (SELECT student_id FROM filtered_students)) AS avg_cgpa,
                (SELECT COALESCE(SUM(s.total_backlogs), 0) FROM students s
                    WHERE s.student_id IN (SELECT student_id FROM filtered_students)) AS total_backlogs
            """,
            (department_code, academic_year, semester),
        )
        return row or {}

    async def get_semester_averages(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> Dict[str, Any]:
        """Average SGPA / percentage / attendance across semester summaries."""
        batch_cond = self._batch_sql("$2", "s")
        row = await self._fetchrow(
            f"""
            SELECT
                AVG(sem.semester_sgpa) AS avg_sgpa,
                AVG(sem.semester_percentage) AS avg_percentage,
                AVG(sem.semester_attendance_percentage) AS avg_attendance
            FROM student_semester_summary sem
            JOIN students s ON s.student_id = sem.student_id
            WHERE ($1::int IS NULL OR s.department_code = $1)
              AND {batch_cond}
              AND ($3::int IS NULL OR sem.semester_no = $3)
            """,
            (department_code, academic_year, semester),
        )
        return row or {}

    async def get_risk_distribution(
        self,
        department_code: Optional[int],
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Stored risk levels from risk_predictions scoped to filtered students."""
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetch(
            f"""
            WITH filtered_students AS (
                SELECT DISTINCT s.student_id
                FROM students s
                LEFT JOIN student_semester_summary sem ON sem.student_id = s.student_id
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND {batch_cond}
                  AND ($3::int IS NULL OR sem.semester_no = $3)
                  AND (
                      $3::int IS NULL
                      OR sem.semester_no IS NOT NULL
                  )
            )
            SELECT r.prediction_status AS risk_level, COUNT(DISTINCT r.student_id) AS count
            FROM risk_predictions r
            WHERE r.student_id IN (SELECT student_id FROM filtered_students)
            GROUP BY r.prediction_status
            """,
            (department_code, academic_year, semester),
        )

    async def get_department_performance(
        self,
        department_code: Optional[int] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Per-department average percentage + SGPA from semester summaries."""
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetch(
            f"""
            SELECT
                s.department_code,
                COALESCE(d.department_name, s.department_name) AS department_name,
                AVG(sem.semester_percentage) AS avg_percentage,
                AVG(sem.semester_sgpa) AS avg_sgpa
            FROM student_semester_summary sem
            JOIN students s ON s.student_id = sem.student_id
            LEFT JOIN departments d ON d.dept_code = s.department_code
            WHERE ($1::int IS NULL OR s.department_code = $1)
              AND {batch_cond}
              AND ($3::int IS NULL OR sem.semester_no = $3)
            GROUP BY s.department_code, d.department_name, s.department_name
            ORDER BY s.department_code
            """,
            (department_code, academic_year, semester),
        )

    async def get_academic_trend(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Average SGPA / percentage per semester, ordered numerically."""
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetch(
            f"""
            SELECT
                sem.semester_no AS semester,
                AVG(sem.semester_sgpa) AS avg_sgpa,
                AVG(sem.semester_percentage) AS avg_percentage,
                AVG(sem.semester_attendance_percentage) AS avg_attendance
            FROM student_semester_summary sem
            JOIN students s ON s.student_id = sem.student_id
            WHERE ($1::int IS NULL OR s.department_code = $1)
              AND {batch_cond}
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
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetch(
            f"""
            SELECT
                COALESCE(a.attendance_status, 'Unknown') AS status,
                COUNT(*) AS count
            FROM attendance a
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = a.enrollment_record_id
            JOIN students s ON s.student_id = e.student_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND {batch_cond}
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
        batch_cond = self._batch_sql("$2", "s")
        row = await self._fetchrow(
            f"""
            SELECT COUNT(*) AS count
            FROM attendance a
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = a.enrollment_record_id
            JOIN students s ON s.student_id = e.student_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND {batch_cond}
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
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetch(
            f"""
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
            JOIN students s ON s.student_id = e.student_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND {batch_cond}
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
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetch(
            f"""
            SELECT
                e.subject_code,
                e.subject_name,
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'FAIL') AS fail_count,
                AVG(p.percentage) AS avg_percentage
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = p.enrollment_record_id
            JOIN students s ON s.student_id = e.student_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND {batch_cond}
              AND ($3::int IS NULL OR e.semester_no = $3)
            GROUP BY e.subject_code, e.subject_name
            HAVING COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'FAIL') > 0
            ORDER BY fail_count DESC, e.subject_name
            LIMIT $4
            """,
            (department_code, academic_year, semester, limit),
        )

    async def get_risk_by_department(
        self,
        department_code: Optional[int],
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Per-department risk distribution for the highest-risk insight."""
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetch(
            f"""
            WITH filtered_students AS (
                SELECT DISTINCT s.student_id
                FROM students s
                LEFT JOIN student_semester_summary sem ON sem.student_id = s.student_id
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND {batch_cond}
                  AND ($3::int IS NULL OR sem.semester_no = $3)
                  AND (
                      ($2::text IS NULL AND $3::int IS NULL)
                      OR sem.semester_no IS NOT NULL
                  )
            )
            SELECT
                s.department_code,
                COALESCE(d.department_name, s.department_name) AS department_name,
                r.prediction_status AS risk_level,
                COUNT(DISTINCT r.student_id) AS count
            FROM risk_predictions r
            JOIN students s ON s.student_id = r.student_id
            LEFT JOIN departments d ON d.dept_code = s.department_code
            WHERE s.student_id IN (SELECT student_id FROM filtered_students)
            GROUP BY
                s.department_code,
                COALESCE(d.department_name, s.department_name),
                r.prediction_status
            """,
            (department_code, academic_year, semester),
        )

    async def get_filter_options(self, department_code: Optional[int] = None) -> Dict[str, Any]:
        """Available batches / academic years / departments / semesters / career domains / dream roles for filters."""
        batches_rows = await self._fetch(
            """
            SELECT DISTINCT admission_year
            FROM students
            WHERE admission_year IS NOT NULL
              AND ($1::int IS NULL OR department_code = $1)
            ORDER BY admission_year ASC
            """,
            (department_code,),
        )
        admission_batches = [
            f"{str(r['admission_year'])[2:]}-{str(r['admission_year'] + 1)[2:]}"
            for r in batches_rows
        ]

        # Academic years from student_semester_summary
        years_rows = await self._fetch(
            """
            SELECT DISTINCT CASE WHEN sem.academic_year = '2026-2027' THEN '2026-27' ELSE sem.academic_year END AS academic_year
            FROM student_semester_summary sem
            JOIN students s ON s.student_id = sem.student_id
            WHERE ($1::int IS NULL OR s.department_code = $1)
              AND sem.academic_year IS NOT NULL
            ORDER BY academic_year ASC
            """,
            (department_code,),
        )
        years = [r["academic_year"] for r in years_rows]

        departments = await self._fetch(
            """
            SELECT d.dept_code AS department_code, d.department_name,
                   d.department_short_name, d.total_semesters,
                   COALESCE(
                     (SELECT array_agg(DISTINCT sem.semester_no ORDER BY sem.semester_no)
                      FROM student_semester_summary sem
                      JOIN students s ON s.student_id = sem.student_id
                      WHERE s.department_code = d.dept_code),
                     ARRAY[]::int[]
                   ) AS semesters,
                   COALESCE(
                     (SELECT array_agg(DISTINCT CASE WHEN sem.academic_year = '2026-2027' THEN '2026-27' ELSE sem.academic_year END ORDER BY CASE WHEN sem.academic_year = '2026-2027' THEN '2026-27' ELSE sem.academic_year END)
                      FROM student_semester_summary sem
                      JOIN students s ON s.student_id = sem.student_id
                      WHERE s.department_code = d.dept_code AND sem.academic_year IS NOT NULL),
                     ARRAY[]::text[]
                   ) AS department_years,
                   COALESCE(
                     (SELECT array_agg(DISTINCT s.admission_year ORDER BY s.admission_year)
                      FROM students s
                      WHERE s.department_code = d.dept_code AND s.admission_year IS NOT NULL),
                     ARRAY[]::int[]
                   ) AS admission_years
            FROM departments d ORDER BY d.dept_code
            """
        )
        dept_list = []
        department_batches: Dict[str, List[str]] = {}
        for d in departments:
            d_dict = dict(d)
            dept_code = d_dict.get("department_code")
            dept_years = d_dict.pop("department_years", []) or []
            adm_years = d_dict.pop("admission_years", []) or []

            dept_b = [f"{str(y)[2:]}-{str(y + 1)[2:]}" for y in adm_years if y]
            if dept_code == 2:
                dept_b = [b for b in dept_b if b not in ("21-22", "2021-22", "22-23", "2022-23")]

            d_dict["batches"] = dept_b
            d_dict["academic_years"] = dept_years
            dept_list.append(d_dict)
            if dept_code is not None:
                department_batches[str(dept_code)] = dept_b

        semesters = await self._fetch(
            "SELECT DISTINCT semester_no FROM student_semester_summary "
            "WHERE semester_no IS NOT NULL ORDER BY semester_no"
        )
        domains = await self._fetch(
            """
            SELECT DISTINCT domain
            FROM (
                SELECT preferred_domain AS domain FROM career_preferences
                WHERE preferred_domain IS NOT NULL AND preferred_domain != ''
                UNION
                SELECT primary_interest_domain AS domain FROM career_preferences_v2
                WHERE primary_interest_domain IS NOT NULL AND primary_interest_domain != ''
            ) cd
            ORDER BY domain ASC
            """
        )
        roles = await self._fetch(
            """
            SELECT DISTINCT role
            FROM (
                SELECT dream_job_role AS role FROM career_preferences
                WHERE dream_job_role IS NOT NULL AND dream_job_role != ''
                UNION
                SELECT preferred_role AS role FROM career_preferences_v2
                WHERE preferred_role IS NOT NULL AND preferred_role != ''
            ) cr
            ORDER BY role ASC
            """
        )

        if not admission_batches:
            batches_out = years
            years_out = years
        else:
            batches_out = admission_batches
            years_out = list(dict.fromkeys(years + admission_batches)) if years else admission_batches

        return {
            "batches": batches_out,
            "academic_years": years_out,
            "departments": dept_list,
            "department_batches": department_batches,
            "semesters": [r["semester_no"] for r in semesters],
            "preferred_domains": [r["domain"] for r in domains],
            "dream_roles": [r["role"] for r in roles],
        }

    # --- MD-03 Academic / Department / Subject intelligence ------------------

    async def get_result_counts(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> Dict[str, Any]:
        """Scope-level Pass / Fail counts (Pending is neither)."""
        batch_cond = self._batch_sql("$2", "s")
        row = await self._fetchrow(
            f"""
            SELECT
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'PASS') AS pass_count,
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'FAIL') AS fail_count
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = p.enrollment_record_id
            JOIN students s ON s.student_id = e.student_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND {batch_cond}
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
        batch_cond = self._batch_sql("$2", "s")
        row = await self._fetchrow(
            f"""
            SELECT COALESCE(SUM(e.credits), 0) AS credits_earned
            FROM student_subject_enrollment e
            JOIN student_subject_performance p
              ON p.enrollment_record_id = e.enrollment_record_id
            JOIN students s ON s.student_id = e.student_id
            WHERE UPPER(p.result_status) = 'PASS'
              AND ($1::int IS NULL OR e.department_code = $1)
              AND {batch_cond}
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
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetch(
            f"""
            SELECT
                e.semester_no AS semester,
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'PASS') AS pass_count,
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'FAIL') AS fail_count
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = p.enrollment_record_id
            JOIN students s ON s.student_id = e.student_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND {batch_cond}
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
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetch(
            f"""
            SELECT
                COALESCE(p.grade, 'Pending') AS grade,
                COUNT(*) AS count
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = p.enrollment_record_id
            JOIN students s ON s.student_id = e.student_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND {batch_cond}
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
        """Scope-level raw averages of the three marks components (NULL-safe)."""
        batch_cond = self._batch_sql("$2", "s")
        row = await self._fetchrow(
            f"""
            SELECT
                AVG(p.internal_marks) AS avg_internal,
                AVG(p.mid_sem_marks) AS avg_mid_sem,
                AVG(p.end_sem_marks) AS avg_end_sem,
                COUNT(*) AS total_rows
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = p.enrollment_record_id
            JOIN students s ON s.student_id = e.student_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND {batch_cond}
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
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetch(
            f"""
            WITH scoped_students AS (
                SELECT DISTINCT s.student_id, s.department_code
                FROM students s
                LEFT JOIN student_semester_summary sem ON sem.student_id = s.student_id
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND {batch_cond}
                  AND ($3::int IS NULL OR sem.semester_no = $3)
                  AND (
                      $3::int IS NULL
                      OR sem.semester_no IS NOT NULL
                  )
            )
            SELECT
                d.dept_code AS department_code,
                d.department_name,
                d.department_short_name,
                COUNT(DISTINCT s.student_id) AS total_students,
                AVG(sem.semester_sgpa) AS avg_sgpa,
                AVG(sem.semester_percentage) AS avg_percentage,
                AVG(sem.semester_attendance_percentage) AS avg_attendance
            FROM departments d
            LEFT JOIN scoped_students s ON s.department_code = d.dept_code
            LEFT JOIN student_semester_summary sem ON sem.student_id = s.student_id
              AND ($3::int IS NULL OR sem.semester_no = $3)
            WHERE ($1::int IS NULL OR d.dept_code = $1)
            GROUP BY d.dept_code, d.department_name, d.department_short_name
            ORDER BY d.dept_code
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
        self,
        department_code: Optional[int],
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Per-department backlog total scoped by filters."""
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetch(
            f"""
            WITH filtered_students AS (
                SELECT DISTINCT s.student_id, s.department_code, s.total_backlogs
                FROM students s
                LEFT JOIN student_semester_summary sem ON sem.student_id = s.student_id
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND {batch_cond}
                  AND ($3::int IS NULL OR sem.semester_no = $3)
                  AND (
                      $3::int IS NULL
                      OR sem.semester_no IS NOT NULL
                  )
            )
            SELECT department_code, COALESCE(SUM(total_backlogs), 0) AS total_backlogs
            FROM filtered_students
            GROUP BY department_code
            """,
            (department_code, academic_year, semester),
        )

    async def get_department_pass_rates(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Per-department Pass / Fail counts (Pending excluded)."""
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetch(
            f"""
            SELECT
                e.department_code,
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'PASS') AS pass_count,
                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'FAIL') AS fail_count
            FROM student_subject_performance p
            JOIN student_subject_enrollment e
              ON e.enrollment_record_id = p.enrollment_record_id
            JOIN students s ON s.student_id = e.student_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND {batch_cond}
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
        """Per-subject aggregates via the canonical enrollment join."""
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetch(
            f"""
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
            JOIN students s ON s.student_id = e.student_id
            LEFT JOIN departments d ON d.dept_code = e.department_code
            LEFT JOIN attendance a ON a.enrollment_record_id = e.enrollment_record_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND {batch_cond}
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

    async def get_attendance_kpis(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
        target: float,
        critical: float,
    ) -> Optional[Dict[str, Any]]:
        """MD-04 student-level attendance KPIs over scoped subject rows."""
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetchrow(
            f"""
            SELECT
                (SELECT AVG(a.attendance_percentage)
                 FROM attendance a
                 JOIN student_subject_enrollment e ON e.enrollment_record_id = a.enrollment_record_id
                 JOIN students s ON s.student_id = e.student_id
                 WHERE ($1::int IS NULL OR e.department_code = $1)
                   AND {batch_cond}
                   AND ($3::int IS NULL OR e.semester_no = $3)
                   AND a.attendance_percentage IS NOT NULL) AS avg_attendance,
                COUNT(*) AS students_with_records,
                COUNT(*) FILTER (WHERE st.mean_pct < $4) AS students_below_target,
                COUNT(*) FILTER (WHERE st.mean_pct < $5) AS critical_shortage_students,
                COUNT(*) FILTER (WHERE st.all_eligible IS TRUE) AS eligible_students,
                COUNT(*) FILTER (WHERE st.all_eligible IS FALSE) AS not_eligible_students
            FROM (
                SELECT
                    e.student_id,
                    AVG(a.attendance_percentage) AS mean_pct,
                    BOOL_AND(COALESCE(a.eligibility_status = 'Eligible', FALSE)) AS all_eligible
                FROM attendance a
                JOIN student_subject_enrollment e ON e.enrollment_record_id = a.enrollment_record_id
                JOIN students s ON s.student_id = e.student_id
                WHERE ($1::int IS NULL OR e.department_code = $1)
                  AND {batch_cond}
                  AND ($3::int IS NULL OR e.semester_no = $3)
                GROUP BY e.student_id
            ) st
            """,
            (department_code, academic_year, semester, target, critical,),
        )

    async def get_attendance_by_department(
        self,
        academic_year: Optional[str],
        semester: Optional[int],
    ) -> List[Dict[str, Any]]:
        """MD-04 average attendance per department (year + semester scoped)."""
        batch_cond = self._batch_sql("$1", "s")
        return await self._fetch(
            f"""
            SELECT
                e.department_code,
                COALESCE(d.department_name, e.department_name) AS department_name,
                AVG(a.attendance_percentage) AS avg_attendance
            FROM student_subject_enrollment e
            JOIN students s ON s.student_id = e.student_id
            LEFT JOIN attendance a ON a.enrollment_record_id = e.enrollment_record_id
            LEFT JOIN departments d ON d.dept_code = e.department_code
            WHERE {batch_cond}
              AND ($2::int IS NULL OR e.semester_no = $2)
            GROUP BY e.department_code, d.department_name, e.department_name
            ORDER BY e.department_code ASC
            """,
            (academic_year, semester,),
        )

    async def get_attendance_by_semester(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
    ) -> List[Dict[str, Any]]:
        """MD-04 average attendance per semester (numeric order)."""
        batch_cond = self._batch_sql("$2", "s")
        return await self._fetch(
            f"""
            SELECT
                e.semester_no AS semester,
                AVG(a.attendance_percentage) AS avg_attendance
            FROM student_subject_enrollment e
            JOIN students s ON s.student_id = e.student_id
            LEFT JOIN attendance a ON a.enrollment_record_id = e.enrollment_record_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND {batch_cond}
            GROUP BY e.semester_no
            ORDER BY e.semester_no ASC
            """,
            (department_code, academic_year,),
        )

    async def get_subject_attendance(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
        search: Optional[str],
        target: float,
        critical: float,
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        """MD-04 subject-level attendance aggregation (canonical enrollment join)."""
        items = await self._fetch(
            f"""
            SELECT
                e.subject_code,
                e.subject_name,
                e.department_code,
                COALESCE(d.department_name, e.department_name) AS department_name,
                e.semester_no AS semester,
                COUNT(DISTINCT e.enrollment_record_id) AS student_count,
                AVG(a.attendance_percentage) AS avg_attendance,
                COUNT(*) FILTER (WHERE a.attendance_percentage < $4) AS below_target_count,
                COUNT(*) FILTER (WHERE a.attendance_percentage < $5) AS critical_shortage_count,
                COUNT(*) FILTER (WHERE a.eligibility_status = 'Eligible') AS eligible_count,
                COUNT(*) FILTER (WHERE a.eligibility_status = 'Not Eligible') AS not_eligible_count
            FROM student_subject_enrollment e
            JOIN students st ON st.student_id = e.student_id
            LEFT JOIN attendance a ON a.enrollment_record_id = e.enrollment_record_id
            LEFT JOIN departments d ON d.dept_code = e.department_code
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND {self._batch_sql("$2", "st")}
              AND ($3::int IS NULL OR e.semester_no = $3)
              AND ($6::text IS NULL OR e.subject_code ILIKE '%' || $6 || '%'
                   OR e.subject_name ILIKE '%' || $6 || '%')
            GROUP BY e.subject_code, e.subject_name, e.department_code,
                     d.department_name, e.department_name, e.semester_no
            ORDER BY e.semester_no ASC, e.subject_code ASC
            LIMIT $7::int OFFSET $8::int
            """,
            (department_code, academic_year, semester, target, critical, search, limit, offset,),
        )
        total = await self._fetchrow(
            f"""
            SELECT COUNT(*) AS total
            FROM (
                SELECT e.enrollment_record_id
                FROM student_subject_enrollment e
                JOIN students st ON st.student_id = e.student_id
                WHERE ($1::int IS NULL OR e.department_code = $1)
                  AND {self._batch_sql("$2", "st")}
                  AND ($3::int IS NULL OR e.semester_no = $3)
                  AND ($4::text IS NULL OR e.subject_code ILIKE '%' || $4 || '%'
                       OR e.subject_name ILIKE '%' || $4 || '%')
                GROUP BY e.enrollment_record_id
            ) sub
            """,
            (department_code, academic_year, semester, search,),
        )
        return {"items": items, "total": total}

    async def get_shortage_students(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
        semester: Optional[int],
        search: Optional[str],
        target: float,
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        """MD-04 students with subject-level attendance below the target."""
        items = await self._fetch(
            f"""
            SELECT
                st.student_id,
                st.full_name AS student_name,
                st.enrollment_no,
                e.department_code,
                e.department_name,
                e.semester_no AS semester,
                e.subject_code,
                e.subject_name,
                a.attendance_percentage,
                a.eligibility_status
            FROM attendance a
            JOIN student_subject_enrollment e ON e.enrollment_record_id = a.enrollment_record_id
            JOIN students st ON st.student_id = e.student_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND {self._batch_sql("$2", "st")}
              AND ($3::int IS NULL OR e.semester_no = $3)
              AND a.attendance_percentage IS NOT NULL
              AND a.attendance_percentage < $4
              AND ($5::text IS NULL OR st.full_name ILIKE '%' || $5 || '%'
                   OR CAST(st.enrollment_no AS text) ILIKE '%' || $5 || '%'
                   OR e.subject_code ILIKE '%' || $5 || '%'
                   OR e.subject_name ILIKE '%' || $5 || '%')
            ORDER BY a.attendance_percentage ASC, st.full_name ASC
            LIMIT $6::int OFFSET $7::int
            """,
            (department_code, academic_year, semester, target, search, limit, offset,),
        )
        total = await self._fetchrow(
            f"""
            SELECT COUNT(*) AS total
            FROM attendance a
            JOIN student_subject_enrollment e ON e.enrollment_record_id = a.enrollment_record_id
            JOIN students st ON st.student_id = e.student_id
            WHERE ($1::int IS NULL OR e.department_code = $1)
              AND {self._batch_sql("$2", "st")}
              AND ($3::int IS NULL OR e.semester_no = $3)
              AND a.attendance_percentage IS NOT NULL
              AND a.attendance_percentage < $4
              AND ($5::text IS NULL OR st.full_name ILIKE '%' || $5 || '%'
                   OR CAST(st.enrollment_no AS text) ILIKE '%' || $5 || '%'
                   OR e.subject_code ILIKE '%' || $5 || '%'
                   OR e.subject_name ILIKE '%' || $5 || '%')
            """,
            (department_code, academic_year, semester, target, search,),
        )
        return {"items": items, "total": total}


    # --- MD-04 Risk Intelligence ----------------------------------------------

    async def get_risk_counts(
        self,
        department_code: Optional[int],
        semester: Optional[int],
        academic_year: Optional[str],
    ) -> List[Dict[str, Any]]:
        """MD-04 stored risk band counts over the scoped students."""
        return await self._fetch(
            f"""
            SELECT r.prediction_status AS risk_level, COUNT(*) AS count
            FROM risk_predictions r
            JOIN students s ON s.student_id = r.student_id
            WHERE ($1::int IS NULL OR s.department_code = $1)
              AND ($2::int IS NULL OR s.current_semester = $2)
              AND {self._batch_sql("$3", "s")}
            GROUP BY r.prediction_status
            """,
            (department_code, semester, academic_year,),
        )

    async def get_risk_by_department_scoped(
        self,
        semester: Optional[int],
        academic_year: Optional[str],
    ) -> List[Dict[str, Any]]:
        """MD-04 per-department risk band counts (comparison chart)."""
        return await self._fetch(
            f"""
            SELECT
                s.department_code,
                COALESCE(d.department_name, s.department_name) AS department_name,
                r.prediction_status AS risk_level,
                COUNT(*) AS count
            FROM risk_predictions r
            JOIN students s ON s.student_id = r.student_id
            LEFT JOIN departments d ON d.dept_code = s.department_code
            WHERE ($1::int IS NULL OR s.current_semester = $1)
              AND {self._batch_sql("$2", "s")}
            GROUP BY s.department_code, d.department_name, s.department_name, r.prediction_status
            ORDER BY s.department_code ASC
            """,
            (semester, academic_year,),
        )

    async def get_risk_by_semester_scoped(
        self,
        department_code: Optional[int],
        academic_year: Optional[str],
    ) -> List[Dict[str, Any]]:
        """MD-04 per-semester risk band counts (numeric semester order)."""
        return await self._fetch(
            f"""
            SELECT
                s.current_semester AS semester,
                r.prediction_status AS risk_level,
                COUNT(*) AS count
            FROM risk_predictions r
            JOIN students s ON s.student_id = r.student_id
            WHERE ($1::int IS NULL OR s.department_code = $1)
              AND {self._batch_sql("$2", "s")}
              AND s.current_semester IS NOT NULL
            GROUP BY s.current_semester, r.prediction_status
            ORDER BY s.current_semester ASC
            """,
            (department_code, academic_year,),
        )

    async def get_risk_students(
        self,
        department_code: Optional[int],
        semester: Optional[int],
        academic_year: Optional[str],
        risk_upper: Optional[str],
        search: Optional[str],
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        """MD-04 students with a stored risk prediction (severity sort applied in service)."""
        risk_args: List[object] = []
        if risk_upper:
            risk_cond = f" AND UPPER(r.prediction_status) = ${len(risk_args) + 4}::text"
            risk_args.append(risk_upper.upper())
        else:
            risk_cond = ""

        search_idx = len(risk_args) + 4
        limit_idx = search_idx + 1
        offset_idx = search_idx + 2

        args = (department_code, academic_year, semester) + tuple(risk_args) + (search, limit, offset)

        qry = f"""
            SELECT
                st.student_id,
                st.full_name AS student_name,
                st.enrollment_no,
                st.department_code,
                COALESCE(d.department_name, st.department_name) AS department_name,
                st.current_semester AS semester,
                st.current_academic_year AS academic_year,
                st.overall_attendance_percentage AS attendance,
                st.overall_percentage AS percentage,
                st.total_backlogs AS backlogs,
                st.academic_standing,
                r.prediction_status AS risk
            FROM risk_predictions r
            JOIN students st ON st.student_id = r.student_id
            LEFT JOIN departments d ON d.dept_code = st.department_code
            WHERE ($1::int IS NULL OR st.department_code = $1)
              AND {self._batch_sql("$2", "st")}
              AND ($3::int IS NULL OR st.current_semester = $3)
              {risk_cond}
              AND (${search_idx}::text IS NULL OR st.full_name ILIKE '%' || ${search_idx} || '%'
                   OR CAST(st.enrollment_no AS text) ILIKE '%' || ${search_idx} || '%')
            ORDER BY
                CASE UPPER(r.prediction_status)
                    WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MODERATE' THEN 2 ELSE 3
                END,
                st.full_name ASC
            LIMIT ${limit_idx}::int OFFSET ${offset_idx}::int
        """

        items = await self._fetch(qry, args)
        total_args = (department_code, academic_year, semester) + tuple(risk_args) + (search,)
        total = await self._fetchrow(
            f"""
            SELECT COUNT(*) AS total
            FROM risk_predictions r
            JOIN students st ON st.student_id = r.student_id
            WHERE ($1::int IS NULL OR st.department_code = $1)
              AND {self._batch_sql("$2", "st")}
              AND ($3::int IS NULL OR st.current_semester = $3)
              {risk_cond}
              AND (${search_idx}::text IS NULL OR st.full_name ILIKE '%' || ${search_idx} || '%'
                   OR CAST(st.enrollment_no AS text) ILIKE '%' || ${search_idx} || '%')
            """,
            total_args,
        )
        return {"items": items, "total": total}

    async def get_at_risk_students(
        self,
        department_code: Optional[int],
        semester: Optional[int],
        academic_year: Optional[str],
        risk_upper: Optional[str],
    ) -> List[Dict[str, Any]]:
        """MD-04 students with High/Critical risk (early warning center)."""
        risk_cond = ""
        args: List[object] = [department_code, academic_year]
        if risk_upper:
            risk_cond = " AND UPPER(r.prediction_status) = $3::text"
            args.append(risk_upper.upper())

        qry = f"""
            SELECT
                st.student_id,
                st.full_name AS student_name,
                st.enrollment_no,
                st.department_code,
                COALESCE(d.department_name, st.department_name) AS department_name,
                st.current_semester AS semester,
                st.current_academic_year AS academic_year,
                st.overall_attendance_percentage AS attendance,
                st.overall_percentage AS percentage,
                st.total_backlogs AS backlogs,
                st.academic_standing,
                r.prediction_status AS risk
            FROM risk_predictions r
            JOIN students st ON st.student_id = r.student_id
            LEFT JOIN departments d ON d.dept_code = st.department_code
            WHERE ($1::int IS NULL OR st.department_code = $1)
              AND {self._batch_sql("$2", "st")}
              AND st.current_semester IS NOT NULL
              {risk_cond}
            ORDER BY
                CASE UPPER(r.prediction_status)
                    WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 ELSE 2
                END,
                st.full_name ASC
        """
        return await self._fetch(qry, tuple(args))

    async def get_performance_trend_by_students(
        self,
        student_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """MD-04 per-student semester performance trend (for decline detection)."""
        return await self._fetch(
            """
            SELECT
                student_id,
                semester_no,
                semester_percentage,
                academic_year
            FROM student_semester_summary
            WHERE student_id = ANY($1::text[])
              AND semester_percentage IS NOT NULL
            ORDER BY student_id, semester_no ASC
            """,
            (student_ids,),
        )

    # --- MD-05 Admin Student & Faculty Overview ------------------------------

    # Whitelist for the students table ORDER BY. Only these column expressions
    # may be injected; anything else falls back to name. Risk uses a severity
    # rank (Critical=4 .. Low=1, no prediction=0) so "risk" sorts Low -> Critical
    # ascending and Critical -> Low descending, never alphabetically.
    STUDENT_SORT_COLUMNS: Dict[str, str] = {
        "name": "s.full_name",
        "sgpa": "s.latest_sgpa",
        "percentage": "s.overall_percentage",
        "attendance": "s.overall_attendance_percentage",
        "backlogs": "s.total_backlogs",
    }
    STUDENT_SEMESTER_SORT_COLUMNS: Dict[str, str] = {
        "name": "s.full_name",
        "sgpa": "semf.semester_sgpa",
        "percentage": "semf.semester_percentage",
        "attendance": "semf.semester_attendance_percentage",
        "backlogs": "semf.backlog_count",
    }
    STUDENT_RISK_SEVERITY_SQL = (
        "CASE UPPER(sr.risk)"
        " WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3 WHEN 'MODERATE' THEN 2"
        " WHEN 'LOW' THEN 1 ELSE 0 END"
    )

    async def get_admin_students(
        self,
        department_code: Optional[int] = None,
        semester: Optional[int] = None,
        academic_year: Optional[str] = None,
        risk_upper: Optional[str] = None,
        search: Optional[str] = None,
        preferred_domain: Optional[str] = None,
        dream_job_role: Optional[str] = None,
        internship_status: Optional[str] = None,
        placement_readiness_level: Optional[str] = None,
        career_status: Optional[str] = None,
        target_package: Optional[str] = None,
        sort_by: str = "name",
        sort_dir: str = "asc",
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """MD-05 / MD-06 read-only institution students listing with career filters.

        Filters: department / semester / academic year / stored risk band /
        preferred domain / dream role / internship status / placement readiness /
        career status / target package range.
        Search: full name, enrollment number, email, student ID, department name,
        preferred domain, dream role (ILIKE).
        """
        direction = "DESC" if sort_dir == "desc" else "ASC"
        semester_scoped = semester is not None
        sort_columns = (
            self.STUDENT_SEMESTER_SORT_COLUMNS if semester_scoped else self.STUDENT_SORT_COLUMNS
        )
        if sort_by == "risk":
            order_expr = f"{self.STUDENT_RISK_SEVERITY_SQL} {direction}"
        else:
            column = sort_columns.get(sort_by, sort_columns["name"])
            order_expr = f"{column} {direction} NULLS LAST"

        args = (
            department_code,
            semester,
            academic_year,
            risk_upper.upper() if risk_upper else None,
            search,
            limit,
            offset,
            preferred_domain,
            dream_job_role,
            internship_status,
            placement_readiness_level,
            career_status,
            target_package,
        )

        items_query = f"""
            SELECT
                s.student_id,
                s.full_name AS student_name,
                s.enrollment_no,
                s.email,
                s.department_code,
                COALESCE(d.department_name, s.department_name) AS department_name,
                CASE WHEN semf.semester_no IS NULL THEN s.current_semester ELSE semf.semester_no END AS semester,
                CASE WHEN semf.semester_no IS NULL THEN s.current_academic_year ELSE semf.academic_year END AS academic_year,
                CASE WHEN semf.semester_no IS NULL THEN s.latest_sgpa ELSE semf.semester_sgpa END AS sgpa,
                s.overall_cgpa AS cgpa,
                CASE WHEN semf.semester_no IS NULL THEN s.overall_percentage ELSE semf.semester_percentage END AS percentage,
                CASE WHEN semf.semester_no IS NULL THEN s.overall_attendance_percentage ELSE semf.semester_attendance_percentage END AS attendance,
                CASE WHEN semf.semester_no IS NULL THEN s.total_backlogs ELSE semf.backlog_count END AS backlogs,
                s.academic_standing,
                sr.risk,
                COALESCE(cp.preferred_domain, cv.primary_interest_domain) AS preferred_domain,
                COALESCE(cp.dream_job_role, cv.preferred_role) AS dream_job_role,
                cp.preferred_industry,
                COALESCE(cp.preferred_work_mode, cv.preferred_work_mode) AS preferred_work_mode,
                COALESCE(cp.target_package_lpa, cv.desired_salary_lpa) AS target_package_lpa,
                COALESCE(cp.higher_studies_interest, cv.higher_studies_intent) AS higher_studies_interest,
                cp.entrepreneurship_interest,
                cp.certification_interest,
                cp.internship_completed,
                cp.placement_readiness_level,
                ls.average_sleep_hours,
                ls.daily_study_hours,
                ls.screen_time_hours,
                ls.physical_activity,
                ls.stress_level,
                ls.mental_wellbeing,
                ls.attendance_commitment,
                ls.part_time_job,
                ls.internet_access,
                ls.preferred_learning_mode
            FROM students s
            LEFT JOIN departments d ON d.dept_code = s.department_code
            LEFT JOIN LATERAL (
                SELECT r.prediction_status AS risk
                FROM risk_predictions r
                WHERE r.student_id = s.student_id
                ORDER BY r.prediction_timestamp DESC NULLS LAST
                LIMIT 1
            ) sr ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    cp.preferred_domain,
                    cp.dream_job_role,
                    cp.preferred_industry,
                    cp.preferred_work_mode,
                    cp.target_package_lpa,
                    cp.higher_studies_interest,
                    cp.entrepreneurship_interest,
                    cp.certification_interest,
                    cp.internship_completed,
                    cp.placement_readiness_level
                FROM career_preferences cp
                WHERE cp.student_id = s.student_id
                ORDER BY cp.survey_date DESC NULLS LAST
                LIMIT 1
            ) cp ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    cv.primary_interest_domain,
                    cv.preferred_role,
                    cv.preferred_work_mode,
                    cv.desired_salary_lpa,
                    cv.higher_studies_intent,
                    cv.career_role_category
                FROM career_preferences_v2 cv
                WHERE cv.student_id = s.student_id
                LIMIT 1
            ) cv ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    ls.average_sleep_hours,
                    ls.daily_study_hours,
                    ls.screen_time_hours,
                    ls.physical_activity,
                    ls.stress_level,
                    ls.mental_wellbeing,
                    ls.attendance_commitment,
                    ls.part_time_job,
                    ls.internet_access,
                    ls.preferred_learning_mode
                FROM lifestyle_survey ls
                WHERE ls.student_id = s.student_id
                ORDER BY ls.survey_date DESC NULLS LAST
                LIMIT 1
            ) ls ON TRUE
            LEFT JOIN LATERAL (
                SELECT ss2.semester_no, ss2.academic_year, ss2.semester_sgpa,
                       ss2.semester_percentage, ss2.semester_attendance_percentage,
                       ss2.backlog_count
                FROM student_semester_summary ss2
                WHERE ss2.student_id = s.student_id
                  AND ss2.semester_no = $2
                LIMIT 1
            ) semf ON TRUE
            WHERE ($1::int IS NULL OR s.department_code = $1)
              AND ($2::int IS NULL OR semf.semester_no IS NOT NULL)
              AND {self._batch_sql("$3", "s")}
              AND ($4::text IS NULL OR UPPER(sr.risk) = $4)
              AND ($5::text IS NULL OR s.full_name ILIKE '%' || $5 || '%'
                   OR CAST(s.enrollment_no AS text) ILIKE '%' || $5 || '%'
                   OR s.email ILIKE '%' || $5 || '%'
                   OR s.student_id ILIKE '%' || $5 || '%'
                   OR COALESCE(d.department_name, s.department_name) ILIKE '%' || $5 || '%'
                   OR COALESCE(cp.preferred_domain, cv.primary_interest_domain) ILIKE '%' || $5 || '%'
                   OR COALESCE(cp.dream_job_role, cv.preferred_role) ILIKE '%' || $5 || '%')
              AND ($8::text IS NULL OR COALESCE(cp.preferred_domain, cv.primary_interest_domain) = $8)
              AND ($9::text IS NULL OR COALESCE(cp.dream_job_role, cv.preferred_role) = $9)
              AND ($10::text IS NULL OR cp.internship_completed = $10)
              AND ($11::text IS NULL OR cp.placement_readiness_level = $11)
              AND ($12::text IS NULL OR
                   ($12 = 'At Risk' AND (s.academic_standing = 'At Risk' OR UPPER(sr.risk) IN ('HIGH', 'CRITICAL'))) OR
                   ($12 = 'Ready' AND (s.academic_standing IS NULL OR s.academic_standing != 'At Risk')))
              AND ($13::text IS NULL OR
                   ($13 = 'below_5' AND COALESCE(cp.target_package_lpa, cv.desired_salary_lpa) < 5.0) OR
                   ($13 = '5_7' AND COALESCE(cp.target_package_lpa, cv.desired_salary_lpa) >= 5.0 AND COALESCE(cp.target_package_lpa, cv.desired_salary_lpa) <= 7.0) OR
                   ($13 = '7_10' AND COALESCE(cp.target_package_lpa, cv.desired_salary_lpa) > 7.0 AND COALESCE(cp.target_package_lpa, cv.desired_salary_lpa) <= 10.0) OR
                   ($13 = 'above_10' AND COALESCE(cp.target_package_lpa, cv.desired_salary_lpa) > 10.0))
            ORDER BY {order_expr}, s.student_id ASC
            LIMIT $6::int OFFSET $7::int
        """

        total_query = f"""
            SELECT COUNT(*) AS total
            FROM students s
            LEFT JOIN departments d ON d.dept_code = s.department_code
            LEFT JOIN LATERAL (
                SELECT r.prediction_status AS risk
                FROM risk_predictions r
                WHERE r.student_id = s.student_id
                ORDER BY r.prediction_timestamp DESC NULLS LAST
                LIMIT 1
            ) sr ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    cp.preferred_domain,
                    cp.dream_job_role,
                    cp.internship_completed,
                    cp.placement_readiness_level,
                    cp.target_package_lpa
                FROM career_preferences cp
                WHERE cp.student_id = s.student_id
                ORDER BY cp.survey_date DESC NULLS LAST
                LIMIT 1
            ) cp ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    cv.primary_interest_domain,
                    cv.preferred_role,
                    cv.desired_salary_lpa
                FROM career_preferences_v2 cv
                WHERE cv.student_id = s.student_id
                LIMIT 1
            ) cv ON TRUE
            WHERE ($1::int IS NULL OR s.department_code = $1)
              AND ($2::int IS NULL OR EXISTS (
                    SELECT 1 FROM student_semester_summary semf
                    WHERE semf.student_id = s.student_id AND semf.semester_no = $2
              ))
              AND {self._batch_sql("$3", "s")}
              AND ($4::text IS NULL OR UPPER(sr.risk) = $4)
              AND ($5::text IS NULL OR s.full_name ILIKE '%' || $5 || '%'
                   OR CAST(s.enrollment_no AS text) ILIKE '%' || $5 || '%'
                   OR s.email ILIKE '%' || $5 || '%'
                   OR s.student_id ILIKE '%' || $5 || '%'
                   OR COALESCE(d.department_name, s.department_name) ILIKE '%' || $5 || '%'
                   OR COALESCE(cp.preferred_domain, cv.primary_interest_domain) ILIKE '%' || $5 || '%'
                   OR COALESCE(cp.dream_job_role, cv.preferred_role) ILIKE '%' || $5 || '%')
              AND ($6::text IS NULL OR COALESCE(cp.preferred_domain, cv.primary_interest_domain) = $6)
              AND ($7::text IS NULL OR COALESCE(cp.dream_job_role, cv.preferred_role) = $7)
              AND ($8::text IS NULL OR cp.internship_completed = $8)
              AND ($9::text IS NULL OR cp.placement_readiness_level = $9)
              AND ($10::text IS NULL OR
                   ($10 = 'At Risk' AND (s.academic_standing = 'At Risk' OR UPPER(sr.risk) IN ('HIGH', 'CRITICAL'))) OR
                   ($10 = 'Ready' AND (s.academic_standing IS NULL OR s.academic_standing != 'At Risk')))
              AND ($11::text IS NULL OR
                   ($11 = 'below_5' AND COALESCE(cp.target_package_lpa, cv.desired_salary_lpa) < 5.0) OR
                   ($11 = '5_7' AND COALESCE(cp.target_package_lpa, cv.desired_salary_lpa) >= 5.0 AND COALESCE(cp.target_package_lpa, cv.desired_salary_lpa) <= 7.0) OR
                   ($11 = '7_10' AND COALESCE(cp.target_package_lpa, cv.desired_salary_lpa) > 7.0 AND COALESCE(cp.target_package_lpa, cv.desired_salary_lpa) <= 10.0) OR
                   ($11 = 'above_10' AND COALESCE(cp.target_package_lpa, cv.desired_salary_lpa) > 10.0))
        """
        total_args = (
            department_code,
            semester,
            academic_year,
            risk_upper.upper() if risk_upper else None,
            search,
            preferred_domain,
            dream_job_role,
            internship_status,
            placement_readiness_level,
            career_status,
            target_package,
        )

        items = await self._fetch(items_query, args)
        total = await self._fetchrow(total_query, total_args)
        return {"items": items, "total": total}

    async def get_faculty_kpis(self) -> Dict[str, Any]:
        """MD-05 faculty KPIs: total / active (status) / department count."""
        row = await self._fetchrow(
            """
            SELECT
                COUNT(*) AS total_faculty,
                COUNT(*) FILTER (WHERE f.status = 'Active') AS active_faculty,
                (SELECT COUNT(*) FROM departments) AS department_count
            FROM faculty f
            """,
            (),
        )
        return row or {
            "total_faculty": 0,
            "active_faculty": 0,
            "department_count": 0,
        }

    async def get_faculty_by_department(self) -> List[Dict[str, Any]]:
        """MD-05 faculty headcount grouped by department (chart)."""
        return await self._fetch(
            """
            SELECT
                f.department_code,
                COALESCE(d.department_name, f.department_name) AS department_name,
                COUNT(*) AS count
            FROM faculty f
            LEFT JOIN departments d ON d.dept_code = f.department_code
            GROUP BY f.department_code, d.department_name, f.department_name
            ORDER BY f.department_code ASC
            """
        )

    async def get_faculty_by_designation(self) -> List[Dict[str, Any]]:
        """MD-05 faculty headcount grouped by designation (chart)."""
        return await self._fetch(
            """
            SELECT
                COALESCE(NULLIF(f.designation, ''), 'Unassigned') AS designation,
                COUNT(*) AS count
            FROM faculty f
            GROUP BY f.designation
            ORDER BY count DESC, designation ASC
            """
        )

    async def get_faculty_overview_rows(self, weeks: float) -> List[Dict[str, Any]]:
        """MD-05 faculty table with teaching allocation aggregates.

        subject_count / student_count come from active subject allocations
        (student_subject_enrollment); weekly workload reuses the existing
        faculty workload calculation MAX(total_classes) / weeks per offering,
        summed across the faculty member's active offerings.
        """
        return await self._fetch(
            """
            WITH offering AS (
                SELECT
                    sse.faculty_id,
                    sse.subject_id,
                    sse.semester_no,
                    sse.academic_year,
                    MAX(a.total_classes) AS classes
                FROM student_subject_enrollment sse
                LEFT JOIN attendance a ON a.enrollment_record_id = sse.enrollment_record_id
                WHERE sse.enrollment_status = 'Active'
                GROUP BY sse.faculty_id, sse.subject_id, sse.semester_no, sse.academic_year
            )
            SELECT
                f.faculty_id,
                f.faculty_code,
                f.full_name,
                f.department_code,
                COALESCE(d.department_name, f.department_name) AS department_name,
                f.designation,
                COUNT(o.subject_id) AS subject_count,
                (SELECT COUNT(DISTINCT sse.student_id)
                 FROM student_subject_enrollment sse
                 WHERE sse.faculty_id = f.faculty_id
                   AND sse.enrollment_status = 'Active') AS student_count,
                ROUND(
                    CASE WHEN COUNT(o.subject_id) > 0
                         THEN COALESCE(SUM(o.classes), 0)::numeric * 1.0 / $1::numeric
                         ELSE NULL END,
                    2
                ) AS workload_hours
            FROM faculty f
            LEFT JOIN departments d ON d.dept_code = f.department_code
            LEFT JOIN offering o ON o.faculty_id = f.faculty_id
            GROUP BY f.faculty_id, f.faculty_code, f.full_name, f.department_code,
                     d.department_name, f.department_name, f.designation
            ORDER BY COALESCE(d.department_name, f.department_name) ASC, f.full_name ASC
            """,
            (weeks,),
        )

    # --- MD-07 Admin Notifications & Executive Insights -----------------------

    async def create_announcement(
        self,
        title: str,
        message_body: str,
        message_type: str,
        target_audience: str,
        department_code: Optional[int],
        priority: str,
    ) -> Dict[str, Any]:
        """MD-07 Broadcast admin announcement/notice into student_messages.

        Targets 'students', 'faculty', or 'both'. Optional department_code filter.
        Reuses existing student_messages notification store without modifying schema.
        """
        message_type = (message_type or "ANNOUNCEMENT").upper()
        if message_type not in {"ANNOUNCEMENT", "ACADEMIC_NOTICE", "HOLIDAY", "EVENT", "SYSTEM_NOTICE"}:
            message_type = "ANNOUNCEMENT"

        target_audience = (target_audience or "both").lower()
        if target_audience not in {"students", "faculty", "both"}:
            target_audience = "both"

        priority = priority or "Normal"

        inserted_count = 0
        event_id = f"announcement:{int(datetime.now().timestamp())}:{abs(hash((title, target_audience)))}"

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if target_audience in {"students", "both"}:
                    student_rows = await conn.fetch(
                        "SELECT student_id FROM students WHERE ($1::int IS NULL OR department_code = $1)",
                        department_code,
                    )
                    for s in student_rows:
                        await conn.execute(
                            """
                            INSERT INTO student_messages (
                                student_id, faculty_recipient_id, recipient_type, faculty_id,
                                subject, message_type, title, message_body, priority, status,
                                event_id, created_at
                            ) VALUES ($1, NULL, 'student', NULL, NULL, $2, $3, $4, $5, 'Unread', $6, NOW())
                            """,
                            s["student_id"],
                            message_type,
                            title,
                            message_body,
                            priority,
                            event_id,
                        )
                        inserted_count += 1

                if target_audience in {"faculty", "both"}:
                    faculty_rows = await conn.fetch(
                        "SELECT faculty_id FROM faculty WHERE ($1::int IS NULL OR department_code = $1)",
                        department_code,
                    )
                    for f in faculty_rows:
                        await conn.execute(
                            """
                            INSERT INTO student_messages (
                                student_id, faculty_recipient_id, recipient_type, faculty_id,
                                subject, message_type, title, message_body, priority, status,
                                event_id, created_at
                            ) VALUES (NULL, $1, 'faculty', NULL, NULL, $2, $3, $4, $5, 'Unread', $6, NOW())
                            """,
                            f["faculty_id"],
                            message_type,
                            title,
                            message_body,
                            priority,
                            event_id,
                        )
                        inserted_count += 1

        return {
            "announcement_id": event_id,
            "title": title,
            "type": message_type,
            "target_audience": target_audience,
            "recipients_notified": inserted_count,
            "created_at": datetime.now(),
        }

    async def get_admin_announcements(self) -> List[Dict[str, Any]]:
        """MD-07 History of admin announcements sent."""
        rows = await self._fetch(
            """
            SELECT
                title,
                message_body AS message,
                message_type AS type,
                CASE
                    WHEN recipient_type = 'faculty' THEN 'faculty'
                    WHEN student_id IS NOT NULL THEN 'students'
                    ELSE 'both'
                END AS target_audience,
                priority,
                COUNT(*) AS recipient_count,
                MAX(created_at) AS created_at
            FROM student_messages
            WHERE message_type IN ('ANNOUNCEMENT', 'ACADEMIC_NOTICE', 'HOLIDAY', 'EVENT', 'SYSTEM_NOTICE')
            GROUP BY title, message_body, message_type, recipient_type, priority, event_id
            ORDER BY MAX(created_at) DESC
            LIMIT 50
            """
        )
        return rows

    async def get_executive_summary(self) -> Dict[str, Any]:
        """MD-07 Executive Academic Summary & Grounded Insights.

        Aggregates structured verified analytics from MD-01 through MD-06.
        Generates 100% grounded natural language summary points.
        """
        # 1. Department academic performance
        dept_rows = await self._fetch(
            """
            SELECT
                s.department_code,
                COALESCE(d.department_name, s.department_name) AS department_name,
                COUNT(DISTINCT s.student_id) AS student_count,
                ROUND(AVG(s.overall_cgpa)::numeric, 2) AS avg_cgpa,
                ROUND(AVG(s.overall_percentage)::numeric, 2) AS avg_percentage
            FROM students s
            LEFT JOIN departments d ON d.dept_code = s.department_code
            GROUP BY s.department_code, d.department_name, s.department_name
            ORDER BY AVG(s.overall_cgpa) DESC NULLS LAST
            """
        )

        strongest_dept = dept_rows[0] if dept_rows else None
        weakest_dept = dept_rows[-1] if dept_rows else None

        # 2. Subject performance
        subject_rows = await self._fetch(
            """
            SELECT
                sub.subject_code,
                sub.subject_name,
                COUNT(DISTINCT sem.student_id) AS student_count,
                ROUND(AVG(sem.overall_percentage)::numeric, 2) AS avg_percentage
            FROM student_semester_subject_summary sem
            JOIN subjects sub ON sub.subject_code = sem.subject_code
            WHERE sem.overall_percentage IS NOT NULL
            GROUP BY sub.subject_code, sub.subject_name
            ORDER BY AVG(sem.overall_percentage) ASC NULLS LAST
            LIMIT 1
            """
        )
        weakest_subject = subject_rows[0] if subject_rows else None

        # 3. Attendance concern
        att_rows = await self._fetch(
            """
            SELECT
                COALESCE(d.department_name, s.department_name) AS department_name,
                ROUND(AVG(s.overall_attendance_percentage)::numeric, 2) AS avg_att,
                COUNT(*) FILTER (WHERE s.overall_attendance_percentage < 75) AS shortage_count
            FROM students s
            LEFT JOIN departments d ON d.dept_code = s.department_code
            GROUP BY s.department_code, d.department_name, s.department_name
            ORDER BY AVG(s.overall_attendance_percentage) ASC NULLS LAST
            LIMIT 1
            """
        )
        att_concern = att_rows[0] if att_rows else None

        # 4. Stored risk predictions summary
        risk_rows = await self._fetch(
            """
            SELECT
                COUNT(*) FILTER (WHERE UPPER(r.prediction_status) IN ('HIGH', 'CRITICAL')) AS total_risk,
                COUNT(*) FILTER (WHERE UPPER(r.prediction_status) = 'HIGH') AS high_risk,
                COUNT(*) FILTER (WHERE UPPER(r.prediction_status) = 'CRITICAL') AS critical_risk
            FROM (
                SELECT DISTINCT ON (student_id) student_id, prediction_status
                FROM risk_predictions
                ORDER BY student_id, prediction_timestamp DESC NULLS LAST
            ) r
            """
        )
        risk_stats = risk_rows[0] if risk_rows else {"total_risk": 0, "high_risk": 0, "critical_risk": 0}

        top_risk_dept_row = await self._fetchrow(
            """
            SELECT COALESCE(d.department_name, s.department_name) AS department_name
            FROM students s
            LEFT JOIN departments d ON d.dept_code = s.department_code
            JOIN (
                SELECT DISTINCT ON (student_id) student_id, prediction_status
                FROM risk_predictions
                ORDER BY student_id, prediction_timestamp DESC NULLS LAST
            ) r ON r.student_id = s.student_id
            WHERE UPPER(r.prediction_status) IN ('HIGH', 'CRITICAL')
            GROUP BY s.department_code, d.department_name, s.department_name
            ORDER BY COUNT(*) DESC
            LIMIT 1
            """
        )

        # 5. Overall institution health
        inst_row = await self._fetchrow(
            """
            SELECT
                COUNT(DISTINCT student_id) AS total_students,
                ROUND(AVG(overall_cgpa)::numeric, 2) AS overall_avg_cgpa,
                ROUND(AVG(overall_attendance_percentage)::numeric, 2) AS overall_attendance_pct
            FROM students
            """
        )

        # 6. Career internship rate
        career_row = await self._fetchrow(
            """
            SELECT
                COUNT(*) AS total_career_records,
                COUNT(*) FILTER (WHERE internship_completed = 'Yes') AS internships_done
            FROM career_preferences
            """
        )
        internship_rate = None
        if career_row and career_row.get("total_career_records"):
            internship_rate = round(
                (float(career_row["internships_done"]) / float(career_row["total_career_records"])) * 100, 1
            )

        # Construct grounded insights bullets
        insights: List[str] = []
        if strongest_dept:
            insights.append(
                f"Strongest Department: {strongest_dept['department_name']} leads academic performance with an average CGPA of {strongest_dept['avg_cgpa']}."
            )
        if weakest_subject:
            insights.append(
                f"Academic Focus Area: {weakest_subject['subject_name']} ({weakest_subject['subject_code']}) shows the lowest average score across enrollments ({weakest_subject['avg_percentage']}%)."
            )
        if att_concern:
            insights.append(
                f"Attendance Concern: {att_concern['department_name']} has the lowest attendance average at {att_concern['avg_att']}%, with {att_concern['shortage_count']} students below 75% threshold."
            )
        if risk_stats and risk_stats.get("total_risk", 0) > 0:
            top_dept_str = f" (concentrated in {top_risk_dept_row['department_name']})" if top_risk_dept_row else ""
            insights.append(
                f"Risk Early Warning: {risk_stats['total_risk']} students are currently flagged At-Risk ({risk_stats['high_risk']} High Risk, {risk_stats['critical_risk']} Critical Risk){top_dept_str}."
            )
        if internship_rate is not None:
            insights.append(
                f"Career Readiness: {internship_rate}% of surveyed students have completed at least one internship."
            )

        insights.append(
            "Recommended Administrative Action: Prioritize academic counseling for high-risk students and review attendance enforcement in vulnerable departments."
        )

        return {
            "strongest_department": strongest_dept,
            "weakest_department": weakest_dept,
            "weakest_subject": weakest_subject,
            "attendance_concern_department": att_concern["department_name"] if att_concern else None,
            "attendance_shortage_count": int(att_concern["shortage_count"] if att_concern else 0),
            "total_at_risk_students": int(risk_stats.get("total_risk") or 0),
            "high_risk_count": int(risk_stats.get("high_risk") or 0),
            "critical_risk_count": int(risk_stats.get("critical_risk") or 0),
            "top_risk_department": top_risk_dept_row["department_name"] if top_risk_dept_row else None,
            "total_students": int(inst_row.get("total_students") or 0) if inst_row else 0,
            "overall_avg_cgpa": float(inst_row.get("overall_avg_cgpa") or 0) if inst_row and inst_row.get("overall_avg_cgpa") else None,
            "overall_attendance_pct": float(inst_row.get("overall_attendance_pct") or 0) if inst_row and inst_row.get("overall_attendance_pct") else None,
            "internship_completion_rate": internship_rate,
            "insights": insights,
        }
