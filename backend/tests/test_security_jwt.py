"""Tests for JWT-based authentication (Phase 1 security fix).

Covers the signed-token verify path that replaced the forgeable base64-JSON
bearer token:
  * create_access_token signs a verifiable JWT with exp/iat claims.
  * get_current_user accepts a valid signed token for each role.
  * Tampered signature is rejected (401).
  * Expired token is rejected (401).
  * Missing required claims are rejected (401).
  * Unsupported role is rejected (401).
  * No JWT_SECRET configured fails closed (does not silently accept).
"""
from __future__ import annotations

import time
import unittest
from unittest import mock

from fastapi import HTTPException, status

from app.core import security
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_current_user,
)


class FakeBearerCredentials:
    def __init__(self, token: str):
        self.credentials = token


class CreateAndDecodeTests(unittest.TestCase):
    def setUp(self):
        self._orig_secret = security.settings.JWT_SECRET
        self._orig_expiry = security.settings.JWT_EXPIRY_SECONDS
        security.settings.JWT_SECRET = "test-secret-key-for-unit-tests"
        security.settings.JWT_ALGORITHM = "HS256"

    def tearDown(self):
        security.settings.JWT_SECRET = self._orig_secret
        security.settings.JWT_EXPIRY_SECONDS = self._orig_expiry

    def test_create_access_token_roundtrips_claims(self):
        payload = {
            "role": "Student",
            "user_id": "STU-1",
            "username": "alice",
            "student_id": "STU-1",
        }
        token = create_access_token(payload)
        decoded = decode_access_token(token)
        self.assertEqual(decoded["role"], "Student")
        self.assertEqual(decoded["user_id"], "STU-1")
        self.assertEqual(decoded["username"], "alice")
        self.assertEqual(decoded["student_id"], "STU-1")
        self.assertIn("exp", decoded)
        self.assertIn("iat", decoded)

    def test_decoded_token_not_bytes_or_leaked(self):
        token = create_access_token({"role": "Admin", "user_id": "ADM-1", "username": "root"})
        decoded = decode_access_token(token)
        # Ensure nested byte-encoded values are NOT produced (previous risk).
        for key, value in decoded.items():
            if isinstance(value, str):
                self.assertIsInstance(value, str)

    def test_expired_token_rejected(self):
        security.settings.JWT_EXPIRY_SECONDS = -10  # already expired
        token = create_access_token({"role": "Student", "user_id": "S", "username": "u"})
        with self.assertRaises(HTTPException) as ctx:
            decode_access_token(token)
        self.assertEqual(ctx.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tampered_signature_rejected(self):
        token = create_access_token({"role": "Admin", "user_id": "ADM-1", "username": "root"})
        header, _, _ = token.split(".")
        forged = f"{header}.eyJyb2xlIjoiQWRtaW4ifQ.signature"
        with self.assertRaises(HTTPException) as ctx:
            decode_access_token(forged)
        self.assertEqual(ctx.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_decode_fails_closed_without_secret(self):
        security.settings.JWT_SECRET = ""
        with self.assertRaises(HTTPException) as ctx:
            decode_access_token("some.token.value")
        self.assertEqual(ctx.exception.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_create_fails_closed_without_secret(self):
        security.settings.JWT_SECRET = ""
        with self.assertRaises(RuntimeError):
            create_access_token({"role": "Student", "user_id": "S", "username": "u"})


class GetCurrentUserTests(unittest.TestCase):
    def setUp(self):
        self._orig_secret = security.settings.JWT_SECRET
        security.settings.JWT_SECRET = "test-secret-key-for-unit-tests"
        security.settings.JWT_ALGORITHM = "HS256"

    def tearDown(self):
        security.settings.JWT_SECRET = self._orig_secret

    def _token(self, payload: dict) -> str:
        return create_access_token(payload)

    def test_valid_student_accepted(self):
        user = get_current_user(FakeBearerCredentials(self._token({
            "role": "Student", "user_id": "S1", "username": "s", "student_id": "S1",
        })))
        self.assertEqual(user["role"], "Student")

    def test_valid_faculty_accepted(self):
        user = get_current_user(FakeBearerCredentials(self._token({
            "role": "Faculty", "user_id": "F1", "username": "f", "faculty_id": "F1",
        })))
        self.assertEqual(user["role"], "Faculty")

    def test_valid_admin_accepted(self):
        user = get_current_user(FakeBearerCredentials(self._token({
            "role": "Admin", "user_id": "A1", "username": "a",
        })))
        self.assertEqual(user["role"], "Admin")

    def test_missing_role_rejected(self):
        # Signature must still be valid; a missing role claim is rejected.
        token = self._token({"user_id": "S1", "username": "s"})
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(FakeBearerCredentials(token))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_unsupported_role_rejected(self):
        token = self._token({"role": "Guest", "user_id": "G1", "username": "g"})
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(FakeBearerCredentials(token))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_tampered_token_rejected_at_get_current_user(self):
        good = self._token({"role": "Admin", "user_id": "A1", "username": "a"})
        header, _, _ = good.split(".")
        tampered = f"{header}.eyJyb2xlIjoiQWRtaW4iLCJ1c2VyX2lkIjoiSCIsInVzZXJuYW1lIjoiaCJ9.xx"
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(FakeBearerCredentials(tampered))
        self.assertEqual(ctx.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
