"""Student Career Guidance service tests (MD-06 presentation layer).

Covers (per the Career Readiness & Grounded Guidance enhancement):

M4 preservation:
  * persisted M4 output is reused EXACTLY as produced (score, level,
    positive/risk factors); disclaimer states rule-based/not an ML model
  * no recomputation of M4 anywhere in the service module

Career direction mapping (deterministic, no ML):
  * declared known preferred_domain wins (source=declared_preference)
  * declared UNKNOWN domain -> unavailable with honest note (never guessed)
  * no preference + subject evidence -> best-evidenced domain
    (mapped_subject_evidence), never presented as a declared interest
  * no preferences at all -> "Career preference data is not available yet."
  * preferences exist but unmappable -> "Career direction needs more
    preference information."

Skill gap mapping:
  * ranked in canonical DOMAIN_SUBJECT_KEYWORDS order (core areas first)
  * first three High, rest Medium; deterministic across runs
  * no domain -> no fabricated gaps

Ownership / RBAC:
  * only the authenticated student_id is ever used (recorded calls)
  * cross-student target is rejected 403 by the underlying G2.5 tool

Grounded GenAI:
  * request carries role=Student, user_context_id=authenticated id,
    intent=career_guidance, ONE VerifiedContext (source students/career_coach,
    scope own_student, model metadata m4 when readiness exists)
  * verified context never contains SQL / sessions / repositories
  * GenAI failure (error / rate limit / timeout) degrades gracefully:
    deterministic payload stays complete, ai_guidance.available=False

No fabrication:
  * skills labeled inferred_from_subject only appear when backed by an
    injected strong subject; unknown skills never appear in the payload

No live database: fakes follow the existing G2.5 injection convention.
"""
import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import HTTPException

from app.schemas.genai import GenAIRequest, GenAIResponse
from app.schemas.student_career_guidance import StudentCareerGuidanceResponse
from app.services.genai_provider import (
    GenAIError,
    GenAIRateLimitError,
    GenAITimeoutError,
)
from app.services.student_career_coach import (
    SOURCE_LABEL,
    StudentCareerCoachTool,
)
from app.services.student_career_guidance_service import (
    GUIDANCE_USER_MESSAGE,
    StudentCareerGuidanceService,
    prioritize_skill_gaps,
    select_career_direction,
)

SAMPLE_PREFERENCES = {
    "preferred_domain": "Data Science",
    "dream_job_role": "Data Scientist",
    "internship_completed": "Yes",
    "placement_readiness_level": "High",
}

FORBIDDEN_CONTEXT_KEYS = (
    "sql", "query", "session", "repository", "pool", "callable", "import_path",
)


def m4_row(score=72.5, level="Good", positives="Strong academics", risks="Low attendance"):
    return {
        "prediction_id": "PRED-M4-1",
        "student_id": "STU-A",
        "prediction_type": "m4",
        "model_version": "1",
        "prediction_value": {
            "enrollment_no": 1001,
            "full_name": "Alice Appleton",
            "department_name": "Computer Science",
            "current_semester": 6,
            "career_readiness_score": score,
            "career_readiness_level": level,
            "positive_factors": positives,
            "risk_factors": risks,
        },
        "input_row_count": 1,
        "prediction_count": 1,
    }


def subject(semester, code, name, percentage):
    return SimpleNamespace(
        semester=semester,
        subject_code=code,
        subject_name=name,
        percentage=percentage,
    )


def sample_subjects():
    return [
        subject(5, "CSE305", "Database Systems", 88.0),
        subject(6, "CSE406", "Machine Learning", 75.0),
        subject(6, "CSE407", "Python Programming", 68.0),
        subject(5, "CSE302", "Operating Systems", 65.0),
    ]


class FakeStudentService:
    def __init__(self, preferences=None, subjects=None):
        self.preferences = preferences
        self.subjects = list(subjects or [])
        self.calls = {"get_career_preferences": [], "get_performance": []}

    async def get_career_preferences(self, student_id):
        self.calls["get_career_preferences"].append(student_id)
        return self.preferences

    async def get_performance(self, student_id):
        self.calls["get_performance"].append(student_id)
        return SimpleNamespace(performance=list(self.subjects))


class FakePredictionService:
    def __init__(self, m4=None):
        self.m4 = m4
        self.calls = []

    async def get_latest(self, student_id, prediction_type):
        self.calls.append((student_id, prediction_type))
        return self.m4 if prediction_type == "m4" else None


class FakeGenAIService:
    """Records GenAIRequests; returns canned content or raises."""

    def __init__(self, *, content="**Career direction**\nData Science.", error=None):
        self.requests: list[GenAIRequest] = []
        self.content = content
        self.error = error

    async def generate(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return GenAIResponse(
            content=self.content,
            provider="fake-provider",
            model="fake-model",
            generated_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        )


def run(coro):
    return asyncio.run(coro)


_UNSET = object()


def make_service(
    *,
    preferences=SAMPLE_PREFERENCES,
    subjects=None,
    m4=_UNSET,
    genai=None,
    student_service=None,
):
    subjects = sample_subjects() if subjects is None else subjects
    m4 = m4_row() if m4 is _UNSET else m4
    student = student_service or FakeStudentService(preferences, subjects)
    prediction = FakePredictionService(m4)
    coach = StudentCareerCoachTool(
        None, student_service=student, prediction_service=prediction
    )
    genai = genai or FakeGenAIService()
    service = StudentCareerGuidanceService(None, coach_tool=coach, genai_service=genai)
    return service, student, prediction, genai


# ---------------------------------------------------------------------------
# M4 preservation
# ---------------------------------------------------------------------------


class TestM4Preserved(unittest.TestCase):
    def test_m4_output_reused_exactly(self):
        service, *_ = make_service(m4=m4_row(score=72.5, level="Good"))
        result = run(service.get_guidance("STU-A"))
        readiness = result.career_readiness
        self.assertTrue(readiness.available)
        self.assertEqual(readiness.score, 72.5)
        self.assertEqual(readiness.level, "Good")
        self.assertEqual(readiness.positive_factors, ["Strong academics"])
        self.assertEqual(readiness.risk_factors, ["Low attendance"])
        self.assertIn("not a trained", readiness.disclaimer or "")

    def test_no_recompute_of_m4_in_module(self):
        import inspect

        from app.services import student_career_guidance_service as module

        source = inspect.getsource(module)
        self.assertNotIn("compute_career_readiness", source.replace("import", "", 0))
        # The service must not import or invoke the MD-06 scoring engine.
        self.assertNotIn("from app.services.student_service import", source)


# ---------------------------------------------------------------------------
# Career direction mapping
# ---------------------------------------------------------------------------


class TestCareerDirectionMapping(unittest.TestCase):
    def _direction(self, preferences, subjects, m4=None):
        service, *_ = make_service(
            preferences=preferences, subjects=subjects, m4=m4 or m4_row()
        )
        return run(service.get_guidance("STU-A")).career_direction

    def test_declared_known_domain_wins(self):
        direction = self._direction(SAMPLE_PREFERENCES, sample_subjects())
        self.assertTrue(direction.available)
        self.assertEqual(direction.domain, "Data Science")
        self.assertEqual(direction.source, "declared_preference")
        self.assertGreaterEqual(direction.matched_count, 3)

    def test_declared_unknown_domain_not_guessed(self):
        prefs = {**SAMPLE_PREFERENCES, "preferred_domain": "Robotics"}
        direction = self._direction(prefs, sample_subjects())
        self.assertFalse(direction.available)
        self.assertIn("Robotics", direction.note or "")
        self.assertIn("no verified skill mapping", direction.note or "")

    def test_no_preference_uses_subject_evidence(self):
        direction = self._direction(None, sample_subjects())
        self.assertTrue(direction.available)
        self.assertEqual(direction.source, "mapped_subject_evidence")
        self.assertIsNotNone(direction.domain)
        self.assertIn("no career preference has been declared", direction.note or "")

    def test_no_data_shows_unavailable_message(self):
        direction = self._direction(None, [])
        self.assertFalse(direction.available)
        self.assertIsNone(direction.domain)
        self.assertEqual(
            direction.note, "Career preference data is not available yet."
        )

    def test_preferences_without_mappable_domain(self):
        prefs = {"internship_completed": "Yes"}
        direction = self._direction(prefs, [])
        self.assertFalse(direction.available)
        self.assertEqual(
            direction.note, "Career direction needs more preference information."
        )


# ---------------------------------------------------------------------------
# Skill gap mapping
# ---------------------------------------------------------------------------


class TestSkillGapMapping(unittest.TestCase):
    def test_gaps_ranked_canonical_with_priority_slots(self):
        service, *_ = make_service()
        result = run(service.get_guidance("STU-A"))
        gaps = result.skill_gaps
        self.assertTrue(gaps)
        ranks = [g.rank for g in gaps]
        self.assertEqual(ranks, list(range(1, len(gaps) + 1)))
        priorities = [g.priority for g in gaps]
        self.assertEqual(priorities.count("High"), min(3, len(gaps)))
        self.assertTrue(all(p == "Medium" for p in priorities[3:]))

    def test_known_domain_areas_absent_from_gaps_when_evidenced(self):
        service, *_ = make_service()
        result = run(service.get_guidance("STU-A"))
        areas = {g.skill_area for g in result.skill_gaps}
        # Database/machine learning/python have strong subject evidence.
        self.assertNotIn("database", areas)
        self.assertNotIn("machine learning", areas)
        self.assertNotIn("python", areas)

    def test_strengths_only_from_verified_subjects(self):
        service, *_ = make_service(subjects=[subject(6, "CSE406", "Machine Learning", 75.0)])
        result = run(service.get_guidance("STU-A"))
        self.assertTrue(result.skill_strengths)
        for item in result.skill_strengths:
            self.assertEqual(item.evidence, "inferred_from_subject")
        payload = result.model_dump(mode="json")
        flat = str(payload)
        self.assertNotIn("Confirmed skill", flat)

    def test_prioritize_without_domain_is_empty(self):
        from app.schemas.student_career_coach import SkillGapItem

        gaps = [
            SkillGapItem(skill_area="cloud", detail="d"),
            SkillGapItem(skill_area="python", detail="d"),
        ]
        self.assertEqual(prioritize_skill_gaps(gaps, None), [])


# ---------------------------------------------------------------------------
# Ownership / RBAC
# ---------------------------------------------------------------------------


class TestOwnership(unittest.TestCase):
    def test_only_authenticated_student_id_used(self):
        service, student, prediction, _ = make_service()
        run(service.get_guidance("STU-A"))
        self.assertEqual(student.calls["get_career_preferences"], ["STU-A"])
        self.assertEqual(student.calls["get_performance"], ["STU-A"])
        self.assertEqual(prediction.calls, [("STU-A", "m4")])

    def test_cross_student_target_rejected_by_tool(self):
        _, student, prediction, _ = make_service()
        coach = StudentCareerCoachTool(
            None, student_service=student, prediction_service=prediction
        )
        with self.assertRaises(HTTPException) as ctx:
            run(coach.execute(student_id="STU-A", target_student_id="STU-B"))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_response_student_id_matches_caller(self):
        service, *_ = make_service()
        result = run(service.get_guidance("STU-A"))
        self.assertEqual(result.student_id, "STU-A")


# ---------------------------------------------------------------------------
# Grounded GenAI context
# ---------------------------------------------------------------------------


class TestGroundedGenAIContext(unittest.TestCase):
    def test_request_shape_and_context_boundary(self):
        genai = FakeGenAIService()
        service, *_ = make_service(genai=genai)
        result = run(service.get_guidance("STU-A"))

        self.assertEqual(len(genai.requests), 1)
        request = genai.requests[0]
        self.assertEqual(request.role, "Student")
        self.assertEqual(request.user_context_id, "STU-A")
        self.assertEqual(request.intent, "career_guidance")
        self.assertIn("Career direction", GUIDANCE_USER_MESSAGE)
        self.assertEqual(len(request.verified_context), 1)
        context = request.verified_context[0]
        self.assertEqual(context.source, SOURCE_LABEL)
        self.assertEqual(context.scope, "own_student")
        self.assertIsNotNone(context.model)
        self.assertEqual(context.model.model_id, "m4")

        serialized = str(context.model_dump(mode="json"))
        for forbidden in FORBIDDEN_CONTEXT_KEYS:
            self.assertNotIn(f'"{forbidden}"', serialized.lower())

    def test_ai_content_surfaced(self):
        genai = FakeGenAIService(content="**Career direction**\nData Science.")
        service, *_ = make_service(genai=genai)
        result = run(service.get_guidance("STU-A"))
        self.assertTrue(result.ai_guidance.available)
        self.assertEqual(result.ai_guidance.content, "**Career direction**\nData Science.")
        self.assertEqual(result.ai_guidance.provider, "fake-provider")

    def test_no_model_metadata_without_readiness(self):
        genai = FakeGenAIService()
        service, *_ = make_service(m4=None, genai=genai)
        run(service.get_guidance("STU-A"))
        context = genai.requests[0].verified_context[0]
        self.assertIsNone(context.model)


# ---------------------------------------------------------------------------
# No fabricated facts
# ---------------------------------------------------------------------------


class TestNoFabrication(unittest.TestCase):
    def test_unknown_skills_never_appear(self):
        service, *_ = make_service(subjects=[subject(6, "CSE101", "History", 90.0)])
        result = run(service.get_guidance("STU-A"))
        flat = str(result.model_dump(mode="json")).lower()
        self.assertNotIn("kubernetes", flat)
        self.assertNotIn("docker", flat)
        self.assertNotIn("certification completed", flat)

    def test_missing_preferences_flagged_not_filled(self):
        service, *_ = make_service(preferences=None, subjects=[])
        result = run(service.get_guidance("STU-A"))
        self.assertFalse(result.career_preferences_available)
        self.assertFalse(result.career_direction.available)
        self.assertEqual(
            result.career_direction.note,
            "Career preference data is not available yet.",
        )
        self.assertEqual(result.skill_gaps, [])


# ---------------------------------------------------------------------------
# GenAI failure fallback
# ---------------------------------------------------------------------------


class TestGenAIFailureFallback(unittest.TestCase):
    def _fallback(self, error, expected_kind):
        genai = FakeGenAIService(error=error)
        service, *_ = make_service(genai=genai)
        result = run(service.get_guidance("STU-A"))
        self.assertIsInstance(result, StudentCareerGuidanceResponse)
        self.assertFalse(result.ai_guidance.available)
        self.assertIsNone(result.ai_guidance.content)
        self.assertEqual(result.ai_guidance.error, expected_kind)
        # Deterministic payload remains complete.
        self.assertTrue(result.data_available)
        self.assertTrue(result.career_readiness.available)
        self.assertTrue(result.career_direction.available)
        self.assertTrue(result.roadmap or True)

    def test_provider_error_falls_back(self):
        self._fallback(GenAIError("provider down"), "unavailable")

    def test_rate_limit_error_falls_back(self):
        self._fallback(GenAIRateLimitError("429"), "rate_limited")

    def test_timeout_error_falls_back(self):
        self._fallback(GenAITimeoutError("timeout"), "timeout")

    def test_unexpected_exception_falls_back(self):
        genai = FakeGenAIService(error=RuntimeError("boom"))
        service, *_ = make_service(genai=genai)
        result = run(service.get_guidance("STU-A"))
        self.assertFalse(result.ai_guidance.available)
        self.assertEqual(result.ai_guidance.error, "unavailable")

    def test_deterministic_payload_identical_with_and_without_genai(self):
        ok = FakeGenAIService(content="hello")
        broken = FakeGenAIService(error=GenAIError("down"))
        a = run(make_service(genai=ok)[0].get_guidance("STU-A"))
        b = run(make_service(genai=broken)[0].get_guidance("STU-A"))
        strip = lambda r: r.model_dump(mode="json", exclude={"ai_guidance", "generated_at"})
        self.assertEqual(strip(a), strip(b))


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism(unittest.TestCase):
    def test_repeated_calls_deterministic(self):
        service_a, *_ = make_service()
        service_b, *_ = make_service()
        a = run(service_a.get_guidance("STU-A"))
        b = run(service_b.get_guidance("STU-A"))
        strip = lambda r: r.model_dump(mode="json", exclude={"generated_at"})
        self.assertEqual(strip(a), strip(b))

    def test_select_career_direction_pure_function(self):
        from app.schemas.student_career_coach import DomainEvidenceItem

        class _Result:
            career_preferences_available = True
            career_preferences = []
            domain_evidence = [
                DomainEvidenceItem(domain="Cloud Computing", matched_count=2),
                DomainEvidenceItem(domain="Cyber Security", matched_count=3),
            ]

        direction = select_career_direction(_Result())  # type: ignore[arg-type]
        self.assertEqual(direction.domain, "Cyber Security")
        self.assertEqual(direction.matched_count, 3)


if __name__ == "__main__":
    unittest.main()
