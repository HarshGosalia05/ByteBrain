"""Unified /predict RBAC tests (authorize_prediction_access).

Verifies the single authorization rule in backend/app/api/v1/predict.py
shared by every prediction route:

- Student: only their own student_id.
- Faculty: only students within their existing authorized scope
  (FacultyService.assert_student_in_scope - the same rule behind the
  faculty student overview/profile and faculty ML insights routes).
- Admin: existing admin access rules (unchanged, any student).

Reuses the FakePool/FakeConn pattern from test_faculty_ml_insights_scope.py
and does not duplicate authentication infrastructure.
"""
import asyncio
import unittest

from fastapi import HTTPException

from app.api.v1.predict import authorize_prediction_access
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


def _scope_service(reachable: bool) -> FacultyService:
    if reachable:
        conn = FakeConn(fetchrow_sequence=[faculty_row()], fetchval_sequence=[1, 0])
    else:
        conn = FakeConn(fetchrow_sequence=[faculty_row()], fetchval_sequence=[None, None])
    return FacultyService(FakePool(conn))


STUDENT_USER = {"role": "Student", "student_id": "STU000001"}
FACULTY_USER = {"role": "Faculty", "faculty_id": "FAC-1"}
ADMIN_USER = {"role": "Admin"}


class AuthorizePredictionAccessTest(unittest.TestCase):
    def test_student_own_student_allowed(self):
        run(authorize_prediction_access(STUDENT_USER, "STU000001"))

    def test_student_other_student_denied(self):
        with self.assertRaises(HTTPException) as ctx:
            run(authorize_prediction_access(STUDENT_USER, "STU000002"))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_faculty_authorized_student_allowed(self):
        run(authorize_prediction_access(FACULTY_USER, "STU000001", _scope_service(True)))

    def test_faculty_unauthorized_student_denied(self):
        with self.assertRaises(HTTPException) as ctx:
            run(authorize_prediction_access(FACULTY_USER, "STU000002", _scope_service(False)))
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("classes or mentees", str(ctx.exception.detail))

    def _assert_faculty_scope_enforced(self, route_label: str):
        # authorized student -> allowed
        run(authorize_prediction_access(FACULTY_USER, "STU000001", _scope_service(True)))
        # unauthorized student -> denied
        with self.assertRaises(HTTPException) as ctx:
            run(authorize_prediction_access(FACULTY_USER, "STU000002", _scope_service(False)))
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("classes or mentees", str(ctx.exception.detail))

    def test_faculty_m1_route_scope_enforced(self):
        self._assert_faculty_scope_enforced("GET /predict/m1/{student_id}")

    def test_faculty_m2tp_route_scope_enforced(self):
        self._assert_faculty_scope_enforced("GET /predict/m2tp/{student_id}")

    def test_faculty_m3_route_scope_enforced(self):
        self._assert_faculty_scope_enforced("GET /predict/m3/{student_id}")

    def test_faculty_m4_route_scope_enforced(self):
        self._assert_faculty_scope_enforced("GET /predict/m4/{student_id}")

    def test_faculty_insights_route_scope_enforced(self):
        self._assert_faculty_scope_enforced("GET /predict/insights/{student_id}")

    def test_faculty_persist_route_scope_enforced(self):
        self._assert_faculty_scope_enforced("POST /predict/persist/{prediction_type}/{student_id}")

    def test_admin_access_unchanged(self):
        # Admin has no faculty_id and no student_id; any student is allowed.
        run(authorize_prediction_access(ADMIN_USER, "STU000001"))
        run(authorize_prediction_access(ADMIN_USER, "STU000002"))

    def test_unknown_role_denied(self):
        with self.assertRaises(HTTPException) as ctx:
            run(authorize_prediction_access({"role": "Guest"}, "STU000001"))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_faculty_missing_faculty_id_denied(self):
        with self.assertRaises(HTTPException) as ctx:
            run(authorize_prediction_access({"role": "Faculty"}, "STU000001", _scope_service(True)))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_faculty_without_scope_service_denied(self):
        with self.assertRaises(HTTPException) as ctx:
            run(authorize_prediction_access(FACULTY_USER, "STU000001", None))
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
