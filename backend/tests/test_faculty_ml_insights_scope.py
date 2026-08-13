"""ML-10: FacultyService.assert_student_in_scope tests.

Verifies that ML insights are only reachable for students linked to the
faculty (class or mentee), reusing the exact scope rule behind
get_student_overview / get_student_profile_view.
"""
import asyncio
import unittest

from fastapi import HTTPException

from app.services.faculty_service import FacultyService


class _TransactionContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConn:
    def __init__(self, fetchrow_sequence=None, fetchval_sequence=None):
        self.fetchrow_sequence = list(fetchrow_sequence or [])
        self.fetchval_sequence = list(fetchval_sequence or [])
        self.executed = []

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


class AssertStudentInScopeTest(unittest.TestCase):
    def test_reachable_via_class(self):
        conn = FakeConn(fetchrow_sequence=[faculty_row()], fetchval_sequence=[1, 0])
        run(FacultyService(FakePool(conn)).assert_student_in_scope("FAC-1", "STU000001"))
        fetchvals = [entry for entry in conn.executed if entry[0] == "fetchval"]
        self.assertEqual(len(fetchvals), 2)
        self.assertIn("student_subject_enrollment", fetchvals[0][1])
        self.assertIn("faculty_student_map", fetchvals[1][1])

    def test_reachable_via_mentee(self):
        conn = FakeConn(fetchrow_sequence=[faculty_row()], fetchval_sequence=[0, 1])
        run(FacultyService(FakePool(conn)).assert_student_in_scope("FAC-1", "STU000001"))

    def test_not_reachable_raises_404(self):
        conn = FakeConn(fetchrow_sequence=[faculty_row()], fetchval_sequence=[None, None])
        with self.assertRaises(HTTPException) as ctx:
            run(FacultyService(FakePool(conn)).assert_student_in_scope("FAC-1", "STU999999"))
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("classes or mentees", str(ctx.exception.detail))

    def test_missing_faculty_profile_raises_404(self):
        conn = FakeConn(fetchrow_sequence=[None], fetchval_sequence=[1, 0])
        with self.assertRaises(HTTPException) as ctx:
            run(FacultyService(FakePool(conn)).assert_student_in_scope("FAC-1", "STU000001"))
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Faculty profile not found")


if __name__ == "__main__":
    unittest.main()
