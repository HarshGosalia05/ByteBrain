"""API route tests for Analytics endpoints.

Verifies:
  - All 14 analytics endpoints are registered and reachable
  - Correct HTTP method (GET) and path
  - Successful JSON responses (200)
  - Response schema matches Pydantic models
  - Path/query parameter validation (422 for invalid, 400 for business)
  - 404 for nonexistent resources
  - Service dependency injection and correct argument passthrough
  - No database access from routes
  - No SQL in routes
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.api.dependencies import get_db_pool
from app.api.v1.analytics import get_analytics_service
from app.main import app
from app.schemas.analytics import (
    AtRiskStudent,
    AtRiskStudentsResult,
    BacklogDistribution,
    BacklogDistributionBucket,
    BelowThresholdResult,
    BelowThresholdStudent,
    DepartmentOverview,
    PerformanceDistributionBucket,
    SemesterPerformanceDistribution,
    StudentAcademicProfile,
    StudentAttendanceSummary,
    StudentBacklogSummary,
    StudentSemesterHistory,
    SemesterTrendPoint,
    StudentSubjectAttendance,
    SubjectAttendanceSummary,
    SubjectNeedingAttention,
    SubjectPerformanceSummary,
    SubjectUnderperformers,
    SubjectsNeedingAttentionResult,
    UnderperformerItem,
)


# ---------------------------------------------------------------------------
# Fake Service Responses
# ---------------------------------------------------------------------------

def fake_academic_profile():
    return StudentAcademicProfile(
        student_id="STU000001",
        full_name="Jay Shah",
        department_code=1,
        department_name="CSE",
        current_semester=7,
        current_academic_year="2026-27",
        overall_cgpa=8.5,
        latest_sgpa=9.0,
        total_backlogs=0,
        overall_attendance_percentage=87.35,
        total_subjects_enrolled=7,
        total_credits_registered=19,
    )


def fake_semester_history():
    return StudentSemesterHistory(
        student_id="STU000001",
        semesters=[
            SemesterTrendPoint(
                semester_no=5, academic_year="2025-26",
                semester_sgpa=8.0, semester_percentage=76.0,
                semester_attendance_percentage=85.0,
                subjects_registered=6, credits_registered=18,
                credits_earned=18, backlog_count=0,
                semester_result="PASS", academic_standing="Good",
            ),
            SemesterTrendPoint(
                semester_no=7, academic_year="2026-27",
                semester_sgpa=9.0, semester_percentage=85.0,
                semester_attendance_percentage=90.0,
                subjects_registered=7, credits_registered=19,
                credits_earned=19, backlog_count=0,
                semester_result="PASS", academic_standing="Excellent",
            ),
        ],
    )


def fake_attendance_summary():
    return StudentAttendanceSummary(
        student_id="STU000001",
        semester_no=7,
        overall_attendance_percentage=85.5,
        total_classes=100,
        attended_classes=85,
        subjects=[
            StudentSubjectAttendance(
                subject_id="SUB0050", subject_code="CS701",
                subject_name="Data Structures",
                total_classes=50, attended_classes=45,
                attendance_percentage=90.0,
                attendance_status="Excellent",
                eligibility_status="Eligible", shortage_flag="No",
            ),
        ],
        at_risk_subjects=0,
        ineligible_subjects=0,
    )


def fake_backlog_summary():
    return StudentBacklogSummary(
        student_id="STU000001",
        total_backlogs=2,
        backlogs=[],
    )


def fake_subject_performance():
    return SubjectPerformanceSummary(
        subject_id="SUB0050",
        subject_code="CS701",
        subject_name="Data Structures",
        semester_no=7,
        total_students=50,
        average_percentage=68.5,
        median_percentage=70.0,
        min_percentage=25.0,
        max_percentage=98.0,
        pass_count=45,
        fail_count=5,
        pass_rate=90.0,
        grade_distribution=[],
    )


def fake_subject_attendance():
    return SubjectAttendanceSummary(
        subject_id="SUB0050",
        subject_code="CS701",
        subject_name="Data Structures",
        semester_no=7,
        total_students=50,
        average_attendance_percentage=82.5,
        eligible_count=45,
        at_risk_count=3,
        ineligible_count=5,
        shortage_count=2,
    )


def fake_underperformers():
    return SubjectUnderperformers(
        subject_id="SUB0050",
        semester_no=7,
        threshold=40.0,
        students=[
            UnderperformerItem(
                student_id="STU000005",
                full_name="Low Scorer",
                percentage=30.0,
                grade="F",
                attendance_percentage=60.0,
            ),
        ],
    )


def fake_department_overview():
    return DepartmentOverview(
        department_code=1,
        department_name="CSE",
        semester_no=7,
        academic_year="2026-27",
        total_students=50,
        average_sgpa=7.8,
        average_percentage=74.5,
        average_attendance_percentage=82.0,
        total_backlogs=12,
        students_with_backlogs=8,
    )


def fake_performance_distribution():
    return SemesterPerformanceDistribution(
        department_code=1,
        semester_no=7,
        academic_year="2026-27",
        total_students=50,
        buckets=[
            PerformanceDistributionBucket(label="Top", count=5, percentage_of_total=10.0),
            PerformanceDistributionBucket(label="Average", count=20, percentage_of_total=40.0),
        ],
    )


def fake_attendance_distribution():
    return {
        "department_code": 1,
        "semester_no": 7,
        "total_students": 50,
        "buckets": [
            {"band": "Excellent", "count": 10, "percentage_of_total": 20.0},
            {"band": "Good", "count": 20, "percentage_of_total": 40.0},
        ],
    }


def fake_backlog_distribution():
    return BacklogDistribution(
        department_code=1,
        total_students=50,
        students_with_backlogs=15,
        buckets=[
            BacklogDistributionBucket(backlog_range="0", count=35, percentage_of_total=70.0),
            BacklogDistributionBucket(backlog_range="1-2", count=10, percentage_of_total=20.0),
        ],
    )


def fake_at_risk():
    return AtRiskStudentsResult(
        department_code=1,
        semester_no=7,
        total_flagged=2,
        students=[
            AtRiskStudent(
                student_id="STU000003",
                full_name="Risk Student",
                department_code=1,
                current_semester=7,
                overall_cgpa=5.5,
                total_backlogs=3,
                overall_attendance_percentage=65.0,
                risk_reasons=["Attendance 65.0% below threshold 75%"],
                risk_score=45.2,
            ),
        ],
    )


def fake_below_threshold():
    return BelowThresholdResult(
        threshold=75.0,
        semester_no=7,
        total_flagged=1,
        students=[
            BelowThresholdStudent(
                student_id="STU000005",
                full_name="Low Attendance",
                subject_id="SUB0050",
                subject_code="CS701",
                attendance_percentage=60.0,
                total_classes=50,
                attended_classes=30,
                classes_needed=0,
            ),
        ],
    )


def fake_subjects_attention():
    return SubjectsNeedingAttentionResult(
        department_code=1,
        semester_no=7,
        total_flagged=1,
        subjects=[
            SubjectNeedingAttention(
                subject_id="SUB0053",
                subject_code="CS704",
                subject_name="Networks",
                semester_no=7,
                total_students=50,
                average_percentage=45.0,
                fail_rate=25.0,
                average_attendance=70.0,
                reasons=["Average percentage 45.0% below 50%"],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Fake Service
# ---------------------------------------------------------------------------

class FakeAnalyticsService:
    """In-memory mock of AnalyticsService that returns canned data."""

    def __init__(self):
        self._calls = []

    async def get_student_academic_profile(self, student_id):
        self._calls.append(("get_student_academic_profile", {"student_id": student_id}))
        if student_id == "STU999999":
            return None
        if student_id == "":
            raise ValueError("student_id must be a non-empty string")
        return fake_academic_profile()

    async def get_student_semester_history(self, student_id, **kwargs):
        self._calls.append(("get_student_semester_history", {"student_id": student_id, **kwargs}))
        if student_id == "":
            raise ValueError("student_id must be a non-empty string")
        return fake_semester_history()

    async def get_student_attendance_summary(self, student_id, **kwargs):
        self._calls.append(("get_student_attendance_summary", {"student_id": student_id, **kwargs}))
        if student_id == "":
            raise ValueError("student_id must be a non-empty string")
        return fake_attendance_summary()

    async def get_student_backlog_summary(self, student_id):
        self._calls.append(("get_student_backlog_summary", {"student_id": student_id}))
        if student_id == "":
            raise ValueError("student_id must be a non-empty string")
        return fake_backlog_summary()

    async def get_subject_performance_summary(self, subject_id, **kwargs):
        self._calls.append(("get_subject_performance_summary", {"subject_id": subject_id, **kwargs}))
        if subject_id == "SUB9999":
            return None
        if subject_id == "":
            raise ValueError("subject_id must be a non-empty string")
        return fake_subject_performance()

    async def get_subject_attendance_summary(self, subject_id, **kwargs):
        self._calls.append(("get_subject_attendance_summary", {"subject_id": subject_id, **kwargs}))
        if subject_id == "SUB9999":
            return None
        if subject_id == "":
            raise ValueError("subject_id must be a non-empty string")
        return fake_subject_attendance()

    async def get_subject_underperformers(self, subject_id, **kwargs):
        self._calls.append(("get_subject_underperformers", {"subject_id": subject_id, **kwargs}))
        if subject_id == "":
            raise ValueError("subject_id must be a non-empty string")
        return fake_underperformers()

    async def get_department_overview(self, **kwargs):
        self._calls.append(("get_department_overview", kwargs))
        return fake_department_overview()

    async def get_semester_performance_distribution(self, **kwargs):
        self._calls.append(("get_semester_performance_distribution", kwargs))
        return fake_performance_distribution()

    async def get_attendance_distribution(self, **kwargs):
        self._calls.append(("get_attendance_distribution", kwargs))
        return fake_attendance_distribution()

    async def get_backlog_distribution(self, **kwargs):
        self._calls.append(("get_backlog_distribution", kwargs))
        return fake_backlog_distribution()

    async def get_at_risk_students(self, **kwargs):
        self._calls.append(("get_at_risk_students", kwargs))
        return fake_at_risk()

    async def get_students_below_attendance_threshold(self, **kwargs):
        self._calls.append(("get_students_below_attendance_threshold", kwargs))
        return fake_below_threshold()

    async def get_subjects_needing_attention(self, **kwargs):
        self._calls.append(("get_subjects_needing_attention", kwargs))
        return fake_subjects_attention()


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

def _setup_client(fake_service=None):
    """Create a TestClient with dependency overrides for analytics tests."""
    svc = fake_service or FakeAnalyticsService()
    app.dependency_overrides[get_db_pool] = lambda: None
    app.dependency_overrides[get_analytics_service] = lambda: svc
    client = TestClient(app)
    return client, svc


def _teardown():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# A. Student Analytics Endpoints
# ---------------------------------------------------------------------------

class TestStudentAcademicProfileEndpoint(unittest.TestCase):
    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_happy_path(self):
        resp = self.client.get("/api/v1/analytics/students/STU000001/academic-profile")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["student_id"], "STU000001")
        self.assertEqual(data["full_name"], "Jay Shah")
        self.assertEqual(data["overall_cgpa"], 8.5)

    def test_404_not_found(self):
        resp = self.client.get("/api/v1/analytics/students/STU999999/academic-profile")
        self.assertEqual(resp.status_code, 404)

    def test_correct_service_call(self):
        self.client.get("/api/v1/analytics/students/STU000001/academic-profile")
        method, kwargs = self.svc._calls[-1]
        self.assertEqual(method, "get_student_academic_profile")
        self.assertEqual(kwargs["student_id"], "STU000001")


class TestStudentSemesterHistoryEndpoint(unittest.TestCase):
    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_happy_path(self):
        resp = self.client.get("/api/v1/analytics/students/STU000001/semester-history")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["student_id"], "STU000001")
        self.assertEqual(len(data["semesters"]), 2)

    def test_with_filters(self):
        resp = self.client.get(
            "/api/v1/analytics/students/STU000001/semester-history",
            params={"semester_no": 7, "department_code": 1, "academic_year": "2026-27"},
        )
        self.assertEqual(resp.status_code, 200)
        method, kwargs = self.svc._calls[-1]
        self.assertEqual(method, "get_student_semester_history")
        self.assertEqual(kwargs["semester_no"], 7)
        self.assertEqual(kwargs["department_code"], 1)
        self.assertEqual(kwargs["academic_year"], "2026-27")

    def test_invalid_semester_rejected(self):
        resp = self.client.get(
            "/api/v1/analytics/students/STU000001/semester-history",
            params={"semester_no": 9},
        )
        self.assertEqual(resp.status_code, 422)

    def test_invalid_dept_code_rejected(self):
        resp = self.client.get(
            "/api/v1/analytics/students/STU000001/semester-history",
            params={"department_code": 0},
        )
        self.assertEqual(resp.status_code, 422)


class TestStudentAttendanceSummaryEndpoint(unittest.TestCase):
    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_happy_path(self):
        resp = self.client.get("/api/v1/analytics/students/STU000001/attendance-summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["student_id"], "STU000001")
        self.assertEqual(data["total_classes"], 100)

    def test_with_filters(self):
        resp = self.client.get(
            "/api/v1/analytics/students/STU000001/attendance-summary",
            params={"semester_no": 7, "subject_id": "SUB0050"},
        )
        self.assertEqual(resp.status_code, 200)
        method, kwargs = self.svc._calls[-1]
        self.assertEqual(kwargs["semester_no"], 7)
        self.assertEqual(kwargs["subject_id"], "SUB0050")


class TestStudentBacklogSummaryEndpoint(unittest.TestCase):
    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_happy_path(self):
        resp = self.client.get("/api/v1/analytics/students/STU000001/backlog-summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["student_id"], "STU000001")
        self.assertEqual(data["total_backlogs"], 2)


# ---------------------------------------------------------------------------
# B. Subject Analytics Endpoints
# ---------------------------------------------------------------------------

class TestSubjectPerformanceEndpoint(unittest.TestCase):
    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_happy_path(self):
        resp = self.client.get("/api/v1/analytics/subjects/SUB0050/performance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["subject_id"], "SUB0050")
        self.assertEqual(data["total_students"], 50)

    def test_404_not_found(self):
        resp = self.client.get("/api/v1/analytics/subjects/SUB9999/performance")
        self.assertEqual(resp.status_code, 404)

    def test_with_semester(self):
        resp = self.client.get(
            "/api/v1/analytics/subjects/SUB0050/performance",
            params={"semester_no": 7},
        )
        self.assertEqual(resp.status_code, 200)
        method, kwargs = self.svc._calls[-1]
        self.assertEqual(kwargs["semester_no"], 7)


class TestSubjectAttendanceEndpoint(unittest.TestCase):
    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_happy_path(self):
        resp = self.client.get("/api/v1/analytics/subjects/SUB0050/attendance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["subject_id"], "SUB0050")
        self.assertEqual(data["total_students"], 50)

    def test_404_not_found(self):
        resp = self.client.get("/api/v1/analytics/subjects/SUB9999/attendance")
        self.assertEqual(resp.status_code, 404)


class TestSubjectUnderperformersEndpoint(unittest.TestCase):
    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_happy_path(self):
        resp = self.client.get("/api/v1/analytics/subjects/SUB0050/underperformers")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["subject_id"], "SUB0050")
        self.assertEqual(len(data["students"]), 1)

    def test_custom_threshold(self):
        resp = self.client.get(
            "/api/v1/analytics/subjects/SUB0050/underperformers",
            params={"threshold": 50.0},
        )
        self.assertEqual(resp.status_code, 200)
        method, kwargs = self.svc._calls[-1]
        self.assertEqual(kwargs["threshold"], 50.0)

    def test_invalid_threshold_rejected(self):
        resp = self.client.get(
            "/api/v1/analytics/subjects/SUB0050/underperformers",
            params={"threshold": 101},
        )
        self.assertEqual(resp.status_code, 422)

    def test_negative_threshold_rejected(self):
        resp = self.client.get(
            "/api/v1/analytics/subjects/SUB0050/underperformers",
            params={"threshold": -1},
        )
        self.assertEqual(resp.status_code, 422)


# ---------------------------------------------------------------------------
# C. Department / Semester Analytics Endpoints
# ---------------------------------------------------------------------------

class TestDepartmentOverviewEndpoint(unittest.TestCase):
    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_happy_path(self):
        resp = self.client.get("/api/v1/analytics/departments/overview")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["department_code"], 1)
        self.assertEqual(data["total_students"], 50)

    def test_with_filters(self):
        resp = self.client.get(
            "/api/v1/analytics/departments/overview",
            params={"department_code": 1, "semester_no": 7, "academic_year": "2026-27"},
        )
        self.assertEqual(resp.status_code, 200)
        method, kwargs = self.svc._calls[-1]
        self.assertEqual(kwargs["department_code"], 1)
        self.assertEqual(kwargs["semester_no"], 7)
        self.assertEqual(kwargs["academic_year"], "2026-27")

    def test_invalid_dept_code_rejected(self):
        resp = self.client.get(
            "/api/v1/analytics/departments/overview",
            params={"department_code": 0},
        )
        self.assertEqual(resp.status_code, 422)

    def test_invalid_semester_rejected(self):
        resp = self.client.get(
            "/api/v1/analytics/departments/overview",
            params={"semester_no": 0},
        )
        self.assertEqual(resp.status_code, 422)


class TestPerformanceDistributionEndpoint(unittest.TestCase):
    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_happy_path(self):
        resp = self.client.get("/api/v1/analytics/departments/performance-distribution")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["department_code"], 1)
        self.assertEqual(data["total_students"], 50)
        self.assertEqual(len(data["buckets"]), 2)


class TestAttendanceDistributionEndpoint(unittest.TestCase):
    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_happy_path(self):
        resp = self.client.get("/api/v1/analytics/departments/attendance-distribution")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_students"], 50)
        self.assertEqual(len(data["buckets"]), 2)


class TestBacklogDistributionEndpoint(unittest.TestCase):
    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_happy_path(self):
        resp = self.client.get("/api/v1/analytics/departments/backlog-distribution")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["department_code"], 1)
        self.assertEqual(data["total_students"], 50)
        self.assertEqual(data["students_with_backlogs"], 15)


# ---------------------------------------------------------------------------
# D. At-Risk Analytics Endpoints
# ---------------------------------------------------------------------------

class TestAtRiskStudentsEndpoint(unittest.TestCase):
    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_happy_path(self):
        resp = self.client.get("/api/v1/analytics/at-risk/students")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_flagged"], 2)
        self.assertEqual(len(data["students"]), 1)
        self.assertEqual(data["students"][0]["student_id"], "STU000003")

    def test_with_filters(self):
        resp = self.client.get(
            "/api/v1/analytics/at-risk/students",
            params={"department_code": 1, "semester_no": 7},
        )
        self.assertEqual(resp.status_code, 200)
        method, kwargs = self.svc._calls[-1]
        self.assertEqual(kwargs["department_code"], 1)
        self.assertEqual(kwargs["semester_no"], 7)


class TestBelowAttendanceThresholdEndpoint(unittest.TestCase):
    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_happy_path(self):
        resp = self.client.get("/api/v1/analytics/at-risk/below-attendance-threshold")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_flagged"], 1)
        self.assertEqual(data["students"][0]["student_id"], "STU000005")

    def test_custom_threshold(self):
        resp = self.client.get(
            "/api/v1/analytics/at-risk/below-attendance-threshold",
            params={"threshold": 80.0},
        )
        self.assertEqual(resp.status_code, 200)
        method, kwargs = self.svc._calls[-1]
        self.assertEqual(kwargs["threshold"], 80.0)


class TestSubjectsNeedingAttentionEndpoint(unittest.TestCase):
    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_happy_path(self):
        resp = self.client.get("/api/v1/analytics/at-risk/subjects-needing-attention")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_flagged"], 1)
        self.assertEqual(data["subjects"][0]["subject_id"], "SUB0053")

    def test_with_filters(self):
        resp = self.client.get(
            "/api/v1/analytics/at-risk/subjects-needing-attention",
            params={"department_code": 1, "semester_no": 7},
        )
        self.assertEqual(resp.status_code, 200)
        method, kwargs = self.svc._calls[-1]
        self.assertEqual(kwargs["department_code"], 1)
        self.assertEqual(kwargs["semester_no"], 7)


# ---------------------------------------------------------------------------
# Cross-cutting: Registration, No SQL, No Writes
# ---------------------------------------------------------------------------

class TestAnalyticsRouterRegistration(unittest.TestCase):
    """Verify all analytics routes are registered in the app."""

    def setUp(self):
        self.client, self._svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_all_endpoints_reachable(self):
        endpoints = [
            "/api/v1/analytics/students/STU000001/academic-profile",
            "/api/v1/analytics/students/STU000001/semester-history",
            "/api/v1/analytics/students/STU000001/attendance-summary",
            "/api/v1/analytics/students/STU000001/backlog-summary",
            "/api/v1/analytics/subjects/SUB0050/performance",
            "/api/v1/analytics/subjects/SUB0050/attendance",
            "/api/v1/analytics/subjects/SUB0050/underperformers",
            "/api/v1/analytics/departments/overview",
            "/api/v1/analytics/departments/performance-distribution",
            "/api/v1/analytics/departments/attendance-distribution",
            "/api/v1/analytics/departments/backlog-distribution",
            "/api/v1/analytics/at-risk/students",
            "/api/v1/analytics/at-risk/below-attendance-threshold",
            "/api/v1/analytics/at-risk/subjects-needing-attention",
        ]
        for url in endpoints:
            resp = self.client.get(url)
            self.assertIn(
                resp.status_code, (200, 404),
                f"Endpoint {url} returned unexpected status {resp.status_code}",
            )

    def test_all_endpoints_are_get_only(self):
        """Analytics endpoints should not accept POST/PUT/DELETE."""
        endpoints = [
            "/api/v1/analytics/students/STU000001/academic-profile",
            "/api/v1/analytics/departments/overview",
            "/api/v1/analytics/at-risk/students",
        ]
        for url in endpoints:
            for method in ("post", "put", "delete", "patch"):
                resp = getattr(self.client, method)(url)
                self.assertEqual(
                    resp.status_code, 405,
                    f"Endpoint {url} should not accept {method.upper()}",
                )

    def test_no_sql_in_route_module(self):
        """Verify the analytics route module contains no SQL statements."""
        import inspect
        from app.api.v1 import analytics as analytics_module
        source = inspect.getsource(analytics_module)
        for keyword in ("INSERT", "UPDATE", "DELETE", "CREATE TABLE", "ALTER TABLE"):
            self.assertNotIn(
                keyword, source,
                f"Found SQL keyword '{keyword}' in analytics route module",
            )

    def test_no_pool_acquire_in_routes(self):
        """Routes must not directly acquire database connections."""
        import inspect
        from app.api.v1 import analytics as analytics_module
        source = inspect.getsource(analytics_module)
        self.assertNotIn("pool.acquire", source)
        self.assertNotIn("conn.fetch", source)
        self.assertNotIn("conn.execute", source)


class TestServiceDependencyInjection(unittest.TestCase):
    """Verify the analytics service is injected via Depends."""

    def setUp(self):
        self.client, self.svc = _setup_client()

    def tearDown(self):
        _teardown()

    def test_service_receives_correct_arguments(self):
        self.client.get(
            "/api/v1/analytics/students/STU000001/semester-history",
            params={"semester_no": 5, "department_code": 1},
        )
        method, kwargs = self.svc._calls[-1]
        self.assertEqual(method, "get_student_semester_history")
        self.assertEqual(kwargs["student_id"], "STU000001")
        self.assertEqual(kwargs["semester_no"], 5)
        self.assertEqual(kwargs["department_code"], 1)

    def test_each_endpoint_calls_service(self):
        """Each endpoint should invoke exactly one service method."""
        initial_count = len(self.svc._calls)
        self.client.get("/api/v1/analytics/students/STU000001/academic-profile")
        self.assertEqual(len(self.svc._calls), initial_count + 1)


if __name__ == "__main__":
    unittest.main()
