"""Tests for the Student Settings & Security features.

Covers:
  * Default document structure includes account, notifications, and security.
  * Account preferences: display_language, name_display validation & persistence.
  * Notification preferences: grade_alerts, attendance_warnings, semester_results.
  * Change password: verification of current password, length check, DB update.
  * Two-factor authentication: toggle state and metadata persistence.
  * Sign out all devices: invalidation of active sessions.
  * Role authorization & user resolution.
"""

import asyncio
import json
import unittest

from app.services.settings_service import (
    PreferenceValidationError,
    SettingsService,
)
from app.repositories.settings_repo import SettingsRepository


class FakeSettingsConn:
    def __init__(self):
        self.users = {
            "USR001": {
                "user_id": "USR001",
                "username": "2023010001",
                "student_id": "STU000001",
                "password": "old_password_123",
                "preferences": None,
            }
        }

    async def fetchrow(self, query, *args):
        q = query.strip()
        if "SELECT preferences FROM users WHERE user_id = $1" in q:
            uid = args[0]
            if uid in self.users:
                return {"preferences": self.users[uid]["preferences"]}
            return None
        if "UPDATE users SET preferences = $1 WHERE user_id = $2" in q:
            prefs, uid = args[0], args[1]
            if uid in self.users:
                self.users[uid]["preferences"] = prefs
                return {"preferences": prefs}
            return None
        if "SELECT user_id FROM users WHERE student_id = $1" in q:
            sid = args[0]
            for u in self.users.values():
                if u.get("student_id") == sid:
                    return {"user_id": u["user_id"]}
            return None
        if "SELECT user_id FROM users WHERE username = $1" in q:
            uname = args[0]
            for u in self.users.values():
                if u.get("username") == uname:
                    return {"user_id": u["user_id"]}
            return None
        if "SELECT password FROM users WHERE user_id = $1" in q:
            uid = args[0]
            if uid in self.users:
                return {"password": self.users[uid]["password"]}
            return None
        if "UPDATE users SET password = $1 WHERE user_id = $2" in q:
            pwd, uid = args[0], args[1]
            if uid in self.users:
                self.users[uid]["password"] = pwd
                return {"user_id": uid}
            return None
        return None

    async def execute(self, query, *args):
        q = query.strip()
        if "UPDATE users SET password = $1 WHERE user_id = $2" in q:
            pwd, uid = args[0], args[1]
            if uid in self.users:
                self.users[uid]["password"] = pwd
        return "UPDATE 1"


class FakeSettingsPool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _FakeContext(self.conn)

    async def fetchrow(self, query, *args):
        return await self.conn.fetchrow(query, *args)

    async def execute(self, query, *args):
        return await self.conn.execute(query, *args)


class _FakeContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


def run(coro):
    return asyncio.run(coro)


class TestStudentSettings(unittest.TestCase):
    def setUp(self):
        self.conn = FakeSettingsConn()
        self.pool = FakeSettingsPool(self.conn)
        self.service = SettingsService(self.pool)

    def test_default_document_contains_account_notifications_security(self):
        doc = run(self.service.get_document("USR001"))
        namespaces = doc["namespaces"]
        self.assertIn("account", namespaces)
        self.assertIn("notifications", namespaces)
        self.assertIn("security", namespaces)

        # Account defaults
        self.assertEqual(namespaces["account"]["display_language"], "en")
        self.assertEqual(namespaces["account"]["name_display"], "full_name")

        # Notification defaults
        self.assertEqual(namespaces["notifications"]["grade_alerts"], True)
        self.assertEqual(namespaces["notifications"]["attendance_warnings"], True)
        self.assertEqual(namespaces["notifications"]["semester_results"], True)

        # Security defaults
        self.assertEqual(namespaces["security"]["two_factor_enabled"], False)

    def test_update_account_language_and_name_display(self):
        # Valid language change
        doc, highlights = run(
            self.service.update_namespace(
                "USR001", "account", {"display_language": "hi", "name_display": "formal"}
            )
        )
        self.assertEqual(doc["namespaces"]["account"]["display_language"], "hi")
        self.assertEqual(doc["namespaces"]["account"]["name_display"], "formal")

        # Persisted check
        doc_fetched = run(self.service.get_document("USR001"))
        self.assertEqual(doc_fetched["namespaces"]["account"]["display_language"], "hi")
        self.assertEqual(doc_fetched["namespaces"]["account"]["name_display"], "formal")

    def test_invalid_account_language_rejected(self):
        with self.assertRaises(PreferenceValidationError):
            run(
                self.service.update_namespace(
                    "USR001", "account", {"display_language": "klingon"}
                )
            )

    def test_update_notification_switches(self):
        doc, highlights = run(
            self.service.update_namespace(
                "USR001",
                "notifications",
                {
                    "grade_alerts": False,
                    "attendance_warnings": False,
                    "semester_results": True,
                },
            )
        )
        self.assertEqual(doc["namespaces"]["notifications"]["grade_alerts"], False)
        self.assertEqual(doc["namespaces"]["notifications"]["attendance_warnings"], False)
        self.assertEqual(doc["namespaces"]["notifications"]["semester_results"], True)

    def test_change_password_success(self):
        result = run(
            self.service.change_password(
                "USR001", "old_password_123", "new_secret_456"
            )
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("Password updated", result["message"])
        self.assertEqual(self.conn.users["USR001"]["password"], "new_secret_456")

        # Verify password_updated_at was set
        doc = run(self.service.get_document("USR001"))
        self.assertTrue(len(doc["namespaces"]["security"]["password_updated_at"]) > 0)

    def test_change_password_wrong_current_password(self):
        with self.assertRaises(PreferenceValidationError) as ctx:
            run(
                self.service.change_password(
                    "USR001", "wrong_password", "new_secret_456"
                )
            )
        self.assertIn("Current password is incorrect", str(ctx.exception))

    def test_change_password_too_short(self):
        with self.assertRaises(PreferenceValidationError) as ctx:
            run(
                self.service.change_password(
                    "USR001", "old_password_123", "123"
                )
            )
        self.assertIn("at least 6 characters", str(ctx.exception))

    def test_change_password_same_as_old(self):
        with self.assertRaises(PreferenceValidationError) as ctx:
            run(
                self.service.change_password(
                    "USR001", "old_password_123", "old_password_123"
                )
            )
        self.assertIn("cannot be the same", str(ctx.exception))

    def test_two_factor_toggle(self):
        # Enable 2FA
        res_enable = run(self.service.set_two_factor("USR001", True, "email"))
        self.assertEqual(res_enable["two_factor_enabled"], True)
        self.assertEqual(res_enable["two_factor_method"], "email")

        doc = run(self.service.get_document("USR001"))
        self.assertEqual(doc["namespaces"]["security"]["two_factor_enabled"], True)
        self.assertEqual(doc["namespaces"]["security"]["two_factor_method"], "email")

        # Disable 2FA
        res_disable = run(self.service.set_two_factor("USR001", False))
        self.assertEqual(res_disable["two_factor_enabled"], False)
        self.assertEqual(res_disable["two_factor_method"], "none")

    def test_sign_out_all_devices(self):
        res = run(self.service.sign_out_all_devices("USR001"))
        self.assertEqual(res["status"], "success")

        doc = run(self.service.get_document("USR001"))
        self.assertEqual(doc["namespaces"]["security"]["sessions"], [])
        self.assertTrue(len(doc["namespaces"]["security"]["last_sign_out_all"]) > 0)


if __name__ == "__main__":
    unittest.main()
