"""Analytics query layer — read-only repository.

All methods are pure SELECT queries against ETL-produced canonical tables.
No writes, no schema changes, no side-effects.  Every query uses
positional parameterized placeholders ($1, $2 …) for safety.

Tables read:
  - students, departments, faculty
  - student_subject_enrollment, student_semester_summary
  - student_subject_performance
  - attendance (derived), daily_attendance_07
  - weekly_timetable_07
"""

from typing import Any, Dict, List, Optional

import asyncpg

from app.core.config import settings


class AnalyticsRepository:
    """Read-only analytics queries against the canonical data warehouse."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # ------------------------------------------------------------------
    # Internal helpers (match admin_repo pattern)
    # ------------------------------------------------------------------

    async def _fetch(self, query: str, *args: Any) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]

    async def _fetchrow(
        self, query: str, *args: Any
    ) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def _fetchval(self, query: str, *args: Any) -> Any:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    # ==================================================================
    # A. Student Analytics
    # ==================================================================

    async def get_student_academic_profile(
        self, student_id: str
    ) -> Optional[Dict[str, Any]]:
        """Overall academic profile for a single student.

        Grain: one row per student.
        """
        return await self._fetchrow(
            """
            SELECT
                s.student_id,
                s.full_name,
                s.department_code,
                s.department_name,
                s.current_semester,
                s.current_academic_year,
                s.overall_cgpa,
                s.latest_sgpa,
                s.total_backlogs,
                s.overall_attendance_percentage,
                (SELECT count(*)
                 FROM student_subject_enrollment e
                 WHERE e.student_id = s.student_id
                   AND e.semester_no = s.current_semester
                )::int AS total_subjects_enrolled,
                (SELECT COALESCE(sum(e.credits), 0)::int
                 FROM student_subject_enrollment e
                 WHERE e.student_id = s.student_id
                   AND e.semester_no = s.current_semester
                ) AS total_credits_registered
            FROM students s
            WHERE s.student_id = $1
            """,
            student_id,
        )

    async def get_student_semester_history(
        self,
        student_id: str,
        *,
        department_code: Optional[int] = None,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Semester-wise performance trend for a student.

        Grain: one row per (student_id, semester_no).
        All filters are optional; when None the filter is skipped.
        """
        return await self._fetch(
            """
            SELECT
                sem.semester_no,
                sem.academic_year,
                sem.semester_sgpa,
                sem.semester_percentage,
                sem.semester_attendance_percentage,
                sem.subjects_registered,
                sem.credits_registered,
                sem.credits_earned,
                sem.backlog_count,
                sem.semester_result,
                sem.academic_standing
            FROM student_semester_summary sem
            JOIN students s ON s.student_id = sem.student_id
            WHERE sem.student_id = $1
              AND ($2::int IS NULL OR s.department_code = $2)
              AND ($3::int IS NULL OR sem.semester_no = $3)
              AND ($4::text IS NULL OR sem.academic_year = $4)
            ORDER BY sem.semester_no
            """,
            student_id,
            department_code,
            semester_no,
            academic_year,
        )

    async def get_student_attendance_summary(
        self,
        student_id: str,
        *,
        semester_no: Optional[int] = None,
        subject_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Per-subject attendance for a student.

        Returns a summary dict with a ``subjects`` list (grain: one row per
        subject) and aggregate totals.
        """
        subjects = await self._fetch(
            """
            SELECT
                a.subject_id,
                sub.subject_code,
                sub.subject_name,
                a.total_classes,
                a.attended_classes,
                a.attendance_percentage,
                a.attendance_status,
                a.eligibility_status,
                a.shortage_flag
            FROM attendance a
            LEFT JOIN subjects sub ON sub.subject_id = a.subject_id
            WHERE a.student_id = $1
              AND ($2::int IS NULL OR a.semester_no = $2)
              AND ($3::text IS NULL OR a.subject_id = $3)
            ORDER BY a.subject_id
            """,
            student_id,
            semester_no,
            subject_id,
        )

        total_classes = sum(r["total_classes"] for r in subjects)
        attended_classes = sum(r["attended_classes"] for r in subjects)
        overall_pct = (
            round(attended_classes / total_classes * 100, 2)
            if total_classes
            else None
        )
        at_risk = sum(
            1 for r in subjects
            if r["attendance_status"] in ("Low", "Critical")
        )
        ineligible = sum(
            1 for r in subjects
            if r["eligibility_status"] == "Not Eligible"
        )

        sem = semester_no if semester_no else None
        return {
            "student_id": student_id,
            "semester_no": sem,
            "overall_attendance_percentage": overall_pct,
            "total_classes": total_classes,
            "attended_classes": attended_classes,
            "subjects": subjects,
            "at_risk_subjects": at_risk,
            "ineligible_subjects": ineligible,
        }

    async def get_student_backlog_summary(
        self, student_id: str
    ) -> Dict[str, Any]:
        """Backlog details for a student.

        Grain: one row per failed subject (grade = 'F').
        """
        backlogs = await self._fetch(
            """
            SELECT
                p.subject_id,
                sub.subject_code,
                sub.subject_name,
                p.semester_no,
                p.percentage,
                p.grade
            FROM student_subject_performance p
            LEFT JOIN subjects sub ON sub.subject_id = p.subject_id
            WHERE p.student_id = $1
              AND p.grade = 'F'
            ORDER BY p.semester_no, p.subject_id
            """,
            student_id,
        )
        student = await self._fetchrow(
            "SELECT total_backlogs FROM students WHERE student_id = $1",
            student_id,
        )
        return {
            "student_id": student_id,
            "total_backlogs": student["total_backlogs"] if student else 0,
            "backlogs": backlogs,
        }

    # ==================================================================
    # B. Subject Analytics
    # ==================================================================

    async def get_subject_performance_summary(
        self,
        subject_id: str,
        *,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Aggregate performance metrics for a subject.

        Grain: one row per subject.
        Note: academic_year is not available on student_subject_performance,
        so it is accepted for API compatibility but not used in the query.
        """
        base = await self._fetchrow(
            """
            SELECT
                p.subject_id,
                sub.subject_code,
                sub.subject_name,
                $2::int AS semester_no,
                count(*)::int AS total_students,
                round(avg(p.percentage)::numeric, 2) AS average_percentage,
                round(percentile_cont(0.5)
                      WITHIN GROUP (ORDER BY p.percentage)::numeric, 2)
                    AS median_percentage,
                round(min(p.percentage)::numeric, 2) AS min_percentage,
                round(max(p.percentage)::numeric, 2) AS max_percentage,
                sum(CASE WHEN p.grade != 'F' THEN 1 ELSE 0 END)::int
                    AS pass_count,
                sum(CASE WHEN p.grade = 'F' THEN 1 ELSE 0 END)::int
                    AS fail_count
            FROM student_subject_performance p
            LEFT JOIN subjects sub ON sub.subject_id = p.subject_id
            WHERE p.subject_id = $1
              AND ($2::int IS NULL OR p.semester_no = $2)
            GROUP BY p.subject_id, sub.subject_code, sub.subject_name
            """,
            subject_id,
            semester_no,
        )
        if not base:
            return None

        result = dict(base)
        total = result["total_students"]
        result["pass_rate"] = (
            round(result["pass_count"] / total * 100, 2) if total else None
        )

        # Grade distribution
        grades = await self._fetch(
            """
            SELECT p.grade, count(*)::int AS count
            FROM student_subject_performance p
            WHERE p.subject_id = $1
              AND ($2::int IS NULL OR p.semester_no = $2)
            GROUP BY p.grade
            ORDER BY p.grade
            """,
            subject_id,
            semester_no,
        )
        result["grade_distribution"] = grades
        return result

    async def get_subject_attendance_summary(
        self,
        subject_id: str,
        *,
        semester_no: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Aggregate attendance for a subject.

        Grain: one row per subject.
        """
        result = await self._fetchrow(
            """
            SELECT
                a.subject_id,
                sub.subject_code,
                sub.subject_name,
                $2::int AS semester_no,
                count(*)::int AS total_students,
                round(avg(a.attendance_percentage)::numeric, 2)
                    AS average_attendance_percentage,
                sum(CASE WHEN a.eligibility_status = 'Eligible' THEN 1 ELSE 0 END)::int
                    AS eligible_count,
                sum(CASE WHEN a.eligibility_status = 'Not Eligible' THEN 1 ELSE 0 END)::int
                    AS ineligible_count,
                sum(CASE WHEN a.attendance_status IN ('Low', 'Critical') THEN 1 ELSE 0 END)::int
                    AS at_risk_count,
                sum(CASE WHEN a.shortage_flag = 'Yes' THEN 1 ELSE 0 END)::int
                    AS shortage_count
            FROM attendance a
            LEFT JOIN subjects sub ON sub.subject_id = a.subject_id
            WHERE a.subject_id = $1
              AND ($2::int IS NULL OR a.semester_no = $2)
            GROUP BY a.subject_id, sub.subject_code, sub.subject_name
            """,
            subject_id,
            semester_no,
        )
        return dict(result) if result else None

    async def get_subject_underperformers(
        self,
        subject_id: str,
        *,
        semester_no: Optional[int] = None,
        threshold: float = 40.0,
    ) -> Dict[str, Any]:
        """Students below a percentage threshold in a subject.

        Grain: one row per underperforming student.
        """
        students = await self._fetch(
            """
            SELECT
                p.student_id,
                s.full_name,
                p.percentage,
                p.grade,
                a.attendance_percentage
            FROM student_subject_performance p
            JOIN students s ON s.student_id = p.student_id
            LEFT JOIN attendance a
              ON a.student_id = p.student_id
             AND a.subject_id = p.subject_id
             AND a.semester_no = p.semester_no
            WHERE p.subject_id = $1
              AND ($2::int IS NULL OR p.semester_no = $2)
              AND p.percentage < $3
            ORDER BY p.percentage
            """,
            subject_id,
            semester_no,
            threshold,
        )
        return {
            "subject_id": subject_id,
            "semester_no": semester_no,
            "threshold": threshold,
            "total_flagged": len(students),
            "students": students,
        }

    # ==================================================================
    # C. Department / Semester Analytics
    # ==================================================================

    async def get_department_overview(
        self,
        *,
        department_code: Optional[int] = None,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
    ) -> Dict[str, Any]:
        """High-level department stats for a semester.

        Grain: one row per (department, semester).
        """
        row = await self._fetchrow(
            """
            SELECT
                $1::int AS department_code,
                (SELECT d.department_name FROM departments d
                 WHERE d.dept_code = $1) AS department_name,
                $2::int AS semester_no,
                $3::text AS academic_year,
                count(DISTINCT sem.student_id)::int AS total_students,
                round(avg(sem.semester_sgpa)::numeric, 2) AS average_sgpa,
                round(avg(sem.semester_percentage)::numeric, 2) AS average_percentage,
                round(avg(sem.semester_attendance_percentage)::numeric, 2)
                    AS average_attendance_percentage,
                COALESCE(sum(sem.backlog_count), 0)::int AS total_backlogs,
                sum(CASE WHEN sem.backlog_count > 0 THEN 1 ELSE 0 END)::int
                    AS students_with_backlogs
            FROM student_semester_summary sem
            JOIN students s ON s.student_id = sem.student_id
            WHERE ($1::int IS NULL OR s.department_code = $1)
              AND ($2::int IS NULL OR sem.semester_no = $2)
              AND ($3::text IS NULL OR sem.academic_year = $3)
            """,
            department_code,
            semester_no,
            academic_year,
        )
        return dict(row) if row else {}

    async def get_semester_performance_distribution(
        self,
        *,
        department_code: Optional[int] = None,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Distribution of students across performance bands.

        Bands: Top (>=90), Above Average (>=80), Average (>=60),
               Below Average (>=40), Low Performer (<40).
        """
        rows = await self._fetch(
            """
            WITH bands AS (
                SELECT
                    sem.student_id,
                    CASE
                        WHEN sem.semester_percentage >= 90 THEN 'Top'
                        WHEN sem.semester_percentage >= 80 THEN 'Above Average'
                        WHEN sem.semester_percentage >= 60 THEN 'Average'
                        WHEN sem.semester_percentage >= 40 THEN 'Below Average'
                        ELSE 'Low Performer'
                    END AS band
                FROM student_semester_summary sem
                JOIN students s ON s.student_id = sem.student_id
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND ($2::int IS NULL OR sem.semester_no = $2)
                  AND ($3::text IS NULL OR sem.academic_year = $3)
            ),
            counts AS (
                SELECT band, count(*)::int AS cnt
                FROM bands
                GROUP BY band
            ),
            total AS (
                SELECT sum(cnt)::int AS total FROM counts
            )
            SELECT c.band AS label, c.cnt AS count,
                   CASE WHEN t.total > 0
                        THEN round(c.cnt * 100.0 / t.total, 1)
                        ELSE 0 END AS percentage_of_total
            FROM counts c, total t
            ORDER BY
                CASE c.band
                    WHEN 'Top' THEN 1
                    WHEN 'Above Average' THEN 2
                    WHEN 'Average' THEN 3
                    WHEN 'Below Average' THEN 4
                    WHEN 'Low Performer' THEN 5
                END
            """,
            department_code,
            semester_no,
            academic_year,
        )
        total_students = await self._fetchval(
            """
            SELECT count(DISTINCT sem.student_id)::int
            FROM student_semester_summary sem
            JOIN students s ON s.student_id = sem.student_id
            WHERE ($1::int IS NULL OR s.department_code = $1)
              AND ($2::int IS NULL OR sem.semester_no = $2)
              AND ($3::text IS NULL OR sem.academic_year = $3)
            """,
            department_code,
            semester_no,
            academic_year,
        )
        return {
            "department_code": department_code,
            "semester_no": semester_no,
            "academic_year": academic_year,
            "total_students": total_students or 0,
            "buckets": rows,
        }

    async def get_attendance_distribution(
        self,
        *,
        department_code: Optional[int] = None,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Distribution of students across attendance bands.

        Bands: Excellent (>=90), Good (>=80), Average (>=75),
               Low (>=60), Critical (<60).
        """
        rows = await self._fetch(
            """
            WITH bands AS (
                SELECT DISTINCT
                    a.student_id,
                    a.subject_id,
                    a.attendance_percentage,
                    CASE
                        WHEN a.attendance_percentage >= 90 THEN 'Excellent'
                        WHEN a.attendance_percentage >= 80 THEN 'Good'
                        WHEN a.attendance_percentage >= 75 THEN 'Average'
                        WHEN a.attendance_percentage >= 60 THEN 'Low'
                        ELSE 'Critical'
                    END AS band
                FROM attendance a
                JOIN students s ON s.student_id = a.student_id
                LEFT JOIN student_semester_summary sem
                       ON sem.student_id = a.student_id
                      AND sem.semester_no = a.semester_no
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND ($2::int IS NULL OR a.semester_no = $2)
                  AND ($3::text IS NULL OR sem.academic_year = $3)
            ),
            counts AS (
                SELECT band, count(*)::int AS cnt
                FROM bands
                GROUP BY band
            ),
            total AS (
                SELECT sum(cnt)::int AS total FROM counts
            )
            SELECT c.band, c.cnt AS count,
                   CASE WHEN t.total > 0
                        THEN round(c.cnt * 100.0 / t.total, 1)
                        ELSE 0 END AS percentage_of_total
            FROM counts c, total t
            ORDER BY
                CASE c.band
                    WHEN 'Excellent' THEN 1
                    WHEN 'Good' THEN 2
                    WHEN 'Average' THEN 3
                    WHEN 'Low' THEN 4
                    WHEN 'Critical' THEN 5
                END
            """,
            department_code,
            semester_no,
            academic_year,
        )
        total_students = await self._fetchval(
            """
            SELECT count(DISTINCT a.student_id)::int
            FROM attendance a
            JOIN students s ON s.student_id = a.student_id
            LEFT JOIN student_semester_summary sem
                   ON sem.student_id = a.student_id
                  AND sem.semester_no = a.semester_no
            WHERE ($1::int IS NULL OR s.department_code = $1)
              AND ($2::int IS NULL OR a.semester_no = $2)
              AND ($3::text IS NULL OR sem.academic_year = $3)
            """,
            department_code,
            semester_no,
            academic_year,
        )
        return {
            "department_code": department_code,
            "semester_no": semester_no,
            "total_students": total_students or 0,
            "buckets": rows,
        }

    async def get_backlog_distribution(
        self, *, department_code: Optional[int] = None, academic_year: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Distribution of backlogs across the student population.

        Ranges: 0, 1-2, 3-5, 6-10, 11+.
        """
        # For backlog distribution, we need to filter by students who have semester records
        # in the specified academic year. If no academic_year is specified, use all students.
        if academic_year:
            rows = await self._fetch(
                """
                WITH banded AS (
                    SELECT
                        s.student_id,
                        CASE
                            WHEN s.total_backlogs = 0 THEN '0'
                            WHEN s.total_backlogs BETWEEN 1 AND 2 THEN '1-2'
                            WHEN s.total_backlogs BETWEEN 3 AND 5 THEN '3-5'
                            WHEN s.total_backlogs BETWEEN 6 AND 10 THEN '6-10'
                            ELSE '11+'
                        END AS backlog_range
                    FROM students s
                    WHERE ($1::int IS NULL OR s.department_code = $1)
                      AND EXISTS (
                          SELECT 1 FROM student_semester_summary sem
                          WHERE sem.student_id = s.student_id
                            AND sem.academic_year = $2
                      )
                ),
                counts AS (
                    SELECT backlog_range, count(*)::int AS cnt
                    FROM banded
                    GROUP BY backlog_range
                ),
                total AS (
                    SELECT sum(cnt)::int AS total FROM counts
                )
                SELECT c.backlog_range, c.cnt AS count,
                       CASE WHEN t.total > 0
                            THEN round(c.cnt * 100.0 / t.total, 1)
                            ELSE 0 END AS percentage_of_total
                FROM counts c, total t
                ORDER BY
                    CASE c.backlog_range
                        WHEN '0' THEN 1
                        WHEN '1-2' THEN 2
                        WHEN '3-5' THEN 3
                        WHEN '6-10' THEN 4
                        WHEN '11+' THEN 5
                    END
                """,
                department_code,
                academic_year,
            )
            total = await self._fetchval(
                """
                SELECT count(*)::int FROM students s
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND EXISTS (
                      SELECT 1 FROM student_semester_summary sem
                      WHERE sem.student_id = s.student_id
                        AND sem.academic_year = $2
                  )
                """,
                department_code,
                academic_year,
            )
            with_backlogs = await self._fetchval(
                """
                SELECT count(*)::int FROM students s
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND s.total_backlogs > 0
                  AND EXISTS (
                      SELECT 1 FROM student_semester_summary sem
                      WHERE sem.student_id = s.student_id
                        AND sem.academic_year = $2
                  )
                """,
                department_code,
                academic_year,
            )
        else:
            rows = await self._fetch(
                """
                WITH banded AS (
                    SELECT
                        s.student_id,
                        CASE
                            WHEN s.total_backlogs = 0 THEN '0'
                            WHEN s.total_backlogs BETWEEN 1 AND 2 THEN '1-2'
                            WHEN s.total_backlogs BETWEEN 3 AND 5 THEN '3-5'
                            WHEN s.total_backlogs BETWEEN 6 AND 10 THEN '6-10'
                            ELSE '11+'
                        END AS backlog_range
                    FROM students s
                    WHERE ($1::int IS NULL OR s.department_code = $1)
                ),
                counts AS (
                    SELECT backlog_range, count(*)::int AS cnt
                    FROM banded
                    GROUP BY backlog_range
                ),
                total AS (
                    SELECT sum(cnt)::int AS total FROM counts
                )
                SELECT c.backlog_range, c.cnt AS count,
                       CASE WHEN t.total > 0
                            THEN round(c.cnt * 100.0 / t.total, 1)
                            ELSE 0 END AS percentage_of_total
                FROM counts c, total t
                ORDER BY
                    CASE c.backlog_range
                        WHEN '0' THEN 1
                        WHEN '1-2' THEN 2
                        WHEN '3-5' THEN 3
                        WHEN '6-10' THEN 4
                        WHEN '11+' THEN 5
                    END
                """,
                department_code,
            )
            total = await self._fetchval(
                """
                SELECT count(*)::int FROM students
                WHERE ($1::int IS NULL OR department_code = $1)
                """,
                department_code,
            )
            with_backlogs = await self._fetchval(
                """
                SELECT count(*)::int FROM students
                WHERE ($1::int IS NULL OR department_code = $1)
                  AND total_backlogs > 0
                """,
                department_code,
            )
        return {
            "department_code": department_code,
            "total_students": total or 0,
            "students_with_backlogs": with_backlogs or 0,
            "buckets": rows,
        }

    # ==================================================================
    # D. At-Risk / Academic Gap Analytics (deterministic, rule-based)
    # ==================================================================

    async def get_at_risk_students(
        self,
        *,
        department_code: Optional[int] = None,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Identify students meeting at-risk conditions (rule-based).

        Rules (OR logic — any triggered reason flags the student):
          R1: overall_attendance_percentage < ATTENDANCE_THRESHOLD (75)
          R2: total_backlogs >= BACKLOG_THRESHOLD (2)
          R3: latest_sgpa < SGPA_THRESHOLD (6.0)
          R4: any subject with attendance_status in ('Low', 'Critical')
              in the specified semester
          R5: any subject with grade 'F' in the specified semester

        ``risk_score`` is a simple 0-100 health-like composite:
          score = 100 - (attendance_gap_weight + backlog_weight + sgpa_weight)
        where each component is 0-33.3 max.
        """
        att_thresh = settings.FACULTY_ATTENDANCE_THRESHOLD
        backlog_thresh = settings.FACULTY_MENTEE_BACKLOG_THRESHOLD
        sgpa_thresh = settings.FACULTY_MENTEE_SGPA_THRESHOLD

        # If academic_year is specified, filter students who have semester records in that year
        if academic_year:
            students = await self._fetch(
                """
                SELECT
                    s.student_id,
                    s.full_name,
                    s.department_code,
                    s.current_semester,
                    s.overall_cgpa,
                    s.latest_sgpa,
                    s.total_backlogs,
                    s.overall_attendance_percentage
                FROM students s
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND EXISTS (
                      SELECT 1 FROM student_semester_summary sem
                      WHERE sem.student_id = s.student_id
                        AND sem.academic_year = $2
                  )
                ORDER BY s.student_id
                """,
                department_code,
                academic_year,
            )
        else:
            students = await self._fetch(
                """
                SELECT
                    s.student_id,
                    s.full_name,
                    s.department_code,
                    s.current_semester,
                    s.overall_cgpa,
                    s.latest_sgpa,
                    s.total_backlogs,
                    s.overall_attendance_percentage
                FROM students s
                WHERE ($1::int IS NULL OR s.department_code = $1)
                ORDER BY s.student_id
                """,
                department_code,
            )

        flagged: List[Dict[str, Any]] = []
        for stu in students:
            reasons: List[str] = []
            att = stu["overall_attendance_percentage"]
            sgpa = stu["latest_sgpa"]
            backlogs = stu["total_backlogs"]

            if att is not None and att < att_thresh:
                reasons.append(
                    f"Attendance {att}% below threshold {att_thresh}%"
                )
            if backlogs >= backlog_thresh:
                reasons.append(
                    f"Backlogs {backlogs} >= threshold {backlog_thresh}"
                )
            if sgpa is not None and sgpa < sgpa_thresh:
                reasons.append(
                    f"SGPA {sgpa} below threshold {sgpa_thresh}"
                )

            # Semester-specific checks (optional)
            if semester_no is not None:
                low_att = await self._fetchval(
                    """
                    SELECT count(*)::int FROM attendance
                    WHERE student_id = $1
                      AND semester_no = $2
                      AND attendance_status IN ('Low', 'Critical')
                    """,
                    stu["student_id"],
                    semester_no,
                )
                if low_att:
                    reasons.append(
                        f"{low_att} subject(s) with Low/Critical attendance "
                        f"in semester {semester_no}"
                    )
                failed = await self._fetchval(
                    """
                    SELECT count(*)::int FROM student_subject_performance
                    WHERE student_id = $1
                      AND semester_no = $2
                      AND grade = 'F'
                    """,
                    stu["student_id"],
                    semester_no,
                )
                if failed:
                    reasons.append(
                        f"{failed} failed subject(s) in semester {semester_no}"
                    )

            if reasons:
                # Simple deterministic risk score
                att_val = float(att) if att else 0.0
                sgpa_val = float(sgpa) if sgpa else 0.0
                att_gap = max(0, (att_thresh - att_val)) / att_thresh * 33.3
                bl_gap = min(backlogs / 10, 1.0) * 33.3
                sgpa_gap = max(0, (sgpa_thresh - sgpa_val)) / sgpa_thresh * 33.3
                score = round(max(0, 100 - att_gap - bl_gap - sgpa_gap), 1)

                flagged.append({
                    "student_id": stu["student_id"],
                    "full_name": stu["full_name"],
                    "department_code": stu["department_code"],
                    "current_semester": stu["current_semester"],
                    "overall_cgpa": stu["overall_cgpa"],
                    "total_backlogs": backlogs,
                    "overall_attendance_percentage": att,
                    "risk_reasons": reasons,
                    "risk_score": score,
                })

        return {
            "department_code": department_code,
            "semester_no": semester_no,
            "total_flagged": len(flagged),
            "students": flagged,
        }

    async def get_students_below_attendance_threshold(
        self,
        *,
        department_code: Optional[int] = None,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
        threshold: float = 75.0,
    ) -> Dict[str, Any]:
        """Students below an attendance threshold in individual subjects.

        Grain: one row per (student, subject) below threshold.
        """
        students = await self._fetch(
            """
            SELECT
                a.student_id,
                s.full_name,
                a.subject_id,
                sub.subject_code,
                a.attendance_percentage,
                a.total_classes,
                a.attended_classes
            FROM attendance a
            JOIN students s ON s.student_id = a.student_id
            LEFT JOIN subjects sub ON sub.subject_id = a.subject_id
            LEFT JOIN student_semester_summary sem
                   ON sem.student_id = a.student_id
                  AND sem.semester_no = a.semester_no
            WHERE a.attendance_percentage < $1
              AND ($2::int IS NULL OR s.department_code = $2)
              AND ($3::int IS NULL OR a.semester_no = $3)
              AND ($4::text IS NULL OR sem.academic_year = $4)
            ORDER BY a.attendance_percentage
            """,
            threshold,
            department_code,
            semester_no,
            academic_year,
        )
        return {
            "threshold": threshold,
            "semester_no": semester_no,
            "total_flagged": len(students),
            "students": students,
        }

    async def get_subjects_needing_attention(
        self,
        *,
        department_code: Optional[int] = None,
        semester_no: Optional[int] = None,
        academic_year: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Subjects flagged for concerning metrics.

        Flags (any triggered reason includes the subject):
          - Average percentage below 50
          - Fail rate above 20%
          - Average attendance below 75%
        """
        # If academic_year is specified, filter by subjects that have records in that year
        # We need to join with student_semester_summary to filter by academic_year
        if academic_year:
            rows = await self._fetch(
                """
                SELECT
                    p.subject_id,
                    sub.subject_code,
                    sub.subject_name,
                    p.semester_no,
                    count(*)::int AS total_students,
                    round(avg(p.percentage)::numeric, 2) AS average_percentage,
                    round(
                        sum(CASE WHEN p.grade = 'F' THEN 1 ELSE 0 END)::numeric
                        / count(*)::numeric * 100, 2
                    ) AS fail_rate,
                    (SELECT round(avg(a.attendance_percentage)::numeric, 2)
                     FROM attendance a
                     WHERE a.subject_id = p.subject_id
                       AND a.semester_no = p.semester_no
                    ) AS average_attendance
                FROM student_subject_performance p
                JOIN students s ON s.student_id = p.student_id
                LEFT JOIN subjects sub ON sub.subject_id = p.subject_id
                JOIN student_semester_summary sem ON sem.student_id = p.student_id
                    AND sem.semester_no = p.semester_no
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND ($2::int IS NULL OR p.semester_no = $2)
                  AND sem.academic_year = $3
                GROUP BY p.subject_id, sub.subject_code, sub.subject_name,
                         p.semester_no
                """,
                department_code,
                semester_no,
                academic_year,
            )
        else:
            rows = await self._fetch(
                """
                SELECT
                    p.subject_id,
                    sub.subject_code,
                    sub.subject_name,
                    p.semester_no,
                    count(*)::int AS total_students,
                    round(avg(p.percentage)::numeric, 2) AS average_percentage,
                    round(
                        sum(CASE WHEN p.grade = 'F' THEN 1 ELSE 0 END)::numeric
                        / count(*)::numeric * 100, 2
                    ) AS fail_rate,
                    (SELECT round(avg(a.attendance_percentage)::numeric, 2)
                     FROM attendance a
                     WHERE a.subject_id = p.subject_id
                       AND a.semester_no = p.semester_no
                    ) AS average_attendance
                FROM student_subject_performance p
                JOIN students s ON s.student_id = p.student_id
                LEFT JOIN subjects sub ON sub.subject_id = p.subject_id
                WHERE ($1::int IS NULL OR s.department_code = $1)
                  AND ($2::int IS NULL OR p.semester_no = $2)
                GROUP BY p.subject_id, sub.subject_code, sub.subject_name,
                         p.semester_no
                """,
                department_code,
                semester_no,
            )

        flagged: List[Dict[str, Any]] = []
        for r in rows:
            reasons: List[str] = []
            avg_pct = r["average_percentage"]
            fail_rate = r["fail_rate"]
            avg_att = r["average_attendance"]

            if avg_pct is not None and avg_pct < 50:
                reasons.append(f"Average percentage {avg_pct}% below 50%")
            if fail_rate is not None and fail_rate > 20:
                reasons.append(f"Fail rate {fail_rate}% above 20%")
            if avg_att is not None and avg_att < 75:
                reasons.append(f"Average attendance {avg_att}% below 75%")

            if reasons:
                entry = dict(r)
                entry["reasons"] = reasons
                flagged.append(entry)

        return {
            "department_code": department_code,
            "semester_no": semester_no,
            "total_flagged": len(flagged),
            "subjects": flagged,
        }
