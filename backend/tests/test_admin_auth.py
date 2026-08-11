"""Authorization tests for the Admin role dependency (MD-01 foundation).

Covers the access-control matrix enforced by the backend for the Admin
module while guarding the existing Student/Faculty role dependencies from
regression.

The dependency functions are pure: they only inspect the authenticated
user payload produced by ``get_current_user``, so no database is required.
"""

import unittest

from fastapi import HTTPException

from app.api.dependencies import (
    require_admin_role,
    require_faculty_role,
    require_student_role,
)


class RequireAdminRoleTests(unittest.TestCase):
    def test_admin_role_allows_admin(self):
        user = {"user_id": "u-1", "username": "admin", "role": "Admin"}
        self.assertEqual(require_admin_role(user), user)

    def test_admin_role_rejects_student(self):
        with self.assertRaises(HTTPException) as ctx:
            require_admin_role({"user_id": "u-2", "role": "Student"})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_admin_role_rejects_faculty(self):
        with self.assertRaises(HTTPException) as ctx:
            require_admin_role({"user_id": "u-3", "role": "Faculty"})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_admin_role_rejects_unknown_role(self):
        with self.assertRaises(HTTPException) as ctx:
            require_admin_role({"user_id": "u-4", "role": "Guest"})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_admin_role_rejects_missing_role(self):
        with self.assertRaises(HTTPException) as ctx:
            require_admin_role({"user_id": "u-5"})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_admin_role_rejects_empty_payload(self):
        with self.assertRaises(HTTPException) as ctx:
            require_admin_role({})
        self.assertEqual(ctx.exception.status_code, 403)


class ExistingRoleDependencyRegressionTests(unittest.TestCase):
    """Existing Student/Faculty authorization must remain unchanged."""

    def test_student_role_allows_student(self):
        user = {"user_id": "u-1", "role": "Student", "student_id": "STU000001"}
        self.assertEqual(require_student_role(user), user)

    def test_student_role_rejects_admin(self):
        with self.assertRaises(HTTPException) as ctx:
            require_student_role({"user_id": "u-2", "role": "Admin"})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_student_role_rejects_faculty(self):
        with self.assertRaises(HTTPException) as ctx:
            require_student_role({"user_id": "u-3", "role": "Faculty"})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_faculty_role_allows_faculty(self):
        user = {"user_id": "u-1", "role": "Faculty", "faculty_id": "FAC001"}
        self.assertEqual(require_faculty_role(user), user)

    def test_faculty_role_rejects_admin(self):
        with self.assertRaises(HTTPException) as ctx:
            require_faculty_role({"user_id": "u-2", "role": "Admin"})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_faculty_role_rejects_student(self):
        with self.assertRaises(HTTPException) as ctx:
            require_faculty_role({"user_id": "u-3", "role": "Student"})
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
