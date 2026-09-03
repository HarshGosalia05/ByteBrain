"""Contract tests for MD-05 Admin Student & Faculty Overview.

Covers:
  * Part A — Admin Students: filtered/searchable/sorted/paginated table with
    real database figures, canonical MD-04 risk bands, NULL academic values
    stay None, risk sorting by severity (Critical -> Low, never alphabetical).
  * Part B — Admin Faculty: KPIs (total / active / department count),
    department & designation breakdowns, and the allocation-aware table whose
    workload reuses the existing faculty derivation
    (MAX(total_classes) / WORKLOAD_WEEKS_PER_SEMESTER).
  * All reads are SELECT-only; the endpoints depend on require_admin_role.

No live database is required: a fake asyncpg pool records the executed SQL.
"""

import asyncio
import unittest
from decimal import Decimal

from app.schemas.admin_students_faculty import (
    AdminFacultyResponse,
    AdminStudentsResponse,
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
        # ---- Part A: Admin Students ----
        # Items query (paginated table)
        ("fetch", "s.full_name AS student_name"): [
            {
                "student_id": "STU000001",
                "student_name": "Alice Shah",
                "enrollment_no": 202301,
                "email": "alice@example.edu",
                "department_code": 1,
                "department_name": "CSE",
                "semester": 7,
                "academic_year": "2026-27",
                "sgpa": Decimal("8.42"),
                "cgpa": Decimal("8.10"),
                "percentage": Decimal("82.5"),
                "attendance": Decimal("91.3"),
                "backlogs": 0,
                "risk": "CRITICAL",
                "academic_standing": "Good",
            },
            {
                "student_id": "STU000002",
                "student_name": "Bob Mehta",
                "enrollment_no": 202302,
                "email": None,
                "department_code": 1,
                "department_name": "CSE",
                "semester": 7,
                "academic_year": "2026-27",
                "sgpa": None,
                "cgpa": None,
                "percentage": None,
                "attendance": None,
                "backlogs": 3,
                "risk": None,
                "academic_standing": "Probation",
            },
        ],
        ("fetchrow", "SELECT COUNT(*) AS total"): {"total": 2},
        # ---- Part B: Admin Faculty ----
        ("fetchrow", "COUNT(*) FILTER (WHERE f.status = 'Active')"): {
            "total_faculty": 20,
            "active_faculty": 18,
            "department_count": 4,
        },
        ("fetch", "GROUP BY f.department_code"): [
            {"department_code": 1, "department_name": "CSE", "count": 8},
            {"department_code": 2, "department_name": "BBA", "count": 4},
        ],
        ("fetch", "COALESCE(NULLIF(f.designation"): [
            {"designation": "Professor", "count": 6},
            {"designation": "Assistant Professor", "count": 12},
            {"designation": "Unassigned", "count": 2},
        ],
        ("fetch", "WITH offering AS"): [
            {
                "faculty_id": "FAC000001",
                "faculty_code": "FAC-CSE-001",
                "full_name": "Dr. A Sharma",
                "department_code": 1,
                "department_name": "CSE",
                "designation": "Professor",
                "subject_count": 2,
                "student_count": 120,
                "workload_hours": Decimal("10.50"),
            },
            {
                "faculty_id": "FAC000002",
                "faculty_code": "FAC-BBA-001",
                "full_name": "Prof. B Joshi",
                "department_code": 2,
                "department_name": "BBA",
                "designation": None,
                "subject_count": 0,
                "student_count": 0,
                "workload_hours": None,
            },
        ],
        # ---- Shared filter options ----
        ("fetch", "academic_year FROM student_semester_summary"): [
            {"academic_year": "2025-26"},
            {"academic_year": "2026-27"},
        ],
        ("fetch", "AS department_code, d.department_name"): [
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


class AdminStudentsOverviewServiceTests(unittest.TestCase):
    def test_students_contract_assembles_response(self):
        service, conn = _service()
        response = run(service.get_admin_students())
        self.assertIsInstance(response, AdminStudentsResponse)
        self.assertEqual(response.students_total, 2)
        self.assertEqual(len(response.students), 2)

        first = response.students[0]
        self.assertEqual(first.student_id, "STU000001")
        self.assertEqual(first.student_name, "Alice Shah")
        self.assertEqual(first.enrollment_no, 202301)
        self.assertEqual(first.risk, "Critical")
        self.assertEqual(first.attendance, 91.3)
        self.assertEqual(first.backlogs, 0)
        self.assertEqual(first.semester, 7)

        # Academic NULLs stay None (never coerced to 0).
        second = response.students[1]
        self.assertIsNone(second.risk)
        self.assertIsNone(second.sgpa)
        self.assertIsNone(second.cgpa)
        self.assertIsNone(second.percentage)
        self.assertIsNone(second.attendance)

        # Filters are assembled from the shared filter options source.
        self.assertEqual(
            [y for y in response.filters.academic_years], ["2025-26", "2026-27"]
        )
        self.assertEqual(len(response.filters.departments), 2)

    def test_students_filters_and_search_are_forwarded_into_sql(self):
        service, conn = _service()
        run(service.get_admin_students(
            department_code=1, academic_year="2026-27", semester=7,
            risk="High", search="rahul",
        ))
        queries = [q for _, q, _ in conn.executed]
        items = next(q for q in queries if "s.full_name AS student_name" in q)
        total = next(q for q in queries if "SELECT COUNT(*) AS total" in q)
        for q in (items, total):
            self.assertIn("($1::int IS NULL OR s.department_code = $1)", q)
            self.assertIn("($2::int IS NULL OR s.current_semester = $2)", q)
            self.assertIn("($3::text IS NULL OR s.current_academic_year = $3)", q)
            self.assertIn("($4::text IS NULL OR UPPER(sr.risk) = $4)", q)
            self.assertIn("ILIKE '%' || $5 || '%'", q)
        # The risk band is forwarded uppercased so it matches stored bands.
        item_args = [a for _, _, a in conn.executed if len(a) == 13][0]
        self.assertEqual(item_args[3], "HIGH")

    def test_students_risk_sort_uses_severity_case(self):
        service, conn = _service()
        run(service.get_admin_students(sort_by="risk", sort_dir="desc"))
        items = next(q for _, q, _ in conn.executed if "s.full_name AS student_name" in q)
        self.assertIn("CASE UPPER(sr.risk)", items)
        self.assertIn("'CRITICAL' THEN 4", items)
        self.assertIn("'LOW' THEN 1", items)
        self.assertIn("ORDER BY", items)

    def test_students_invalid_sort_falls_back_to_name(self):
        service, conn = _service()
        response = run(service.get_admin_students(sort_by="zzz", sort_dir="up"))
        items = next(q for _, q, _ in conn.executed if "s.full_name AS student_name" in q)
        self.assertIn("ORDER BY s.full_name ASC", items)
        self.assertEqual(response.sort_by, "name")
        self.assertEqual(response.sort_dir, "asc")

    def test_students_pagination_forwarded(self):
        service, conn = _service()
        run(service.get_admin_students(limit=50, offset=10))
        items = next(q for _, q, _ in conn.executed if "s.full_name AS student_name" in q)
        self.assertIn("LIMIT $6::int OFFSET $7::int", items)
        args = [a for _, _, a in conn.executed if len(a) == 13][0]
        self.assertEqual(args[5], 50)
        self.assertEqual(args[6], 10)


class AdminFacultyOverviewServiceTests(unittest.TestCase):
    def test_faculty_contract_assembles_response(self):
        service, conn = _service()
        response = run(service.get_admin_faculty())
        self.assertIsInstance(response, AdminFacultyResponse)
        self.assertEqual(response.kpis.total_faculty, 20)
        self.assertEqual(response.kpis.active_faculty, 18)
        self.assertEqual(response.kpis.department_count, 4)
        self.assertEqual(len(response.by_department), 2)
        self.assertEqual(len(response.by_designation), 3)

        row = response.faculty[0]
        self.assertEqual(row.faculty_id, "FAC000001")
        self.assertEqual(row.subject_count, 2)
        self.assertEqual(row.student_count, 120)
        self.assertEqual(row.workload_hours, 10.5)

        # Faculty with no active allocation has zero counts and NULL workload.
        empty = response.faculty[1]
        self.assertEqual(empty.subject_count, 0)
        self.assertEqual(empty.student_count, 0)
        self.assertIsNone(empty.workload_hours)

    def test_faculty_workload_reuses_existing_derivation(self):
        service, conn = _service()
        run(service.get_admin_faculty())
        entry = next((q, a) for k, q, a in conn.executed if k == "fetch" and "WITH offering AS" in q)
        workload, args = entry
        self.assertIn("MAX(a.total_classes) AS classes", workload)
        self.assertIn("WHERE sse.enrollment_status = 'Active'", workload)
        # Workload is divided by the configured weeks-per-semester param.
        self.assertEqual(len(args), 1)

    def test_faculty_empty_state(self):
        overrides = {
            ("fetchrow", "COUNT(*) FILTER (WHERE f.status = 'Active')"): {
                "total_faculty": 0,
                "active_faculty": 0,
                "department_count": 0,
            },
            ("fetch", "GROUP BY f.department_code"): [],
            ("fetch", "COALESCE(NULLIF(f.designation"): [],
            ("fetch", "WITH offering AS"): [],
        }
        service, _ = _service(overrides)
        response = run(service.get_admin_faculty())
        self.assertEqual(response.kpis.total_faculty, 0)
        self.assertEqual(response.kpis.active_faculty, 0)
        self.assertEqual(response.kpis.department_count, 0)
        self.assertEqual(response.by_department, [])
        self.assertEqual(response.by_designation, [])
        self.assertEqual(response.faculty, [])


if __name__ == "__main__":
    unittest.main()
