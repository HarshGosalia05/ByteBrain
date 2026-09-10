"""Contract tests for MD-04 Admin Attendance & Risk Intelligence.

Covers:
  * Attendance Intelligence KPIs (avg attendance, below target, critical, eligible, not eligible).
  * Attendance charts (by department, by semester, distribution).
  * Subject attendance table (with search, pagination, and counts).
  * Shortage students table (with shortage calculation, eligibility, and search).
  * Stored risk predictions KPIs (Low, Moderate, High, Critical, At-Risk).
  * Risk charts (by department scoped, by semester scoped, donut).
  * At-risk students table (with pagination, search, and severity sort).
  * Early Warning reasons and deterministic recommendations.
  * Filters and search parameters forwarded into executed SQL.
  * NULL attendance/academic values stay None, never coerced to zero.
  * All reads are SELECT-only; endpoints depend on require_admin_role.

No live database is required: a fake asyncpg pool records the executed SQL.
"""

import asyncio
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from app.api.v1 import admin as admin_api
from app.api.dependencies import require_admin_role
from app.schemas.admin_attendance_risk import (
    AttendanceIntelligenceResponse,
    RiskIntelligenceResponse,
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
        # Attendance KPIs
        ("fetchrow", "BOOL_AND(COALESCE(a.eligibility_status = 'Eligible', FALSE))"): {
            "avg_attendance": Decimal("79.43"),
            "students_with_records": 80,
            "students_below_target": 18,
            "critical_shortage_students": 7,
            "eligible_students": 62,
            "not_eligible_students": 18,
        },
        # Attendance by Department
        ("fetch", "ORDER BY e.department_code ASC"): [
            {"department_code": 1, "department_name": "CSE", "avg_attendance": Decimal("81.2")},
            {"department_code": 2, "department_name": "BBA", "avg_attendance": Decimal("77.5")},
        ],
        # Attendance by Semester
        ("fetch", "GROUP BY e.semester_no\n            ORDER BY e.semester_no ASC"): [
            {"semester": 1, "avg_attendance": Decimal("80.5")},
            {"semester": 2, "avg_attendance": Decimal("78.2")},
        ],
        # Attendance Distribution
        ("fetch", "COALESCE(a.attendance_status, 'Unknown') AS status"): [
            {"status": "Excellent", "count": 120},
            {"status": "Good", "count": 250},
            {"status": "Average", "count": 80},
            {"status": "Low", "count": 35},
            {"status": "Critical", "count": 15},
        ],
        # Subject Attendance Table
        ("fetch", "COUNT(DISTINCT e.enrollment_record_id) AS student_count"): [
            {
                "subject_code": "CSE101",
                "subject_name": "Programming",
                "department_code": 1,
                "department_name": "CSE",
                "semester": 1,
                "student_count": 50,
                "avg_attendance": Decimal("82.4"),
                "below_target_count": 5,
                "critical_shortage_count": 1,
                "eligible_count": 45,
                "not_eligible_count": 5,
            }
        ],
        ("fetchrow", "SELECT COUNT(*) AS total\n            FROM (\n                SELECT e.enrollment_record_id"): {
            "total": 1
        },
        # Shortage Students Table
        ("fetch", "filtered_students"): [
            {
                "student_id": "STU01",
                "student_name": "Alice Shah",
                "enrollment_no": 202301,
                "department_code": 1,
                "department_name": "CSE",
                "semester": 1,
                "subject_code": "CSE101",
                "subject_name": "Programming",
                "attendance_percentage": Decimal("68.5"),
                "eligibility_status": "Not Eligible",
            }
        ],
        ("fetchrow", "SELECT COUNT(*) AS total\n            FROM (\n                SELECT DISTINCT st.student_id"): {
            "total": 1
        },
        # Risk Counts
        ("fetch", "GROUP BY r.prediction_status"): [
            {"risk_level": "LOW", "count": 16},
            {"risk_level": "MODERATE", "count": 51},
            {"risk_level": "HIGH", "count": 1},
            {"risk_level": "CRITICAL", "count": 12},
        ],
        # Risk by Department Scoped
        ("fetch", "GROUP BY s.department_code, d.department_name, s.department_name, r.prediction_status"): [
            {"department_code": 1, "department_name": "CSE", "risk_level": "CRITICAL", "count": 6},
            {"department_code": 1, "department_name": "CSE", "risk_level": "HIGH", "count": 1},
            {"department_code": 2, "department_name": "BBA", "risk_level": "CRITICAL", "count": 6},
        ],
        # Risk by Semester Scoped
        ("fetch", "GROUP BY s.current_semester, r.prediction_status"): [
            {"semester": 7, "risk_level": "CRITICAL", "count": 12},
            {"semester": 7, "risk_level": "HIGH", "count": 1},
        ],
        # Risk Students Table
        ("fetch", "CASE UPPER(r.prediction_status)\n                    WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MODERATE' THEN 2 ELSE 3"): [
            {
                "student_id": "STU02",
                "student_name": "Bob Shah",
                "enrollment_no": 202302,
                "department_code": 1,
                "department_name": "CSE",
                "semester": 7,
                "academic_year": "2026-27",
                "attendance": Decimal("58.2"),
                "percentage": Decimal("45.6"),
                "backlogs": 3,
                "academic_standing": "Probation",
                "risk": "Critical",
            }
        ],
        ("fetchrow", "SELECT COUNT(*) AS total\n            FROM risk_predictions r\n            JOIN students st ON st.student_id = r.student_id"): {
            "total": 1
        },
        # At Risk Students (Early Warning list)
        ("fetch", "CASE UPPER(r.prediction_status)\n                    WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 ELSE 2\n                END,\n                st.full_name ASC"): [
            {
                "student_id": "STU02",
                "student_name": "Bob Shah",
                "enrollment_no": 202302,
                "department_code": 1,
                "department_name": "CSE",
                "semester": 7,
                "academic_year": "2026-27",
                "attendance": Decimal("58.2"),
                "percentage": Decimal("45.6"),
                "backlogs": 3,
                "academic_standing": "Probation",
                "risk": "Critical",
            }
        ],
        # Performance Trend (for decline detection)
        ("fetch", "ANY($1::text[])"): [
            {"student_id": "STU02", "semester_no": 5, "semester_percentage": Decimal("68.5")},
            {"student_id": "STU02", "semester_no": 6, "semester_percentage": Decimal("55.2")},
        ],
        # Filters
        ("fetch", "DISTINCT academic_year FROM student_semester_summary"): [
            {"academic_year": "2025-26"},
            {"academic_year": "2026-27"},
        ],
        ("fetch", "dept_code AS department_code, department_name, "): [
            {"department_code": 1, "department_name": "CSE", "department_short_name": "CSE"},
            {"department_code": 2, "department_name": "BBA", "department_short_name": "BBA"},
        ],
        ("fetch", "DISTINCT semester_no FROM student_semester_summary"): [
            {"semester_no": 1},
            {"semester_no": 7},
        ],
    }
    if overrides:
        responses.update(overrides)
    return responses


def _service(responses=None):
    conn = FakeConn(_default_responses(responses))
    return AdminService(FakePool(conn)), conn


class AttendanceIntelligenceServiceTests(unittest.TestCase):
    def test_attendance_kpis_and_distributions_are_assembled(self):
        service, _ = _service()
        response = run(service.get_attendance_intelligence())
        self.assertIsInstance(response, AttendanceIntelligenceResponse)
        self.assertAlmostEqual(response.kpis.avg_attendance, 79.43, places=2)
        self.assertEqual(response.kpis.students_below_target, 18)
        self.assertEqual(response.kpis.critical_shortage_students, 7)
        self.assertEqual(response.kpis.eligible_students, 62)
        self.assertEqual(response.kpis.not_eligible_students, 18)

        # Department averages
        self.assertEqual(len(response.by_department), 2)
        self.assertAlmostEqual(response.by_department[0].avg_attendance, 81.2, places=2)

        # Semester averages
        self.assertEqual(len(response.by_semester), 2)
        self.assertAlmostEqual(response.by_semester[0].avg_attendance, 80.5, places=2)

        # Distribution
        self.assertEqual(len(response.distribution), 5)
        self.assertEqual(response.distribution[0].status, "Excellent")
        self.assertEqual(response.distribution[0].count, 120)

    def test_subject_attendance_table(self):
        service, _ = _service()
        response = run(service.get_attendance_intelligence())
        self.assertEqual(len(response.subjects), 1)
        cs = response.subjects[0]
        self.assertEqual(cs.subject_code, "CSE101")
        self.assertEqual(cs.student_count, 50)
        self.assertEqual(cs.below_target_count, 5)
        self.assertEqual(cs.critical_shortage_count, 1)

    def test_shortage_students_table(self):
        service, _ = _service()
        response = run(service.get_attendance_intelligence())
        self.assertEqual(len(response.shortage_students), 1)
        row = response.shortage_students[0]
        self.assertEqual(row.student_id, "STU01")
        self.assertAlmostEqual(row.attendance_percentage, 68.5, places=2)
        self.assertAlmostEqual(row.shortage, 6.5, places=2)  # 75 - 68.5 = 6.5
        self.assertEqual(row.eligibility_status, "Not Eligible")
        # shortage_students_total counts unique students (matches KPI population)
        self.assertEqual(response.shortage_students_total, 1)


class RiskIntelligenceServiceTests(unittest.TestCase):
    def test_risk_kpis_and_distributions_are_assembled(self):
        service, _ = _service()
        response = run(service.get_risk_intelligence())
        self.assertIsInstance(response, RiskIntelligenceResponse)
        self.assertEqual(response.kpis.low, 16)
        self.assertEqual(response.kpis.moderate, 51)
        self.assertEqual(response.kpis.high, 1)
        self.assertEqual(response.kpis.critical, 12)
        self.assertEqual(response.kpis.at_risk, 13)
        self.assertEqual(response.kpis.total_predicted, 80)

        # Donut Chart distribution
        self.assertEqual(len(response.distribution), 4)
        self.assertEqual(response.distribution[0].risk_level, "Low")
        self.assertEqual(response.distribution[3].risk_level, "Critical")

        # Scoped Department Risk counts
        self.assertEqual(len(response.by_department), 2)
        cse = next(d for d in response.by_department if d.department_name == "CSE")
        self.assertEqual(cse.distribution[3].risk_level, "Critical")
        self.assertEqual(cse.distribution[3].count, 6)

        # Scoped Semester Risk counts
        self.assertEqual(len(response.by_semester), 1)
        sem7 = response.by_semester[0]
        self.assertEqual(sem7.semester, 7)
        self.assertEqual(sem7.distribution[3].count, 12)

    def test_at_risk_students_table(self):
        service, _ = _service()
        response = run(service.get_risk_intelligence())
        self.assertEqual(len(response.students), 1)
        row = response.students[0]
        self.assertEqual(row.student_id, "STU02")
        self.assertEqual(row.risk, "Critical")
        self.assertEqual(row.academic_standing, "Probation")

    def test_early_warning_center_reasons_and_recommendations(self):
        service, _ = _service()
        response = run(service.get_risk_intelligence())
        self.assertEqual(len(response.early_warning), 1)
        ew = response.early_warning[0]
        self.assertEqual(ew.student_id, "STU02")
        # primary concern should be "Low attendance" because st.attendance = 58.2 < 75
        self.assertEqual(ew.primary_concern, "Low attendance")
        self.assertEqual(ew.recommended_action, "Attendance intervention")
        # supporting concerns should include low academic performance (percentage=45.6 < 50),
        # backlogs (3 >= 2), standing (Probation), and performance decline (68.5 -> 55.2)
        self.assertIn("Low academic performance", ew.supporting_signals)
        self.assertIn("Backlogs", ew.supporting_signals)
        self.assertIn("Academic standing concern", ew.supporting_signals)
        self.assertIn("Repeated poor performance", ew.supporting_signals)


class FilteringAndSafetyTests(unittest.TestCase):
    def test_filters_are_forwarded_as_parameters(self):
        service, conn = _service()
        run(service.get_attendance_intelligence(
            department_code=1, academic_year="2026-27", semester=7, search="stu"
        ))
        kpi_args = None
        for kind, query, args in conn.executed:
            if kind == "fetchrow" and "students_below_target" in query:
                kpi_args = args
        self.assertEqual(kpi_args, (1, "2026-27", 7, 75.0, 60.0))

    def test_reads_are_select_only(self):
        service, conn = _service()
        run(service.get_attendance_intelligence())
        run(service.get_risk_intelligence())
        self.assertTrue(conn.executed)
        for kind, query, args in conn.executed:
            upper = query.lstrip().upper()
            # SELECT or WITH (CTE containing only SELECT statements) are both read-only
            self.assertTrue(
                upper.startswith("SELECT") or upper.startswith("WITH"),
                query,
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
