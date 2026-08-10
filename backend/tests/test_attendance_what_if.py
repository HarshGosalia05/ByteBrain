"""Contract + rule tests for the MD-04 attendance what-if simulator.

Covers:
  * Pure projection math (attend next N / miss next N / delta)
  * Target math: classes needed to reach 75% and classes skippable before
    dropping below 75%
  * Status / eligibility / shortage derivation reusing the canonical
    ``attendance_aggregate_fields`` bands
  * NULL / invalid baseline handling (a missing baseline is never zero)
  * Service-level response shape (context baseline + optional simulation) and
    404 routing (unknown subject / missing student)

Pure rule tests use crafted rows. Service-level tests use a fake asyncpg pool,
so no live database is required.
"""

import asyncio
import unittest

from app.schemas.student_analytics import AttendanceWhatIfResponse
from app.services.student_analytics_rules import compute_attendance_what_if
from app.services.student_service import StudentService
from fastapi import HTTPException


class FakeConn:
    def __init__(self, fetch_sequence=None, fetchrow_row=None):
        self.fetch_sequence = list(fetch_sequence or [])
        self.fetchrow_row = fetchrow_row
        self.executed = []

    async def fetch(self, query, *args):
        self.executed.append(("fetch", query, args))
        if self.fetch_sequence:
            return self.fetch_sequence.pop(0)
        return []

    async def fetchrow(self, query, *args):
        self.executed.append(("fetchrow", query, args))
        return self.fetchrow_row


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


def attendance_row(**overrides):
    row = {
        "subject_id": "SUBJ-A",
        "subject_code": "CSE701",
        "subject_name": "Software Engineering",
        "credits": 4,
        "total_classes": 40,
        "attended_classes": 32,
        "attendance_percentage": 80.0,
        "attendance_status": "Good",
        "eligibility_status": "Eligible",
        "shortage_flag": "No",
        "performance_percentage": 78.0,
        "grade": "A",
        "result_status": "Pass",
    }
    row.update(overrides)
    return row


PROFILE_ROW = {
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
    "total_credits_registered": 60,
    "total_credits_earned": 45,
    "total_backlogs": 1,
    "academic_standing": "Good",
}


class AttendanceWhatIfRuleTests(unittest.TestCase):
    """Pure projection + target-math matrix."""

    def test_no_hypothetical_keeps_baseline(self):
        result = compute_attendance_what_if(40, 32)
        self.assertTrue(result["complete"])
        self.assertEqual(result["current_attendance"], 80.0)
        self.assertEqual(result["resulting_attendance"], 80.0)
        self.assertEqual(result["delta"], 0.0)
        self.assertTrue(result["at_target"])
        self.assertEqual(result["attendance_status"], "Good")
        self.assertEqual(result["eligibility_status"], "Eligible")
        self.assertEqual(result["shortage_flag"], "No")

    def test_attend_next_classes_raises_percentage(self):
        # (32 + 2) / (40 + 2) = 34/42 = 80.95%
        result = compute_attendance_what_if(40, 32, hypothetical_present=2)
        self.assertEqual(result["resulting_attendance"], 80.95)
        self.assertEqual(result["delta"], 0.95)
        self.assertTrue(result["at_target"])

    def test_miss_next_classes_lowers_percentage(self):
        # 32 / (40 + 4) = 72.73% -> below target, not eligible, shortage flagged.
        result = compute_attendance_what_if(40, 32, hypothetical_absent=4)
        self.assertEqual(result["resulting_attendance"], 72.73)
        self.assertEqual(result["delta"], -7.27)
        self.assertFalse(result["at_target"])
        self.assertEqual(result["attendance_status"], "Low")
        self.assertEqual(result["eligibility_status"], "Not Eligible")
        self.assertEqual(result["shortage_flag"], "Yes")
        self.assertIn("below the 75% target", result["message"])

    def test_present_and_absent_combine(self):
        # 40 held, 32 attended: attend 2, miss 1 -> (34)/(43) = 79.07%.
        result = compute_attendance_what_if(
            40, 32, hypothetical_present=2, hypothetical_absent=1
        )
        self.assertEqual(result["resulting_attendance"], 79.07)

    def test_classes_to_reach_target(self):
        # 24/40 = 60%. Need (24 + N)/(40 + N) >= 75% -> N = 24.
        result = compute_attendance_what_if(40, 24)
        self.assertEqual(result["classes_to_reach_target"], 24)
        self.assertEqual(result["classes_to_skip_below_target"], 0)
        self.assertFalse(result["at_target"])

    def test_classes_skippable_before_dropping_below_target(self):
        # 32/40 = 80%. Can miss floor(32/0.75 - 40) = 2 classes.
        result = compute_attendance_what_if(40, 32)
        self.assertEqual(result["classes_to_reach_target"], 0)
        self.assertEqual(result["classes_to_skip_below_target"], 2)

    def test_exactly_at_target_cannot_skip_any(self):
        # 15/20 = 75%: missing even one class drops below the target.
        result = compute_attendance_what_if(20, 15)
        self.assertTrue(result["at_target"])
        self.assertEqual(result["classes_to_reach_target"], 0)
        self.assertEqual(result["classes_to_skip_below_target"], 0)

    def test_zero_total_is_incomplete(self):
        result = compute_attendance_what_if(0, 0)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["current_attendance"])
        self.assertIsNone(result["resulting_attendance"])
        self.assertIsNone(result["attendance_status"])

    def test_attended_exceeding_total_is_incomplete(self):
        result = compute_attendance_what_if(40, 45)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["resulting_attendance"])

    def test_status_bands_follow_canonical_aggregate(self):
        # Bands: >=90 Excellent | 80-89 Good | 75-79 Average | 60-74 Low | <60 Critical.
        cases = [
            ((90, 81), "Excellent", "Eligible", "No"),
            ((40, 32), "Good", "Eligible", "No"),
            ((20, 15), "Average", "Eligible", "No"),
            ((40, 24), "Low", "Not Eligible", "Yes"),
            ((40, 16), "Critical", "Not Eligible", "Yes"),
        ]
        for (total, attended), status, eligibility, shortage in cases:
            with self.subTest(total=total, attended=attended):
                result = compute_attendance_what_if(total, attended)
                self.assertEqual(result["attendance_status"], status)
                self.assertEqual(result["eligibility_status"], eligibility)
                self.assertEqual(result["shortage_flag"], shortage)

    def test_custom_target_is_honoured(self):
        # 32/40 = 80%. To reach 85%: (32 + N)/(40 + N) >= 0.85 -> N = 14.
        result = compute_attendance_what_if(40, 32, target_attendance=85.0)
        self.assertEqual(result["target_attendance"], 85.0)
        self.assertFalse(result["at_target"])
        self.assertEqual(result["classes_to_reach_target"], 14)


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


class AttendanceWhatIfServiceTests(unittest.TestCase):
    def _service(self, conn):
        return StudentService(FakePool(conn))

    def test_context_only_call_returns_sorted_baseline(self):
        rows = [
            attendance_row(
                subject_id="SUBJ-B", subject_name="Databases", subject_code="CSE702"
            ),
            attendance_row(
                subject_id="SUBJ-A", subject_name="Algorithms", subject_code="CSE701"
            ),
        ]
        conn = FakeConn(fetch_sequence=[rows], fetchrow_row=dict(PROFILE_ROW))
        response = run(self._service(conn).simulate_attendance("STU-A"))
        self.assertIsInstance(response, AttendanceWhatIfResponse)
        self.assertEqual(response.student_id, "STU-A")
        self.assertEqual(response.context.target_attendance, 75.0)
        self.assertIsNone(response.simulation)
        # Subjects sorted by name.
        self.assertEqual(
            [s.subject_name for s in response.context.subjects],
            ["Algorithms", "Databases"],
        )

    def test_context_recomputes_percentage_from_counts(self):
        rows = [
            attendance_row(
                total_classes=50,
                attended_classes=25,
                attendance_percentage=None,  # stored aggregate stale/absent
            )
        ]
        conn = FakeConn(fetch_sequence=[rows], fetchrow_row=dict(PROFILE_ROW))
        response = run(self._service(conn).simulate_attendance("STU-A"))
        subject = response.context.subjects[0]
        self.assertEqual(subject.total_classes, 50)
        self.assertEqual(subject.attended_classes, 25)
        self.assertEqual(subject.attendance_percentage, 50.0)

    def test_simulation_with_subject_id(self):
        rows = [attendance_row()]
        conn = FakeConn(fetch_sequence=[rows], fetchrow_row=dict(PROFILE_ROW))
        response = run(
            self._service(conn).simulate_attendance(
                "STU-A", "SUBJ-A", hypothetical_present=2
            )
        )
        sim = response.simulation
        self.assertIsNotNone(sim)
        self.assertTrue(sim.complete)
        self.assertEqual(sim.subject_code, "CSE701")
        self.assertEqual(sim.hypothetical_present, 2)
        self.assertEqual(sim.resulting_attendance, 80.95)
        self.assertEqual(sim.classes_to_skip_below_target, 2)

    def test_unknown_subject_404(self):
        rows = [attendance_row()]
        conn = FakeConn(fetch_sequence=[rows], fetchrow_row=dict(PROFILE_ROW))
        with self.assertRaises(HTTPException) as ctx:
            run(self._service(conn).simulate_attendance("STU-A", "NOPE"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_missing_student_404(self):
        conn = FakeConn(fetchrow_row=None)
        with self.assertRaises(HTTPException) as ctx:
            run(self._service(conn).simulate_attendance("NOPE"))
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
