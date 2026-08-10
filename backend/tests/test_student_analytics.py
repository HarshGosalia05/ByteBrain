"""Contract + rule tests for MD-03 Student Performance Analytics.

Covers (from the MD-03 acceptance checklist):
  * Student ownership / read-only routing
  * Trend calculations and interpretation
  * Strength classification thresholds
  * Needs Attention classification (failed / critical / needs-attention /
    declining / incomplete)
  * Learning-gap rules (assessment progression gap, repeated weakness) and the
    guarantee that an incomplete assessment is NOT a learning gap
  * Privacy-safe class benchmark (matching, min cohort, NULL handling,
    no peer identity fields)
  * Attempt history (grouping, improvement, missing history)
  * What-if simulator (reuses canonical derivation, never persists)

Pure rule tests use crafted rows. Service-level tests use a fake asyncpg pool
that records the executed SQL, so no live database is required.
"""

import asyncio
import unittest

from app.schemas.student_analytics import (
    AttemptHistoryItem,
    BenchmarkItem,
    StudentAnalyticsResponse,
    WhatIfResponse,
)
from app.services.student_analytics_rules import (
    classify_subject,
    compute_attempt_history,
    compute_benchmark,
    compute_learning_gaps,
    compute_needs_attention,
    compute_strengths,
    compute_trends,
)
from app.services.student_service import StudentService
from fastapi import HTTPException


class FakeConn:
    def __init__(self, fetch_sequence=None, fetchrow_row=None):
        self.fetch_sequence = list(fetch_sequence or [])
        self.fetchrow_row = fetchrow_row
        self.executed = []  # list of (kind, query, args)

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


def run(coro):
    return asyncio.run(coro)


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


# ---------------------------------------------------------------------------
# Feature 1 — Performance trends
# ---------------------------------------------------------------------------


class TrendRulesTests(unittest.TestCase):
    def test_trends_improvement_interpretation(self):
        summaries = [
            summary_row(semester=1, sgpa=8.1, semester_percentage=72.0, attendance_percentage=88.0),
            summary_row(semester=2, sgpa=8.4, semester_percentage=75.0, attendance_percentage=90.0),
            summary_row(semester=3, sgpa=8.7, semester_percentage=78.0, attendance_percentage=91.0),
        ]
        trends = compute_trends(summaries)
        sgpa = trends["movements"]["sgpa"]
        self.assertTrue(sgpa["available"])
        self.assertEqual(sgpa["delta"], 0.3)
        self.assertEqual(sgpa["previous_semester"], 2)
        self.assertEqual(sgpa["current_semester"], 3)
        self.assertEqual(sgpa["direction"], "up")
        self.assertEqual(trends["overall_direction"], "improving")
        self.assertIn("improved by 0.30 from Semester 2 to Semester 3", trends["interpretation"])

    def test_trends_decline_interpretation(self):
        summaries = [
            summary_row(semester=1, sgpa=8.7),
            summary_row(semester=2, sgpa=8.5),
        ]
        trends = compute_trends(summaries)
        sgpa = trends["movements"]["sgpa"]
        self.assertEqual(sgpa["direction"], "down")
        self.assertEqual(sgpa["delta"], -0.2)
        self.assertEqual(trends["overall_direction"], "declining")
        self.assertIn("declined by 0.20 SGPA in the latest semester", trends["interpretation"])

    def test_trends_null_metrics_stay_null_and_do_not_break_trend(self):
        summaries = [
            summary_row(semester=1, sgpa=None, semester_percentage=None, attendance_percentage=85.0),
            summary_row(semester=2, sgpa=8.2, semester_percentage=None, attendance_percentage=91.0),
        ]
        trends = compute_trends(summaries)
        self.assertEqual(trends["points"][0]["sgpa"], None)
        self.assertFalse(trends["movements"]["percentage"]["available"])
        self.assertTrue(trends["movements"]["attendance"]["available"])
        self.assertFalse(trends["movements"]["sgpa"]["available"])

    def test_trends_insufficient_history(self):
        trends = compute_trends([summary_row(semester=1, sgpa=8.1)])
        self.assertEqual(trends["overall_direction"], "insufficient")
        self.assertEqual(trends["interpretation"], "Not enough semester history to determine a trend.")
        self.assertFalse(trends["movements"]["sgpa"]["available"])


# ---------------------------------------------------------------------------
# Feature 2 — Strengths
# ---------------------------------------------------------------------------


class StrengthRulesTests(unittest.TestCase):
    def test_classify_subject_bands(self):
        self.assertEqual(classify_subject(87.14), "Strong")
        self.assertEqual(classify_subject(75.0), "Strong")
        self.assertEqual(classify_subject(60.0), "Good")
        self.assertEqual(classify_subject(48.0), "Needs Attention")
        self.assertEqual(classify_subject(44.99), "Critical")

    def test_strengths_only_strong_and_good(self):
        rows = [
            perf_row(subject_code="CSE704", subject_name="Deep Learning", percentage=87.14, grade="A+", grade_point=9),
            perf_row(subject_code="CSE701", subject_name="Software Engineering", percentage=65.0, grade="B+", grade_point=7),
            perf_row(subject_code="CSE702", subject_name="HCI", percentage=55.0, grade="B", grade_point=6),
            perf_row(subject_code="CSE703", subject_name="ISE", percentage=None),
        ]
        strengths = compute_strengths(rows)
        self.assertEqual([s["subject_code"] for s in strengths], ["CSE704", "CSE701"])
        self.assertEqual(strengths[0]["category"], "Strong")
        self.assertEqual(strengths[1]["category"], "Good")

    def test_strengths_use_latest_attempt(self):
        rows = [
            perf_row(subject_code="CSE701", subject_name="SE", semester=7, percentage=50.0, attempt_number=1),
            perf_row(subject_code="CSE701", subject_name="SE", semester=8, percentage=78.0, attempt_number=2, grade="A"),
        ]
        strengths = compute_strengths(rows)
        self.assertEqual(len(strengths), 1)
        self.assertEqual(strengths[0]["percentage"], 78.0)
        self.assertEqual(strengths[0]["category"], "Strong")


# ---------------------------------------------------------------------------
# Feature 3 — Needs Attention
# ---------------------------------------------------------------------------


class NeedsAttentionRulesTests(unittest.TestCase):
    def test_needs_attention_failed_has_top_priority(self):
        rows = [perf_row(subject_code="CSE705", subject_name="NLP", percentage=38.0, result_status="Fail", grade="F", grade_point=0)]
        items = compute_needs_attention(rows)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["reason_code"], "failed")
        self.assertEqual(items[0]["priority"], 1)

    def test_needs_attention_critical_band(self):
        rows = [perf_row(subject_code="CSE703", subject_name="ISE", percentage=42.0, result_status="Pass")]
        items = compute_needs_attention(rows)
        self.assertEqual(items[0]["reason_code"], "critical")
        self.assertEqual(items[0]["reason"], "Very low percentage")

    def test_needs_attention_band_matches_spec_example(self):
        rows = [perf_row(subject_code="CSE705", subject_name="NLP", percentage=48.0, result_status="Pass")]
        items = compute_needs_attention(rows)
        self.assertEqual(items[0]["reason_code"], "needs_attention")
        self.assertEqual(items[0]["reason"], "Needs attention")

    def test_needs_attention_incomplete_is_not_failure(self):
        rows = [
            perf_row(
                subject_code="CSE706",
                subject_name="DL Lab",
                internal_marks=16.0,
                mid_sem_marks=42.0,
                end_sem_marks=None,
                percentage=None,
                result_status=None,
            )
        ]
        items = compute_needs_attention(rows)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["reason_code"], "incomplete")
        self.assertEqual(items[0]["reason"], "Final result pending")
        self.assertIsNone(items[0]["percentage"])

    def test_needs_attention_declining_across_attempts(self):
        rows = [
            perf_row(subject_code="CSE702", subject_name="HCI", semester=7, percentage=68.0, result_status="Pass", attempt_number=1),
            perf_row(subject_code="CSE702", subject_name="HCI", semester=8, percentage=62.0, result_status="Pass", attempt_number=2),
        ]
        items = compute_needs_attention(rows)
        self.assertEqual(items[0]["reason_code"], "declining")
        self.assertEqual(items[0]["reason"], "Performance declined across attempts")

    def test_needs_attention_empty_for_good_performance(self):
        rows = [
            perf_row(subject_code="CSE701", subject_name="SE", percentage=82.0, result_status="Pass"),
            perf_row(subject_code="CSE704", subject_name="DL", percentage=90.0, result_status="Pass"),
        ]
        self.assertEqual(compute_needs_attention(rows), [])


# ---------------------------------------------------------------------------
# Feature 4 — Learning gaps
# ---------------------------------------------------------------------------


class LearningGapRulesTests(unittest.TestCase):
    def test_assessment_progression_gap(self):
        rows = [
            perf_row(
                subject_code="CSE705",
                subject_name="NLP",
                internal_marks=18.0,
                mid_sem_marks=24.0,
                end_sem_marks=None,
                percentage=None,
            )
        ]
        gaps = compute_learning_gaps(rows)
        gap = next(g for g in gaps if g["signal_code"] == "assessment_progression_gap")
        self.assertIn("internal assessment", gap["detail"])
        self.assertIn("mid-sem", gap["detail"])
        self.assertIn("42.0 percentage points", gap["detail"])

    def test_incomplete_assessment_is_not_a_learning_gap(self):
        rows = [
            perf_row(
                subject_code="CSE706",
                subject_name="DL Lab",
                internal_marks=16.0,
                mid_sem_marks=42.0,
                end_sem_marks=None,
                percentage=None,
            )
        ]
        self.assertEqual(compute_learning_gaps(rows), [])

    def test_repeated_weakness_signal(self):
        rows = [
            perf_row(subject_code="CSE702", subject_name="HCI", semester=7, percentage=48.0, attempt_number=1),
            perf_row(subject_code="CSE702", subject_name="HCI", semester=8, percentage=52.0, attempt_number=2),
        ]
        gaps = compute_learning_gaps(rows)
        self.assertTrue(any(g["signal_code"] == "repeated_weakness" for g in gaps))

    def test_repeated_low_performance_signal(self):
        rows = [
            perf_row(subject_code="CSE705", subject_name="NLP", semester=7, percentage=38.0, attempt_number=1),
            perf_row(subject_code="CSE705", subject_name="NLP", semester=8, percentage=42.0, attempt_number=2),
        ]
        gaps = compute_learning_gaps(rows)
        self.assertTrue(any(g["signal_code"] == "repeated_low_performance" for g in gaps))

    def test_no_gap_when_components_rise(self):
        rows = [
            perf_row(
                subject_code="CSE701",
                subject_name="SE",
                internal_marks=12.0,
                mid_sem_marks=44.0,
                end_sem_marks=60.0,
                percentage=82.0,
            )
        ]
        self.assertEqual(compute_learning_gaps(rows), [])


# ---------------------------------------------------------------------------
# Feature 5 — Privacy-safe class benchmark
# ---------------------------------------------------------------------------


class ClassBenchmarkRulesTests(unittest.TestCase):
    def test_benchmark_matching_and_difference(self):
        rows = [
            perf_row(
                subject_code="CSE704",
                subject_name="Deep Learning",
                subject_id="SUBJ-4",
                semester=7,
                percentage=78.0,
            )
        ]
        averages = [
            {
                "subject_id": "SUBJ-4",
                "semester_no": 7,
                "academic_year": "2026-27",
                "cohort_size": 12,
                "class_average": 71.0,
            }
        ]
        items = compute_benchmark(rows, averages)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["available"])
        self.assertEqual(items[0]["your_percentage"], 78.0)
        self.assertEqual(items[0]["class_average"], 71.0)
        self.assertEqual(items[0]["difference"], 7.0)
        self.assertEqual(items[0]["cohort_size"], 12)

    def test_benchmark_minimum_cohort_threshold(self):
        rows = [perf_row(subject_code="CSE704", subject_name="DL", subject_id="SUBJ-4", percentage=78.0)]
        averages = [
            {
                "subject_id": "SUBJ-4",
                "semester_no": 7,
                "academic_year": "2026-27",
                "cohort_size": 4,
                "class_average": 71.0,
            }
        ]
        items = compute_benchmark(rows, averages)
        self.assertFalse(items[0]["available"])
        self.assertIsNone(items[0]["class_average"])
        self.assertIsNone(items[0]["difference"])
        self.assertEqual(items[0]["cohort_size"], 4)

    def test_benchmark_skips_null_percentage(self):
        rows = [perf_row(subject_code="CSE701", subject_name="SE", percentage=None)]
        self.assertEqual(compute_benchmark(rows, []), [])

    def test_benchmark_unavailable_when_no_average(self):
        rows = [perf_row(subject_code="CSE701", subject_name="SE", percentage=70.0)]
        items = compute_benchmark(rows, [])
        self.assertFalse(items[0]["available"])
        self.assertEqual(items[0]["cohort_size"], 0)


# ---------------------------------------------------------------------------
# Feature 6 — Attempt history
# ---------------------------------------------------------------------------


class AttemptHistoryRulesTests(unittest.TestCase):
    def test_attempt_history_grouping_and_improvement(self):
        rows = [
            perf_row(
                subject_code="CSE705",
                subject_name="NLP",
                semester=7,
                percentage=42.0,
                grade="F",
                grade_point=0,
                result_status="Fail",
                attempt_number=1,
                academic_year="2026-27",
            ),
            perf_row(
                subject_code="CSE705",
                subject_name="NLP",
                semester=8,
                percentage=61.0,
                grade="B+",
                grade_point=7,
                result_status="Pass",
                attempt_number=2,
                academic_year="2027-28",
            ),
        ]
        history = compute_attempt_history(rows)
        self.assertEqual(len(history), 1)
        item = history[0]
        self.assertTrue(item["has_multiple_attempts"])
        self.assertEqual(len(item["attempts"]), 2)
        self.assertEqual(item["attempts"][0]["attempt_number"], 1)
        self.assertEqual(item["attempts"][0]["result_status"], "Fail")
        self.assertEqual(item["attempts"][1]["attempt_number"], 2)
        self.assertEqual(item["attempts"][1]["result_status"], "Pass")
        self.assertEqual(item["improvement"], 19.0)

    def test_missing_attempt_history_is_flagged(self):
        rows = [perf_row(subject_code="CSE701", subject_name="SE", percentage=70.0, attempt_number=1)]
        history = compute_attempt_history(rows)
        self.assertEqual(len(history), 1)
        self.assertFalse(history[0]["has_multiple_attempts"])
        self.assertIsNone(history[0]["improvement"])
        self.assertEqual(len(history[0]["attempts"]), 1)


# ---------------------------------------------------------------------------
# Service-level tests (ownership, benchmark scoping, what-if)
# ---------------------------------------------------------------------------


class StudentAnalyticsServiceTests(unittest.TestCase):
    def _service(self, conn):
        return StudentService(FakePool(conn))

    def test_analytics_404_when_student_missing(self):
        conn = FakeConn(fetchrow_row=None)
        with self.assertRaises(HTTPException) as ctx:
            run(self._service(conn).get_analytics("NOPE"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_analytics_queries_scoped_and_benchmark_excludes_self(self):
        summaries = [summary_row(semester=7, sgpa=8.4)]
        performance = [
            perf_row(
                subject_code="CSE704",
                subject_name="Deep Learning",
                subject_id="SUBJ-4",
                percentage=78.0,
            )
        ]
        benchmarks = [
            {
                "subject_id": "SUBJ-4",
                "semester_no": 7,
                "academic_year": "2026-27",
                "cohort_size": 12,
                "class_average": 71.0,
            }
        ]
        conn = FakeConn(
            fetch_sequence=[summaries, performance, benchmarks],
            fetchrow_row=dict(PROFILE_ROW),
        )
        response = run(self._service(conn).get_analytics("STU-A"))
        self.assertIsInstance(response, StudentAnalyticsResponse)
        self.assertEqual(response.student_id, "STU-A")

        self.assertEqual(conn.executed[0][0], "fetchrow")
        self.assertEqual(conn.executed[0][2], ("STU-A",))
        self.assertIn("student_id = $1", conn.executed[1][1])
        self.assertEqual(conn.executed[1][2], ("STU-A",))
        self.assertIn("sse.student_id = $1", conn.executed[2][1])

        benchmark_kind, benchmark_query, benchmark_args = conn.executed[3]
        self.assertEqual(benchmark_kind, "fetch")
        self.assertIn("sse.department_code = $1", benchmark_query)
        self.assertIn("sp.student_id <> $2", benchmark_query)
        self.assertIn("sse.subject_id = ANY($3::text[])", benchmark_query)
        self.assertEqual(benchmark_args[0], "CSE")
        self.assertEqual(benchmark_args[1], "STU-A")
        self.assertEqual(benchmark_args[2], ["SUBJ-4"])

        self.assertTrue(response.class_benchmark[0].available)
        self.assertEqual(response.class_benchmark[0].difference, 7.0)

    def test_analytics_no_benchmark_query_without_department(self):
        profile = dict(PROFILE_ROW)
        profile["department_code"] = None
        performance = [perf_row(subject_code="CSE704", subject_name="DL", percentage=78.0)]
        conn = FakeConn(
            fetch_sequence=[[], performance],
            fetchrow_row=profile,
        )
        run(self._service(conn).get_analytics("STU-A"))
        self.assertEqual(len(conn.executed), 3)  # profile + summaries + performance only

    def test_what_if_reuses_canonical_derivation(self):
        service = StudentService(FakePool(FakeConn()))
        result = service.simulate_marks(18, 49, 60)
        self.assertIsInstance(result, WhatIfResponse)
        self.assertTrue(result.complete)
        self.assertEqual(result.total_marks, 127)
        self.assertEqual(result.percentage, 90.71)
        self.assertEqual(result.grade, "O")
        self.assertEqual(result.grade_point, 10)
        self.assertEqual(result.result_status, "Pass")

    def test_what_if_incomplete_keeps_derived_null(self):
        service = StudentService(FakePool(FakeConn()))
        result = service.simulate_marks(18, 49, None)
        self.assertFalse(result.complete)
        self.assertIsNone(result.total_marks)
        self.assertIsNone(result.percentage)
        self.assertIsNone(result.grade)
        self.assertIsNone(result.grade_point)
        self.assertIsNone(result.result_status)

    def test_what_if_never_touches_database(self):
        conn = FakeConn()
        service = StudentService(FakePool(conn))
        service.simulate_marks(10, 20, 30)
        self.assertEqual(conn.executed, [])

    def test_what_if_rejects_negative_marks(self):
        service = StudentService(FakePool(FakeConn()))
        with self.assertRaises(HTTPException) as cm:
            service.simulate_marks(-25, 90, -2)
        self.assertEqual(cm.exception.status_code, 422)

    def test_what_if_rejects_over_max_marks(self):
        service = StudentService(FakePool(FakeConn()))
        with self.assertRaises(HTTPException) as cm:
            service.simulate_marks(20, 90, 70)
        self.assertEqual(cm.exception.status_code, 422)

    def test_what_if_rejects_non_integer_marks(self):
        service = StudentService(FakePool(FakeConn()))
        with self.assertRaises(HTTPException) as cm:
            service.simulate_marks(12.5, 50, 70)
        self.assertEqual(cm.exception.status_code, 422)

    def test_what_if_end_sem_below_min_cannot_pass(self):
        service = StudentService(FakePool(FakeConn()))
        result = service.simulate_marks(20, 50, 17)
        self.assertTrue(result.complete)
        self.assertEqual(result.total_marks, 87)
        self.assertEqual(result.percentage, 62.14)
        self.assertEqual(result.result_status, "Fail")

    def test_what_if_end_sem_at_min_can_pass(self):
        service = StudentService(FakePool(FakeConn()))
        result = service.simulate_marks(20, 50, 18)
        self.assertTrue(result.complete)
        self.assertEqual(result.total_marks, 88)
        self.assertEqual(result.result_status, "Pass")

    def test_student_router_is_read_only(self):
        from app.api.v1 import student

        for route in student.router.routes:
            if not hasattr(route, "methods"):
                continue
            self.assertTrue(
                route.methods <= {"GET"},
                f"Route {route.path} must be GET-only, got {route.methods}",
            )

    def test_benchmark_schema_exposes_no_peer_identity(self):
        fields = set(BenchmarkItem.model_fields.keys())
        self.assertTrue({"class_average", "cohort_size", "difference"} <= fields)
        self.assertFalse(
            fields & {"peer_student_id", "peer_enrollment_no", "peer_name", "student_id"}
        )


if __name__ == "__main__":
    unittest.main()
