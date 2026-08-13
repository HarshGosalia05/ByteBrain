"""G2.2 Student Attendance Tool tests.

Covers (from the G2.2 acceptance checklist):

RBAC:
  * authenticated student can retrieve own attendance
  * student cannot retrieve another student's attendance
  * client-supplied target_student_id cannot override authenticated identity
  * client role cannot override authenticated role (no role claim exists)
  * unauthenticated / missing identity rejected
  * non-student roles cannot use the Student-only attendance tool
  * G1 registry marks student_attendance as implemented
  * other G1 placeholders remain unimplemented
  * intent still resolves through the existing IntentRouter

Data:
  * correct attendance percentage returned
  * correct semester association
  * subject attendance maps correctly
  * no future/predicted attendance appears
  * no marks are used as attendance
  * no ML prediction values appear
  * no NaN/invalid values
  * missing attendance handled safely
  * repeated execution deterministic
  * source metadata correct

Grounding:
  * every numeric attendance value is source-backed
  * no invented threshold, trend, confidence, or recommendation
  * controlled "data unavailable" result when nothing is verified

Security:
  * no SQL / DB-session / repository capability reachable from the result
  * no arbitrary callable / import path in the registry contract
  * tool output feeds G0 VerifiedContext (never bypasses G0)
  * no cross-student access

No live database: a fake asyncpg pool records the executed SQL.
"""
import asyncio
import inspect
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import HTTPException

from app.schemas.genai import VerifiedContext
from app.schemas.student_attendance_tool import (
    StudentAttendanceResult,
    ToolSubjectAttendance,
)
from app.schemas.tools import IntentRequest, ToolDefinition
from app.services.intent_router import IntentRouter
from app.services.student_attendance_tool import (
    INTENT,
    SOURCE_LABEL,
    TOOL_NAME,
    StudentAttendanceTool,
)
from app.services.student_service import StudentService
from app.services.tool_registry import build_default_registry


class FakeConn:
    """Serves one row-set per fetch (summaries, then subject attendance)."""

    def __init__(self, fetch_sets=None, fetchrow_row=None):
        self._fetch_sets = [list(s) for s in (fetch_sets or [])]
        self.fetchrow_row = fetchrow_row
        self._fetch_index = 0
        self.executed = []

    def reset(self):
        """Re-run the same plan (used to prove repeated-execution determinism)."""
        self._fetch_index = 0

    async def fetch(self, query, *args):
        self.executed.append(("fetch", query, args))
        if self._fetch_index < len(self._fetch_sets):
            rows = self._fetch_sets[self._fetch_index]
            self._fetch_index += 1
            return list(rows)
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
        "sgpa": 8.0,
        "total_credits_earned": 20,
        "attendance_percentage": 80.0,
        "active_backlogs": 0,
        "academic_year": "2025-26",
    }
    row.update(overrides)
    return row


def attendance_subject_row(**overrides):
    row = {
        "subject_id": "SUB001",
        "subject_code": "CSE101",
        "subject_name": "Programming Fundamentals",
        "credits": 4,
        "total_classes": 20,
        "attended_classes": 15,
        "attendance_percentage": 75.0,
        "attendance_status": "Average",
        "eligibility_status": "Eligible",
        "shortage_flag": "No",
    }
    row.update(overrides)
    return row


def _conn(summaries=None, subjects=None, profile=None):
    return FakeConn(
        fetch_sets=[
            list(summaries or []),
            list(subjects or []),
        ],
        fetchrow_row=profile if profile is not None else profile_row(),
    )


def _service(conn):
    return StudentAttendanceTool(FakePool(conn))


class TestStudentSelfScope(unittest.TestCase):
    def test_authenticated_student_retrieves_own_attendance(self):
        conn = _conn(
            summaries=[summary_row(6)],
            subjects=[attendance_subject_row()],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertIsInstance(result, StudentAttendanceResult)
        self.assertTrue(result.data_available)
        self.assertEqual(result.student_id, "STU-A")

    def test_student_cannot_retrieve_another_student_attendance(self):
        conn = _conn(
            summaries=[summary_row(6)],
            subjects=[attendance_subject_row()],
        )
        with self.assertRaises(HTTPException) as ctx:
            run(_service(conn).execute(student_id="STU-A", target_student_id="STU-B"))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(conn.executed, [])  # no data access for the foreign id

    def test_client_student_id_cannot_override_identity(self):
        conn = _conn(
            summaries=[summary_row(6)],
            subjects=[attendance_subject_row()],
        )
        with self.assertRaises(HTTPException) as ctx:
            run(_service(conn).execute(student_id="STU-A", target_student_id="STU-B"))
        self.assertEqual(ctx.exception.status_code, 403)
        # repository was never queried with the client-supplied id
        for _kind, query, args in conn.executed:
            self.assertNotIn("STU-B", args)

    def test_client_role_cannot_override_authenticated_role(self):
        # There is no role/user_id parameter on the tool contract - a client
        # role claim is structurally impossible. Role gating is enforced by
        # the G1 registry (see TestToolRegistration).
        params = inspect.signature(StudentAttendanceTool.execute).parameters
        self.assertNotIn("role", params)
        self.assertNotIn("user_id", params)

    def test_missing_authenticated_identity_rejected(self):
        conn = _conn()
        with self.assertRaises(HTTPException) as ctx:
            run(_service(conn).execute(student_id=""))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(conn.executed, [])

    def test_missing_student_profile_404(self):
        conn = FakeConn(fetch_sets=[[], []], fetchrow_row=None)
        with self.assertRaises(HTTPException) as ctx:
            run(_service(conn).execute(student_id="STU-UNKNOWN"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_tool_takes_only_authenticated_identity(self):
        params = inspect.signature(StudentAttendanceTool.execute).parameters
        self.assertNotIn("role", params)
        self.assertNotIn("user_id", params)
        self.assertNotIn("enrollment_no", params)


class TestToolRegistration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = build_default_registry()

    def test_registry_marks_student_attendance_implemented(self):
        tool = self.registry.get(TOOL_NAME)
        self.assertIsNotNone(tool)
        self.assertTrue(tool.implemented)
        resolved = self.registry.tool_for_intent(INTENT, "Student")
        self.assertEqual(resolved.tool_name, TOOL_NAME)
        self.assertTrue(resolved.implemented)

    def test_student_tools_implemented(self):
        for tool_name in (
            "student_academic_performance_tool",
            "student_attendance_tool",
            "student_career_coach_tool",
            "student_prediction_explanation_tool",
            "student_subject_analysis_tool",
        ):
            tool = self.registry.get(tool_name)
            self.assertIsNotNone(tool)
            self.assertTrue(tool.implemented)

    def test_non_student_roles_cannot_use_student_attendance_tool(self):
        self.assertFalse(self.registry.is_allowed(TOOL_NAME, "Faculty"))
        self.assertFalse(self.registry.is_allowed(TOOL_NAME, "Admin"))
        self.assertIsNone(self.registry.tool_for_intent(INTENT, "Faculty"))
        self.assertIsNone(self.registry.tool_for_intent(INTENT, "Admin"))

    def test_tool_contract_matches_registered_definition(self):
        self.assertEqual(TOOL_NAME, "student_attendance_tool")
        self.assertEqual(INTENT, "attendance")
        self.assertEqual(SOURCE_LABEL, "students/attendance")

    def test_intent_resolves_through_existing_router(self):
        router = IntentRouter(self.registry)
        request = IntentRequest(
            role="Student",
            user_context_id="STU-A",
            message="What is my attendance?",
        )
        decision = router.route(request)
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.tool_name, TOOL_NAME)
        self.assertTrue(decision.is_implemented)
        self.assertEqual(decision.scope_requirements.scope, "own_student")
        self.assertEqual(decision.scope_requirements.target_student_id, "STU-A")

    def test_classifier_still_recognizes_attendance_intent(self):
        kind, intent = IntentRouter.classify("how is my attendance?", "Student")
        self.assertEqual(kind, "intent")
        self.assertEqual(intent, "attendance")


class TestDataSemantics(unittest.TestCase):
    def test_correct_attendance_percentage_returned(self):
        conn = _conn(
            summaries=[summary_row(6, attendance_percentage=75.0)],
            subjects=[attendance_subject_row()],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertEqual(result.current_semester, 6)
        self.assertEqual(result.current_academic_year, "2025-26")
        # simulate_attendance derives 15/20 -> 75.0; mean of one subject -> 75.0
        self.assertEqual(result.overall_attendance, 75.0)
        self.assertEqual(result.overall_attendance_status, "Average")
        self.assertEqual(result.overall_eligibility_status, "Eligible")
        self.assertEqual(result.overall_shortage_flag, "No")
        self.assertEqual(result.semester_attendance[0].attendance_percentage, 75.0)

    def test_correct_semester_association(self):
        conn = _conn(
            summaries=[
                summary_row(1, attendance_percentage=70.0, academic_year="2022-23"),
                summary_row(2, attendance_percentage=80.0, academic_year="2023-24"),
            ],
            subjects=[attendance_subject_row()],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        by_semester = {m.semester: m for m in result.semester_attendance}
        self.assertEqual(by_semester[1].attendance_percentage, 70.0)
        self.assertEqual(by_semester[1].academic_year, "2022-23")
        self.assertEqual(by_semester[2].attendance_percentage, 80.0)

    def test_semester_ordering_ascending(self):
        conn = _conn(
            summaries=[
                summary_row(6),
                summary_row(1),
                summary_row(4),
                summary_row(2),
                summary_row(5),
                summary_row(3),
            ],
            subjects=[attendance_subject_row()],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        semesters = [m.semester for m in result.semester_attendance]
        self.assertEqual(semesters, [1, 2, 3, 4, 5, 6])

    def test_subject_attendance_maps_correctly(self):
        conn = _conn(
            summaries=[summary_row(6)],
            subjects=[
                attendance_subject_row(
                    subject_id="SUB001",
                    subject_code="CSE101",
                    subject_name="Programming Fundamentals",
                    total_classes=20,
                    attended_classes=15,
                    attendance_percentage=75.0,
                    attendance_status="Average",
                    eligibility_status="Eligible",
                    shortage_flag="No",
                ),
                attendance_subject_row(
                    subject_id="SUB002",
                    subject_code="CSE102",
                    subject_name="Data Structures",
                    total_classes=30,
                    attended_classes=27,
                    attendance_percentage=90.0,
                    attendance_status="Excellent",
                    eligibility_status="Eligible",
                    shortage_flag="No",
                ),
            ],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertEqual(len(result.subject_attendance), 2)
        by_code = {s.subject_code: s for s in result.subject_attendance}
        cse102 = by_code["CSE102"]
        self.assertIsInstance(cse102, ToolSubjectAttendance)
        self.assertEqual(cse102.subject_name, "Data Structures")
        self.assertEqual(cse102.semester, 6)
        self.assertEqual(cse102.attendance_percentage, 90.0)
        self.assertEqual(cse102.total_classes, 30)
        self.assertEqual(cse102.attended_classes, 27)
        self.assertEqual(cse102.attendance_status, "Excellent")
        self.assertEqual(cse102.eligibility_status, "Eligible")
        self.assertEqual(cse102.shortage_flag, "No")

    def test_subject_attendance_semester_tagged_current(self):
        conn = _conn(
            summaries=[summary_row(6)],
            subjects=[attendance_subject_row()],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        for subject in result.subject_attendance:
            self.assertEqual(subject.semester, 6)

    def test_no_future_semester_attendance(self):
        conn = _conn(
            summaries=[
                summary_row(1),
                summary_row(2),
                summary_row(3),
                summary_row(4),
                summary_row(5),
                summary_row(6),
            ],
            subjects=[attendance_subject_row()],
            profile=profile_row(current_semester=6),
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        semesters = [m.semester for m in result.semester_attendance]
        self.assertEqual(max(semesters), 6)
        self.assertEqual(result.current_semester, 6)
        self.assertNotIn(7, semesters)

    def test_no_marks_used_as_attendance(self):
        conn = _conn(
            summaries=[summary_row(6)],
            subjects=[attendance_subject_row()],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        for key in result.model_dump():
            for token in ("sgpa", "marks", "grade", "cgpa", "performance"):
                self.assertNotIn(token, key.lower(), f"{token} leaked in key {key}")

    def test_no_prediction_values_in_output(self):
        conn = _conn(
            summaries=[summary_row(1), summary_row(2), summary_row(3)],
            subjects=[attendance_subject_row()],
        )
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
        conn = _conn(
            summaries=[
                summary_row(1, attendance_percentage=70.0),
                summary_row(2, attendance_percentage=80.0),
            ],
            subjects=[
                attendance_subject_row(total_classes=20, attended_classes=15),
            ],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        for metric in result.semester_attendance:
            if metric.attendance_percentage is not None:
                self.assertTrue(math.isfinite(float(metric.attendance_percentage)))
        for subject in result.subject_attendance:
            if subject.attendance_percentage is not None:
                self.assertTrue(math.isfinite(float(subject.attendance_percentage)))
        if result.overall_attendance is not None:
            self.assertTrue(math.isfinite(float(result.overall_attendance)))
        if result.trend.delta is not None:
            self.assertTrue(math.isfinite(float(result.trend.delta)))

    def test_missing_attendance_handled_safely(self):
        # A semester summary always carries a required attendance_percentage,
        # so "data unavailable" means no summary rows AND no subject rows.
        conn = _conn(summaries=[], subjects=[])
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertFalse(result.data_available)
        self.assertEqual(result.note, "No verified attendance data available.")
        self.assertEqual(result.semester_attendance, [])
        self.assertEqual(result.subject_attendance, [])
        self.assertIsNone(result.overall_attendance)
        self.assertIsNone(result.overall_attendance_status)
        self.assertIsNone(result.overall_eligibility_status)
        self.assertIsNone(result.overall_shortage_flag)
        self.assertFalse(result.trend.available)
        self.assertEqual(result.trend.direction, "insufficient")
        self.assertEqual(result.signals.strong_areas, [])
        self.assertEqual(result.signals.attention_areas, [])

    def test_missing_subject_attendance_still_reports_semester_level(self):
        conn = _conn(
            summaries=[
                summary_row(1, attendance_percentage=70.0),
                summary_row(2, attendance_percentage=80.0),
            ],
            subjects=[],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertTrue(result.data_available)
        self.assertEqual(len(result.semester_attendance), 2)
        self.assertEqual(result.subject_attendance, [])
        self.assertIsNone(result.overall_attendance)

    def test_numeric_output_deterministic(self):
        summaries = [
            summary_row(1, attendance_percentage=70.0),
            summary_row(2, attendance_percentage=80.0),
        ]
        subjects = [attendance_subject_row()]
        first = run(_service(_conn(summaries, subjects)).execute(student_id="STU-A"))
        second = run(_service(_conn(summaries, subjects)).execute(student_id="STU-A"))
        self.assertEqual(
            first.model_dump(exclude={"generated_at"}),
            second.model_dump(exclude={"generated_at"}),
        )

    def test_repeated_execution_identical_output(self):
        summaries = [
            summary_row(1, attendance_percentage=70.0),
            summary_row(2, attendance_percentage=80.0),
        ]
        subjects = [attendance_subject_row()]
        conn = _conn(summaries, subjects)
        svc = _service(conn)
        first = run(svc.execute(student_id="STU-A"))
        conn.reset()
        second = run(svc.execute(student_id="STU-A"))
        self.assertEqual(
            first.model_dump(exclude={"generated_at"}),
            second.model_dump(exclude={"generated_at"}),
        )

    def test_source_metadata_correct(self):
        conn = _conn(
            summaries=[summary_row(6)],
            subjects=[attendance_subject_row()],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertEqual(result.tool_name, TOOL_NAME)
        self.assertEqual(result.intent, INTENT)
        self.assertEqual(result.source, SOURCE_LABEL)
        self.assertIsNotNone(result.generated_at)


class TestGrounding(unittest.TestCase):
    def test_output_only_source_backed_values(self):
        conn = _conn(
            summaries=[
                summary_row(1, attendance_percentage=70.0),
                summary_row(2, attendance_percentage=80.0),
            ],
            subjects=[
                attendance_subject_row(
                    total_classes=20, attended_classes=15, attendance_status="Average"
                ),
            ],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertEqual(result.overall_attendance, 75.0)  # mean of 75.0
        self.assertEqual(
            result.subject_attendance[0].attendance_percentage, 75.0
        )  # 15/20 derived from verified classes
        self.assertEqual(result.subject_attendance[0].attendance_status, "Average")

    def test_no_invented_threshold_or_status(self):
        conn = _conn(
            summaries=[summary_row(6)],
            subjects=[attendance_subject_row()],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        for subject in result.subject_attendance:
            if subject.attendance_status is not None:
                self.assertIn(
                    subject.attendance_status,
                    ("Critical", "Low", "Average", "Good", "Excellent"),
                )
            if subject.eligibility_status is not None:
                self.assertIn(
                    subject.eligibility_status, ("Eligible", "Not Eligible")
                )
            if subject.shortage_flag is not None:
                self.assertIn(subject.shortage_flag, ("Yes", "No"))
        for token in ("danger", "safe", "critical!", "emergency"):
            self.assertNotIn(token, " ".join(result.signals.attention_areas).lower())

    def test_no_fake_confidence(self):
        conn = _conn(
            summaries=[summary_row(6)],
            subjects=[attendance_subject_row()],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertNotIn("confidence", result.model_dump())

    def test_no_fabricated_recommendations(self):
        conn = _conn(
            summaries=[
                summary_row(1, attendance_percentage=70.0),
                summary_row(2, attendance_percentage=80.0),
            ],
            subjects=[
                attendance_subject_row(
                    subject_code="CSE101",
                    total_classes=20,
                    attended_classes=12,
                    attendance_percentage=60.0,
                    attendance_status="Low",
                    eligibility_status="Not Eligible",
                    shortage_flag="Yes",
                ),
                attendance_subject_row(
                    subject_id="SUB002",
                    subject_code="CSE102",
                    subject_name="Data Structures",
                    total_classes=30,
                    attended_classes=28,
                    attendance_percentage=93.0,
                    attendance_status="Excellent",
                    eligibility_status="Eligible",
                    shortage_flag="No",
                ),
            ],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        all_signals = result.signals.strong_areas + result.signals.attention_areas
        self.assertGreater(len(all_signals), 0)
        for signal in all_signals:
            for token in ("should", "recommend", "suggest", "advice", "try "):
                self.assertNotIn(token, signal.lower())

    def test_signals_traceable_to_data(self):
        conn = _conn(
            summaries=[
                summary_row(1, attendance_percentage=70.0),
                summary_row(2, attendance_percentage=80.0),
            ],
            subjects=[
                attendance_subject_row(
                    subject_code="CSE101",
                    total_classes=20,
                    attended_classes=12,
                    attendance_percentage=60.0,
                    attendance_status="Low",
                    eligibility_status="Not Eligible",
                    shortage_flag="Yes",
                ),
                attendance_subject_row(
                    subject_id="SUB002",
                    subject_code="CSE102",
                    subject_name="Data Structures",
                    total_classes=30,
                    attended_classes=28,
                    attendance_percentage=93.0,
                    attendance_status="Excellent",
                    eligibility_status="Eligible",
                    shortage_flag="No",
                ),
            ],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        strong = " ".join(result.signals.strong_areas)
        attention = " ".join(result.signals.attention_areas)
        self.assertIn("Attendance improving from semester 1 to 2", strong)
        self.assertIn("CSE102", strong)
        self.assertIn("Low attendance in CSE101: 60.0%", attention)
        self.assertIn("Not eligible for exams in CSE101: 60.0%", attention)

    def test_trend_uses_existing_rule(self):
        conn = _conn(
            summaries=[
                summary_row(1, attendance_percentage=90.0),
                summary_row(2, attendance_percentage=70.0),
            ],
            subjects=[attendance_subject_row()],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertTrue(result.trend.available)
        self.assertEqual(result.trend.direction, "down")
        self.assertEqual(result.trend.previous_semester, 1)
        self.assertEqual(result.trend.current_semester, 2)
        self.assertEqual(result.trend.previous_value, 90.0)
        self.assertEqual(result.trend.current_value, 70.0)
        self.assertEqual(result.trend.delta, -20.0)

    def test_insufficient_history_means_trend_unavailable(self):
        conn = _conn(
            summaries=[summary_row(6, attendance_percentage=80.0)],
            subjects=[attendance_subject_row()],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertFalse(result.trend.available)
        self.assertEqual(result.trend.direction, "insufficient")


class TestSecurityCapabilities(unittest.TestCase):
    def test_result_never_exposes_db_repo_or_session(self):
        conn = _conn(
            summaries=[summary_row(6)],
            subjects=[attendance_subject_row()],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        dumped = result.model_dump()
        for token in ("sql", "pool", "session", "repository", "conn", "cursor", "query"):
            self.assertNotIn(token, dumped)

    def test_tool_reuses_existing_service_through_normal_architecture(self):
        self.assertIsInstance(
            StudentAttendanceTool(FakePool(FakeConn()))._student_service,
            StudentService,
        )

    def test_registry_has_no_callable_or_import_path(self):
        tool = build_default_registry().get(TOOL_NAME)
        fields = set(ToolDefinition.model_fields)
        for token in ("callable", "import_path", "exec", "eval", "sql", "handler"):
            self.assertNotIn(token, fields)

    def test_result_feeds_g0_verified_context(self):
        conn = _conn(
            summaries=[summary_row(6)],
            subjects=[attendance_subject_row()],
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        verified = StudentAttendanceTool.to_verified_context(
            _service(conn), result
        )
        self.assertIsInstance(verified, VerifiedContext)
        self.assertEqual(verified.source, result.source)
        self.assertEqual(verified.data["student_id"], "STU-A")
        self.assertIsInstance(verified.data["semester_attendance"], list)
        self.assertIsInstance(verified.data["subject_attendance"], list)


if __name__ == "__main__":
    unittest.main()
