"""Service-level tests for MD-05 faculty notification clear (hard delete).

Uses the same fake asyncpg pool pattern as the student MD-05 service tests so
no live database is required. Verifies ownership scoping (a faculty member can
only clear their own notifications), 404 handling, and the clear-all response.
"""

import asyncio
import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from app.schemas.faculty import (
    FacultyClearAllResponse,
    FacultyNotificationItem,
)
from app.services.faculty_service import FacultyService

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
        fetchrow_sequence=None,
        fetchval_sequence=None,
    ):
        self.fetchrow_sequence = list(fetchrow_sequence or [])
        self.fetchval_sequence = list(fetchval_sequence or [])
        self.executed = []  # list of (kind, query, args)

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


def faculty_row(**overrides):
    row = {
        "faculty_id": "FAC-1",
        "name": "Dr. Jane Doe",
        "email": "jane.doe@college.edu",
        "department_code": "CSE",
        "department_name": "Computer Science",
    }
    row.update(overrides)
    return row


def notification_row(**overrides):
    row = {
        "message_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "message_type": "STUDENT_ATTENDANCE_WARNING",
        "title": "Attendance below target: Alice",
        "message_body": "Body text",
        "subject": "Deep Learning",
        "priority": "Normal",
        "status": "Unread",
        "created_at": NOW,
    }
    row.update(overrides)
    return row


class FacultyClearNotificationTests(unittest.TestCase):
    def _service(self, conn):
        return FacultyService(FakePool(conn))

    def test_clear_notification_returns_item(self):
        conn = FakeConn(fetchrow_sequence=[faculty_row(), notification_row()])
        response = run(
            self._service(conn).clear_notification(
                "FAC-1", notification_row()["message_id"]
            )
        )
        self.assertIsInstance(response, FacultyNotificationItem)
        self.assertEqual(response.status, "Unread")
        deletes = [entry for entry in conn.executed if entry[0] == "fetchrow"]
        self.assertIn("DELETE FROM student_messages", deletes[1][1])
        self.assertIn("faculty_recipient_id = $1", deletes[1][1])
        self.assertIn("recipient_type = 'faculty'", deletes[1][1])
        self.assertEqual(deletes[1][2], ("FAC-1", notification_row()["message_id"]))

    def test_clear_notification_404_for_unknown_or_foreign(self):
        conn = FakeConn(fetchrow_sequence=[faculty_row(), None])
        with self.assertRaises(HTTPException) as ctx:
            run(
                self._service(conn).clear_notification(
                    "FAC-1", "00000000-0000-0000-0000-000000000000"
                )
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_clear_notification_404_when_faculty_missing(self):
        with self.assertRaises(HTTPException) as ctx:
            run(
                self._service(FakeConn()).clear_notification(
                    "NOPE", "00000000-0000-0000-0000-000000000000"
                )
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_clear_all_notifications_response(self):
        conn = FakeConn(fetchrow_sequence=[faculty_row()], fetchval_sequence=[9])
        response = run(self._service(conn).clear_all_notifications("FAC-1"))
        self.assertIsInstance(response, FacultyClearAllResponse)
        self.assertEqual(response.cleared_count, 9)
        self.assertEqual(response.faculty_id, "FAC-1")
        deletes = [entry for entry in conn.executed if entry[0] == "fetchval"]
        self.assertIn("DELETE FROM student_messages", deletes[0][1])
        self.assertIn("faculty_recipient_id = $1", deletes[0][1])
        self.assertEqual(deletes[0][2], ("FAC-1",))


if __name__ == "__main__":
    unittest.main()
