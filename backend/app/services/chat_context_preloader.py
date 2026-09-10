"""Chat Context Preloader: ETL-style role-specific portal data aggregation.

Extracts, transforms, and loads a compact portal-data snapshot for each role
(Student / Faculty / Admin) when the chatbot is opened. This snapshot is
used by the chatbot to:
  1. Pre-populate role-aware context so the LLM can give better answers
  2. Generate dynamic, context-aware suggested queries
  3. Provide a rich welcome message showing the user's current portal state
  4. Enable the LLM to reference live data without per-query tool calls

The preloader runs at chat-open time (not per-message) to keep latency low.
Each query is tightly scoped:
  - Student: own profile + academic + attendance + subjects + career
  - Faculty: own profile + subjects taught + mentees + flagged students
  - Admin: institution-wide summary + department performance + trends
"""
from __future__ import annotations

import logging
from typing import Any

import asyncpg

from app.schemas.chat_context import (
    AdminPortalContext,
    ChatContextResponse,
    FacultyPortalContext,
    StudentPortalContext,
)

logger = logging.getLogger(__name__)

# Hard timeout per individual query to prevent slow queries from blocking context load
QUERY_TIMEOUT_SECONDS = 8


class ChatContextPreloader:
    """ETL pipeline: Extract -> Transform -> Load portal context per role."""

    def __init__(self, pool: asyncpg.Pool | None = None) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # Student context
    # ------------------------------------------------------------------

    async def _student_profile(self, conn: asyncpg.Connection, student_id: str) -> dict[str, Any]:
        row = await conn.fetchrow(
            """
            SELECT first_name, last_name, enrollment_no, department_name,
                   current_semester, current_academic_year, latest_sgpa,
                   overall_cgpa, overall_percentage, total_backlogs,
                   academic_standing, overall_attendance_percentage
            FROM students WHERE student_id = $1
            """,
            student_id,
        )
        if not row:
            return {}
        first = row["first_name"] or ""
        last = row["last_name"] or ""
        name = f"{first} {last}".strip() or None
        return {
            "name": name,
            "enrollment_no": row["enrollment_no"],
            "department": row["department_name"],
            "current_semester": row["current_semester"],
            "academic_year": row["current_academic_year"],
            "cgpa": float(row["overall_cgpa"]) if row["overall_cgpa"] is not None else None,
            "sgpa": float(row["latest_sgpa"]) if row["latest_sgpa"] is not None else None,
            "percentage": float(row["overall_percentage"]) if row["overall_percentage"] is not None else None,
            "backlogs": row["total_backlogs"],
            "academic_standing": row["academic_standing"],
            "overall_attendance": float(row["overall_attendance_percentage"]) if row["overall_attendance_percentage"] is not None else None,
        }

    async def _student_subjects(self, conn: asyncpg.Connection, student_id: str) -> tuple[list[dict], list[dict]]:
        """Top and weak subjects from latest semester subject performance."""
        rows = await conn.fetch(
            """
            SELECT subj.subject_name, sp.percentage, sp.grade
            FROM student_subject_performance sp
            JOIN student_subject_enrollment sse ON sse.enrollment_record_id = sp.enrollment_record_id
            JOIN subjects subj ON subj.subject_id = sse.subject_id
            WHERE sse.student_id = $1 AND sp.percentage IS NOT NULL
              AND sse.semester_no = (SELECT MAX(semester_no) FROM student_subject_enrollment WHERE student_id = $1)
            ORDER BY sp.percentage DESC
            LIMIT 20
            """,
            student_id,
        )
        all_subjects = [{"name": r["subject_name"], "percentage": float(r["percentage"]), "grade": r["grade"]} for r in rows]
        top = all_subjects[:3]
        weak = [s for s in reversed(all_subjects) if s["percentage"] < 60][:3]
        return top, weak

    async def _student_predictions(self, conn: asyncpg.Connection, student_id: str) -> dict[str, Any]:
        """Compact prediction summary from ml_predictions or risk_predictions."""
        rows = await conn.fetch(
            """
            SELECT prediction_type, prediction_status, predicted_value
            FROM ml_predictions
            WHERE student_id = $1
            ORDER BY created_at DESC NULLS LAST
            LIMIT 8
            """,
            student_id,
        )
        if not rows:
            return {"available": False}
        preds = {}
        for r in rows:
            ptype = r["prediction_type"]
            if ptype not in preds:
                preds[ptype] = {
                    "type": ptype,
                    "status": r["prediction_status"],
                }
        return {"available": True, "predictions": list(preds.values())}

    async def _student_career(self, conn: asyncpg.Connection, student_id: str) -> dict[str, Any]:
        row = await conn.fetchrow(
            """
            SELECT preferred_domain, dream_job_role, internship_completed,
                   placement_readiness_level
            FROM career_preferences
            WHERE student_id = $1 ORDER BY survey_date DESC NULLS LAST LIMIT 1
            """,
            student_id,
        )
        if not row:
            return {"available": False}
        return {
            "available": True,
            "domain": row["preferred_domain"],
            "dream_role": row["dream_job_role"],
            "internship": row["internship_completed"],
            "readiness": row["placement_readiness_level"],
        }

    async def _student_upcoming_classes(self, conn: asyncpg.Connection, student_id: str) -> list[dict]:
        """Next 3 classes from timetable."""
        rows = await conn.fetch(
            """
            SELECT tt.day_name, tt.start_time, tt.end_time,
                   subj.subject_name, tt.lecture_type
            FROM weekly_timetable tt
            JOIN student_subject_enrollment sse ON sse.subject_id = tt.subject_id
            JOIN subjects subj ON subj.subject_id = tt.subject_id
            WHERE sse.student_id = $1
              AND sse.semester_no = (SELECT current_semester FROM students WHERE student_id = $1)
            ORDER BY
              CASE tt.day_name
                WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6
                ELSE 7
              END,
              tt.start_time
            LIMIT 5
            """,
            student_id,
        )
        return [
            {
                "day": r["day_name"],
                "time": str(r["start_time"])[:5] if r["start_time"] else None,
                "subject": r["subject_name"],
                "type": r["lecture_type"],
            }
            for r in rows
        ]

    async def _student_notifications(self, conn: asyncpg.Connection, student_id: str) -> list[dict]:
        rows = await conn.fetch(
            """
            SELECT title, message_body, priority, created_at
            FROM student_messages
            WHERE student_id = $1 AND status = 'Unread'
            ORDER BY created_at DESC LIMIT 3
            """,
            student_id,
        )
        return [
            {"title": r["title"], "body": r["message_body"][:100], "priority": r["priority"]}
            for r in rows
        ]

    async def build_student_context(self, student_id: str) -> StudentPortalContext:
        if not self._pool:
            return StudentPortalContext()
        try:
            async with self._pool.acquire() as conn:
                profile = await self._student_profile(conn, student_id)
                if not profile.get("name"):
                    return StudentPortalContext(data_available=False, note="Student profile not found")
                top, weak = await self._student_subjects(conn, student_id)
                predictions = await self._student_predictions(conn, student_id)
                career = await self._student_career(conn, student_id)
                upcoming = await self._student_upcoming_classes(conn, student_id)
                notifications = await self._student_notifications(conn, student_id)
                return StudentPortalContext(
                    name=profile["name"],
                    enrollment_no=profile["enrollment_no"],
                    department=profile["department"],
                    current_semester=profile["current_semester"],
                    academic_year=profile["academic_year"],
                    cgpa=profile["cgpa"],
                    sgpa=profile["sgpa"],
                    percentage=profile["percentage"],
                    backlogs=profile["backlogs"],
                    academic_standing=profile["academic_standing"],
                    overall_attendance=profile["overall_attendance"],
                    top_subjects=top,
                    weak_subjects=weak,
                    prediction_summary=predictions,
                    career_readiness=career,
                    upcoming_classes=upcoming,
                    recent_notifications=notifications,
                )
        except Exception as exc:
            logger.warning("Student context load failed: %s", exc)
            return StudentPortalContext(data_available=False, note="Failed to load student context")

    # ------------------------------------------------------------------
    # Faculty context
    # ------------------------------------------------------------------

    async def _faculty_profile(self, conn: asyncpg.Connection, faculty_id: str) -> dict[str, Any]:
        row = await conn.fetchrow(
            """
            SELECT full_name, department_name, designation
            FROM faculty WHERE faculty_id = $1
            """,
            faculty_id,
        )
        if not row:
            return {}
        return {
            "name": row["full_name"],
            "department": row["department_name"],
            "designation": row["designation"],
        }

    async def _faculty_subjects(self, conn: asyncpg.Connection, faculty_id: str) -> list[dict]:
        rows = await conn.fetch(
            """
            SELECT DISTINCT subj.subject_name, subj.subject_code, sse.semester_no
            FROM student_subject_enrollment sse
            JOIN subjects subj ON subj.subject_id = sse.subject_id
            WHERE sse.faculty_id = $1
            ORDER BY sse.semester_no DESC, subj.subject_name
            LIMIT 10
            """,
            faculty_id,
        )
        return [
            {"name": r["subject_name"], "code": r["subject_code"], "semester": r["semester_no"]}
            for r in rows
        ]

    async def _faculty_mentee_count(self, conn: asyncpg.Connection, faculty_id: str) -> int:
        return await conn.fetchval(
            """
            SELECT COUNT(*) FROM faculty_student_map
            WHERE faculty_id = $1 AND status = 'Active'
            """,
            faculty_id,
        ) or 0

    async def _faculty_flagged(self, conn: asyncpg.Connection, faculty_id: str) -> list[dict]:
        rows = await conn.fetch(
            """
            SELECT s.student_id, s.first_name, s.last_name, s.overall_cgpa,
                   s.total_backlogs, s.academic_standing
            FROM faculty_student_map fsm
            JOIN students s ON s.student_id = fsm.student_id
            WHERE fsm.faculty_id = $1 AND fsm.status = 'Active'
              AND (
                s.total_backlogs > 0
                OR s.academic_standing IN ('Probation', 'Detained', 'At Risk')
                OR s.overall_cgpa < 6.0
              )
            ORDER BY s.overall_cgpa ASC NULLS LAST
            LIMIT 10
            """,
            faculty_id,
        )
        return [
            {
                "id": r["student_id"],
                "name": f"{r['first_name']} {r['last_name']}",
                "cgpa": float(r["overall_cgpa"]) if r["overall_cgpa"] is not None else None,
                "backlogs": r["total_backlogs"],
                "standing": r["academic_standing"],
            }
            for r in rows
        ]

    async def _faculty_class_summary(self, conn: asyncpg.Connection, faculty_id: str) -> dict[str, Any]:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT s.student_id) AS total_students,
                AVG(s.overall_cgpa) AS avg_cgpa,
                AVG(s.overall_attendance_percentage) AS avg_attendance
            FROM faculty_student_map fsm
            JOIN students s ON s.student_id = fsm.student_id
            WHERE fsm.faculty_id = $1 AND fsm.status = 'Active'
            """,
            faculty_id,
        )
        if not row:
            return {}
        return {
            "total_students": row["total_students"],
            "avg_cgpa": float(row["avg_cgpa"]) if row["avg_cgpa"] is not None else None,
            "avg_attendance": float(row["avg_attendance"]) if row["avg_attendance"] is not None else None,
        }

    async def build_faculty_context(self, faculty_id: str) -> FacultyPortalContext:
        if not self._pool:
            return FacultyPortalContext()
        try:
            async with self._pool.acquire() as conn:
                profile = await self._faculty_profile(conn, faculty_id)
                if not profile.get("name"):
                    return FacultyPortalContext(data_available=False, note="Faculty profile not found")
                subjects = await self._faculty_subjects(conn, faculty_id)
                mentee_count = await self._faculty_mentee_count(conn, faculty_id)
                flagged = await self._faculty_flagged(conn, faculty_id)
                class_summary = await self._faculty_class_summary(conn, faculty_id)
                return FacultyPortalContext(
                    name=profile["name"],
                    department=profile["department"],
                    designation=profile["designation"],
                    subjects_taught=subjects,
                    total_mentees=mentee_count,
                    flagged_students=flagged,
                    class_summary=class_summary,
                )
        except Exception as exc:
            logger.warning("Faculty context load failed: %s", exc)
            return FacultyPortalContext(data_available=False, note="Failed to load faculty context")

    # ------------------------------------------------------------------
    # Admin context
    # ------------------------------------------------------------------

    async def _admin_institution(self, conn: asyncpg.Connection) -> dict[str, Any]:
        row = await conn.fetchrow(
            """
            SELECT
                (SELECT COUNT(*) FROM students) AS total_students,
                (SELECT COUNT(*) FROM faculty) AS total_faculty,
                (SELECT COUNT(*) FROM departments) AS total_departments,
                (SELECT AVG(overall_cgpa) FROM students) AS avg_cgpa,
                (SELECT AVG(overall_attendance_percentage) FROM students) AS avg_attendance
            """
        )
        if not row:
            return {}
        return {
            "total_students": row["total_students"],
            "total_faculty": row["total_faculty"],
            "total_departments": row["total_departments"],
            "avg_cgpa": float(row["avg_cgpa"]) if row["avg_cgpa"] is not None else None,
            "avg_attendance": float(row["avg_attendance"]) if row["avg_attendance"] is not None else None,
        }

    async def _admin_departments(self, conn: asyncpg.Connection) -> list[dict]:
        rows = await conn.fetch(
            """
            SELECT d.department_name,
                   COUNT(DISTINCT s.student_id) AS student_count,
                   AVG(s.overall_cgpa) AS avg_cgpa,
                   AVG(s.overall_attendance_percentage) AS avg_attendance
            FROM departments d
            LEFT JOIN students s ON s.department_code = d.dept_code
            GROUP BY d.dept_code, d.department_name
            ORDER BY d.department_name
            """
        )
        return [
            {
                "name": r["department_name"],
                "students": r["student_count"],
                "avg_cgpa": float(r["avg_cgpa"]) if r["avg_cgpa"] is not None else None,
                "avg_attendance": float(r["avg_attendance"]) if r["avg_attendance"] is not None else None,
            }
            for r in rows
        ]

    async def _admin_flagged_count(self, conn: asyncpg.Connection) -> int:
        return await conn.fetchval(
            """
            SELECT COUNT(DISTINCT student_id) FROM students
            WHERE total_backlogs > 0
               OR academic_standing IN ('Probation', 'Detained', 'At Risk')
            """
        ) or 0

    async def build_admin_context(self) -> AdminPortalContext:
        if not self._pool:
            return AdminPortalContext()
        try:
            async with self._pool.acquire() as conn:
                inst = await self._admin_institution(conn)
                depts = await self._admin_departments(conn)
                flagged = await self._admin_flagged_count(conn)
                return AdminPortalContext(
                    institution_name="CampusX Institution",
                    total_students=inst.get("total_students"),
                    total_faculty=inst.get("total_faculty"),
                    total_departments=inst.get("total_departments"),
                    overall_cgpa=inst.get("avg_cgpa"),
                    overall_attendance=inst.get("avg_attendance"),
                    flagged_count=flagged,
                    department_performance=depts,
                )
        except Exception as exc:
            logger.warning("Admin context load failed: %s", exc)
            return AdminPortalContext(data_available=False, note="Failed to load admin context")

    # ------------------------------------------------------------------
    # Unified entry point
    # ------------------------------------------------------------------

    async def load(
        self,
        role: str,
        user_context_id: str,
    ) -> ChatContextResponse:
        """Load role-specific portal context snapshot."""
        if role == "Student":
            student_ctx = await self.build_student_context(user_context_id)
            return ChatContextResponse(
                role="Student",
                student=student_ctx,
                data_available=student_ctx.name is not None,
                note=student_ctx.note if not student_ctx.name else None,
            )
        if role == "Faculty":
            faculty_ctx = await self.build_faculty_context(user_context_id)
            return ChatContextResponse(
                role="Faculty",
                faculty=faculty_ctx,
                data_available=faculty_ctx.name is not None,
                note=faculty_ctx.note if not faculty_ctx.name else None,
            )
        if role == "Admin":
            admin_ctx = await self.build_admin_context()
            return ChatContextResponse(
                role="Admin",
                admin=admin_ctx,
                data_available=admin_ctx.total_students is not None,
                note=admin_ctx.note,
            )
        return ChatContextResponse(
            role="Student",
            data_available=False,
            note=f"Unsupported role: {role}",
        )
