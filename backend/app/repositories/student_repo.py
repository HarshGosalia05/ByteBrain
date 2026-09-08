import asyncpg
from datetime import date
from typing import List, Optional, Dict, Any, Union


async def insert_student_messages(
    conn: asyncpg.Connection, notifications: List[Dict[str, Any]]
) -> int:
    """Insert notification rows inside an existing transaction.

    Deduplication contract (MD-05): ``event_id`` is a pure function of the
    underlying event; the partial unique indexes on (student_id, event_id) and
    (faculty_recipient_id, event_id) WHERE event_id IS NOT NULL guarantee
    at-most-one row per event per recipient, enforced here with
    ``ON CONFLICT DO NOTHING``. Rows without an event_id (e.g. human faculty
    messages) are never deduplicated.

    Each notification dict must carry exactly one recipient: ``student_id``
    (recipient_type 'student', the default) or ``faculty_recipient_id``
    (recipient_type 'faculty'). Faculty rows store no student id.
    """
    if not notifications:
        return 0
    inserted = 0
    for n in notifications:
        recipient_type = n.get("recipient_type", "student")
        if recipient_type == "faculty":
            result = await conn.execute(
                """
                INSERT INTO student_messages (
                    student_id, faculty_recipient_id, recipient_type, faculty_id,
                    subject, message_type, title, message_body, priority, status,
                    event_id, created_at
                ) VALUES (NULL,$1,'faculty',$2,$3,$4,$5,$6,$7,'Unread',$8,now())
                ON CONFLICT (faculty_recipient_id, event_id)
                WHERE event_id IS NOT NULL AND recipient_type = 'faculty'
                DO NOTHING
                """,
                n["faculty_recipient_id"],
                n.get("faculty_id"),
                n.get("subject"),
                n.get("message_type", "SYSTEM"),
                n.get("title", ""),
                n.get("message_body", ""),
                n.get("priority", "Normal"),
                n.get("event_id"),
            )
        else:
            result = await conn.execute(
                """
                INSERT INTO student_messages (
                    student_id, faculty_recipient_id, recipient_type, faculty_id,
                    subject, message_type, title, message_body, priority, status,
                    event_id, created_at
                ) VALUES ($1,NULL,'student',$2,$3,$4,$5,$6,$7,'Unread',$8,now())
                ON CONFLICT (student_id, event_id) WHERE event_id IS NOT NULL
                DO NOTHING
                """,
                n["student_id"],
                n.get("faculty_id"),
                n.get("subject"),
                n.get("message_type", "SYSTEM"),
                n.get("title", ""),
                n.get("message_body", ""),
                n.get("priority", "Normal"),
                n.get("event_id"),
            )
        if result.endswith(" 1"):
            inserted += 1
    return inserted


class StudentRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_student_term_context(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Current-term context used by the daily assistant and timetable.

        MD-04: timetable stitching keys are the student's department, current
        semester, and current academic year. The stored academic year uses the
        short form (``2026-27``) while the timetable table uses the long form
        (``2026-2027``), so year matching is done on the shared 4-digit prefix.
        """
        query = """
            SELECT
                s.student_id, s.department_code, s.department_name,
                s.current_semester, s.current_academic_year,
                s.overall_attendance_percentage
            FROM students s
            WHERE s.student_id = $1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, student_id)
            return dict(row) if row else None

    async def get_student_timetable(
        self,
        department_code: int,
        semester_no: int,
        year_prefix: str,
    ) -> Dict[str, Any]:
        """Department-scoped weekly timetable sessions for the student's term."""
        query = """
            SELECT
                wt.timetable_id, wt.day_name, wt.slot_no, wt.start_time, wt.end_time,
                wt.subject_id, wt.subject_name, wt.faculty_id, wt.lecture_type,
                wt.academic_year,
                s.subject_code, s.credits,
                f.full_name AS faculty_name
            FROM weekly_timetable_07 wt
            LEFT JOIN subjects s ON s.subject_id = wt.subject_id
            LEFT JOIN faculty f ON f.faculty_id = wt.faculty_id
            WHERE wt.department_code = $1
                AND wt.semester_no = $2
                AND LEFT(wt.academic_year, 4) = $3
            ORDER BY wt.slot_no, wt.start_time
        """
        slots_query = """
            SELECT DISTINCT slot_no, start_time, end_time
            FROM weekly_timetable_07
            WHERE department_code = $1
                AND semester_no = $2
                AND LEFT(academic_year, 4) = $3
            ORDER BY slot_no, start_time
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, department_code, semester_no, year_prefix)
            slots = await conn.fetch(slots_query, department_code, semester_no, year_prefix)
            return {
                "sessions": [dict(row) for row in rows],
                "slots": [dict(row) for row in slots],
            }

    async def get_recorded_day_name(self, student_id: str, focus_date: date) -> Optional[str]:
        """Stored day label for a lecture date, if any record exists for it.

        MD-04 day/time handling: the institution's recorded ``day_name`` is the
        ground truth for a date when daily records exist; otherwise the calendar
        weekday is used. This keeps the assistant aligned with seeded data.
        """
        query = """
            SELECT day_name
            FROM daily_attendance_07
            WHERE student_id = $1 AND lecture_date = $2::date
            ORDER BY lecture_date
            LIMIT 1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, student_id, focus_date)
            return row["day_name"] if row else None

    async def get_daily_statuses(
        self,
        student_id: str,
        focus_date: date,
        subject_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """Recorded lecture statuses for a student/date/subject set.

        Only actually recorded rows are returned. A missing row means the
        lecture was not recorded — it is never interpreted as absence.
        """
        query = """
            SELECT subject_id, attendance_status
            FROM daily_attendance_07
            WHERE student_id = $1
                AND lecture_date = $2::date
                AND subject_id = ANY($3::text[])
            ORDER BY lecture_number ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, student_id, focus_date, subject_ids)
            return [dict(row) for row in rows]

    async def get_semester_attendance(
        self, student_id: str, semester_no: int
    ) -> List[Dict[str, Any]]:
        """Authoritative per-subject attendance plus performance for a semester."""
        query = """
            SELECT
                sse.subject_id, sse.subject_code, sse.subject_name, sse.credits,
                a.total_classes, a.attended_classes, a.attendance_percentage,
                a.attendance_status, a.eligibility_status, a.shortage_flag,
                sp.percentage AS performance_percentage, sp.grade, sp.result_status
            FROM student_subject_enrollment sse
            LEFT JOIN attendance a
                ON a.enrollment_record_id = sse.enrollment_record_id
            LEFT JOIN student_subject_performance sp
                ON sp.enrollment_record_id = sse.enrollment_record_id
            WHERE sse.student_id = $1
                AND sse.semester_no = $2
                AND (a.student_id = $1 OR a.student_id IS NULL)
            ORDER BY sse.subject_name ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, student_id, semester_no)
            return [dict(row) for row in rows]

    async def get_class_benchmark_averages(
        self,
        department_code: Union[int, str],
        exclude_student_id: str,
        subject_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """Peer-only aggregate percentages for a subject/semester/year cohort.

        MD-03 feature 5: aggregates are computed over the authenticated
        student's department and explicitly EXCLUDE the student's own record so
        the benchmark stays a classmate average. Only aggregate statistics are
        returned — no peer identity ever crosses this boundary.
        """
        dept_code_int = 1
        if isinstance(department_code, int):
            dept_code_int = department_code
        elif isinstance(department_code, str):
            cleaned = department_code.strip()
            if cleaned.isdigit():
                dept_code_int = int(cleaned)
            elif cleaned.upper() == "CSE":
                dept_code_int = 1
            elif cleaned.upper() == "BBA":
                dept_code_int = 2
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
            WHERE sse.department_code = $1::int
              AND sp.student_id <> $2
              AND sp.percentage IS NOT NULL
              AND sse.subject_id = ANY($3::text[])
            GROUP BY sse.subject_id, sse.semester_no, sse.academic_year
            ORDER BY sse.semester_no ASC, sse.subject_id ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, dept_code_int, exclude_student_id, subject_ids)
            return [dict(row) for row in rows]

    async def get_student_profile(self, student_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT
                s.student_id, s.first_name, s.last_name,
                s.enrollment_no, s.admission_year, s.current_semester,
                s.department_name, s.department_code,
                s.current_academic_year, s.latest_sgpa, s.overall_cgpa,
                s.overall_percentage, s.overall_attendance_percentage,
                s.total_credits_registered, s.total_credits_earned,
                s.total_backlogs, s.academic_standing
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
                semester_total_marks,
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

    # ------------------------------------------------------------------
    # MD-05 personal goals
    # ------------------------------------------------------------------

    @staticmethod
    def _goal(row: asyncpg.Record) -> Dict[str, Any]:
        return {
            "goal_id": str(row["goal_id"]),
            "student_id": row["student_id"],
            "goal_type": row["goal_type"],
            "target_value": float(row["target_value"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    async def get_goals(self, student_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT goal_id, student_id, goal_type, target_value, status,
                   created_at, updated_at
            FROM student_goals
            WHERE student_id = $1
            ORDER BY created_at ASC, goal_type ASC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, student_id)
            return [self._goal(row) for row in rows]

    async def get_goal(self, student_id: str, goal_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT goal_id, student_id, goal_type, target_value, status,
                   created_at, updated_at
            FROM student_goals
            WHERE student_id = $1 AND goal_id = $2::uuid
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, student_id, goal_id)
            return self._goal(row) if row else None

    async def create_goal(
        self, student_id: str, goal_type: str, target_value: float
    ) -> Optional[Dict[str, Any]]:
        """Insert a goal. When an Active goal of the same type already exists
        (partial unique index), the insert is a no-op and None is returned so
        the service can surface a clear, typed error."""
        query = """
            INSERT INTO student_goals (student_id, goal_type, target_value, status)
            VALUES ($1, $2, $3, 'Active')
            ON CONFLICT (student_id, goal_type) WHERE status = 'Active'
            DO NOTHING
            RETURNING goal_id, student_id, goal_type, target_value, status,
                      created_at, updated_at
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, student_id, goal_type, target_value)
            return self._goal(row) if row else None

    async def update_goal(
        self,
        student_id: str,
        goal_id: str,
        target_value: Optional[float] = None,
        status: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Ownership-scoped update. Returns None when the goal does not belong
        to the student or when activating a goal would collide with an already
        Active goal of the same type."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if status == "Active":
                    existing = await conn.fetchval(
                        """
                        SELECT goal_id FROM student_goals
                        WHERE student_id = $1 AND goal_type = (
                            SELECT goal_type FROM student_goals WHERE goal_id = $2::uuid
                        ) AND status = 'Active' AND goal_id <> $2::uuid
                        """,
                        student_id, goal_id,
                    )
                    if existing:
                        return None
                sets = ["updated_at = now()"]
                params: List[Any] = []
                if target_value is not None:
                    params.append(target_value)
                    sets.append(f"target_value = ${len(params)}")
                if status is not None:
                    params.append(status)
                    sets.append(f"status = ${len(params)}")
                params.extend([student_id, goal_id])
                row = await conn.fetchrow(
                    f"""
                    UPDATE student_goals
                    SET {", ".join(sets)}
                    WHERE student_id = ${len(params) - 1}
                        AND goal_id = ${len(params)}::uuid
                    RETURNING goal_id, student_id, goal_type, target_value,
                              status, created_at, updated_at
                    """,
                    *params,
                )
                return self._goal(row) if row else None

    async def delete_goal(self, student_id: str, goal_id: str) -> bool:
        """Delete a goal. Returns True if a row was deleted."""
        query = """
            DELETE FROM student_goals
            WHERE student_id = $1 AND goal_id = $2::uuid
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, student_id, goal_id)
            return result.endswith("1")

    # ------------------------------------------------------------------
    # MD-05 notifications
    # ------------------------------------------------------------------

    @staticmethod
    def _notification(row: asyncpg.Record) -> Dict[str, Any]:
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

    async def get_notifications(
        self,
        student_id: str,
        message_type: Optional[str] = None,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        params: List[Any] = [student_id]
        filters = ["student_id = $1"]
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
                WHERE student_id = $1 AND status = 'Unread'
                """,
                student_id,
            )
        return {
            "items": [self._notification(row) for row in rows],
            "total": int(total),
            "unread_count": int(unread_count),
        }

    async def get_unread_count(self, student_id: str) -> int:
        async with self.pool.acquire() as conn:
            value = await conn.fetchval(
                """
                SELECT count(*) FROM student_messages
                WHERE student_id = $1 AND status = 'Unread'
                """,
                student_id,
            )
            return int(value)

    async def mark_notification_read(
        self, student_id: str, message_id: str
    ) -> Optional[Dict[str, Any]]:
        """Ownership-scoped read toggle. Returns None for unknown/foreign ids."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE student_messages
                SET status = 'Read'
                WHERE student_id = $1 AND message_id = $2::uuid
                RETURNING message_id, message_type, title, message_body,
                          subject, priority, status, created_at
                """,
                student_id, message_id,
            )
            return self._notification(row) if row else None

    async def mark_all_notifications_read(self, student_id: str) -> int:
        """Mark every unread student notification read; returns rows affected."""
        async with self.pool.acquire() as conn:
            value = await conn.fetchval(
                """
                WITH upd AS (
                    UPDATE student_messages
                    SET status = 'Read'
                    WHERE student_id = $1 AND status = 'Unread'
                    RETURNING 1
                )
                SELECT count(*) FROM upd
                """,
                student_id,
            )
            return int(value)

    async def delete_notification(
        self, student_id: str, message_id: str
    ) -> Optional[Dict[str, Any]]:
        """Ownership-scoped clear (hard delete). Returns None for unknown ids."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                DELETE FROM student_messages
                WHERE student_id = $1 AND message_id = $2::uuid
                RETURNING message_id, message_type, title, message_body,
                          subject, priority, status, created_at
                """,
                student_id, message_id,
            )
            return self._notification(row) if row else None

    async def delete_all_notifications(self, student_id: str) -> int:
        """Clear every notification for the student; returns rows deleted."""
        async with self.pool.acquire() as conn:
            value = await conn.fetchval(
                """
                WITH del AS (
                    DELETE FROM student_messages
                    WHERE student_id = $1
                    RETURNING 1
                )
                SELECT count(*) FROM del
                """,
                student_id,
            )
            return int(value)

    # ------------------------------------------------------------------
    # MD-06 career intelligence
    # ------------------------------------------------------------------

    async def get_career_preferences(
        self, student_id: str
    ) -> Optional[Dict[str, Any]]:
        """Most recent career survey response for the student, if any.

        Survey data is student-scoped and read-only; the most recent response
        wins when multiple surveys exist (``survey_date`` descending).
        """
        query = """
            SELECT preferred_domain, dream_job_role, preferred_industry,
                   preferred_work_mode, target_package_lpa,
                   higher_studies_interest, entrepreneurship_interest,
                   certification_interest, internship_completed,
                   placement_readiness_level, survey_date
            FROM career_preferences
            WHERE student_id = $1
            ORDER BY survey_date DESC NULLS LAST
            LIMIT 1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, student_id)
            return dict(row) if row else None