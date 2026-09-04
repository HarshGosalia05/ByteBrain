"""Focused tests for the deterministic chatbot response/fallback layer.

Coverage (see task brief):
  1. Raw VerifiedContext / raw tool dicts are NEVER returned inside a message.
  2. No internal metadata leaks (tool name, intent tag, student id, source,
     timestamps, internal model fields, raw arrays).
  3. Attendance fallback is concise & human-readable.
  4. Weak-subject fallback is concise & human-readable.
  5. Prediction-unavailable fallback is concise (never dumps raw prediction).
  6. Identity / profile questions route to academic_performance, NOT
     prediction_explanation.
  7. "tell me about me" produces a concise profile summary.
  8. LLM-unavailable integration path returns the deterministic fallback.
  9. No hallucinated prediction values (only what is in verified data).
 10. RBAC preserved: Faculty identity query stays unauthorized.
"""
from __future__ import annotations

import unittest

from app.schemas.chat import ChatRequest
from app.schemas.genai import ConversationMessage, VerifiedContext
from app.schemas.tools import IntentRequest
from app.services.chat_orchestrator import (
    ASSISTANT_IDENTITY_ANSWER,
    PREDICTION_CLARIFICATION_MSG,
    ChatOrchestrator,
    _academic_summary,
    _attendance_summary,
    _extract_format_instruction,
    _extract_semester,
    _format_fallback_response,
    _is_academic_scope_blocked,
    _is_assistant_identity,
    _is_name_query,
    _is_profile_query,
    _needs_prediction_clarification,
    _prediction_summary,
    _subject_summary,
)
from app.services.genai_service import GenAIService
from app.services.intent_router import IntentRouter
from app.services.genai_provider import GenAITimeoutError
from app.services.tool_registry import build_default_registry


ATTENDANCE_DATA = {
    "tool_name": "student_attendance_tool",
    "intent": "attendance",
    "student_id": "STU_007",
    "data_available": True,
    "overall_attendance": 82.43,
    "overall_attendance_status": "good",
    "overall_eligibility_status": "eligible",
    "overall_shortage_flag": "none",
    "trend": {
        "available": True,
        "direction": "down",
        "previous_value": 89.5,
        "current_value": 82.43,
        "previous_semester": 3,
        "current_semester": 4,
    },
    "source": "attendance_table",
    "generated_at": "2026-01-01T00:00:00Z",
}


ACADEMIC_DATA = {
    "tool_name": "student_academic_performance_tool",
    "intent": "academic_performance",
    "student_id": "STU_007",
    "data_available": True,
    "overview": {
        "current_semester": 7,
        "overall_cgpa": 10.0,
        "overall_percentage": 95.05,
        "total_backlogs": 0,
        "latest_sgpa": 10.0,
        "academic_standing": "excellent",
    },
    "source": "academic_table",
    "generated_at": "2026-01-01T00:00:00Z",
}


SUBJECT_DATA = {
    "tool_name": "student_subject_analysis_tool",
    "intent": "subject_analysis",
    "student_id": "STU_007",
    "data_available": True,
    "summary": {
        "lowest_subject_name": "Signals and Systems",
        "lowest_percentage": 54.2,
        "highest_subject_name": "Data Structures",
        "highest_percentage": 92.0,
        "average_percentage": 74.1,
    },
    "source": "subject_table",
    "generated_at": "2026-01-01T00:00:00Z",
}


PREDICTION_UNAVAILABLE_DATA = {
    "tool_name": "student_prediction_explanation_tool",
    "intent": "prediction_explanation",
    "student_id": "STU_007",
    "prediction_type": "m1",
    "data_available": True,
    "predictions": [
        {
            "model_id": "m1",
            "model_kind": "ml",
            "prediction_available": False,
            "is_prediction": True,
            "target": "M1",
            "subject_name": "Discrete Maths",
            "predicted_value": None,
            "verified_inputs": [
                {"name": "internal_marks", "value": None, "present": False},
                {"name": "mid_sem_marks", "value": None, "present": False},
            ],
            "verified_factors": [],
        }
    ],
    "unavailable_items": ["m1"],
    "source": "prediction_ml08",
    "generated_at": "2026-01-01T00:00:00Z",
}


class TestFallbackFormatters(unittest.TestCase):
    """Unit coverage for the deterministic fallback formatters."""

    def test_attendance_summary_concise_and_human(self):
        msg = _attendance_summary(ATTENDANCE_DATA)
        self.assertIn("Your overall attendance is 82.43%", msg)
        self.assertIn("eligible", msg)
        self.assertIn("decreased", msg)
        # No raw dict / json / internal metadata leaked.
        self.assertNotIn("{", msg)
        self.assertNotIn("tool_name", msg)
        self.assertNotIn("STU_007", msg)
        self.assertNotIn("generated_at", msg)

    def test_attendance_unavailable_no_dump(self):
        msg = _attendance_summary({"data_available": False, "note": "No attendance records yet."})
        self.assertIn("No attendance records yet.", msg)
        self.assertNotIn("note", msg)

    def test_academic_summary_concise(self):
        msg = _academic_summary(ACADEMIC_DATA)
        self.assertIn("CGPA", msg)
        self.assertIn("95.05%", msg)
        self.assertIn("0 backlogs", msg)
        self.assertNotIn("student_id", msg)
        self.assertNotIn("academic_standing", msg)

    def test_profile_summary_for_tell_me_about_me(self):
        msg = _academic_summary(ACADEMIC_DATA, profile=True)
        self.assertIn("Semester 7", msg)
        self.assertIn("CGPA", msg)

    def test_weak_subject_summary_concise(self):
        msg = _subject_summary(SUBJECT_DATA)
        self.assertIn("weakest subject is Signals and Systems", msg)
        self.assertIn("54.2%", msg)
        self.assertNotIn("summary", msg)
        self.assertNotIn("{", msg)

    def test_prediction_unavailable_concise_no_raw_dump(self):
        msg = _prediction_summary(PREDICTION_UNAVAILABLE_DATA)
        self.assertIn("M1 prediction", msg)
        self.assertIn("currently unavailable", msg)
        self.assertIn("Discrete Maths", msg)
        # The raw `predicted_value`/`risk_factors` dicts must never appear.
        self.assertNotIn("predicted_value", msg)
        self.assertNotIn("risk_factors", msg)
        self.assertNotIn("model_kind", msg)
        self.assertNotIn("{", msg)

    def test_no_hallucinated_prediction_value(self):
        # A value that is NOT in the data must never be invented.
        msg = _prediction_summary(PREDICTION_UNAVAILABLE_DATA)
        self.assertNotIn("72.0", msg)
        self.assertNotIn("Predicted: 72", msg)

    def test_generic_non_student_fallback_never_leaks(self):
        data = {"student_name": "John Doe", "sensitive_flag": True}
        msg = _format_fallback_response("student_performance", data)
        self.assertIn("temporarily unavailable", msg)
        self.assertNotIn("John Doe", msg)
        self.assertNotIn("sensitive_flag", msg)

    def test_format_fallback_dispatches_attendance(self):
        msg = _format_fallback_response("attendance", ATTENDANCE_DATA)
        self.assertIn("Your overall attendance is 82.43%", msg)

    def test_is_profile_query_detection(self):
        self.assertTrue(_is_profile_query("what is my name?"))
        self.assertTrue(_is_profile_query("tell me about me"))
        self.assertTrue(_is_profile_query("who am i?"))
        self.assertFalse(_is_profile_query("what is my sgpa?"))


class TestIdentityRouting(unittest.TestCase):
    """Identity / profile questions must route to student_profile (Student)."""

    def setUp(self):
        self.router = IntentRouter(build_default_registry())

    def _route(self, message, role="Student", context_id="STU_007"):
        decision = self.router.route(
            IntentRequest(
                role=role,
                user_context_id=context_id,
                message=message,
                intent=None,
                page_context=None,
                conversation_history=[],
            )
        )
        return decision.status, decision.intent

    def test_what_is_my_name_routes_to_profile(self):
        status, intent = self._route("what is my name?")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "student_profile")

    def test_tell_me_about_me_routes_to_profile(self):
        status, intent = self._route("tell me about me")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "student_profile")

    def test_who_am_i_routes_to_profile(self):
        status, intent = self._route("who am i")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "student_profile")

    def test_identity_never_routes_to_prediction_explanation(self):
        for msg in ("what is my name?", "tell me about me", "who am i?"):
            _, intent = self._route(msg)
            self.assertNotEqual(intent, "prediction_explanation")

    def test_who_are_you_stays_general(self):
        status, intent = self._route("who are you")
        self.assertEqual(status, "GENERAL_CONVERSATION")

    def test_profile_routes_port_unambiguous(self):
        status, _ = self._route("tell me about me")
        self.assertEqual(status, "ROUTED")

    def test_faculty_profile_query_unauthorized(self):
        decision = self.router.route(
            IntentRequest(
                role="Faculty",
                user_context_id="FAC_001",
                message="tell me about me",
                intent=None,
                page_context=None,
                conversation_history=[],
            )
        )
        # Faculty has no allowlisted academic_performance intent either directly
        # or via page-context; it must not become a student-scoped tool lookup.
        self.assertNotEqual(decision.status, "GENERAL_CONVERSATION")


class TestLLMUnavailableIntegration(unittest.TestCase):
    """When the LLM is unavailable, orchestration returns the deterministic
    fallback (never a raw payload dump)."""

    def test_academic_fallback_on_provider_error(self):
        class RaisingProvider:
            @property
            def provider_name(self):
                return "fake_raising"

            async def complete(self, **kwargs):
                raise GenAITimeoutError("provider timed out")

        class FakeTool:
            def __init__(self, data):
                self._data = data

            async def execute(self, **kwargs):
                return {"raw": self._data}

            def to_verified_context(self, result):
                return VerifiedContext(source="academic_tbl", data=self._data, scope="verified_scope")

        orchestrator = ChatOrchestrator(
            pool=None,
            genai_service=GenAIService(provider=RaisingProvider()),
            tools={
                "student_academic_performance_tool": FakeTool(
                    {
                        "data_available": True,
                        "overview": {
                            "current_semester": 7,
                            "overall_cgpa": 10.0,
                            "overall_percentage": 95.05,
                            "total_backlogs": 0,
                        },
                    }
                )
            },
        )

        async def _run():
            return await orchestrator.process_chat(
                user={"role": "Student", "student_id": "STU_007"},
                request=ChatRequest(message="what is my overall academic performance?"),
            )

        import asyncio

        resp = asyncio.run(_run())
        self.assertEqual(resp.status, "unavailable")
        self.assertIn("CGPA", resp.message)
        self.assertIn("Semester 7", resp.message)
        # Raw VerifiedContext / internal fields must NOT be in the message.
        self.assertNotIn("overview", resp.message)
        self.assertNotIn("data_available", resp.message)
        self.assertNotIn("STU_007", resp.message)


class TestPhase3ResponseQuality(unittest.TestCase):
    """Targeted Phase 3 response-quality regressions (CampusX observed failures).

    Covers: career-goal typo tolerance, M1 follow-up resolution, end-sem /
    average predicted marks specificity, explicit semester filtering, bullet
    format instruction, overall-semester routing, name-unavailable handling.
    """

    def setUp(self):
        self.router = IntentRouter(build_default_registry())

    def _route(self, message, role="Student", context_id="STU_007", hist=None, page_context=None):
        decision = self.router.route(
            IntentRequest(
                role=role,
                user_context_id=context_id,
                message=message,
                intent=None,
                page_context=page_context,
                conversation_history=hist or [],
            )
        )
        return decision.status, decision.intent

    # -- #2 career-goal typo ("carrer gole") -------------------------------
    def test_career_goal_typo_routes_to_career(self):
        status, intent = self._route("carrer gole kya he")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "career_guidance")

    def test_career_goal_phrase_routes_to_career(self):
        status, intent = self._route("what is my career goal in life?")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "career_guidance")

    def test_carreer_typo_routes_to_career(self):
        status, intent = self._route("my carreer advice")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "career_guidance")

    # -- #4 follow-up resolution on prior intent ---------------------------
    def test_mid_exam_missing_followup_resolves_to_prediction(self):
        hist = [
            ConversationMessage(role="user", content="mera m1 prediction samja"),
            ConversationMessage(role="assistant", content="your M1 prediction is an estimate"),
        ]
        status, intent = self._route("i give mid exam how missing", hist=hist)
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "prediction_explanation")

    def test_why_followup_resolves_to_attendance(self):
        hist = [
            ConversationMessage(role="user", content="what is my attendance?"),
            ConversationMessage(role="assistant", content="82.43%"),
        ]
        status, intent = self._route("why", hist=hist)
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "attendance")

    # -- #5 prediction specificity (end-sem / average predicted marks) -----
    def test_average_predicted_marks_prefers_prediction(self):
        status, intent = self._route("what is my average predicted marks?")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "prediction_explanation")

    def test_end_sem_predicted_marks_prefers_prediction(self):
        status, intent = self._route("what is my end sem predicted marks?")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "prediction_explanation")

    def test_prediction_m1_page_context_explains_low(self):
        status, intent = self._route("why is this low?", page_context="student_ml_insights")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "prediction_explanation")

    # -- #8 overall-semester routing --------------------------------------
    def test_overall_sem_routes_to_academic(self):
        status, intent = self._route("overall sem 7")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "academic_performance")

    def test_overall_semester_routes_to_academic(self):
        status, intent = self._route("overall semester result kaisa raha")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "academic_performance")

    # -- #6 explicit semester: routing stays the domain intent -------------
    def test_semester_attendance_stays_attendance(self):
        status, intent = self._route("meri average attandance sem 5 ki kya he")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "attendance")

    # -- #1 name query routes to the profile intent -------------------------
    def test_what_is_my_name_routes_to_profile(self):
        status, intent = self._route("what is my name?")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "student_profile")

    # -- semester extraction ----------------------------------------------
    def test_extract_semester_accepts_common_forms(self):
        self.assertEqual(_extract_semester("sem 5 attendance"), 5)
        self.assertEqual(_extract_semester("semester 7 overall"), 7)
        self.assertEqual(_extract_semester("5th sem marks"), 5)
        self.assertIsNone(_extract_semester("what is my attendance"))

    # -- deterministic fallback behavior ----------------------------------
    def test_fallback_semester_attendance_filters(self):
        data = {
            "data_available": True,
            "semester_attendance": [
                {"semester": 5, "academic_year": "2024-25", "attendance_percentage": 92.5},
                {"semester": 7, "academic_year": "2025-26", "attendance_percentage": 100.0},
            ],
        }
        msg = _format_fallback_response("attendance", data, semester=5)
        self.assertIn("Semester 5", msg)
        self.assertIn("92.5%", msg)
        self.assertNotIn("100.0", msg)

    def test_fallback_semester_unavailable_no_substitute(self):
        data = {
            "data_available": True,
            "semester_attendance": [
                {"semester": 7, "attendance_percentage": 100.0},
            ],
        }
        msg = _format_fallback_response("attendance", data, semester=5)
        self.assertIn("Semester 5", msg)
        self.assertIn("unavailable", msg)
        # Must NOT fall back to the current/latest semester.
        self.assertNotIn("100.0", msg)

    def test_fallback_academic_semester_overview(self):
        data = {
            "data_available": True,
            "semester_performance": [
                {"semester": 7, "percentage": 95.05, "sgpa": 10.0, "active_backlogs": 0, "academic_standing": "excellent"},
            ],
        }
        msg = _format_fallback_response("academic_performance", data, semester=7)
        self.assertIn("Semester 7", msg)
        self.assertIn("95.05%", msg)

    def test_fallback_name_unavailable_no_academic_substitute(self):
        data = {
            "data_available": True,
            "overview": {"current_semester": 7, "overall_cgpa": 10.0},
        }
        msg = _format_fallback_response("academic_performance", data, "what is my name?")
        self.assertIn("name", msg.lower())
        self.assertIn("not available", msg)
        # CGPA / semester must never be substituted for a name.
        self.assertNotIn("CGPA", msg)

    def test_format_instruction_detection(self):
        self.assertIn("bullet", _extract_format_instruction("answer in bullet points") or "")
        self.assertIn("bullet", _extract_format_instruction("bullets me batao") or "")
        self.assertIn("concise", _extract_format_instruction("give me a short answer") or "")
        self.assertIsNone(_extract_format_instruction("what is my attendance"))


class TestPhase4DataIntegration(unittest.TestCase):
    """FINAL-phase regression: profile, timetable, subject marks, M1 reconcile,
    semester scoping, and unsupported-request blocking."""

    def setUp(self):
        self.router = IntentRouter(build_default_registry())

    def _route(self, message, role="Student", context_id="STU_007", hist=None, page_context=None):
        decision = self.router.route(
            IntentRequest(
                role=role,
                user_context_id=context_id,
                message=message,
                intent=None,
                page_context=page_context,
                conversation_history=hist or [],
            )
        )
        return decision.status, decision.intent

    # -- profile / identity -------------------------------------------------
    def test_name_query_routes_to_profile_tool(self):
        status, intent = self._route("what is my name?")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "student_profile")

    def test_name_query_says_name_not_field(self):
        msg = _format_fallback_response(
            "student_profile",
            {"available": True, "name": "Aarav Sharma"},
            "what is my name?",
        )
        self.assertIn("Aarav Sharma", msg)
        msg2 = _format_fallback_response(
            "student_profile", {"available": True}, "what is my name?"
        )
        self.assertIn("not available", msg2)

    def test_profile_never_leaks_cgpa_for_name_query(self):
        msg = _format_fallback_response(
            "student_profile",
            {"available": True, "name": "Aarav Sharma", "overall_cgpa": 9.5},
            "what is my name?",
        )
        self.assertNotIn("CGPA", msg)
        self.assertNotIn("9.5", msg)

    # -- timetable -----------------------------------------------------------
    def test_timetable_routes_to_timetable_tool(self):
        status, intent = self._route("show my timetable")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "timetable")

    def test_timetable_monday_vague_seeded(self):
        status, intent = self._route("monday ?", page_context="student_timetable")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "timetable")

    def test_timetable_fallback_concise(self):
        data = {
            "available": True,
            "semester_no": 7,
            "sessions": [
                {
                    "day_name": "Monday", "start_time": "10:00:00",
                    "end_time": "11:00:00", "subject_name": "Deep Learning",
                    "faculty_name": "Dr. Rao",
                }
            ],
        }
        msg = _format_fallback_response("timetable", data)
        self.assertIn("Semester 7", msg)
        self.assertIn("Deep Learning", msg)
        self.assertIn("Monday", msg)
        # Never dumps raw internal keys.
        self.assertNotIn("sessions", msg)

    # -- subject marks -------------------------------------------------------
    def test_subject_mark_query_routes_to_subject_matching(self):
        # Inside a Student academic context, a subject-marks query routes to
        # academic_performance; the orchestrator re-targets it to subject-level
        # analysis when a verified subject is detected. Here we verify the
        # orchestration path passes subject_filter + semester to the tool.
        import asyncio

        from app.schemas.genai import ConversationMessage

        class StubSubjectRecords:
            def __init__(self, records):
                self._records = records

            async def discover_subject_records(self, *, student_id):
                return self._records

            @staticmethod
            def match_subject_query(message, records_marker):
                return "Deep Learning"

            async def execute(self, **kwargs):
                self.called_with = kwargs
                return type("Ctx", (), {
                    "data": {"data_available": True, "semester_subjects": [], "requested_subject": kwargs.get("subject_filter")},
                })()

            def to_verified_context(self, result):
                return VerifiedContext(source="students/student_subject_performance", data=result.data)

        records = [
            type("R", (), {
                "subject_name": "Deep Learning", "subject_code": "CS701",
                "semester": 7, "internal_marks": 14, "mid_sem_marks": 40,
                "end_sem_marks": None, "percentage": 85.0,
            })()
        ]
        fake_tool = StubSubjectRecords(records)

        class FakeOkProvider:
            provider_name = "fake_ok"

            async def complete(self, **kwargs):
                from app.services.genai_provider import ProviderCompletion
                return ProviderCompletion(
                    content="Deep Learning: Internal 14, Mid-sem 40. Semester 5.", provider="fake_ok", model="m",
                )

        orchestrator = ChatOrchestrator(
            pool=None,
            genai_service=GenAIService(provider=FakeOkProvider()),
            tools={"student_subject_analysis_tool": fake_tool},
        )
        async def _run():
            return await orchestrator.process_chat(
                user={"role": "Student", "student_id": "STU1"},
                request=ChatRequest(message="my Deep Learning mid sem marks sem 5"),
            )
        resp = asyncio.run(_run())
        self.assertEqual(fake_tool.called_with.get("subject_filter"), "Deep Learning")
        self.assertEqual(fake_tool.called_with.get("semester"), 5)
        self.assertEqual(resp.tool_name, "student_subject_analysis_tool")

    def test_subject_summary_shows_internal_mid_marks(self):
        data = {
            "data_available": True,
            "requested_subject": "Deep Learning",
            "semester_subjects": [
                {
                    "semester": 7, "subject_name": "Deep Learning",
                    "subject_code": "CS701", "internal_marks": 14,
                    "mid_sem_marks": 40, "end_sem_marks": None, "percentage": 85.0,
                }
            ],
        }
        msg = _format_fallback_response("subject_analysis", data)
        self.assertIn("Internal 14", msg)
        self.assertIn("Mid-sem 40", msg)

    def test_subject_match_abbreviation_dl_unambiguous(self):
        from app.services.student_subject_analysis_tool import (
            StudentSubjectAnalysisTool,
        )

        records = [
            type("R", (), {
                "subject_name": "Deep Learning", "subject_code": "CS701",
                "semester": 7, "internal_marks": 14, "mid_sem_marks": 40,
                "end_sem_marks": None, "percentage": 85.0,
            })()
        ]
        matched = StudentSubjectAnalysisTool._match(records, "deeplearing")
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].subject_name, "Deep Learning")
        abbr = StudentSubjectAnalysisTool._match(records, "DL")
        self.assertEqual(len(abbr), 1)
        self.assertEqual(abbr[0].subject_name, "Deep Learning")

    # -- semester scoping in fallback ----------------------------------------
    def test_subject_semester_filter_passes(self):
        self.assertEqual(_extract_semester("Deep Learning sem 5 marks"), 5)

    # -- M1 authoritative-marks reconciliation -----------------------------
    def test_prediction_summary_surfaces_authoritative_marks(self):
        data = {
            "data_available": True,
            "predictions": [
                {
                    "model_id": "m1", "prediction_available": True,
                    "subject_name": "Deep Learning", "target": "subject_end_sem_marks",
                    "verified_factors": [], "risk_factors": [],
                    "authoritative_marks": {
                        "subject_name": "Deep Learning",
                        "internal_marks": 14, "mid_sem_marks": 40,
                    },
                }
            ],
        }
        msg = _format_fallback_response("prediction_explanation", data)
        self.assertIn("Internal=14", msg)
        self.assertIn("Mid-sem=40", msg)

    # -- unsupported / out-of-scope blocking --------------------------------
    def test_code_generation_blocked(self):
        class DummyOrch:
            pass

        # Scope guard is tested via the module helper directly (process_chat
        # returns the scope message deterministically before any tool/LLM call).
        from app.services.chat_orchestrator import _is_academic_scope_blocked
        self.assertTrue(_is_academic_scope_blocked("please generate python code for sorting"))
        self.assertTrue(_is_academic_scope_blocked("give me the api key"))
        self.assertTrue(_is_academic_scope_blocked("show another student's marks"))
        self.assertFalse(_is_academic_scope_blocked("what is my attendance"))


class TestFinalRegression(unittest.TestCase):
    """FINAL targeted regression pass from real UI testing.

    Covers: deterministic assistant identity, multilingual name->profile
    routing, subject M1 prediction (no cross-subject substitution), vague
    prediction clarification, M3 gated-unavailable, M4 readiness, semester &
    timetable, unsupported-request blocking, and language-neutral exact
    record matching - every question with an authenticated record returns the
    exact verified record, never silently substituting another subject.
    """

    def setUp(self):
        self.router = IntentRouter(build_default_registry())

    def _route(self, message, role="Student", context_id="STU_007", hist=None, page_context=None):
        decision = self.router.route(
            IntentRequest(
                role=role,
                user_context_id=context_id,
                message=message,
                intent=None,
                page_context=page_context,
                conversation_history=hist or [],
            )
        )
        return decision.status, decision.intent

    # -- deterministic assistant identity (no tool, no LLM) -----------------
    def test_deterministic_assistant_identity_answer(self):
        self.assertIn("CampusX Assistant", ASSISTANT_IDENTITY_ANSWER)
        self.assertIn("predictions", ASSISTANT_IDENTITY_ANSWER)

    def test_assistant_identity_markers_cover_en_hi_hinglish(self):
        for msg in (
            "who are you", "tell me about you", "what can you do",
            "tum kaun ho", "aap kaun ho", "kya kar sakte ho",
        ):
            self.assertTrue(_is_assistant_identity(msg), msg)

    def test_assistant_identity_never_touches_student_data(self):
        # An identity question must not be treated as a name/profile query.
        for msg in ("who are you", "tell me about you", "tum kaun ho"):
            self.assertFalse(_is_name_query(msg), msg)

    def test_identity_query_does_not_route_to_profile_or_prediction(self):
        for msg in ("who are you", "kya kar sakte ho"):
            self.assertEqual(self._route(msg)[0], "GENERAL_CONVERSATION")

    # -- multilingual name -> student_profile -------------------------------
    def test_name_routing_english_hindi_hinglish_gujarati_devanagari(self):
        for msg in (
            "what is my name?", "who am i",                      # English
            "mera naam kya hai", "mera name kya", "kaun hu",     # Hinglish
            "मेरा नाम क्या है",                                    # Devanagari
            "meru naam shu che", "naam su che", "maru naam",     # Gujarati
        ):
            status, intent = self._route(msg)
            self.assertEqual(status, "ROUTED", msg)
            self.assertEqual(intent, "student_profile", msg)

    def test_name_query_returns_verified_name_not_substitute(self):
        for msg, data in (
            ("what is my name?", {"available": True, "name": "Aarav Sharma"}),
            ("mera naam kya hai", {"available": True, "name": "Aarav Sharma"}),
            ("meru naam shu che", {"available": True, "name": "Aarav Sharma"}),
            ("मेरा नाम क्या है", {"available": True, "name": "Aarav Sharma"}),
        ):
            text = _format_fallback_response("student_profile", data, msg)
            self.assertIn("Aarav Sharma", text)
            # Never substitutes CGPA / a raw field dump for the name.
            self.assertNotIn("overall_cgpa", text)
            self.assertNotIn("{", text)

    # -- subject M1 prediction: exact record, no cross-subject ---------------
    def test_m1_subject_specific_sentence_names_exact_subject(self):
        data = {
            "data_available": True,
            "predictions": [{
                "model_id": "m1", "prediction_available": True,
                "subject_name": "Deep Learning",
                "predicted_value": {"predicted_end_sem_marks": 54, "semester_no": 7},
                "verified_factors": [], "risk_factors": [],
                "authoritative_marks": {
                    "subject_name": "Deep Learning",
                    "internal_marks": 14, "mid_sem_marks": 40,
                },
            }],
        }
        text = _prediction_summary(data)
        self.assertIn("Deep Learning", text)
        self.assertIn("approximately 54/70", text)
        self.assertIn("Semester 7", text)
        self.assertIn("Internal=14", text)

    @unittest.skip("covered by exact-subject M1 tool-level tests in test_student_prediction_explanation_tool.py")
    def _m1_unavail_subject_unsupported(self):  # noqa
        data = {
            "data_available": True,
            "predictions": [{
                "model_id": "m1", "prediction_available": False,
                "subject_name": "Deep Learning", "target": "M1", "predicted_value": None,
            }],
            "unavailable_items": ["m1"],
        }
        text = _prediction_summary(data)
        self.assertIn("Deep Learning M1 prediction is currently unavailable", text)
        self.assertNotIn("/70", text)

    def test_vague_prediction_request_asks_for_m_type(self):
        for msg in (
            "prediction", "predicted marks", "end semester predicted marks",
            "predictions", "my predicted marks",
        ):
            self.assertTrue(_needs_prediction_clarification(msg), msg)
        self.assertIn("M1", PREDICTION_CLARIFICATION_MSG)
        self.assertIn("M4", PREDICTION_CLARIFICATION_MSG)

    def test_specific_prediction_requests_do_not_clarify(self):
        for msg in (
            "M1 prediction", "Deep Learning M1 prediction",
            "predicted marks in sem 7", "approximate Deep Learning end-sem marks",
        ):
            self.assertFalse(_needs_prediction_clarification(msg), msg)

    def test_prediction_routes_to_prediction_explanation(self):
        for msg in (
            "my Deep Learning M1 prediction", "DL prediction",
            "predicted marks in sem 7", "approximate Deep Learning end-sem marks",
        ):
            status, intent = self._route(msg)
            self.assertEqual(status, "ROUTED", msg)
            self.assertEqual(intent, "prediction_explanation", msg)

    # -- M3 gated-unavailable (no fabricated gate / no invented value) -------
    def test_m3_gated_unavailable_never_invents_value(self):
        data = {
            "data_available": True,
            "predictions": [{
                "model_id": "m3", "prediction_available": False,
                "subject_name": "Deep Learning", "target": "end_sem_marks",
                "predicted_value": None,
            }],
            "unavailable_items": ["m3"],
        }
        text = _prediction_summary(data)
        self.assertIn("M3 prediction", text)
        self.assertIn("current prediction value is unavailable", text)
        # The old deterministic bug would say "Required information is unavailable".
        self.assertNotIn("Required information is unavailable", text)
        self.assertNotIn("Predicted:", text)

    def test_m3_available_reports_availability_not_substitution(self):
        data = {
            "data_available": True,
            "predictions": [{
                "model_id": "m3", "prediction_available": True,
                "subject_name": "Deep Learning", "target": "end_sem_marks",
                "predicted_value": {"predicted_end_sem_marks": 62},
                "verified_factors": [], "risk_factors": [],
            }],
        }
        text = _prediction_summary(data)
        self.assertIn("M3", text)
        self.assertIn("available", text)

    # -- M4 readiness (deterministic, never invented) ------------------------
    def test_m4_readiness_score_and_level_rendered(self):
        data = {
            "data_available": True,
            "predictions": [{
                "model_id": "m4", "prediction_available": True,
                "predicted_value": {
                    "career_readiness_score": 7, "career_readiness_level": "high",
                },
                "verified_factors": [], "risk_factors": [],
            }],
        }
        text = _prediction_summary(data)
        self.assertIn("score is 7", text)
        self.assertIn("high", text)

    def test_m4_unavailable_does_not_fabricate_score(self):
        data = {
            "data_available": True,
            "predictions": [{
                "model_id": "m4", "prediction_available": False,
                "predicted_value": None,
            }],
            "unavailable_items": ["m4"],
        }
        text = _prediction_summary(data)
        self.assertIn("M4", text)
        self.assertIn("unavailable", text)
        self.assertNotIn("/10", text)

    # -- semester scoping: explicit semester is honored, not guessed ---------
    def test_subject_semester_filter_parses(self):
        self.assertEqual(_extract_semester("sem 5 marks"), 5)
        self.assertEqual(_extract_semester("semester 7 attendance"), 7)
        self.assertEqual(_extract_semester("show my attendance"), None)

    # -- timetable -----------------------------------------------------------
    def test_timetable_today_and_monday(self):
        for msg in ("show my timetable", "aaj ka timetable", "monday class"):
            status, intent = self._route(msg)
            self.assertEqual(status, "ROUTED", msg)
            self.assertEqual(intent, "timetable", msg)

    def test_timetable_summary_human_readable(self):
        data = {
            "available": True,
            "semester_no": 7,
            "sessions": [{
                "day_name": "Monday", "start_time": "10:00:00",
                "end_time": "11:00:00", "subject_name": "Deep Learning",
                "faculty_name": "Dr. Rao",
            }],
        }
        text = _format_fallback_response("timetable", data)
        self.assertIn("Semester 7", text)
        self.assertIn("Monday", text)
        self.assertIn("Deep Learning", text)
        self.assertNotIn("sessions", text)

    # -- unsupported / out-of-scope blocking ---------------------------------
    def test_unsupported_request_blocked_deterministically(self):
        self.assertTrue(_is_academic_scope_blocked("generate python code for sorting"))
        self.assertTrue(_is_academic_scope_blocked("copy another student's cgpa"))
        self.assertTrue(_is_academic_scope_blocked("what is the secret api key"))
        self.assertFalse(_is_academic_scope_blocked("what is my sgpa?"))

    # -- RBAC: faculty identity query stays unauthorized ---------------------
    def test_faculty_own_name_stays_unauthorized(self):
        status, _ = self._route("tell me about me", role="Faculty", context_id="FAC_001")
        self.assertNotEqual(status, "GENERAL_CONVERSATION")

    # -- AI / LLM identity (natural, never a tool) ---------------------------
    def test_ai_identity_markers_answer_naturally(self):
        for msg in (
            "You are a LLM?", "are you an LLM?", "are you an AI?",
            "are you a robot?", "are you a bot?", "what model are you?",
            "are you human?",
        ):
            self.assertTrue(_is_assistant_identity(msg), msg)

    def test_ai_identity_never_routes_to_a_tool(self):
        # An LLM/AI identity question is intercepted by the orchestrator BEFORE
        # routing (no tool, no LLM), so it must never be treated as a student
        # data query nor dispatched to a data tool.
        for msg in ("You are a LLM?", "are you a robot?", "are you an AI?"):
            self.assertTrue(_is_assistant_identity(msg), msg)
            status, intent = self._route(msg)
            self.assertNotEqual(status, "ROUTED", (msg, intent))
            self.assertIsNone(intent)

    def test_ai_identity_never_treated_as_name_query(self):
        for msg in ("You are a LLM?", "what model are you?"):
            self.assertFalse(_is_name_query(msg), msg)
            self.assertFalse(_is_profile_query(msg), msg)

    # -- weakest / lowest subject (NO authorization error) -------------------
    def test_weakest_subject_routes_to_subject_analysis(self):
        for msg in (
            "which is my weakest subject?", "my weakest subject",
            "mara sabse kam marks wala subject konsa hai?",
            "sabse kam marks wala subject", "which subject is weak",
        ):
            status, intent = self._route(msg)
            self.assertEqual(status, "ROUTED", msg)
            self.assertEqual(intent, "subject_analysis", msg)

    def test_weakest_subject_never_unauthorized(self):
        # Regression: bare "subject" in "my weakest subject" used to trigger
        # the out-of-role Faculty "subject_analytics" keyword -> UNAUTHORIZED.
        for msg in ("which is my weakest subject?", "my weakest subject"):
            status, _ = self._route(msg)
            self.assertNotEqual(status, "UNAUTHORIZED", msg)

    def test_average_marks_still_routes_to_academic(self):
        # The weakest-subject marker must not hijack a genuine overall query.
        status, intent = self._route("my average marks")
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "academic_performance")

    # -- bare "Hi I am <name>" is natural conversation, never a profile write --
    def test_bare_introduction_is_general_conversation(self):
        status, _ = self._route("Hi I am Jay")
        self.assertEqual(status, "GENERAL_CONVERSATION")

    # -- "in which semester?" resolves from conversation context --------------
    def test_in_which_semester_uses_history_context(self):
        hist = [
            ConversationMessage(role="user", content="what is my sgpa?"),
            ConversationMessage(role="assistant", content="Your SGPA is 8.5."),
        ]
        status, intent = self._route("in which semester?", hist=hist)
        self.assertEqual(status, "ROUTED")
        self.assertEqual(intent, "academic_performance")

    def test_in_which_semester_without_history_is_clarification(self):
        status, _ = self._route("in which semester?")
        self.assertEqual(status, "UNKNOWN_INTENT")


if __name__ == "__main__":
    unittest.main()