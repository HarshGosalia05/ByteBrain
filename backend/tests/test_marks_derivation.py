"""Regression tests for the authoritative marks derivation (plan 14 §7.2).

Contract under test:
  * Derived fields (total/percentage/grade/grade_point/result_status/
    performance_category) are calculated ONLY when ALL THREE marks
    (internal, mid-sem, end-sem) are present.
  * A single NULL mark keeps every derived field NULL (never a partial
    total, never a derived value from COALESCE(NULL, 0)).
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

    def test_f_clear_end_after_complete(self):
        # 18/47/60 -> clear end -> 18/47/NULL -> ALL derived NULL.
        self.assert_all_derived_null(18, 47, None)

    def test_g_clear_mid_after_complete(self):
        # 18/47/60 -> clear mid -> 18/NULL/60 -> ALL derived NULL.
        self.assert_all_derived_null(18, None, 60)

    def test_i_complete_with_end_65(self):
        result = derive_marks_fields(18, 47, 65)
        self.assertEqual(result["total_marks"], 130)
        self.assertEqual(result["percentage"], 92.86)
        self.assertEqual(result["grade"], "O")
        self.assertEqual(result["grade_point"], 10)
        self.assertEqual(result["result_status"], "Pass")
        self.assertEqual(result["performance_category"], "Top")

    def test_zero_is_a_value_not_none(self):
        # 0 is a legitimate mark: it must NOT be treated as NULL.
        result = derive_marks_fields(0, 0, 0)
        self.assertEqual(result["total_marks"], 0)
        self.assertEqual(result["percentage"], 0.0)
        self.assertEqual(result["grade"], "F")
        self.assertEqual(result["grade_point"], 0)
        self.assertEqual(result["result_status"], "Fail")
        self.assertEqual(result["performance_category"], "Low Performer")


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


if __name__ == "__main__":
    unittest.main()
