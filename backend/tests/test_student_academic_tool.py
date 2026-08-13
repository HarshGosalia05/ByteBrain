"""G2.1 Student Academic Performance Tool tests.

Covers (from the G2.1 acceptance checklist):

RBAC:
  * authenticated student can retrieve own academic data
  * student cannot retrieve another student's data
  * client-supplied student_id cannot override authenticated identity
  * missing authenticated identity is rejected
  * non-student roles cannot use the Student-only tool
  * G1 registry marks academic_performance as implemented
  * other G1 placeholders remain unimplemented

Data:
  * correct current semester, semester ordering, semester metric mapping
  * no future/predicted semester included as current performance
  * no prediction values appear in academic performance output
  * no NaN/invalid numerics, missing data represented safely
  * deterministic, repeatable numeric output

Grounding:
  * output contains only source-backed values
  * no fake confidence, no fabricated recommendations
  * controlled "data unavailable" result when nothing is verified

Security:
  * no SQL / DB-session / repository capability reachable from the result
  * no arbitrary callable / import path in the registry contract
  * tool output feeds G0 VerifiedContext (never bypasses G0)

No live database: a fake asyncpg pool records the executed SQL.
"""
import asyncio
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import HTTPException

from app.schemas.genai import VerifiedContext
from app.schemas.student_tool import (
    StudentAcademicPerformanceResult,
    ToolSemesterMetric,
)
from app.schemas.tools import ToolDefinition
from app.services.student_academic_tool import (
    INTENT,
    SOURCE_LABEL,
    TOOL_NAME,
    StudentAcademicTool,
)
from app.services.student_service import StudentService
from app.services.tool_registry import build_default_registry


class FakeConn:
    def __init__(self, fetch_rows=None, fetchrow_row=None):
        self.fetch_rows = list(fetch_rows or [])
        self.fetchrow_row = fetchrow_row
        self.executed = []  # list of (kind, query, args)

    async def fetch(self, query, *args):
        self.executed.append(("fetch", query, args))
        return self.fetch_rows

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


def profile_row(**overrides):
    row = {
        "student_id": "STU-A",
        "first_name": "Alice",
        "last_name": "Appleton",
        "enrollment_no": 1001,
        "admission_year": 2023,
        "current_semester": 6,
        "department_name": "Computer Science",
        "department_code": "CSE",
        "current_academic_year": "2025-26",
        "latest_sgpa": 8.4,
        "overall_cgpa": 8.1,
        "overall_percentage": 72.5,
        "total_credits_registered": 60,
        "total_credits_earned": 45,
        "total_backlogs": 1,
        "academic_standing": "Good",
    }
    row.update(overrides)
    return row


def summary_row(semester, **overrides):
    row = {
        "semester": semester,
        "sgpa": 8.2,
        "total_credits_earned": 20,
        "attendance_percentage": 88.0,
        "active_backlogs": 0,
        "academic_year": "2024-25",
        "subjects_registered": 5,
        "credits_registered": 20,
        "semester_percentage": 75.5,
        "semester_grade": "A",
        "semester_result": "Pass",
        "academic_standing": "Good",
    }
    row.update(overrides)
    return row


def _service(conn):
    return StudentAcademicTool(FakePool(conn))


def _summaries_for(rows):
    return [summary_row(**row) if isinstance(row, dict) else summary_row(row) for row in rows]


class TestStudentSelfScope(unittest.TestCase):
    def test_authenticated_student_retrieves_own_data(self):
        conn = FakeConn(fetch_rows=[summary_row(6)], fetchrow_row=profile_row())
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertIsInstance(result, StudentAcademicPerformanceResult)
        self.assertTrue(result.data_available)
        self.assertEqual(result.student_id, "STU-A")

    def test_student_cannot_retrieve_another_student_data(self):
        conn = FakeConn(fetch_rows=[summary_row(6)], fetchrow_row=profile_row())
        with self.assertRaises(HTTPException) as ctx:
            run(_service(conn).execute(student_id="STU-A", target_student_id="STU-B"))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(conn.executed, [])  # no data access for the foreign id

    def test_client_student_id_cannot_override_identity(self):
        conn = FakeConn(fetch_rows=[summary_row(6)], fetchrow_row=profile_row())
        with self.assertRaises(HTTPException) as ctx:
            run(_service(conn).execute(student_id="STU-A", target_student_id="STU-B"))
        self.assertEqual(ctx.exception.status_code, 403)
        # repository was never queried with the client-supplied id
        for _kind, query, args in conn.executed:
            self.assertNotIn("STU-B", args)

    def test_missing_authenticated_identity_rejected(self):
        conn = FakeConn(fetch_rows=[], fetchrow_row=None)
        with self.assertRaises(HTTPException) as ctx:
            run(_service(conn).execute(student_id=""))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(conn.executed, [])

    def test_missing_student_profile_404(self):
        conn = FakeConn(fetch_rows=[], fetchrow_row=None)
        with self.assertRaises(HTTPException) as ctx:
            run(_service(conn).execute(student_id="STU-UNKNOWN"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_tool_takes_only_authenticated_identity(self):
        # No role parameter exists on the tool contract - identity cannot be
        # elevated from a client claim.
        import inspect

        params = inspect.signature(StudentAcademicTool.execute).parameters
        self.assertNotIn("role", params)
        self.assertNotIn("user_id", params)


class TestToolRegistration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = build_default_registry()

    def test_registry_marks_academic_performance_implemented(self):
        tool = self.registry.get(TOOL_NAME)
        self.assertIsNotNone(tool)
        self.assertTrue(tool.implemented)
        resolved = self.registry.tool_for_intent(INTENT, "Student")
        self.assertEqual(resolved.tool_name, TOOL_NAME)
        self.assertTrue(resolved.implemented)

    def test_student_tools_implemented(self):
        for tool_name in (
            TOOL_NAME,
            "student_attendance_tool",
            "student_career_coach_tool",
            "student_prediction_explanation_tool",
            "student_subject_analysis_tool",
        ):
            tool = self.registry.get(tool_name)
            self.assertIsNotNone(tool)
            self.assertTrue(tool.implemented)

    def test_non_student_roles_cannot_use_student_tool(self):
        self.assertFalse(self.registry.is_allowed(TOOL_NAME, "Faculty"))
        self.assertFalse(self.registry.is_allowed(TOOL_NAME, "Admin"))
        self.assertIsNone(self.registry.tool_for_intent(INTENT, "Faculty"))
        self.assertIsNone(self.registry.tool_for_intent(INTENT, "Admin"))

    def test_tool_contract_matches_registered_definition(self):
        self.assertEqual(TOOL_NAME, "student_academic_performance_tool")
        self.assertEqual(INTENT, "academic_performance")
        self.assertEqual(SOURCE_LABEL, "students/student_semester_summary")


class TestDataSemantics(unittest.TestCase):
    def test_current_semester_from_verified_profile(self):
        conn = FakeConn(fetch_rows=[summary_row(6)], fetchrow_row=profile_row())
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertEqual(result.overview.current_semester, 6)
        self.assertEqual(result.overview.current_academic_year, "2025-26")
        self.assertEqual(result.overview.latest_sgpa, 8.4)

    def test_semester_ordering_ascending(self):
        rows = _summaries_for([6, 1, 4, 2, 5, 3])
        conn = FakeConn(fetch_rows=rows, fetchrow_row=profile_row())
        result = run(_service(conn).execute(student_id="STU-A"))
        semesters = [m.semester for m in result.semester_performance]
        self.assertEqual(semesters, sorted(semesters))
        self.assertEqual(semesters, [1, 2, 3, 4, 5, 6])

    def test_semester_metrics_map_to_correct_semester(self):
        rows = _summaries_for([1, 2, 3])
        conn = FakeConn(fetch_rows=rows, fetchrow_row=profile_row())
        result = run(_service(conn).execute(student_id="STU-A"))
        by_semester = {m.semester: m for m in result.semester_performance}
        self.assertEqual(by_semester[2].percentage, 75.5)
        self.assertEqual(by_semester[2].sgpa, 8.2)
        self.assertEqual(by_semester[1].active_backlogs, 0)

    def test_no_future_semester_included_as_current(self):
        rows = _summaries_for([1, 2, 3, 4, 5, 6])
        conn = FakeConn(fetch_rows=rows, fetchrow_row=profile_row(current_semester=6))
        result = run(_service(conn).execute(student_id="STU-A"))
        semesters = [m.semester for m in result.semester_performance]
        self.assertEqual(max(semesters), 6)
        self.assertEqual(result.overview.current_semester, 6)
        self.assertNotIn(7, semesters)

    def test_no_prediction_values_in_output(self):
        rows = _summaries_for([1, 2, 3])
        conn = FakeConn(fetch_rows=rows, fetchrow_row=profile_row())
        result = run(_service(conn).execute(student_id="STU-A"))
        dumped = result.model_dump()
        def walk(value, path=""):
            if isinstance(value, dict):
                for key, item in value.items():
                    walk(item, f"{path}.{key}")
            elif isinstance(value, list):
                for item in value:
                    walk(item, path)
            else:
                lowered = str(value).lower()
                for token in ("predict", "predicted", "future risk", "m1", "m2", "m3"):
                    self.assertNotIn(token, lowered, f"{token} leaked at {path}")

        walk(dumped)

    def test_no_nan_or_invalid_numerics(self):
        rows = _summaries_for([1, 2, 3])
        conn = FakeConn(fetch_rows=rows, fetchrow_row=profile_row())
        result = run(_service(conn).execute(student_id="STU-A"))
        for metric in result.semester_performance:
            for value in (
                metric.percentage,
                metric.sgpa,
                metric.attendance_percentage,
            ):
                if value is not None:
                    self.assertTrue(math.isfinite(float(value)))

    def test_missing_data_represented_safely(self):
        null_profile = profile_row(
            current_semester=None,
            current_academic_year=None,
            latest_sgpa=None,
            overall_cgpa=None,
            overall_percentage=None,
            total_credits_registered=None,
            total_credits_earned=None,
            total_backlogs=None,
            academic_standing=None,
        )
        conn = FakeConn(fetch_rows=[], fetchrow_row=null_profile)
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertFalse(result.data_available)
        self.assertEqual(result.note, "No verified academic data available.")
        self.assertEqual(result.semester_performance, [])
        self.assertFalse(result.trend.available)
        self.assertEqual(result.signals.strong_areas, [])
        self.assertEqual(result.signals.attention_areas, [])
        self.assertIsNone(result.overview.latest_sgpa)

    def test_numeric_output_deterministic(self):
        rows = _summaries_for([1, 2, 3])
        conn1 = FakeConn(fetch_rows=list(rows), fetchrow_row=profile_row())
        conn2 = FakeConn(fetch_rows=list(rows), fetchrow_row=profile_row())
        first = run(_service(conn1).execute(student_id="STU-A"))
        second = run(_service(conn2).execute(student_id="STU-A"))
        self.assertEqual(
            first.model_dump(exclude={"generated_at"}),
            second.model_dump(exclude={"generated_at"}),
        )

    def test_repeated_execution_identical_output(self):
        rows = _summaries_for([1, 2, 3])
        conn = FakeConn(fetch_rows=list(rows), fetchrow_row=profile_row())
        svc = _service(conn)
        first = run(svc.execute(student_id="STU-A"))
        second = run(svc.execute(student_id="STU-A"))
        self.assertEqual(
            first.model_dump(exclude={"generated_at"}),
            second.model_dump(exclude={"generated_at"}),
        )


class TestGrounding(unittest.TestCase):
    def test_output_only_source_backed_values(self):
        rows = [
            summary_row(1, semester_percentage=70.0, sgpa=7.8),
            summary_row(2, semester_percentage=65.5, sgpa=7.5),
        ]
        conn = FakeConn(fetch_rows=rows, fetchrow_row=profile_row())
        result = run(_service(conn).execute(student_id="STU-A"))
        by_semester = {m.semester: m for m in result.semester_performance}
        self.assertEqual(by_semester[1].percentage, 70.0)
        self.assertEqual(by_semester[1].sgpa, 7.8)
        self.assertEqual(by_semester[2].percentage, 65.5)
        self.assertEqual(by_semester[2].sgpa, 7.5)

    def test_no_fake_confidence(self):
        rows = _summaries_for([1, 2, 3])
        conn = FakeConn(fetch_rows=rows, fetchrow_row=profile_row())
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertNotIn("confidence", result.model_dump())

    def test_no_fabricated_recommendations(self):
        rows = _summaries_for([1, 2, 3])
        conn = FakeConn(fetch_rows=rows, fetchrow_row=profile_row())
        result = run(_service(conn).execute(student_id="STU-A"))
        all_signals = result.signals.strong_areas + result.signals.attention_areas
        self.assertGreater(len(all_signals), 0)
        for signal in all_signals:
            for token in ("should", "recommend", "suggest", "advice", "try "):
                self.assertNotIn(token, signal.lower())

    def test_signals_traceable_to_data(self):
        rows = [
            summary_row(1, semester_percentage=85.0, sgpa=9.0, active_backlogs=1),
            summary_row(2, semester_percentage=60.0, sgpa=7.0, active_backlogs=2),
        ]
        conn = FakeConn(fetch_rows=rows, fetchrow_row=profile_row(total_backlogs=2))
        result = run(_service(conn).execute(student_id="STU-A"))
        strong = " ".join(result.signals.strong_areas)
        attention = " ".join(result.signals.attention_areas)
        self.assertIn("semester 1", strong)
        self.assertIn("85.00%", strong)
        self.assertIn("Active backlogs in semester 2: 2", attention)
        self.assertIn("Total active backlogs: 2", attention)

    def test_trend_uses_existing_rule(self):
        rows = [
            summary_row(1, sgpa=7.0, semester_percentage=60.0),
            summary_row(2, sgpa=8.5, semester_percentage=78.0),
        ]
        conn = FakeConn(fetch_rows=rows, fetchrow_row=profile_row())
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertTrue(result.trend.available)
        self.assertEqual(result.trend.overall_direction, "improving")


class TestSecurityCapabilities(unittest.TestCase):
    def test_result_never_exposes_db_repo_or_session(self):
        rows = _summaries_for([1])
        conn = FakeConn(fetch_rows=rows, fetchrow_row=profile_row())
        result = run(_service(conn).execute(student_id="STU-A"))
        dumped = result.model_dump()
        for token in ("sql", "pool", "session", "repository", "conn", "cursor", "query"):
            self.assertNotIn(token, dumped)

    def test_tool_reuses_existing_service_through_normal_architecture(self):
        # The tool is an adapter over StudentService, the verified layer.
        self.assertIsInstance(
            StudentAcademicTool(FakePool(FakeConn()))._student_service,
            StudentService,
        )

    def test_registry_has_no_callable_or_import_path(self):
        tool = build_default_registry().get(TOOL_NAME)
        fields = set(ToolDefinition.model_fields)
        for token in ("callable", "import_path", "exec", "eval", "sql", "handler"):
            self.assertNotIn(token, fields)

    def test_result_feeds_g0_verified_context(self):
        rows = _summaries_for([1, 2, 3])
        conn = FakeConn(fetch_rows=rows, fetchrow_row=profile_row())
        result = run(_service(conn).execute(student_id="STU-A"))
        verified = StudentAcademicTool.to_verified_context(
            _service(conn), result
        )
        self.assertIsInstance(verified, VerifiedContext)
        self.assertEqual(verified.source, result.source)
        self.assertEqual(verified.data["student_id"], "STU-A")
        self.assertIsInstance(verified.data["semester_performance"], list)


if __name__ == "__main__":
    unittest.main()
