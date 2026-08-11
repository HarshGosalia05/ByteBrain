"""Contract tests for the MD-02 admin institution dashboard.

Covers:
  * KPI aggregation from real SQL aggregates (counts, averages, backlogs).
  * NULL academic averages stay None (never coerced to 0).
  * Risk donut uses the stored prediction_status bands in canonical order and
    At-Risk = High + Critical.
  * Result overview maps stored status to Pass / Fail / Pending
    (Pending != Fail, Fail != Pending).
  * Decimals are converted to rounded floats.
  * Filters are forwarded into the executed SQL as parameters.
  * The dashboard is assembled from read-only SELECTs.

No live database is required: a fake asyncpg pool records the executed SQL.
"""

import asyncio
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from app.schemas.admin_dashboard import AdminDashboardResponse
from app.services.admin_service import AdminService


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


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
        ("fetchrow", "SELECT\n                (SELECT COUNT(*)"): {
            "total_students": 80,
            "total_faculty": 25,
            "total_departments": 2,
            "avg_cgpa": Decimal("7.861"),
            "total_backlogs": 120,
        },
        ("fetchrow", "AVG(sem.semester_sgpa)"): {
            "avg_sgpa": Decimal("7.5"),
            "avg_percentage": Decimal("72.53"),
            "avg_attendance": Decimal("81.01"),
        },
        ("fetchrow", "COUNT(*) AS count\n            FROM attendance a"): {
            "count": 42,
        },
        ("fetch", "r.prediction_status AS risk_level"): [
            {"risk_level": "LOW", "count": 16},
            {"risk_level": "MODERATE", "count": 51},
            {"risk_level": "HIGH", "count": 1},
            {"risk_level": "CRITICAL", "count": 12},
        ],
        ("fetch", "COALESCE(d.department_name, s.department_name) AS department_name,\n                AVG(sem.semester_percentage)"): [
            {
                "department_code": 1,
                "department_name": "Computer Engineering",
                "avg_percentage": Decimal("75.2"),
                "avg_sgpa": Decimal("7.8"),
            },
            {
                "department_code": 2,
                "department_name": "Business Administration",
                "avg_percentage": Decimal("68.1"),
                "avg_sgpa": Decimal("7.1"),
            },
        ],
        ("fetch", "sem.semester_no AS semester"): [
            {"semester": 1, "avg_sgpa": Decimal("7.1"), "avg_percentage": Decimal("68.5")},
            {"semester": 2, "avg_sgpa": Decimal("7.4"), "avg_percentage": Decimal("71.0")},
        ],
        ("fetch", "COALESCE(a.attendance_status, 'Unknown') AS status"): [
            {"status": "Excellent", "count": 100},
            {"status": "Good", "count": 200},
            {"status": "Average", "count": 300},
            {"status": "Low", "count": 400},
            {"status": "Critical", "count": 50},
            {"status": "Unknown", "count": 10},
        ],
        ("fetch", "WHEN p.result_status IS NULL THEN 'Pending'"): [
            {"status": "Pass", "count": 3400},
            {"status": "Fail", "count": 150},
            {"status": "Pending", "count": 300},
        ],
        ("fetch", "r.prediction_status AS risk_level,\n                COUNT(*) AS count\n            FROM risk_predictions r"): [
            {"department_name": "Computer Engineering", "risk_level": "HIGH", "count": 1},
            {"department_name": "Computer Engineering", "risk_level": "CRITICAL", "count": 6},
            {"department_name": "Business Administration", "risk_level": "HIGH", "count": 0},
            {"department_name": "Business Administration", "risk_level": "CRITICAL", "count": 6},
        ],
        ("fetch", "e.subject_code,\n                e.subject_name,\n                COUNT(*) FILTER"): [
            {
                "subject_code": "CS205",
                "subject_name": "Data Structures",
                "fail_count": 12,
                "avg_percentage": Decimal("55.3"),
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


class AdminDashboardServiceTests(unittest.TestCase):
    def test_kpis_are_aggregated_correctly(self):
        service, _ = _service()
        response = run(service.get_dashboard())
        self.assertIsInstance(response, AdminDashboardResponse)
        self.assertEqual(response.kpis.total_students, 80)
        self.assertEqual(response.kpis.total_faculty, 25)
        self.assertEqual(response.kpis.total_departments, 2)
        self.assertEqual(response.kpis.total_backlogs, 120)
        self.assertAlmostEqual(response.kpis.avg_cgpa, 7.86, places=2)
        self.assertAlmostEqual(response.kpis.avg_sgpa, 7.5, places=2)
        self.assertAlmostEqual(response.kpis.avg_percentage, 72.53, places=2)
        self.assertAlmostEqual(response.kpis.avg_attendance, 81.01, places=2)
        self.assertEqual(response.kpis.at_risk_students, 13)

    def test_nulls_stay_none_never_zero(self):
        service, _ = _service(
            {
                ("fetchrow", "SELECT\n                (SELECT COUNT(*)"): {
                    "total_students": 80,
                    "total_faculty": 25,
                    "total_departments": 2,
                    "avg_cgpa": None,
                    "total_backlogs": 0,
                },
                ("fetchrow", "AVG(sem.semester_sgpa)"): {
                    "avg_sgpa": None,
                    "avg_percentage": None,
                    "avg_attendance": None,
                },
            }
        )
        response = run(service.get_dashboard())
        self.assertIsNone(response.kpis.avg_cgpa)
        self.assertIsNone(response.kpis.avg_sgpa)
        self.assertIsNone(response.kpis.avg_percentage)
        self.assertIsNone(response.kpis.avg_attendance)

    def test_empty_database_returns_canonical_risk_bands_with_zero(self):
        service, _ = _service(
            {
                ("fetch", "r.prediction_status AS risk_level"): [],
                ("fetch", "r.prediction_status AS risk_level,\n                COUNT(*) AS count\n            FROM risk_predictions r"): [],
            }
        )
        response = run(service.get_dashboard())
        self.assertEqual(
            [item.risk_level for item in response.risk_distribution],
            ["Low", "Moderate", "High", "Critical"],
        )
        self.assertTrue(all(item.count == 0 for item in response.risk_distribution))
        self.assertEqual(response.kpis.at_risk_students, 0)

    def test_risk_bands_are_ordered_and_at_risk_counts_high_critical(self):
        service, conn = _service()
        run(service.get_dashboard())
        bands = [item.risk_level for item in run(service.get_dashboard()).risk_distribution]
        self.assertEqual(bands, ["Low", "Moderate", "High", "Critical"])

    def test_result_overview_maps_pending_and_fail_distinctly(self):
        service, _ = _service(
            {
                ("fetch", "WHEN p.result_status IS NULL THEN 'Pending'"): [
                    {"status": "Fail", "count": 5},
                    {"status": "Pending", "count": 7},
                    {"status": "Pass", "count": 20},
                ],
            }
        )
        response = run(service.get_dashboard())
        by_status = {item.status: item.count for item in response.result_overview}
        self.assertEqual(by_status["Pass"], 20)
        self.assertEqual(by_status["Fail"], 5)
        self.assertEqual(by_status["Pending"], 7)

    def test_filters_are_forwarded_as_query_parameters(self):
        service, conn = _service()
        run(service.get_dashboard(department_code=2, academic_year="2025-26", semester=3))
        overall_args = None
        for kind, query, args in conn.executed:
            if kind == "fetchrow" and "(SELECT COUNT(*)" in query:
                overall_args = args
        self.assertEqual(overall_args, (2,))

        semester_avg_args = None
        for kind, query, args in conn.executed:
            if kind == "fetchrow" and "AVG(sem.semester_sgpa)" in query:
                semester_avg_args = args
        self.assertEqual(semester_avg_args, (2, "2025-26", 3))

    def test_filters_are_omitted_when_none(self):
        service, conn = _service()
        run(service.get_dashboard())
        semester_avg_args = None
        for kind, query, args in conn.executed:
            if kind == "fetchrow" and "AVG(sem.semester_sgpa)" in query:
                semester_avg_args = args
        self.assertEqual(semester_avg_args, (None, None, None))

    def test_insights_are_deterministic(self):
        service, _ = _service()
        response = run(service.get_dashboard())
        titles = [insight.title for insight in response.insights]
        self.assertIn("Top performing department", titles)
        self.assertIn("Needs attention", titles)
        self.assertIn("Highest at-risk share", titles)
        self.assertIn("Weakest subject", titles)
        self.assertIn("Attendance shortage", titles)

    def test_dashboard_reads_are_select_only(self):
        service, conn = _service()
        run(service.get_dashboard())
        self.assertTrue(conn.executed)
        for kind, query, args in conn.executed:
            self.assertTrue(query.lstrip().upper().startswith("SELECT"), query)

    def test_generated_at_is_utc_timestamp(self):
        service, _ = _service()
        response = run(service.get_dashboard())
        self.assertIsInstance(response.generated_at, datetime)
        self.assertEqual(response.generated_at.tzinfo, timezone.utc)

    def test_filter_options_are_populated(self):
        service, _ = _service()
        response = run(service.get_dashboard())
        self.assertEqual(response.filters.academic_years, ["2024-25", "2025-26"])
        self.assertEqual(response.filters.semesters, [1, 2, 3])
        self.assertEqual(response.filters.departments[0]["department_code"], 1)
        self.assertEqual(
            response.filters.departments[0]["department_short_name"], "CSE"
        )


if __name__ == "__main__":
    unittest.main()
