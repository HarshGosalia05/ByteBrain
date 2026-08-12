"""Contract tests for the MD-03 admin academic / department / subject intelligence.

Covers:
  * Academic overview KPIs (SGPA / percentage / attendance / pass rate /
    backlogs / credits earned).
  * Pass rate excludes Pending from numerator and denominator and reports
    None when there are no completed results.
  * Grade distribution uses canonical order; NULL grade maps to Pending,
    never to F.
  * Academic trend includes the attendance metric for the metric toggle.
  * Department analytics (students / faculty / SGPA / percentage / attendance
    / backlogs / pass rate / at-risk) and deterministic ranking.
  * Subject aggregation (student count, marks components, pass rate,
    attendance) via the canonical enrollment join.
  * NULL marks stay None; top / weak subjects and pass-rate ranking slices.
  * Assessment analysis normalizes each component against its own maximum.
  * Filters are forwarded into the executed SQL as parameters.
  * All reads are SELECT-only; the endpoints depend on require_admin_role
    (the full access-control matrix is covered in test_admin_auth.py).

No live database is required: a fake asyncpg pool records the executed SQL.
"""

import asyncio
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from app.api.v1 import admin as admin_api
from app.api.dependencies import require_admin_role
from app.schemas.admin_academic import (
    AcademicOverviewResponse,
    DepartmentAnalyticsResponse,
    SubjectIntelligenceResponse,
)
from app.services.admin_service import AdminService


def run(coro):
    return asyncio.run(coro)


class FakeConn:
    """Routes responses by (kind, substring) so every query returns its row."""

    def __init__(self, responses):
        self.responses = responses or {}
        self.executed = []

    async def fetch(self, query, *args):
        self.executed.append(("fetch", query, args))
        return self._match("fetch", query)

    async def fetchrow(self, query, *args):
        self.executed.append(("fetchrow", query, args))
        return self._match("fetchrow", query)

    def _match(self, kind, query):
        for (key_kind, sub), result in self.responses.items():
            if key_kind == kind and sub in query:
                return result
        return [] if kind == "fetch" else None


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


def _default_responses(overrides=None):
    responses = {
        ("fetchrow", "AVG(sem.semester_sgpa)"): {
            "avg_sgpa": Decimal("7.5"),
            "avg_percentage": Decimal("72.53"),
            "avg_attendance": Decimal("81.01"),
        },
        ("fetchrow", "SELECT\n                (SELECT COUNT(*)"): {
            "total_students": 80,
            "total_faculty": 25,
            "total_departments": 2,
            "avg_cgpa": Decimal("7.861"),
            "total_backlogs": 120,
        },
        ("fetchrow", "AS pass_count,\n                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'FAIL') AS fail_count\n            FROM student_subject_performance p"): {
            "pass_count": 3400,
            "fail_count": 150,
        },
        ("fetchrow", "COALESCE(SUM(e.credits), 0) AS credits_earned"): {
            "credits_earned": 820,
        },
        ("fetchrow", "AVG(p.internal_marks) AS avg_internal"): {
            "avg_internal": Decimal("15.2"),
            "avg_mid_sem": Decimal("38.4"),
            "avg_end_sem": None,
            "total_rows": 3550,
        },
        ("fetch", "sem.semester_no AS semester"): [
            {
                "semester": 1,
                "avg_sgpa": Decimal("7.1"),
                "avg_percentage": Decimal("68.5"),
                "avg_attendance": Decimal("80.0"),
            },
            {
                "semester": 2,
                "avg_sgpa": Decimal("7.4"),
                "avg_percentage": Decimal("71.0"),
                "avg_attendance": Decimal("82.5"),
            },
        ],
        ("fetch", "e.semester_no AS semester,\n                COUNT(*) FILTER"): [
            {"semester": 1, "pass_count": 100, "fail_count": 10},
            {"semester": 2, "pass_count": 50, "fail_count": 0},
        ],
        ("fetch", "COALESCE(p.grade, 'Pending') AS grade"): [
            {"grade": "A", "count": 1700},
            {"grade": "Pending", "count": 300},
            {"grade": "F", "count": 90},
            {"grade": "O", "count": 353},
        ],
        ("fetch", "COUNT(DISTINCT s.student_id) AS total_students"): [
            {
                "department_code": 1,
                "department_name": "Computer Engineering",
                "department_short_name": "CSE",
                "total_students": 50,
                "avg_sgpa": Decimal("7.8"),
                "avg_percentage": Decimal("75.2"),
                "avg_attendance": Decimal("82.0"),
            },
            {
                "department_code": 2,
                "department_name": "Business Administration",
                "department_short_name": "BBA",
                "total_students": 30,
                "avg_sgpa": Decimal("7.1"),
                "avg_percentage": Decimal("68.1"),
                "avg_attendance": Decimal("78.5"),
            },
        ],
        ("fetch", "SELECT department_code, COUNT(*) AS total_faculty"): [
            {"department_code": 1, "total_faculty": 15},
            {"department_code": 2, "total_faculty": 10},
        ],
        ("fetch", "COALESCE(SUM(s.total_backlogs), 0) AS total_backlogs"): [
            {"department_code": 1, "total_backlogs": 70},
            {"department_code": 2, "total_backlogs": 50},
        ],
        ("fetch", "e.department_code,\n                COUNT(*) FILTER"): [
            {"department_code": 1, "pass_count": 1800, "fail_count": 50},
            {"department_code": 2, "pass_count": 1600, "fail_count": 100},
        ],
        ("fetch", "s.department_code,\n                COALESCE(d.department_name"): [
            {
                "department_code": 1,
                "department_name": "Computer Engineering",
                "risk_level": "HIGH",
                "count": 1,
            },
            {
                "department_code": 1,
                "department_name": "Computer Engineering",
                "risk_level": "CRITICAL",
                "count": 6,
            },
            {
                "department_code": 2,
                "department_name": "Business Administration",
                "risk_level": "HIGH",
                "count": 0,
            },
            {
                "department_code": 2,
                "department_name": "Business Administration",
                "risk_level": "CRITICAL",
                "count": 6,
            },
        ],
        ("fetch", "COUNT(DISTINCT e.enrollment_record_id) AS student_count"): [
            {
                "subject_code": "CS101",
                "subject_name": "Programming",
                "department_code": 1,
                "department_name": "Computer Engineering",
                "semester": 1,
                "student_count": 50,
                "avg_internal": Decimal("15.0"),
                "avg_mid_sem": Decimal("40.0"),
                "avg_end_sem": Decimal("60.0"),
                "avg_percentage": Decimal("82.14"),
                "pass_count": 49,
                "fail_count": 1,
                "avg_attendance": Decimal("85.0"),
            },
            {
                "subject_code": "CS201",
                "subject_name": "Data Structures",
                "department_code": 1,
                "department_name": "Computer Engineering",
                "semester": 3,
                "student_count": 50,
                "avg_internal": Decimal("12.0"),
                "avg_mid_sem": Decimal("30.0"),
                "avg_end_sem": None,
                "avg_percentage": None,
                "pass_count": 0,
                "fail_count": 0,
                "avg_attendance": Decimal("80.0"),
            },
            {
                "subject_code": "BA101",
                "subject_name": "Management",
                "department_code": 2,
                "department_name": "Business Administration",
                "semester": 1,
                "student_count": 30,
                "avg_internal": Decimal("13.0"),
                "avg_mid_sem": Decimal("35.0"),
                "avg_end_sem": Decimal("55.0"),
                "avg_percentage": Decimal("73.57"),
                "pass_count": 28,
                "fail_count": 2,
                "avg_attendance": Decimal("78.0"),
            },
            {
                "subject_code": "BA102",
                "subject_name": "Economics",
                "department_code": 2,
                "department_name": "Business Administration",
                "semester": 1,
                "student_count": 30,
                "avg_internal": Decimal("10.0"),
                "avg_mid_sem": Decimal("28.0"),
                "avg_end_sem": Decimal("40.0"),
                "avg_percentage": Decimal("55.71"),
                "pass_count": 20,
                "fail_count": 10,
                "avg_attendance": Decimal("70.0"),
            },
        ],
        ("fetch", "DISTINCT academic_year FROM student_semester_summary"): [
            {"academic_year": "2024-25"},
            {"academic_year": "2025-26"},
        ],
        ("fetch", "dept_code AS department_code, department_name, "): [
            {
                "department_code": 1,
                "department_name": "Computer Engineering",
                "department_short_name": "CSE",
            },
            {
                "department_code": 2,
                "department_name": "Business Administration",
                "department_short_name": "BBA",
            },
        ],
        ("fetch", "DISTINCT semester_no FROM student_semester_summary"): [
            {"semester_no": 1},
            {"semester_no": 2},
            {"semester_no": 3},
        ],
    }
    if overrides:
        responses.update(overrides)
    return responses


def _service(responses=None):
    conn = FakeConn(_default_responses(responses))
    return AdminService(FakePool(conn)), conn


class AcademicOverviewServiceTests(unittest.TestCase):
    def test_overview_kpis_are_aggregated(self):
        service, _ = _service()
        response = run(service.get_academic_overview())
        self.assertIsInstance(response, AcademicOverviewResponse)
        self.assertAlmostEqual(response.kpis.avg_sgpa, 7.5, places=2)
        self.assertAlmostEqual(response.kpis.avg_percentage, 72.53, places=2)
        self.assertAlmostEqual(response.kpis.avg_attendance, 81.01, places=2)
        self.assertEqual(response.kpis.total_backlogs, 120)
        self.assertEqual(response.kpis.credits_earned, 820)

    def test_pass_rate_excludes_pending_and_is_percentage(self):
        service, _ = _service()
        response = run(service.get_academic_overview())
        self.assertAlmostEqual(response.kpis.pass_rate, 95.77, places=2)

    def test_pass_rate_is_none_when_no_completed_results(self):
        service, _ = _service(
            {
                ("fetchrow", "AS pass_count,\n                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'FAIL') AS fail_count\n            FROM student_subject_performance p"): {
                    "pass_count": 0,
                    "fail_count": 0,
                },
            }
        )
        response = run(service.get_academic_overview())
        self.assertIsNone(response.kpis.pass_rate)

    def test_nulls_stay_none_never_zero(self):
        service, _ = _service(
            {
                ("fetchrow", "AVG(sem.semester_sgpa)"): {
                    "avg_sgpa": None,
                    "avg_percentage": None,
                    "avg_attendance": None,
                },
            }
        )
        response = run(service.get_academic_overview())
        self.assertIsNone(response.kpis.avg_sgpa)
        self.assertIsNone(response.kpis.avg_percentage)
        self.assertIsNone(response.kpis.avg_attendance)

    def test_trend_includes_attendance_for_the_toggle(self):
        service, _ = _service()
        response = run(service.get_academic_overview())
        self.assertEqual(len(response.trend), 2)
        self.assertAlmostEqual(response.trend[0].avg_attendance, 80.0, places=2)
        self.assertAlmostEqual(response.trend[1].avg_attendance, 82.5, places=2)

    def test_pass_rate_trend_maps_each_semester(self):
        service, _ = _service()
        response = run(service.get_academic_overview())
        by_semester = {p.semester: p.pass_rate for p in response.pass_rate_trend}
        self.assertAlmostEqual(by_semester[1], 90.91, places=2)
        self.assertAlmostEqual(by_semester[2], 100.0, places=2)

    def test_grade_distribution_uses_canonical_order(self):
        service, _ = _service()
        response = run(service.get_academic_overview())
        grades = [g.grade for g in response.grade_distribution]
        self.assertEqual(grades, ["O", "A+", "A", "B+", "B", "C", "F", "Pending"])
        counts = {g.grade: g.count for g in response.grade_distribution}
        self.assertEqual(counts["O"], 353)
        self.assertEqual(counts["A"], 1700)
        self.assertEqual(counts["F"], 90)
        self.assertEqual(counts["Pending"], 300)

    def test_null_grade_is_pending_not_f(self):
        service, _ = _service(
            {
                ("fetch", "COALESCE(p.grade, 'Pending') AS grade"): [
                    {"grade": "Pending", "count": 559},
                    {"grade": "F", "count": 90},
                ],
            }
        )
        response = run(service.get_academic_overview())
        counts = {g.grade: g.count for g in response.grade_distribution}
        self.assertEqual(counts["Pending"], 559)
        self.assertEqual(counts["F"], 90)

    def test_empty_scope_returns_zero_bands_and_none_rates(self):
        service, _ = _service(
            {
                ("fetchrow", "AVG(sem.semester_sgpa)"): {
                    "avg_sgpa": None,
                    "avg_percentage": None,
                    "avg_attendance": None,
                },
                ("fetchrow", "SELECT\n                (SELECT COUNT(*)"): {
                    "total_backlogs": 0,
                },
                ("fetchrow", "AS pass_count,\n                COUNT(*) FILTER (WHERE UPPER(p.result_status) = 'FAIL') AS fail_count\n            FROM student_subject_performance p"): {
                    "pass_count": 0,
                    "fail_count": 0,
                },
                ("fetchrow", "COALESCE(SUM(e.credits), 0) AS credits_earned"): {
                    "credits_earned": 0,
                },
                ("fetch", "sem.semester_no AS semester"): [],
                ("fetch", "e.semester_no AS semester,\n                COUNT(*) FILTER"): [],
                ("fetch", "COALESCE(p.grade, 'Pending') AS grade"): [],
            }
        )
        response = run(service.get_academic_overview())
        self.assertIsNone(response.kpis.pass_rate)
        self.assertEqual(response.kpis.credits_earned, 0)
        self.assertEqual(response.trend, [])
        self.assertEqual(response.pass_rate_trend, [])
        self.assertEqual(
            [g.grade for g in response.grade_distribution],
            ["O", "A+", "A", "B+", "B", "C", "F", "Pending"],
        )
        self.assertTrue(all(g.count == 0 for g in response.grade_distribution))


class DepartmentAnalyticsServiceTests(unittest.TestCase):
    def test_department_metrics_are_assembled(self):
        service, _ = _service()
        response = run(service.get_department_analytics())
        self.assertIsInstance(response, DepartmentAnalyticsResponse)
        by_code = {d.department_code: d for d in response.departments}
        cse = by_code[1]
        self.assertEqual(cse.total_students, 50)
        self.assertEqual(cse.total_faculty, 15)
        self.assertEqual(cse.total_backlogs, 70)
        self.assertAlmostEqual(cse.avg_sgpa, 7.8, places=2)
        self.assertAlmostEqual(cse.avg_percentage, 75.2, places=2)
        self.assertAlmostEqual(cse.avg_attendance, 82.0, places=2)
        self.assertAlmostEqual(cse.pass_rate, 97.3, places=2)
        self.assertEqual(cse.at_risk_students, 7)
        self.assertEqual(cse.department_short_name, "CSE")
        bands = {r.risk_level: r.count for r in cse.risk_distribution}
        self.assertEqual(bands, {"Low": 0, "Moderate": 0, "High": 1, "Critical": 6})

    def test_department_ranking_is_deterministic(self):
        service, _ = _service()
        response = run(service.get_department_analytics())
        self.assertEqual(response.ranking[0].department_code, 1)
        self.assertEqual(response.ranking[1].department_code, 2)
        self.assertEqual(response.ranking[0].rank, 1)
        self.assertEqual(response.ranking[1].rank, 2)

    def test_department_ranking_puts_unscored_last(self):
        service, _ = _service(
            {
                ("fetch", "COUNT(DISTINCT s.student_id) AS total_students"): [
                    {
                        "department_code": 1,
                        "department_name": "Computer Engineering",
                        "department_short_name": "CSE",
                        "total_students": 50,
                        "avg_sgpa": None,
                        "avg_percentage": None,
                        "avg_attendance": None,
                    },
                    {
                        "department_code": 2,
                        "department_name": "Business Administration",
                        "department_short_name": "BBA",
                        "total_students": 30,
                        "avg_sgpa": Decimal("7.1"),
                        "avg_percentage": Decimal("68.1"),
                        "avg_attendance": Decimal("78.5"),
                    },
                ],
            }
        )
        response = run(service.get_department_analytics())
        self.assertEqual([d.department_code for d in response.ranking], [2, 1])


class SubjectIntelligenceServiceTests(unittest.TestCase):
    def test_subject_rows_are_aggregated(self):
        service, _ = _service()
        response = run(service.get_subject_intelligence())
        self.assertIsInstance(response, SubjectIntelligenceResponse)
        by_code = {s.subject_code: s for s in response.subjects}
        cs101 = by_code["CS101"]
        self.assertEqual(cs101.student_count, 50)
        self.assertAlmostEqual(cs101.avg_internal, 15.0, places=2)
        self.assertAlmostEqual(cs101.avg_mid_sem, 40.0, places=2)
        self.assertAlmostEqual(cs101.avg_end_sem, 60.0, places=2)
        self.assertAlmostEqual(cs101.avg_percentage, 82.14, places=2)
        self.assertAlmostEqual(cs101.pass_rate, 98.0, places=2)
        self.assertAlmostEqual(cs101.avg_attendance, 85.0, places=2)
        self.assertEqual(cs101.department_name, "Computer Engineering")
        self.assertEqual(cs101.semester, 1)

    def test_pending_subject_keeps_nulls_and_no_pass_rate(self):
        service, _ = _service()
        response = run(service.get_subject_intelligence())
        cs201 = next(s for s in response.subjects if s.subject_code == "CS201")
        self.assertIsNone(cs201.avg_end_sem)
        self.assertIsNone(cs201.avg_percentage)
        self.assertIsNone(cs201.pass_rate)

    def test_top_and_weak_subjects_use_average_percentage(self):
        service, _ = _service()
        response = run(service.get_subject_intelligence())
        self.assertEqual(
            [s.subject_code for s in response.top_subjects],
            ["CS101", "BA101", "BA102"],
        )
        self.assertEqual(
            [s.subject_code for s in response.weak_subjects],
            ["BA102", "BA101", "CS101"],
        )
        # Pending (no percentage) subjects never appear in top/weak lists.
        self.assertNotIn("CS201", [s.subject_code for s in response.top_subjects])
        self.assertNotIn("CS201", [s.subject_code for s in response.weak_subjects])

    def test_subject_pass_rate_ranking_excludes_pending(self):
        service, _ = _service()
        response = run(service.get_subject_intelligence())
        codes = [s.subject_code for s in response.pass_rate_ranking]
        self.assertEqual(codes, ["CS101", "BA101", "BA102"])
        self.assertNotIn("CS201", codes)

    def test_assessment_analysis_normalizes_against_each_max(self):
        service, _ = _service()
        response = run(service.get_subject_intelligence())
        by_component = {a.component: a for a in response.assessment_analysis}
        internal = by_component["Internal"]
        self.assertEqual(internal.max_marks, 20)
        self.assertAlmostEqual(internal.raw_average, 15.2, places=2)
        self.assertAlmostEqual(internal.normalized_percentage, 76.0, places=2)
        mid = by_component["Mid-Sem"]
        self.assertEqual(mid.max_marks, 50)
        self.assertAlmostEqual(mid.normalized_percentage, 76.8, places=2)
        end = by_component["End-Sem"]
        self.assertEqual(end.max_marks, 70)
        self.assertIsNone(end.raw_average)
        self.assertIsNone(end.normalized_percentage)


class FilteringAndSafetyTests(unittest.TestCase):
    def test_filters_are_forwarded_as_parameters(self):
        service, conn = _service()
        run(service.get_subject_intelligence(
            department_code=1, academic_year="2025-26", semester=3, search="data"
        ))
        subject_args = None
        for kind, query, args in conn.executed:
            if kind == "fetch" and "COUNT(DISTINCT e.enrollment_record_id) AS student_count" in query:
                subject_args = args
        self.assertEqual(subject_args, (1, "2025-26", 3, "data"))

    def test_filters_are_omitted_when_none(self):
        service, conn = _service()
        run(service.get_academic_overview())
        result_count_args = None
        for kind, query, args in conn.executed:
            if kind == "fetchrow" and "AS pass_count," in query:
                result_count_args = args
        self.assertEqual(result_count_args, (None, None, None))

    def test_reads_are_select_only(self):
        service, conn = _service()
        run(service.get_academic_overview())
        run(service.get_department_analytics())
        run(service.get_subject_intelligence())
        self.assertTrue(conn.executed)
        for kind, query, args in conn.executed:
            self.assertTrue(query.lstrip().upper().startswith("SELECT"), query)

    def test_generated_at_is_utc_timestamp(self):
        service, _ = _service()
        response = run(service.get_academic_overview())
        self.assertIsInstance(response.generated_at, datetime)
        self.assertEqual(response.generated_at.tzinfo, timezone.utc)

    def test_filter_options_are_populated(self):
        service, _ = _service()
        response = run(service.get_academic_overview())
        self.assertEqual(response.filters.academic_years, ["2024-25", "2025-26"])
        self.assertEqual(response.filters.semesters, [1, 2, 3])
        self.assertEqual(
            response.filters.departments[1]["department_short_name"], "BBA"
        )

    def test_endpoints_depend_on_admin_role(self):
        for route in admin_api.router.routes:
            if not hasattr(route, "dependant"):
                continue
            for dependency in route.dependant.dependencies:
                if dependency.call is require_admin_role:
                    break
            else:
                self.fail(f"route {getattr(route, 'path', route)} lacks require_admin_role")


if __name__ == "__main__":
    unittest.main()
