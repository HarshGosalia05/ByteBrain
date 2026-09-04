"""G2.3 Student Subject Analysis Tool tests.

Covers (from the G2.3 acceptance checklist):

RBAC:
  * authenticated student can access own subject data
  * student cannot access another student's subject data
  * client-supplied target_student_id cannot override authenticated identity
  * client role cannot override authenticated role (no role claim exists)
  * missing identity rejected
  * non-student roles cannot use the Student-only subject tool
  * G1 registry marks student_subject_analysis_tool implemented
  * other G1 placeholders remain unimplemented
  * intent still resolves through the existing IntentRouter

Data:
  * correct subject records / semester association / code-name mapping
  * canonical performance values preserved (marks, percentage, grade)
  * existing subject classification rule reused
  * no future/predicted or M1-M4 values
  * requested-subject filtering works (code + name)
  * unknown subject handled safely
  * no NaN/invalid values
  * repeated execution deterministic
  * summary aggregates + strongest/attention signals source-traceable

Grounding:
  * every numeric subject metric is source-backed
  * classifications come from the approved rule
  * no invented thresholds, confidence, or recommendations

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
from app.schemas.student_subject_analysis_tool import (
    StudentSubjectAnalysisResult,
    ToolSubjectRecord,
)
from app.schemas.tools import IntentRequest, ToolDefinition
from app.services.intent_router import IntentRouter
from app.services.student_analytics_rules import classify_subject
from app.services.student_service import StudentService
from app.services.student_subject_analysis_tool import (
    INTENT,
    SOURCE_LABEL,
    TOOL_NAME,
    StudentSubjectAnalysisTool,
)
from app.services.tool_registry import build_default_registry


class FakeConn:
    """Serves one row-set per fetch (here: subject performance rows)."""

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


def subject_row(semester, subject_id, subject_code, subject_name, **overrides):
    row = {
        "semester": semester,
        "subject_id": subject_id,
        "subject_code": subject_code,
        "subject_name": subject_name,
        "academic_year": "2025-26",
        "credits": 4,
        "internal_marks": 30.0,
        "mid_sem_marks": 25.0,
        "end_sem_marks": 27.0,
        "total_marks": 82.0,
        "percentage": 82.0,
        "grade": "A",
        "grade_point": 8.0,
        "result_status": "Pass",
        "attempt_number": 1,
        "performance_category": None,
        "attendance_percentage": 85.0,
    }
    row.update(overrides)
    return row


def _sample_subjects():
    return [
        subject_row(5, "SUB301", "CSE301", "DBMS", percentage=82.0),
        subject_row(5, "SUB302", "CSE302", "Operating Systems", percentage=65.0),
        subject_row(6, "SUB401", "CSE401", "AI", percentage=50.0),
        subject_row(6, "SUB402", "CSE402", "ML", percentage=40.0),
    ]


def _conn(rows, profile=None):
    return FakeConn(
        fetch_sets=[list(rows)],
        fetchrow_row=profile if profile is not None else profile_row(),
    )


def _service(conn):
    return StudentSubjectAnalysisTool(FakePool(conn))


class TestStudentSelfScope(unittest.TestCase):
    def test_authenticated_student_retrieves_own_subject_data(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertIsInstance(result, StudentSubjectAnalysisResult)
        self.assertTrue(result.data_available)
        self.assertEqual(result.student_id, "STU-A")

    def test_student_cannot_retrieve_another_student_subject_data(self):
        conn = _conn(_sample_subjects())
        with self.assertRaises(HTTPException) as ctx:
            run(_service(conn).execute(student_id="STU-A", target_student_id="STU-B"))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(conn.executed, [])  # no data access for the foreign id

    def test_client_student_id_cannot_override_identity(self):
        conn = _conn(_sample_subjects())
        with self.assertRaises(HTTPException) as ctx:
            run(_service(conn).execute(student_id="STU-A", target_student_id="STU-B"))
        self.assertEqual(ctx.exception.status_code, 403)
        for _kind, query, args in conn.executed:
            self.assertNotIn("STU-B", args)

    def test_client_role_cannot_override_authenticated_role(self):
        params = inspect.signature(StudentSubjectAnalysisTool.execute).parameters
        self.assertNotIn("role", params)
        self.assertNotIn("user_id", params)

    def test_missing_authenticated_identity_rejected(self):
        conn = _conn([])
        with self.assertRaises(HTTPException) as ctx:
            run(_service(conn).execute(student_id=""))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(conn.executed, [])

    def test_missing_student_profile_404(self):
        conn = FakeConn(fetch_sets=[[]], fetchrow_row=None)
        with self.assertRaises(HTTPException) as ctx:
            run(_service(conn).execute(student_id="STU-UNKNOWN"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_tool_takes_only_authenticated_identity(self):
        params = inspect.signature(StudentSubjectAnalysisTool.execute).parameters
        self.assertNotIn("role", params)
        self.assertNotIn("user_id", params)
        self.assertNotIn("enrollment_no", params)


class TestToolRegistration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = build_default_registry()

    def test_registry_marks_subject_analysis_implemented(self):
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

    def test_non_student_roles_cannot_use_student_subject_tool(self):
        self.assertFalse(self.registry.is_allowed(TOOL_NAME, "Faculty"))
        self.assertFalse(self.registry.is_allowed(TOOL_NAME, "Admin"))
        self.assertIsNone(self.registry.tool_for_intent(INTENT, "Faculty"))
        self.assertIsNone(self.registry.tool_for_intent(INTENT, "Admin"))

    def test_tool_contract_matches_registered_definition(self):
        self.assertEqual(TOOL_NAME, "student_subject_analysis_tool")
        self.assertEqual(INTENT, "subject_analysis")
        self.assertEqual(SOURCE_LABEL, "students/student_subject_performance")

    def test_intent_resolves_through_existing_router(self):
        router = IntentRouter(self.registry)
        decision = router.route(
            IntentRequest(
                role="Student",
                user_context_id="STU-A",
                message="What are my weak subjects?",
            )
        )
        self.assertEqual(decision.status, "ROUTED")
        self.assertEqual(decision.tool_name, TOOL_NAME)
        self.assertTrue(decision.is_implemented)
        self.assertEqual(decision.scope_requirements.scope, "own_student")
        self.assertEqual(decision.scope_requirements.target_student_id, "STU-A")

    def test_classifier_still_recognizes_subject_analysis_intent(self):
        kind, intent = IntentRouter.classify("show my strong and weak subjects", "Student")
        self.assertEqual(kind, "intent")
        self.assertEqual(intent, "subject_analysis")


class TestDataSemantics(unittest.TestCase):
    def test_correct_subject_records_returned(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertEqual(len(result.semester_subjects), 4)
        self.assertTrue(
            all(isinstance(s, ToolSubjectRecord) for s in result.semester_subjects)
        )

    def test_correct_semester_association(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        by_code = {s.subject_code: s for s in result.semester_subjects}
        self.assertEqual(by_code["CSE301"].semester, 5)
        self.assertEqual(by_code["CSE302"].semester, 5)
        self.assertEqual(by_code["CSE401"].semester, 6)
        self.assertEqual(by_code["CSE402"].semester, 6)

    def test_subject_code_name_mapping_correct(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        by_code = {s.subject_code: s for s in result.semester_subjects}
        self.assertEqual(by_code["CSE301"].subject_name, "DBMS")
        self.assertEqual(by_code["CSE302"].subject_name, "Operating Systems")
        self.assertEqual(by_code["CSE401"].subject_id, "SUB401")

    def test_canonical_performance_values_preserved(self):
        conn = _conn(
            [
                subject_row(
                    5,
                    "SUB301",
                    "CSE301",
                    "DBMS",
                    internal_marks=28.0,
                    mid_sem_marks=22.0,
                    end_sem_marks=30.0,
                    total_marks=80.0,
                    percentage=80.0,
                    grade="A",
                    grade_point=8.0,
                    result_status="Pass",
                    attempt_number=1,
                )
            ]
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        record = result.semester_subjects[0]
        self.assertEqual(record.internal_marks, 28.0)
        self.assertEqual(record.mid_sem_marks, 22.0)
        self.assertEqual(record.end_sem_marks, 30.0)
        self.assertEqual(record.total_marks, 80.0)
        self.assertEqual(record.percentage, 80.0)
        self.assertEqual(record.grade, "A")
        self.assertEqual(record.grade_point, 8.0)
        self.assertEqual(record.result_status, "Pass")
        self.assertEqual(record.attempt_number, 1)

    def test_classification_reuses_approved_rule(self):
        conn = _conn(
            [
                subject_row(1, "S1", "C100", "Alpha", percentage=88.0),
                subject_row(1, "S2", "C101", "Beta", percentage=72.0),
                subject_row(2, "S3", "C102", "Gamma", percentage=55.0),
                subject_row(2, "S4", "C103", "Delta", percentage=40.0),
                subject_row(3, "S5", "C104", "Epsilon", percentage=None),
            ]
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        by_code = {s.subject_code: s for s in result.semester_subjects}
        self.assertEqual(by_code["C100"].classification, classify_subject(88.0))
        self.assertEqual(by_code["C101"].classification, classify_subject(72.0))
        self.assertEqual(by_code["C102"].classification, classify_subject(55.0))
        self.assertEqual(by_code["C103"].classification, classify_subject(40.0))
        self.assertIsNone(by_code["C104"].classification)
        self.assertEqual(by_code["C100"].classification, "Strong")
        self.assertEqual(by_code["C101"].classification, "Good")
        self.assertEqual(by_code["C102"].classification, "Needs Attention")
        self.assertEqual(by_code["C103"].classification, "Critical")

    def test_semester_ordering(self):
        conn = _conn(
            [
                subject_row(6, "S6", "C600", "Zeta"),
                subject_row(1, "S1", "C100", "Alpha"),
                subject_row(5, "S5", "C500", "Epsilon"),
            ]
        )
        result = run(_service(conn).execute(student_id="STU-A"))
        semesters = [s.semester for s in result.semester_subjects]
        self.assertEqual(semesters, [1, 5, 6])

    def test_no_future_or_predicted_subject_values(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertEqual(max(s.semester for s in result.semester_subjects), 6)
        self.assertNotIn(7, [s.semester for s in result.semester_subjects])

    def test_no_m1_m2_m3_m4_values_in_output(self):
        conn = _conn(_sample_subjects())
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
                for token in ("predict", "predicted", "future risk", "m1", "m2", "m3", "m4"):
                    self.assertNotIn(token, lowered, f"{token} leaked at {path}")

        walk(dumped)

    def test_requested_subject_filter_by_code(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A", subject_filter="cse401"))
        self.assertTrue(result.requested_subject_found)
        self.assertEqual(result.requested_subject, "cse401")
        self.assertEqual([s.subject_code for s in result.semester_subjects], ["CSE401"])
        self.assertEqual(result.summary.total_subjects, 1)

    def test_requested_subject_filter_by_name(self):
        conn = _conn(_sample_subjects())
        result = run(
            _service(conn).execute(student_id="STU-A", subject_filter="Operating")
        )
        self.assertTrue(result.requested_subject_found)
        self.assertEqual(
            [s.subject_code for s in result.semester_subjects], ["CSE302"]
        )

    def test_unknown_subject_handled_safely(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A", subject_filter="PHY101"))
        self.assertTrue(result.data_available)
        self.assertFalse(result.requested_subject_found)
        self.assertEqual(result.semester_subjects, [])
        self.assertIsNone(result.summary)
        self.assertEqual(result.subject_signals.strong_areas, [])
        self.assertEqual(result.subject_signals.attention_areas, [])
        self.assertIn("not found", result.note.lower())

    def test_no_nan_or_invalid_numerics(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        for record in result.semester_subjects:
            for value in (
                record.internal_marks,
                record.mid_sem_marks,
                record.end_sem_marks,
                record.total_marks,
                record.percentage,
                record.attendance_percentage,
            ):
                if value is not None:
                    self.assertTrue(math.isfinite(float(value)))
        if result.summary.average_percentage is not None:
            self.assertTrue(math.isfinite(float(result.summary.average_percentage)))

    def test_missing_data_handled_safely(self):
        conn = _conn([])
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertFalse(result.data_available)
        self.assertEqual(result.note, "No verified subject performance data available.")
        self.assertEqual(result.semester_subjects, [])
        self.assertIsNone(result.summary)
        self.assertEqual(result.subject_signals.strong_areas, [])
        self.assertEqual(result.subject_signals.attention_areas, [])

    def test_numeric_output_deterministic(self):
        rows = _sample_subjects()
        first = run(_service(_conn(rows)).execute(student_id="STU-A"))
        second = run(_service(_conn(rows)).execute(student_id="STU-A"))
        self.assertEqual(
            first.model_dump(exclude={"generated_at"}),
            second.model_dump(exclude={"generated_at"}),
        )

    def test_repeated_execution_identical_output(self):
        conn = _conn(_sample_subjects())
        svc = _service(conn)
        first = run(svc.execute(student_id="STU-A"))
        conn.reset()
        second = run(svc.execute(student_id="STU-A"))
        self.assertEqual(
            first.model_dump(exclude={"generated_at"}),
            second.model_dump(exclude={"generated_at"}),
        )

    def test_summary_aggregates_correct(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        summary = result.summary
        self.assertEqual(summary.total_subjects, 4)
        self.assertEqual(summary.strong_subjects, 1)
        self.assertEqual(summary.good_subjects, 1)
        self.assertEqual(summary.needs_attention_subjects, 1)
        self.assertEqual(summary.critical_subjects, 1)
        self.assertEqual(summary.average_percentage, 59.25)
        self.assertEqual(summary.highest_percentage, 82.0)
        self.assertEqual(summary.highest_subject_code, "CSE301")
        self.assertEqual(summary.highest_subject_name, "DBMS")
        self.assertEqual(summary.lowest_percentage, 40.0)
        self.assertEqual(summary.lowest_subject_code, "CSE402")

    def test_strong_attention_signals_source_traceable(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        strong = " ".join(result.subject_signals.strong_areas)
        attention = " ".join(result.subject_signals.attention_areas)
        self.assertIn("Strong in CSE301 (semester 5): 82.00%", strong)
        self.assertIn("Good in CSE302 (semester 5): 65.00%", strong)
        self.assertIn("Highest subject: CSE301 (82.00%) in semester 5", strong)
        self.assertIn("Needs attention in CSE401 (semester 6): 50.00%", attention)
        self.assertIn("Critical in CSE402 (semester 6): 40.00%", attention)
        self.assertIn("Lowest subject: CSE402 (40.00%) in semester 6", attention)

    def test_source_metadata_correct(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertEqual(result.tool_name, TOOL_NAME)
        self.assertEqual(result.intent, INTENT)
        self.assertEqual(result.source, SOURCE_LABEL)
        self.assertIsNotNone(result.generated_at)


class TestGrounding(unittest.TestCase):
    def test_output_only_source_backed_values(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        by_code = {s.subject_code: s for s in result.semester_subjects}
        self.assertEqual(by_code["CSE301"].percentage, 82.0)
        self.assertEqual(by_code["CSE301"].internal_marks, 30.0)
        self.assertEqual(by_code["CSE402"].percentage, 40.0)

    def test_no_invented_classification_labels(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        for record in result.semester_subjects:
            if record.classification is not None:
                self.assertIn(
                    record.classification,
                    ("Strong", "Good", "Needs Attention", "Critical"),
                )

    def test_no_fake_confidence(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        self.assertNotIn("confidence", result.model_dump())

    def test_no_fabricated_recommendations(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        all_signals = (
            result.subject_signals.strong_areas
            + result.subject_signals.attention_areas
        )
        self.assertGreater(len(all_signals), 0)
        for signal in all_signals:
            for token in ("should", "recommend", "suggest", "advice", "try ",
                          "study 2 hours", "career", "become"):
                self.assertNotIn(token, signal.lower())

    def test_signals_traceable_to_data(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        attention = " ".join(result.subject_signals.attention_areas)
        self.assertIn("CSE401", attention)
        self.assertIn("50.00%", attention)
        self.assertIn("CSE402", attention)
        self.assertIn("40.00%", attention)


class TestSecurityCapabilities(unittest.TestCase):
    def test_result_never_exposes_db_repo_or_session(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        dumped = result.model_dump()
        for token in ("sql", "pool", "session", "repository", "conn", "cursor", "query"):
            self.assertNotIn(token, dumped)

    def test_tool_reuses_existing_service_through_normal_architecture(self):
        self.assertIsInstance(
            StudentSubjectAnalysisTool(FakePool(FakeConn()))._student_service,
            StudentService,
        )

    def test_registry_has_no_callable_or_import_path(self):
        tool = build_default_registry().get(TOOL_NAME)
        fields = set(ToolDefinition.model_fields)
        for token in ("callable", "import_path", "exec", "eval", "sql", "handler"):
            self.assertNotIn(token, fields)

    def test_result_feeds_g0_verified_context(self):
        conn = _conn(_sample_subjects())
        result = run(_service(conn).execute(student_id="STU-A"))
        verified = StudentSubjectAnalysisTool.to_verified_context(
            _service(conn), result
        )
        self.assertIsInstance(verified, VerifiedContext)
        self.assertEqual(verified.source, result.source)
        self.assertEqual(verified.data["student_id"], "STU-A")
        self.assertIsInstance(verified.data["semester_subjects"], list)


def _dl_records():
    """Both 'Deep Learning' and the distinct 'Deep Learning Laboratory' exist."""
    return [
        ToolSubjectRecord(
            semester=7, academic_year="2025-26", subject_id="A",
            subject_code="SUB-DL-701", subject_name="Deep Learning",
            credits=4, internal_marks=14.0, mid_sem_marks=40.0,
            end_sem_marks=None, total_marks=None, percentage=72.0,
            grade="B", grade_point=7.0, result_status="Pass",
            attempt_number=1, classification=None, attendance_percentage=85.0,
        ),
        ToolSubjectRecord(
            semester=7, academic_year="2025-26", subject_id="B",
            subject_code="SUB-DLL-702", subject_name="Deep Learning Laboratory",
            credits=2, internal_marks=20.0, mid_sem_marks=30.0,
            end_sem_marks=None, total_marks=None, percentage=60.0,
            grade="B", grade_point=6.0, result_status="Pass",
            attempt_number=1, classification=None, attendance_percentage=90.0,
        ),
    ]


class TestNoSilentSubjectSubstitution(unittest.TestCase):
    """A more specific subject name must never silently collapse into a prefix
    subject ('Deep Learning Laboratory' -> 'Deep Learning')."""

    def test_laboratory_query_matches_the_laboratory_subject(self):
        records = _dl_records()
        hit = StudentSubjectAnalysisTool.match_subject_query(
            "Deep Learning Laboratory marks", records
        )
        self.assertEqual(hit, "Deep Learning Laboratory")

    def test_laboratory_short_query_matches_laboratory(self):
        records = _dl_records()
        hit = StudentSubjectAnalysisTool.match_subject_query(
            "deep learning laboratory", records
        )
        self.assertEqual(hit, "Deep Learning Laboratory")

    def test_plain_deep_learning_still_matches_deep_learning(self):
        records = _dl_records()
        hit = StudentSubjectAnalysisTool.match_subject_query(
            "my Deep Learning mid sem marks", records
        )
        self.assertEqual(hit, "Deep Learning")

    def test_laboratory_filter_executes_laboratory_record_not_theory(self):
        # End-to-end: subject_filter from match feeds the resolve step; asking
        # for the Laboratory subject must select ONLY the Laboratory record.
        conn = _conn(
            [
                subject_row(7, "SUB-DL-701", "SUB-DL-701", "Deep Learning"),
                subject_row(7, "SUB-DLL-702", "SUB-DLL-702", "Deep Learning Laboratory"),
            ]
        )
        result = run(
            _service(conn).execute(
                student_id="STU-A",
                subject_filter="Deep Learning Laboratory",
            )
        )
        self.assertTrue(result.requested_subject_found)
        names = [r.subject_name for r in result.semester_subjects]
        self.assertIn("Deep Learning Laboratory", names)
        self.assertNotIn("Deep Learning", names)


if __name__ == "__main__":
    unittest.main()
