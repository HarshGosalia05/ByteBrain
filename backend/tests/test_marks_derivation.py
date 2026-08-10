"""Regression tests for the authoritative marks derivation (plan 14 §7.2).

Contract under test:
  * Derived fields (total/percentage/grade/grade_point/result_status/
    performance_category/remarks) are calculated ONLY when ALL THREE marks
    (internal, mid-sem, end-sem) are present.
  * A single NULL mark keeps every derived field NULL (never a partial
    total, never a derived value from COALESCE(NULL, 0)).
  * Remarks is an automatic derived value mapped from percentage
    (>=90 Excellent / >=75 Good / >=60 Satisfactory / >=40 Needs
    improvement / <40 At risk) and is NULL for incomplete records.
  * Explicit NULL is a legal "clear" action and passes validation.
  * Out-of-range marks are rejected with 422 before any DB write.

No live database is required: the derivation is a pure function and the
save-path tests use a mocked repository.
"""

import asyncio
import unittest
from unittest import mock

from app.schemas.faculty import MarksBatchSaveRequest, MarksRowInput
from app.services.faculty_service import FacultyService, derive_marks_fields

from fastapi import HTTPException

DERIVED_FIELDS = (
    "total_marks",
    "percentage",
    "grade",
    "grade_point",
    "result_status",
    "performance_category",
    "remarks",
)


class DeriveMarksFieldsTests(unittest.TestCase):
    """Pure derivation-function matrix (Test A-G, I, plus zero handling)."""

    def assert_all_derived_null(self, internal, mid, end):
        result = derive_marks_fields(internal, mid, end)
        for field in DERIVED_FIELDS:
            self.assertIsNone(
                result[field],
                f"{field} must be NULL for ({internal}, {mid}, {end})",
            )
        return result

    def test_a_internal_and_mid_only(self):
        # internal + mid present, end missing -> ALL derived NULL.
        self.assert_all_derived_null(18, 47, None)

    def test_b_mid_and_end_only(self):
        # internal missing -> ALL derived NULL.
        self.assert_all_derived_null(None, 47, 60)

    def test_c_internal_and_end_only(self):
        # mid missing -> ALL derived NULL.
        self.assert_all_derived_null(18, None, 60)

    def test_d_no_marks_at_all(self):
        self.assert_all_derived_null(None, None, None)

    def test_e_complete_save_derives(self):
        # All three marks present -> authoritative derivation.
        result = derive_marks_fields(18, 47, 60)
        self.assertEqual(result["total_marks"], 125)
        self.assertEqual(result["percentage"], 89.29)
        self.assertEqual(result["grade"], "A+")
        self.assertEqual(result["grade_point"], 9)
        self.assertEqual(result["result_status"], "Pass")
        self.assertEqual(result["performance_category"], "Above Average")
        self.assertEqual(result["remarks"], "Good performance")

    def test_f_clear_end_after_complete(self):
        # 18/47/60 -> clear end -> 18/47/NULL -> ALL derived NULL (incl remarks).
        self.assert_all_derived_null(18, 47, None)

    def test_g_clear_mid_after_complete(self):
        # 18/47/60 -> clear mid -> 18/NULL/60 -> ALL derived NULL (incl remarks).
        self.assert_all_derived_null(18, None, 60)

    def test_i_complete_with_end_65(self):
        result = derive_marks_fields(18, 47, 65)
        self.assertEqual(result["total_marks"], 130)
        self.assertEqual(result["percentage"], 92.86)
        self.assertEqual(result["grade"], "O")
        self.assertEqual(result["grade_point"], 10)
        self.assertEqual(result["result_status"], "Pass")
        self.assertEqual(result["performance_category"], "Top")
        self.assertEqual(result["remarks"], "Excellent performance")

    def test_zero_is_a_value_not_none(self):
        # 0 is a legitimate mark: it must NOT be treated as NULL.
        result = derive_marks_fields(0, 0, 0)
        self.assertEqual(result["total_marks"], 0)
        self.assertEqual(result["percentage"], 0.0)
        self.assertEqual(result["grade"], "F")
        self.assertEqual(result["grade_point"], 0)
        self.assertEqual(result["result_status"], "Fail")
        self.assertEqual(result["performance_category"], "Low Performer")
        self.assertEqual(result["remarks"], "At risk - improvement required")

    def test_remark_band_boundaries(self):
        # (internal, mid, end) -> expected percentage and remark. Boundaries of
        # the automatic-remark bands (90/75/60/40) are exercised both sides.
        cases = [
            ((20, 50, 56), 90.0, "Excellent performance"),
            ((20, 45, 60), 89.29, "Good performance"),
            ((10, 45, 50), 75.0, "Good performance"),
            ((14, 40, 50), 74.29, "Satisfactory performance"),
            ((10, 30, 44), 60.0, "Satisfactory performance"),
            ((13, 30, 40), 59.29, "Needs improvement"),
            ((10, 20, 26), 40.0, "Needs improvement"),
            ((15, 20, 20), 39.29, "At risk - improvement required"),
        ]
        for marks, expected_pct, expected_remark in cases:
            with self.subTest(marks=marks):
                result = derive_marks_fields(*marks)
                self.assertEqual(result["percentage"], expected_pct)
                self.assertEqual(result["remarks"], expected_remark)


class SaveSubjectMarksValidationTests(unittest.TestCase):
    """Save-path tests with a mocked repository (Test H + NULL clear)."""

    def _make_service(self):
        svc = FacultyService(pool=mock.MagicMock())
        svc.repo = mock.MagicMock()
        svc.repo.get_faculty_profile = mock.AsyncMock(return_value={
            "faculty_id": "FAC001",
            "name": "Prof A",
        })
        svc.repo.upsert_subject_marks = mock.AsyncMock()
        return svc

    def _request(self, *rows):
        return MarksBatchSaveRequest(
            semester_no=7,
            academic_year="2026-27",
            rows=list(rows),
        )

    def test_h_end_sem_90_rejected_with_no_db_write(self):
        async def scenario():
            svc = self._make_service()
            request = self._request(
                MarksRowInput(
                    enrollment_record_id="ENR000050",
                    internal_marks=18,
                    mid_sem_marks=47,
                    end_sem_marks=90,  # exceeds end-sem max (70)
                )
            )
            with self.assertRaises(HTTPException) as cm:
                await svc.save_subject_marks("FAC001", "SUB0001", request, "FAC001")
            self.assertEqual(cm.exception.status_code, 422)
            svc.repo.upsert_subject_marks.assert_not_awaited()

        asyncio.run(scenario())

    def test_negative_marks_rejected(self):
        async def scenario():
            svc = self._make_service()
            request = self._request(
                MarksRowInput(enrollment_record_id="ENR000050", end_sem_marks=-5)
            )
            with self.assertRaises(HTTPException) as cm:
                await svc.save_subject_marks("FAC001", "SUB0001", request, "FAC001")
            self.assertEqual(cm.exception.status_code, 422)
            svc.repo.upsert_subject_marks.assert_not_awaited()

        asyncio.run(scenario())

    def test_explicit_null_clear_is_valid_and_forwarded(self):
        async def scenario():
            svc = self._make_service()
            captured = {}

            async def fake_upsert(faculty_id, subject_id, sem, year, entries,
                                  changed_by, derivator):
                captured["entries"] = entries
                captured["derivator"] = derivator
                return {
                    "summary": {
                        "saved": 1, "inserted": 0, "updated": 1,
                        "unchanged": 0, "rejected": 0,
                    },
                    "results": [{
                        "enrollment_record_id": "ENR000050",
                        "student_id": "STU000001",
                        "operation": "update",
                        "fields_changed": ["end_sem_marks"],
                    }],
                }

            svc.repo.upsert_subject_marks.side_effect = fake_upsert
            # The service fetches the grid after the upsert; stop it there with
            # a sentinel before the response object is built.
            svc.get_subject_marks_grid = mock.AsyncMock(
                side_effect=RuntimeError("STOP")
            )

            request = self._request(
                MarksRowInput(
                    enrollment_record_id="ENR000050",
                    end_sem_marks=None,  # explicit clear of end-sem marks
                )
            )
            response = None
            try:
                await svc.save_subject_marks(
                    "FAC001", "SUB0001", request, "FAC001"
                )
            except RuntimeError as exc:
                if str(exc) != "STOP":
                    raise
            self.assertIsNone(response)
            entries = captured["entries"]
            self.assertEqual(len(entries), 1)
            # Explicit NULL survives model_dump(exclude_unset=True): the "clear"
            # contract must reach the repository.
            self.assertIn("end_sem_marks", entries[0])
            self.assertIsNone(entries[0]["end_sem_marks"])
            # The repo receives the authoritative derivator.
            self.assertIs(captured["derivator"], derive_marks_fields)

        asyncio.run(scenario())

    def test_client_supplied_remarks_are_never_forwarded(self):
        # Remarks is a derived field: arbitrary text sent by a client must be
        # ignored (extra input fields are dropped by the request schema).
        async def scenario():
            svc = self._make_service()
            captured = {}

            async def fake_upsert(faculty_id, subject_id, sem, year, entries,
                                  changed_by, derivator):
                captured["entries"] = entries
                return {
                    "summary": {
                        "saved": 1, "inserted": 0, "updated": 1,
                        "unchanged": 0, "rejected": 0,
                    },
                    "results": [],
                }

            svc.repo.upsert_subject_marks.side_effect = fake_upsert
            svc.get_subject_marks_grid = mock.AsyncMock(
                side_effect=RuntimeError("STOP")
            )

            request = self._request(
                MarksRowInput(
                    enrollment_record_id="ENR000050",
                    internal_marks=18,
                    mid_sem_marks=47,
                    end_sem_marks=60,
                    remarks="custom text must be ignored",
                )
            )
            try:
                await svc.save_subject_marks(
                    "FAC001", "SUB0001", request, "FAC001"
                )
            except RuntimeError as exc:
                if str(exc) != "STOP":
                    raise
            entries = captured["entries"]
            self.assertEqual(len(entries), 1)
            self.assertNotIn("remarks", entries[0])

        asyncio.run(scenario())

    def test_boolean_marks_rejected(self):
        # bool is an int subclass: true must never be silently accepted as 1.
        # The request schema rejects it before the service is even reached.
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            MarksRowInput(
                enrollment_record_id="ENR000050",
                internal_marks=True,
            )


class DeriveMarksFieldsInputValidationTests(unittest.TestCase):
    """Canonical derivation rejects any non-whole or out-of-range component."""

    def assert_value_error(self, internal, mid, end):
        with self.assertRaises(ValueError):
            derive_marks_fields(internal, mid, end)

    def test_internal_above_max_rejected(self):
        self.assert_value_error(21, 0, 0)

    def test_internal_negative_rejected(self):
        self.assert_value_error(-1, 0, 0)

    def test_mid_above_max_rejected(self):
        self.assert_value_error(0, 51, 0)

    def test_mid_negative_rejected(self):
        self.assert_value_error(0, -1, 0)

    def test_end_above_max_rejected(self):
        self.assert_value_error(0, 0, 71)

    def test_end_negative_rejected(self):
        self.assert_value_error(0, 0, -1)

    def test_decimal_marks_rejected(self):
        self.assert_value_error(12.5, 0, 0)

    def test_float_nan_rejected(self):
        self.assert_value_error(float("nan"), 0, 0)

    def test_float_infinity_rejected(self):
        self.assert_value_error(float("inf"), 0, 0)

    def test_float_negative_infinity_rejected(self):
        self.assert_value_error(0, 0, float("-inf"))

    def test_boolean_rejected(self):
        self.assert_value_error(True, 0, 0)

    def test_boundaries_are_valid(self):
        result = derive_marks_fields(20, 50, 70)
        self.assertEqual(result["total_marks"], 140)
        self.assertEqual(result["percentage"], 100.0)
        self.assertEqual(result["result_status"], "Pass")


class DeriveMarksFieldsEndSemPassRuleTests(unittest.TestCase):
    """End-Sem below 18/70 can never be treated as Pass (canonical rule)."""

    def test_end_sem_17_cannot_pass_even_with_high_total(self):
        # 20+50+17 = 87 -> 62.14% (well above the 40% pass line) but End-Sem is
        # below the 18/70 minimum, so the result must NOT be Pass.
        result = derive_marks_fields(20, 50, 17)
        self.assertEqual(result["total_marks"], 87)
        self.assertEqual(result["percentage"], 62.14)
        self.assertEqual(result["grade"], "B+")
        self.assertEqual(result["result_status"], "Fail")

    def test_end_sem_0_cannot_pass(self):
        result = derive_marks_fields(20, 50, 0)
        self.assertEqual(result["percentage"], 50.0)
        self.assertEqual(result["result_status"], "Fail")

    def test_end_sem_18_is_eligible_for_pass(self):
        result = derive_marks_fields(20, 50, 18)
        self.assertEqual(result["total_marks"], 88)
        self.assertEqual(result["percentage"], 62.86)
        self.assertEqual(result["result_status"], "Pass")

    def test_end_sem_70_is_valid_and_passes(self):
        result = derive_marks_fields(0, 0, 70)
        self.assertEqual(result["total_marks"], 70)
        self.assertEqual(result["percentage"], 50.0)
        self.assertEqual(result["result_status"], "Pass")


if __name__ == "__main__":
    unittest.main()
