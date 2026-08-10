"""Service-level tests for MD-05 (health score / priorities / goals / notifications).

Uses a fake asyncpg pool that records the executed SQL, so no live database is
required. Verifies ownership routing (404s), goal conflict handling (409),
validation (422), idempotent read marking, and response schema shaping.
"""

import asyncio
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException

from app.schemas.student_md05 import (
    GoalsResponse,
    HealthScoreResponse,
    NotificationItem,
    NotificationsResponse,
    PrioritiesResponse,
    StudentGoal,
    UnreadCountResponse,
)
from app.services.student_service import StudentService

NOW = datetime.now(timezone.utc)


class _TransactionContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConn:
    def __init__(
        self,
        fetch_sequence=None,
        fetchrow_sequence=None,
        fetchval_sequence=None,
    ):
        self.fetch_sequence = list(fetch_sequence or [])
        self.fetchrow_sequence = list(fetchrow_sequence or [])
        self.fetchval_sequence = list(fetchval_sequence or [])
        self.executed = []  # list of (kind, query, args)

    async def fetch(self, query, *args):
        self.executed.append(("fetch", query, args))
        if self.fetch_sequence:
            return self.fetch_sequence.pop(0)
        return []

    async def fetchrow(self, query, *args):
        self.executed.append(("fetchrow", query, args))
        if self.fetchrow_sequence:
            return self.fetchrow_sequence.pop(0)
        return None

    async def fetchval(self, query, *args):
        self.executed.append(("fetchval", query, args))
        if self.fetchval_sequence:
            return self.fetchval_sequence.pop(0)
        return 0

    def transaction(self):
        return _TransactionContext(self)


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _AcquireContext(self.conn)


class _AcquireContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


def run(coro):
    return asyncio.run(coro)


def profile_row(**overrides):
    row = {
        "student_id": "STU-A",
        "first_name": "Alice",
        "last_name": "Appleton",
        "enrollment_no": 1001,
        "admission_year": 2023,
        "current_semester": 7,
        "department_name": "Computer Science",
        "department_code": "CSE",
        "current_academic_year": "2026-27",
        "latest_sgpa": 8.4,
        "overall_cgpa": 8.1,
        "overall_percentage": 72.5,
        "overall_attendance_percentage": None,
        "total_credits_registered": 60,
        "total_credits_earned": 45,
        "total_backlogs": 0,
        "academic_standing": "Good",
    }
    row.update(overrides)
    return row


def summary_row(**overrides):
    row = {
        "semester": 1,
        "sgpa": 8.1,
        "total_credits_earned": 24,
        "attendance_percentage": 88.0,
        "active_backlogs": 0,
        "academic_year": "2023-24",
        "subjects_registered": 6,
        "credits_registered": 24,
        "semester_percentage": 72.0,
        "semester_grade": "A",
        "semester_result": "Pass",
        "academic_standing": "Good",
    }
    row.update(overrides)
    return row


def perf_row(**overrides):
    row = {
        "semester": 7,
        "subject_id": "SUBJ-X",
        "subject_code": "CSE700",
        "subject_name": "Subject X",
        "credits": 4,
        "academic_year": "2026-27",
        "internal_marks": None,
        "mid_sem_marks": None,
        "end_sem_marks": None,
        "total_marks": None,
        "percentage": None,
        "grade": None,
        "grade_point": None,
        "result_status": None,
        "attempt_number": 1,
        "performance_category": None,
        "remarks": None,
        "attendance_percentage": 85.0,
        "updated_at": None,
    }
    row.update(overrides)
    return row


def attendance_row(**overrides):
    row = {
        "subject_id": "SUBJ-DL",
        "subject_code": "CSE704",
        "subject_name": "Deep Learning",
        "credits": 4,
        "total_classes": 40,
        "attended_classes": 30,
        "attendance_percentage": 75.0,
        "attendance_status": "OK",
        "eligibility_status": "Eligible",
        "shortage_flag": None,
        "performance_percentage": None,
        "grade": None,
        "result_status": None,
    }
    row.update(overrides)
    return row


def goal_row(**overrides):
    row = {
        "goal_id": "11111111-1111-1111-1111-111111111111",
        "student_id": "STU-A",
        "goal_type": "target_sgpa",
        "target_value": 9.0,
        "status": "Active",
        "created_at": NOW,
        "updated_at": NOW,
    }
    row.update(overrides)
    return row


def notification_row(**overrides):
    row = {
        "message_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "message_type": "ATTENDANCE_WARNING",
        "title": "Attendance below target",
        "message_body": "Body text",
        "subject": "Deep Learning",
        "priority": "Normal",
        "status": "Unread",
        "created_at": NOW,
    }
    row.update(overrides)
    return row


def ctx_conn(summaries=None, performance=None, attendance=None):
    """A FakeConn that answers the four _health_context queries in order."""
    return FakeConn(
        fetch_sequence=[summaries or [], performance or [], attendance or []]
    )


class StudentHealthServiceTests(unittest.TestCase):
    def _service(self, conn):
        return StudentService(FakePool(conn))

    def test_health_score_404_when_student_missing(self):
        with self.assertRaises(HTTPException) as ctx:
            run(self._service(FakeConn()).get_health_score("NOPE"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_health_score_response(self):
        conn = ctx_conn(
            summaries=[summary_row(semester=6, semester_percentage=82.0, sgpa=8.5)],
            performance=[
                perf_row(semester=6, subject_id="SUBJ-1", percentage=85.0),
                perf_row(semester=7, subject_id="SUBJ-2", end_sem_marks=None),
            ],
            attendance=[attendance_row(attendance_percentage=90.0)],
        )
        conn.fetchrow_sequence = [profile_row()]
        response = run(self._service(conn).get_health_score("STU-A"))
        self.assertIsInstance(response, HealthScoreResponse)
        self.assertTrue(response.available)
        self.assertGreaterEqual(response.score, 80.0)
        self.assertIn("attendance", response.components)
        # ctx queries scoped by student id
        self.assertEqual(conn.executed[0][2], ("STU-A",))
        self.assertEqual(conn.executed[3][2], ("STU-A", 7))

    def test_health_score_with_decimal_sgpa_from_db(self):
        """asyncpg returns NUMERIC sgpa as Decimal; the live health-score 500 path."""
        conn = ctx_conn(
            summaries=[
                summary_row(semester=5, semester_percentage=Decimal("78.0"), sgpa=Decimal("8.1")),
                summary_row(semester=6, semester_percentage=Decimal("82.0"), sgpa=Decimal("8.5")),
            ],
            performance=[
                perf_row(semester=6, subject_id="SUBJ-1", percentage=85.0),
                perf_row(semester=7, subject_id="SUBJ-2", end_sem_marks=None),
            ],
            attendance=[attendance_row(attendance_percentage=Decimal("90.0"))],
        )
        conn.fetchrow_sequence = [profile_row(latest_sgpa=Decimal("8.5"))]
        response = run(self._service(conn).get_health_score("STU-A"))
        self.assertIsInstance(response, HealthScoreResponse)
        self.assertTrue(response.available)
        self.assertIsInstance(response.score, float)
        self.assertGreaterEqual(response.score, 80.0)

    def test_priorities_response(self):
        summaries = [
            summary_row(semester=6, semester_percentage=82.0, sgpa=8.5, semester_result="Pass")
        ]
        performance = [
            perf_row(semester=6, subject_id="SUBJ-1", percentage=55.0, result_status="Pass"),
            perf_row(semester=7, subject_id="SUBJ-2", end_sem_marks=None),
        ]
        attendance = [
            attendance_row(
                attendance_percentage=67.5,
                total_classes=40,
                attended_classes=27,
                performance_percentage=55.0,
            )
        ]
        conn = ctx_conn(summaries, performance, attendance)
        conn.fetchrow_sequence = [profile_row()]
        conn.fetch_sequence.append([goal_row(goal_id="g1", target_value=9.0)])
        response = run(self._service(conn).get_priorities("STU-A"))
        self.assertIsInstance(response, PrioritiesResponse)
        self.assertEqual(response.student_id, "STU-A")
        signals = [item.signal for item in response.items]
        self.assertEqual(signals[0], "attendance")
        self.assertIn("weak_performance", signals)

    def test_priorities_404_when_student_missing(self):
        with self.assertRaises(HTTPException) as ctx:
            run(self._service(FakeConn()).get_priorities("NOPE"))
        self.assertEqual(ctx.exception.status_code, 404)


class GoalServiceTests(unittest.TestCase):
    def _service(self, conn):
        return StudentService(FakePool(conn))

    def test_list_goals_decorates_current_value_and_achieved(self):
        conn = ctx_conn(summaries=[summary_row(semester=6, semester_percentage=72.0)])
        conn.fetchrow_sequence = [profile_row(latest_sgpa=8.4)]
        conn.fetch_sequence.append([goal_row()])
        response = run(self._service(conn).list_goals("STU-A"))
        self.assertIsInstance(response, GoalsResponse)
        self.assertEqual(len(response.goals), 1)
        goal = response.goals[0]
        self.assertIsInstance(goal, StudentGoal)
        self.assertEqual(goal.current_value, 8.4)
        self.assertFalse(goal.achieved)  # 8.4 < 9.0 target

    def test_create_goal_success(self):
        conn = ctx_conn()
        conn.fetchrow_sequence = [profile_row(latest_sgpa=8.4), goal_row(target_value=9.0)]
        response = run(self._service(conn).create_goal("STU-A", "target_sgpa", 9.0))
        self.assertIsInstance(response, StudentGoal)
        self.assertEqual(response.goal_type, "target_sgpa")
        self.assertEqual(response.status, "Active")

    def test_create_goal_conflict_when_active_goal_exists(self):
        conn = ctx_conn()
        conn.fetchrow_sequence = [profile_row(latest_sgpa=8.4), None]
        with self.assertRaises(HTTPException) as ctx:
            run(self._service(conn).create_goal("STU-A", "target_sgpa", 9.0))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_create_goal_rejects_out_of_range_target(self):
        conn = ctx_conn()
        conn.fetchrow_sequence = [profile_row()]
        with self.assertRaises(HTTPException) as ctx:
            run(self._service(conn).create_goal("STU-A", "target_sgpa", 11.0))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_update_goal_success_activates(self):
        conn = ctx_conn()
        conn.fetchrow_sequence = [
            profile_row(latest_sgpa=8.4),
            goal_row(status="Inactive", target_value=9.0),
            goal_row(status="Active", target_value=9.0),
        ]
        conn.fetchval_sequence = [None]
        response = run(
            self._service(conn).update_goal("STU-A", goal_row()["goal_id"], new_status="Active")
        )
        self.assertEqual(response.status, "Active")

    def test_update_goal_target_only(self):
        conn = ctx_conn()
        conn.fetchrow_sequence = [
            profile_row(),
            goal_row(target_value=9.0),
            goal_row(target_value=8.5),
        ]
        response = run(
            self._service(conn).update_goal("STU-A", goal_row()["goal_id"], target_value=8.5)
        )
        self.assertEqual(response.target_value, 8.5)

    def test_update_goal_404_when_missing(self):
        conn = ctx_conn()
        conn.fetchrow_sequence = [profile_row(), None]
        with self.assertRaises(HTTPException) as ctx:
            run(self._service(conn).update_goal("STU-A", "nope", new_status="Active"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_update_goal_409_on_active_collision(self):
        conn = ctx_conn()
        conn.fetchrow_sequence = [profile_row(), goal_row(status="Inactive", target_value=9.0)]
        conn.fetchval_sequence = ["colliding-goal-id"]
        with self.assertRaises(HTTPException) as ctx:
            run(
                self._service(conn).update_goal(
                    "STU-A", goal_row()["goal_id"], new_status="Active"
                )
            )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_goals_404_when_student_missing(self):
        with self.assertRaises(HTTPException) as ctx:
            run(self._service(FakeConn()).list_goals("NOPE"))
        self.assertEqual(ctx.exception.status_code, 404)


class NotificationServiceTests(unittest.TestCase):
    def _service(self, conn):
        return StudentService(FakePool(conn))

    def test_get_notifications_pagination_shape(self):
        conn = FakeConn(
            fetch_sequence=[[notification_row(), notification_row()]],
            fetchval_sequence=[5, 3],
        )
        conn.fetchrow_sequence = [profile_row()]
        response = run(self._service(conn).get_notifications("STU-A", page=2, page_size=10))
        self.assertIsInstance(response, NotificationsResponse)
        self.assertEqual(len(response.items), 2)
        self.assertEqual(response.total, 5)
        self.assertEqual(response.unread_count, 3)
        self.assertEqual(response.page, 2)
        self.assertEqual(response.page_size, 10)
        self.assertIsInstance(response.items[0], NotificationItem)
        # total count query is student-scoped
        self.assertEqual(conn.executed[1][2], ("STU-A",))

    def test_get_notifications_unread_filter_builds_status_clause(self):
        conn = FakeConn(fetchval_sequence=[0, 0])
        conn.fetchrow_sequence = [profile_row()]
        run(self._service(conn).get_notifications("STU-A", message_type="ATTENDANCE_WARNING", unread_only=True))
        queries = [entry[1] for entry in conn.executed if entry[0] in ("fetch", "fetchval")]
        self.assertTrue(any("status = 'Unread'" in q for q in queries))
        self.assertTrue(any("message_type = $2" in q for q in queries))

    def test_get_notifications_404_when_student_missing(self):
        with self.assertRaises(HTTPException) as ctx:
            run(self._service(FakeConn()).get_notifications("NOPE"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_unread_count_response(self):
        conn = FakeConn(fetchval_sequence=[4])
        conn.fetchrow_sequence = [profile_row()]
        response = run(self._service(conn).get_unread_notification_count("STU-A"))
        self.assertIsInstance(response, UnreadCountResponse)
        self.assertEqual(response.unread_count, 4)

    def test_mark_notification_read(self):
        conn = FakeConn()
        conn.fetchrow_sequence = [profile_row(), notification_row(status="Read")]
        response = run(
            self._service(conn).mark_notification_read("STU-A", notification_row()["message_id"])
        )
        self.assertIsInstance(response, NotificationItem)
        self.assertEqual(response.status, "Read")

    def test_mark_notification_read_404_for_unknown_or_foreign(self):
        conn = FakeConn()
        conn.fetchrow_sequence = [profile_row(), None]
        with self.assertRaises(HTTPException) as ctx:
            run(
                self._service(conn).mark_notification_read(
                    "STU-A", "00000000-0000-0000-0000-000000000000"
                )
            )
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
