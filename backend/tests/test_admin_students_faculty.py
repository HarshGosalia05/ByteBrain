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

from datetime import datetime, timezone
from fastapi import HTTPException
from app.schemas.admin_students_faculty import (
    AdminFacultyProfileResponse,
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
        ("fetch", "DISTINCT admission_year"): [
            {"admission_year": 2025},
            {"admission_year": 2026},
        ],
        ("fetch", "AS department_code, d.department_name"): [
            {"department_code": 1, "department_name": "CSE", "department_short_name": "CSE"},
            {"department_code": 2, "department_name": "BBA", "department_short_name": "BBA"},
        ],
        ("fetch", "DISTINCT semester_no FROM student_semester_summary"): [
            {"semester_no": 1},
            {"semester_no": 7},
        ],
        # ---- Student detail profile ----
        ("fetchrow", "FROM students s WHERE s.student_id = $1"): {
            "student_id": "STU000001",
            "first_name": "Alice",
            "last_name": "Shah",
            "full_name": "Alice Shah",
            "enrollment_no": 202301,
            "admission_year": 2023,
            "current_semester": 7,
            "department_name": "CSE",
            "current_academic_year": "2026-27",
            "overall_cgpa": Decimal("8.10"),
            "overall_percentage": Decimal("82.5"),
            "total_credits_registered": 160,
            "total_credits_earned": 140,
            "total_backlogs": 0,
            "academic_standing": "Good",
            "latest_sgpa": Decimal("8.42"),
            "overall_attendance_percentage": Decimal("91.3"),
        },
        ("fetch", "WHERE student_id = $1 ORDER BY semester_no ASC"): [
            {
                "semester": 1,
                "sgpa": Decimal("8.20"),
                "total_credits_earned": 20,
                "attendance_percentage": Decimal("92.0"),
                "active_backlogs": 0,
                "academic_year": "2023-24",
                "semester_percentage": Decimal("81.0"),
                "academic_standing": "Good",
            }
        ],
        ("fetch", "FROM student_subject_performance p"): [
            {
                "semester": 1,
                "subject_code": "CS101",
                "subject_name": "Intro to CS",
                "total_marks": Decimal("85.0"),
                "percentage": Decimal("85.0"),
                "grade": "A",
                "attendance_percentage": Decimal("90.0"),
            }
        ],
        ("fetchrow", "FROM risk_predictions WHERE student_id = $1"): {
            "prediction_status": "LOW",
            "prediction_timestamp": 1234567.89,
            "created_at": datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc),
        },
        ("fetchrow", "FROM ml_predictions WHERE student_id = $1 AND prediction_type = 'm4'"): {
            "prediction_value": '{"career_readiness_score": 75.0, "positive_factors": "Strong coding skills", "risk_factors": "No internship"}',
            "model_version": "1.0",
            "generated_at": datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc),
        },
        ("fetchrow", "FROM career_preferences WHERE student_id = $1"): {
            "preferred_domain": "Data Science",
            "dream_job_role": "Data Scientist",
            "placement_readiness_level": "High",
            "internship_completed": "Yes",
            "target_package_lpa": Decimal("8.5"),
        },
        # ---- Faculty detail profile ----
        ("fetchrow", "FROM faculty f\n            LEFT JOIN departments d ON d.dept_code = f.department_code\n            WHERE f.faculty_id = $1"): {
            "faculty_id": "FAC000001",
            "faculty_code": "FAC-CSE-001",
            "full_name": "Dr. A Sharma",
            "gender": "Male",
            "department_code": 1,
            "department_name": "Computer Science and Engineering",
            "designation": "Professor",
            "qualification": "Ph.D",
            "specialization": "Distributed Systems",
            "experience_years": 12,
            "email": "sharma@example.edu",
            "phone_number": "9876543210",
            "joining_date": "2018-07-01",
            "employment_type": "Full Time",
            "status": "Active",
        },
        ("fetch", "FROM student_subject_enrollment sse\n            JOIN subjects sub ON sub.subject_id = sse.subject_id"): [
            {
                "subject_id": "SUB001",
                "subject_code": "CS101",
                "subject_name": "Intro to CS",
                "department_name": "CSE",
                "semester_no": 1,
                "academic_year": "2026-27",
                "student_count": 60,
                "total_classes": 45,
                "avg_attendance": Decimal("88.50"),
                "avg_marks_pct": Decimal("76.20"),
                "at_risk_count": 2,
            }
        ],
        ("fetchrow", "FROM offering o\n            """,): {
            "total_subjects": 1,
            "total_semesters": 1,
            "active_students": 60,
            "total_students_handled": 60,
            "workload_hours": Decimal("3.00"),
        },
        ("fetchrow", "SELECT \n                ROUND(AVG(p.percentage), 2) AS overall_avg_marks"): {
            "overall_avg_marks": Decimal("76.20"),
            "overall_avg_attendance": Decimal("88.50"),
            "total_at_risk_count": 2,
            "total_evaluated_records": 60,
        },
        ("fetch", "GROUP BY p.grade\n            ORDER BY count DESC"): [
            {"grade": "A", "count": 40},
            {"grade": "B", "count": 18},
            {"grade": "F", "count": 2},
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
            [y for y in response.filters.batches], ["25-26", "26-27"]
        )
        self.assertEqual(
            [y for y in response.filters.academic_years], ["25-26", "26-27"]
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
            self.assertIn("student_semester_summary", q)
            self.assertIn("semester_no = $2", q)
            self.assertIn("$3::text IS NULL", q)
            self.assertIn("s.admission_year", q)
            self.assertIn("($4::text IS NULL OR UPPER(sr.risk) = $4)", q)
            self.assertIn("ILIKE '%' || $5 || '%'", q)
        # Semester-scoped items query surfaces that semester's snapshot columns.
        self.assertIn("semf.semester_no IS NOT NULL", items)
        self.assertIn("CASE WHEN semf.semester_no IS NULL THEN s.latest_sgpa ELSE semf.semester_sgpa END", items)
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

    def test_student_profile_success(self):
        service, conn = _service()
        response = run(service.get_student_profile("STU000001"))
        self.assertIn("student", response)
        self.assertIn("academic", response)
        self.assertIn("semesters", response)
        self.assertIn("performance", response)
        self.assertIn("risk", response)
        self.assertIn("career", response)

        self.assertEqual(response["student"]["student_id"], "STU000001")
        self.assertEqual(response["student"]["first_name"], "Alice")
        self.assertEqual(response["student"]["last_name"], "Shah")
        self.assertEqual(response["academic"]["overall_cgpa"], 8.10)
        self.assertEqual(len(response["semesters"]), 1)
        self.assertEqual(len(response["performance"]), 1)
        self.assertEqual(response["risk"]["risk_level"], "Low")
        self.assertEqual(response["career"]["score"], 75.0)

    def test_student_profile_not_found(self):
        overrides = {
            ("fetchrow", "FROM students s WHERE s.student_id = $1"): None,
        }
        service, _ = _service(overrides)
        with self.assertRaises(HTTPException) as ctx:
            run(service.get_student_profile("NONEXISTENT"))
        self.assertEqual(ctx.exception.status_code, 404)


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

    def test_faculty_profile_success(self):
        service, conn = _service()
        response = run(service.get_faculty_profile("FAC000001"))
        self.assertIsInstance(response, AdminFacultyProfileResponse)
        self.assertEqual(response.faculty.faculty_id, "FAC000001")
        self.assertEqual(response.faculty.full_name, "Dr. A Sharma")
        self.assertEqual(response.faculty.designation, "Professor")
        self.assertEqual(response.faculty.department_name, "Computer Science and Engineering")
        self.assertEqual(response.teaching_overview.total_subjects, 1)
        self.assertEqual(response.teaching_overview.total_semesters, 1)
        self.assertEqual(response.teaching_overview.active_students, 60)
        self.assertEqual(response.teaching_overview.workload_hours, 3.0)
        self.assertEqual(len(response.subjects), 1)
        self.assertEqual(response.subjects[0].subject_code, "CS101")
        self.assertEqual(response.insights.overall_avg_marks, 76.20)
        self.assertEqual(response.insights.overall_avg_attendance, 88.50)
        self.assertEqual(response.insights.total_at_risk_count, 2)
        self.assertEqual(len(response.insights.grade_distribution), 3)

    def test_faculty_profile_not_found(self):
        overrides = {
            ("fetchrow", "FROM faculty f\n            LEFT JOIN departments d ON d.dept_code = f.department_code\n            WHERE f.faculty_id = $1"): None,
        }
        service, _ = _service(overrides)
        with self.assertRaises(HTTPException) as ctx:
            run(service.get_faculty_profile("NONEXISTENT"))
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
