"""Student Career Guidance service (MD-06 presentation layer).

ONE small, Student-only composition step for the ML Insights career section:

  authenticated student_id
      -> G2.5 StudentCareerCoachTool (EXISTING verified data + approved rules)
      -> deterministic CareerDirection selection (no ML)
      -> deterministic skill-gap prioritization (no ML)
      -> optional grounded GenAI narrative via the EXISTING G0 boundary

Hard boundaries:
  * M4 is NEVER recomputed, reinterpreted or modified; the persisted
    rule-based M4 output is reused exactly as produced.
  * The mapping reuses ``student_career_rules.DOMAIN_SUBJECT_KEYWORDS`` -
    no competing taxonomy and no trained model exists anywhere here.
  * No student interest/skill is invented: an absent preference stays absent
    and unknown domains are reported instead of guessed.
  * GenAI receives ONLY the tool's G0 VerifiedContext (JSON-serializable,
    verified values) and can never touch SQL, sessions, repositories or the
    database. A GenAI failure degrades to the deterministic payload; it never
    breaks the response.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.schemas.genai import GenAIRequest, VerifiedContext
from app.schemas.student_career_coach import (
    DomainEvidenceItem,
    SkillGapItem,
    StudentCareerCoachResult,
)
from app.schemas.student_career_guidance import (
    AiGuidance,
    AiGuidanceError,
    CareerDirection,
    CareerPathRecommendation,
    PrioritySkillGap,
    StudentCareerGuidanceResponse,
)
from app.services.genai_provider import (
    GenAIError,
    GenAIRateLimitError,
    GenAITimeoutError,
)
from app.services.genai_service import GenAIService
from app.services.student_career_coach import SOURCE_LABEL, StudentCareerCoachTool
from app.services.student_career_rules import (
    DOMAIN_CAREER_PATHS,
    DOMAIN_SUBJECT_KEYWORDS,
    subject_is_relevant,
)

logger = logging.getLogger(__name__)

# Fixed grounding prompt. The G0 system instruction already enforces
# verified-context-only answering; this message only fixes the requested
# shape so the UI can render a compact guidance block.
GUIDANCE_USER_MESSAGE = (
    "Using ONLY the verified context provided, write concise grounded career "
    "guidance for this student in Markdown with exactly these sections:\n"
    "**Career direction** - the recommended domain from the context.\n"
    "**Why this fits** - cite only verified evidence (readiness score/level, "
    "matched subjects, declared preferences).\n"
    "**Key skill gaps** - list the mapped skill gaps from the context.\n"
    "**Recommended next steps** - 3-5 numbered steps derived from the "
    "roadmap and risk factors in the context.\n"
    "Rules: use only values present in the context; never invent skills, "
    "scores, certifications or outcomes; if something is unavailable say so; "
    "never guarantee career outcomes; keep the whole answer under 220 words."
)

_HIGH_PRIORITY_SLOTS = 3


def build_career_path(
    direction: CareerDirection,
    skill_gaps: list[PrioritySkillGap],
    skill_strengths: list,
    career_preferences: list,
) -> CareerPathRecommendation | None:
    """Build a domain-specific career path recommendation from verified data.

    Every field is grounded in the student's primary domain and actual academic
    evidence.  No recommendations are invented for domains without a mapping.
    """
    if not direction.available or not direction.domain:
        return None

    path_data = DOMAIN_CAREER_PATHS.get(direction.domain)
    if not path_data:
        return None

    # Extract declared preference values for personalization
    preferences = {p.field: p.value for p in career_preferences if p.value}
    declared_role = preferences.get("dream_job_role")
    declared_industry = preferences.get("preferred_industry")

    # Relevant subjects: subjects that match the domain keywords
    relevant_subjects = []
    seen_subjects: set[str] = set()
    for strength in skill_strengths:
        subj = strength.source_subject
        if subj and subj not in seen_subjects and subject_is_relevant(direction.domain, subj):
            relevant_subjects.append(subj)
            seen_subjects.add(subj)

    # Skill gaps from the prioritized list
    gaps = [gap.skill_area for gap in skill_gaps if gap.priority == "High"]

    # Personalize next steps based on actual data
    personalized_next_steps: list[str] = []
    if gaps:
        personalized_next_steps.append(
            f"Strengthen {', '.join(gaps[:3])} to build a stronger foundation "
            f"for {direction.domain} roles."
        )
    if declared_role:
        personalized_next_steps.append(
            f"Explore {declared_role} job descriptions to align your "
            f"preparation with industry expectations."
        )
    if relevant_subjects:
        personalized_next_steps.append(
            f"Build projects that apply concepts from {relevant_subjects[0]} "
            f"to demonstrate practical {direction.domain} skills."
        )
    if not personalized_next_steps:
        personalized_next_steps.append(
            f"Begin with foundational {direction.domain} coursework and "
            f"progress to hands-on projects."
        )

    return CareerPathRecommendation(
        domain=direction.domain,
        roles=path_data["roles"],
        skills=path_data["skills"],
        relevant_subjects=relevant_subjects,
        skill_gaps=gaps,
        certifications=path_data["certifications"],
        project_suggestions=path_data["project_suggestions"],
        personalized_next_steps=personalized_next_steps,
    )


def select_career_direction(
    coach_result: StudentCareerCoachResult,
) -> CareerDirection:
    """Deterministically pick the recommended domain.

    1. Declared preferred_domain wins when it exists in the approved mapping.
    2. Otherwise the best-evidenced known domain leads (most matched
       completed subjects; alphabetical tiebreak keeps it stable).
    3. Otherwise unavailable with an explicit, honest note.
    """
    preferences_available = coach_result.career_preferences_available
    declared = next(
        (
            str(item.value)
            for item in coach_result.career_preferences
            if item.field == "preferred_domain" and item.value
        ),
        None,
    )
    evidence = {
        item.domain: item.matched_count for item in coach_result.domain_evidence
    }

    # A DECLARED preference always wins over inferred suggestions - the
    # mapping layer must never override or ignore the student's own choice.
    if declared:
        if declared in DOMAIN_SUBJECT_KEYWORDS:
            return CareerDirection(
                available=True,
                domain=declared,
                source="declared_preference",
                matched_count=evidence.get(declared, 0),
                note=(
                    f"{evidence.get(declared, 0)} of your completed subjects map "
                    f"to {declared}."
                    if evidence.get(declared)
                    else f"{declared} is your declared career preference."
                ),
            )
        # Declared but not in the approved taxonomy: report honestly instead
        # of guessing skills or silently substituting another domain.
        return CareerDirection(
            available=False,
            domain=declared,
            source="unavailable",
            note=(
                f"'{declared}' is recorded as your preference, but no "
                "verified skill mapping exists for it yet."
            ),
        )

    if coach_result.domain_evidence:
        # Defensive: rank by evidence, alphabetical tiebreak for stability.
        top = max(
            coach_result.domain_evidence,
            key=lambda item: (item.matched_count, item.domain),
        )
        return CareerDirection(
            available=True,
            domain=top.domain,
            source="mapped_subject_evidence",
            matched_count=top.matched_count,
            note=(
                "Suggested from your completed subjects - no career "
                "preference has been declared yet."
            ),
        )

    if preferences_available:
        return CareerDirection(
            available=False,
            note="Career direction needs more preference information.",
        )
    return CareerDirection(
        available=False,
        note="Career preference data is not available yet.",
    )


def prioritize_skill_gaps(
    skill_gaps: list[SkillGapItem],
    domain: str | None,
) -> list[PrioritySkillGap]:
    """Rank unmapped areas of the chosen domain deterministically.

    Order follows the canonical keyword order of the approved domain mapping
    (core areas first); unknown keywords keep alphabetical order at the end.
    The first three ranked gaps are High priority, the rest Medium.
    """
    if not domain:
        return []
    canonical = DOMAIN_SUBJECT_KEYWORDS.get(domain, [])
    order = {keyword: index for index, keyword in enumerate(canonical)}

    def sort_key(gap: SkillGapItem) -> tuple[int, str]:
        return (order.get(gap.skill_area, len(order)), gap.skill_area)

    ranked = sorted(skill_gaps, key=sort_key)
    return [
        PrioritySkillGap(
            rank=index,
            skill_area=gap.skill_area,
            priority="High" if index <= _HIGH_PRIORITY_SLOTS else "Medium",
            detail=gap.detail,
        )
        for index, gap in enumerate(ranked, start=1)
    ]


def _ai_error_kind(exc: Exception) -> AiGuidanceError:
    if isinstance(exc, GenAIRateLimitError):
        return "rate_limited"
    if isinstance(exc, GenAITimeoutError):
        return "timeout"
    return "unavailable"


class StudentCareerGuidanceService:
    """Compose verified career data + deterministic mapping + optional G0 GenAI.

    ``coach_tool`` and ``genai_service`` are injectable for isolated tests
    (same convention as G2.5 / G2.4).
    """

    def __init__(
        self,
        pool: Any,
        *,
        coach_tool: StudentCareerCoachTool | None = None,
        genai_service: GenAIService | None = None,
    ) -> None:
        self._pool = pool
        self._coach = coach_tool
        self._genai = genai_service

    def _coach_tool(self) -> StudentCareerCoachTool:
        if self._coach is None:
            self._coach = StudentCareerCoachTool(self._pool)
        return self._coach

    def _genai_service(self) -> GenAIService:
        if self._genai is None:
            self._genai = GenAIService()
        return self._genai

    async def _generate_ai_guidance(
        self,
        student_id: str,
        context: VerifiedContext,
    ) -> AiGuidance:
        """Grounded narrative via the existing G0 boundary; fail-closed."""
        request = GenAIRequest(
            role="Student",
            user_context_id=student_id,
            intent="career_guidance",
            verified_context=[context],
            user_message=GUIDANCE_USER_MESSAGE,
        )
        try:
            response = await self._genai_service().generate(request)
        except GenAIError as exc:
            kind = _ai_error_kind(exc)
            logger.warning(
                "career_guidance_genai status=failure kind=%s student=%s",
                kind,
                student_id,
            )
            return AiGuidance(available=False, error=kind)
        except Exception as exc:  # pragma: no cover - defensive fail-closed
            logger.warning(
                "career_guidance_genai status=error student=%s exc=%s",
                student_id,
                type(exc).__name__,
            )
            return AiGuidance(available=False, error="unavailable")
        return AiGuidance(
            available=True,
            content=response.content,
            provider=response.provider,
            model=response.model,
        )

    async def get_guidance(self, student_id: str) -> StudentCareerGuidanceResponse:
        """Return combined career guidance for the authenticated student.

        ``student_id`` MUST be the authenticated identity; the underlying
        G2.5 coach enforces self-scope (403 on any mismatched target).
        """
        coach_result = await self._coach_tool().execute(student_id=student_id)

        direction = select_career_direction(coach_result)
        gaps = prioritize_skill_gaps(coach_result.skill_gaps, direction.domain)

        ai_block = AiGuidance(available=False, error=None)
        if coach_result.data_available:
            context = self._coach_tool().to_verified_context(coach_result)
            ai_block = await self._generate_ai_guidance(student_id, context)

        career_path = build_career_path(
            direction=direction,
            skill_gaps=gaps,
            skill_strengths=coach_result.verified_skill_evidence,
            career_preferences=coach_result.career_preferences,
        )

        return StudentCareerGuidanceResponse(
            student_id=student_id,
            data_available=coach_result.data_available,
            career_preferences_available=coach_result.career_preferences_available,
            career_preferences=coach_result.career_preferences,
            career_readiness=coach_result.career_readiness,
            career_direction=direction,
            skill_strengths=coach_result.verified_skill_evidence,
            skill_gaps=gaps,
            roadmap=coach_result.roadmap,
            limitations=coach_result.limitations,
            ai_guidance=ai_block,
            career_path=career_path,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
        )
