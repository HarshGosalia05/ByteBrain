"""G2.5 Student Career Coach Tool.

ONE combined Student-only career capability serving the G1 intents
``career_guidance`` / ``career_readiness`` / ``skill_gap`` / ``roadmap``.
It is a CONTROLLED MAPPING + VERIFIED DATA + GENAI REASONING layer. M5 is
NOT a trained/supervised classifier: nothing is trained and no ML accuracy
or confidence is computed anywhere.

Composes existing verified backend data + approved rules:
  * ``StudentService.get_career_preferences`` -> self-declared survey
    fields (a preference is NEVER an objective predicted career outcome).
  * ``StudentService.get_performance`` -> verified per-subject performance.
  * ``MLPredictionService.get_latest(student_id, "m4")`` -> the persisted
    deterministic rule-based M4 readiness output (score, level, positive
    and risk factors). Reused as evidence, never reinterpreted as a
    placement probability.
  * ``student_career_rules.DOMAIN_SUBJECT_KEYWORDS`` / ``subject_is_relevant``
    -> the APPROVED subject/domain mapping (no competing taxonomy created).
  * A small, explicit ``SUBJECT_SKILL_LABELS`` map (inference-only) is used
    ONLY to label academic-area skills inferred from strong subject
    performance; those skills are always tagged ``inferred_from_subject``
    and never presented as confirmed real-world skills.
  * No job-role mapping exists in the repository, so role suitability is
    returned as controlled unavailable information instead of being invented.

It does NOT:
  * invent skills / certifications / achievements / preferences / role
    suitability / skill gaps / roadmap progress or prediction values,
  * treat ``certification_interest`` as certification completion,
  * claim placement probability or any numeric confidence,
  * call any LLM provider (G0 remains the only LLM boundary),
  * execute or build SQL itself, or accept a DB session / repository.

Security (self-scope):
  * Student-only. The authenticated ``student_id`` is the ONLY identity.
  * A caller-supplied ``target_student_id`` that differs is REJECTED (403)
    before any data access.

G1 integration:
  * ``TOOL_NAME`` matches the registered ``student_career_coach_tool``;
    the tool replaces the four separate career placeholders and serves all
    four career intents through the existing G1 registry + IntentRouter.

G0 boundary:
  * ``to_verified_context`` produces a G0 ``VerifiedContext`` (with G0
    ``ModelMetadata`` for the M4 source when available). The tool never
    bypasses G0.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.schemas.genai import ModelMetadata, VerifiedContext
from app.schemas.student_career_coach import (
    CareerPreference,
    CareerReadiness,
    DomainEvidenceItem,
    LimitationItem,
    RoleGuidance,
    RoadmapItem,
    SkillEvidenceItem,
    SkillGapItem,
    StudentCareerCoachResult,
)
from app.services.ml_prediction_service import MLPredictionService
from app.services.student_career_rules import (
    DOMAIN_SUBJECT_KEYWORDS,
    subject_is_relevant,
)
from app.services.student_service import StudentService

logger = logging.getLogger(__name__)

TOOL_NAME = "student_career_coach_tool"
INTENT = "career_coach"
SOURCE_LABEL = "students/career_coach"

# The four G1 career intents this ONE combined tool serves.
SERVED_INTENTS = ("career_guidance", "career_readiness", "skill_gap", "roadmap")

_DECLARED_PREFERENCE_FIELDS = (
    "preferred_domain",
    "dream_job_role",
    "preferred_industry",
    "preferred_work_mode",
    "target_package_lpa",
    "higher_studies_interest",
    "entrepreneurship_interest",
    "certification_interest",
    "internship_completed",
    "placement_readiness_level",
)

_M4_DISCLAIMER = (
    "M4 is a deterministic rule-based career-readiness score, not a trained "
    "ML model and not an actual placement outcome. It is not a placement "
    "probability."
)

# Approved subject areas reused from the existing domain mapping; a "skill
# area" in the roadmap is a domain subject-area keyword, never an invented
# certification or course.
_STRONG_MIN = 60.0
_CRITICAL_MAX = 45.0

# Small, explicit, inference-ONLY subject-name -> skill-area label map.
# Skills derived through it are ALWAYS labeled ``inferred_from_subject``.
_SUBJECT_SKILL_LABELS: dict[str, tuple[str, ...]] = {
    "dbms": ("SQL", "Database design"),
    "database": ("SQL", "Database concepts"),
    "machine learning": ("Machine Learning concepts",),
    "deep learning": ("Deep Learning concepts",),
    "artificial intelligence": ("AI concepts",),
    "python": ("Python programming",),
    "java": ("Java programming", "Object-oriented programming"),
    "web": ("Web development",),
    "operating systems": ("Operating Systems concepts",),
    "networks": ("Computer networks",),
    "cloud": ("Cloud computing concepts",),
    "linux": ("Linux administration", "Scripting"),
    "compiler": ("Compiler design", "Systems programming"),
    "data": ("Data analysis",),
    "statistics": ("Statistical analysis",),
    "probability": ("Probability concepts",),
    "cryptography": ("Cryptography",),
    "security": ("Cybersecurity concepts",),
    "software engineering": ("Software engineering practices",),
    "mobile": ("Mobile development",),
    "android": ("Android development",),
    "human computer interaction": ("HCI / UI design",),
    "design": ("Design principles",),
    "marketing": ("Marketing concepts",),
    "financial": ("Financial concepts",),
    "analytics": ("Analytics",),
    "operations": ("Operations concepts",),
    "supply chain": ("Supply chain concepts",),
    "human resource": ("HR concepts",),
    "entrepreneurship": ("Entrepreneurship concepts",),
    "business": ("Business concepts",),
}

_BASE_LIMITATIONS = (
    LimitationItem(
        kind="advisory",
        message=(
            "Career guidance is advisory and based on current verified "
            "evidence; it is not a guarantee of any career outcome."
        ),
    ),
    LimitationItem(
        kind="inference",
        message=(
            "Skills labeled inferred_from_subject are academic-area "
            "inferences, not confirmed real-world skills."
        ),
    ),
    LimitationItem(
        kind="not_tracked",
        message=(
            "certification_interest records interest, not completion; no "
            "certification completion dataset exists."
        ),
    ),
    LimitationItem(
        kind="not_tracked",
        message=(
            "The roadmap is a recommendation generated from verified gaps, "
            "not a progress tracker; no progress data is tracked."
        ),
    ),
)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _split_factors(text: Any) -> list[str]:
    if text is None:
        return []
    return [part.strip() for part in str(text).split(";") if part.strip()]


class StudentCareerCoachTool:
    """Combined Student Career Coach over verified backend data.

    ``student_service`` and ``prediction_service`` are injectable for
    isolated testing (same convention as G2.4 / ML-09); when omitted they
    are created lazily from the pool.
    """

    def __init__(
        self,
        pool: Any,
        *,
        student_service: Any = None,
        prediction_service: Any = None,
    ) -> None:
        self._pool = pool
        self._student = student_service
        self._prediction = prediction_service

    # ------------------------------------------------------------------
    # Lazy dependency resolution
    # ------------------------------------------------------------------

    def _student_service(self) -> Any:
        if self._student is None:
            self._student = StudentService(self._pool)
        return self._student

    def _prediction_service(self) -> Any:
        if self._prediction is None:
            self._prediction = MLPredictionService(self._pool)
        return self._prediction

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(
        self,
        *,
        student_id: str,
        target_student_id: str | None = None,
        requested_intent: str | None = None,
    ) -> StudentCareerCoachResult:
        """Return the combined career coach result for the authenticated student.

        ``student_id`` is ALWAYS the authenticated identity. Any differing
        ``target_student_id`` (client-supplied) is rejected before any data
        access.
        """
        if not student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated student identity",
            )
        if target_student_id is not None and target_student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only access their own career data",
            )

        student_service = self._student_service()
        prediction_service = self._prediction_service()

        preferences, m4_row, performance = await asyncio.gather(
            student_service.get_career_preferences(student_id),
            prediction_service.get_latest(student_id, "m4"),
            student_service.get_performance(student_id),
        )

        subjects = self._subject_rows(performance)
        return self._build(student_id, preferences, m4_row, subjects)

    # ------------------------------------------------------------------
    # Verified building
    # ------------------------------------------------------------------

    @staticmethod
    def _subject_rows(performance) -> list[dict[str, Any]]:
        rows = getattr(performance, "performance", None) or []
        out: list[dict[str, Any]] = []
        for item in rows:
            pct = _float_or_none(getattr(item, "percentage", None))
            name = getattr(item, "subject_name", None)
            if pct is None or not name:
                continue
            out.append(
                {
                    "semester": getattr(item, "semester", None),
                    "subject_code": getattr(item, "subject_code", None),
                    "subject_name": str(name),
                    "percentage": pct,
                }
            )
        return sorted(out, key=lambda r: (r["subject_name"], r["semester"]))

    def _build(
        self,
        student_id: str,
        preferences: dict[str, Any] | None,
        m4_row: dict[str, Any] | None,
        subjects: list[dict[str, Any]],
    ) -> StudentCareerCoachResult:
        preference_items = self._preference_items(preferences)
        readiness = self._readiness(m4_row)
        domain_evidence = self._domain_evidence(preferences, subjects)
        role_guidance = self._role_guidance(preferences)
        skill_evidence = self._skill_evidence(subjects)
        skill_gaps = self._skill_gaps(preferences, subjects)
        roadmap = self._roadmap(skill_gaps, readiness)
        limitations = self._limitations(preferences, readiness, subjects)

        data_available = bool(
            preferences or readiness.available or subjects
        )
        return StudentCareerCoachResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            student_id=student_id,
            data_available=data_available,
            career_preferences_available=bool(preferences),
            career_preferences=preference_items,
            career_readiness=readiness,
            domain_evidence=domain_evidence,
            role_guidance=role_guidance,
            verified_skill_evidence=skill_evidence,
            skill_gaps=skill_gaps,
            roadmap=roadmap,
            limitations=list(limitations),
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=None if data_available else (
                "No verified career data is currently available for this student."
            ),
        )

    @staticmethod
    def _preference_items(
        preferences: dict[str, Any] | None,
    ) -> list[CareerPreference]:
        if not preferences:
            return []
        return [
            CareerPreference(
                field=field,
                value=preferences.get(field),
                evidence="declared_preference",
            )
            for field in _DECLARED_PREFERENCE_FIELDS
            if field in preferences
        ]

    @staticmethod
    def _readiness(m4_row: dict[str, Any] | None) -> CareerReadiness:
        if not m4_row:
            return CareerReadiness(
                available=False,
                disclaimer=_M4_DISCLAIMER,
            )
        value = m4_row.get("prediction_value")
        if not isinstance(value, dict):
            value = {}
        return CareerReadiness(
            available=True,
            score=_float_or_none(value.get("career_readiness_score")),
            level=value.get("career_readiness_level") or None,
            positive_factors=_split_factors(value.get("positive_factors")),
            risk_factors=_split_factors(value.get("risk_factors")),
            disclaimer=_M4_DISCLAIMER,
        )

    def _domain_evidence(
        self,
        preferences: dict[str, Any] | None,
        subjects: list[dict[str, Any]],
    ) -> list[DomainEvidenceItem]:
        if not subjects:
            return []
        preferred = (preferences or {}).get("preferred_domain") or None
        rows: list[DomainEvidenceItem] = []
        for domain in DOMAIN_SUBJECT_KEYWORDS:
            matched = [
                subject["subject_name"]
                for subject in subjects
                if subject_is_relevant(domain, subject["subject_name"])
            ]
            if not matched:
                continue
            rows.append(
                DomainEvidenceItem(
                    domain=domain,
                    matched_subjects=sorted(matched),
                    matched_count=len(matched),
                    evidence="mapped_subject_evidence",
                )
            )
        rows.sort(key=lambda item: (-item.matched_count, item.domain))

        top = rows[:5]
        if preferred:
            preferred_item = next(
                (item for item in rows if item.domain == preferred), None
            )
            if preferred_item is not None:
                preferred_item.note = (
                    "Preferred domain; matched {n} of the student's subjects."
                ).format(n=preferred_item.matched_count)
            top = [preferred_item] + [item for item in top if item is not preferred_item]
            top = top[:5]
        return top

    @staticmethod
    def _role_guidance(
        preferences: dict[str, Any] | None,
    ) -> RoleGuidance:
        declared_role = (preferences or {}).get("dream_job_role") or None
        if declared_role:
            return RoleGuidance(
                declared_role=str(declared_role),
                declared_role_evidence="declared_preference",
                mapping_available=False,
                note=(
                    "No verified job-role mapping exists in the system, so "
                    "job-role suitability cannot be asserted. The declared dream "
                    "role is preserved as a declared preference only."
                ),
            )
        return RoleGuidance(
            declared_role=None,
            declared_role_evidence="unavailable",
            mapping_available=False,
            note=(
                "No declared dream job role was recorded; role guidance is "
                "unavailable until a role is declared or a verified job-role "
                "mapping exists."
            ),
        )

    def _skill_evidence(self, subjects: list[dict[str, Any]]) -> list[SkillEvidenceItem]:
        items: list[SkillEvidenceItem] = []
        for subject in subjects:
            pct = subject["percentage"]
            if pct is None or pct < _STRONG_MIN:
                continue
            name = subject["subject_name"].lower()
            for key, labels in _SUBJECT_SKILL_LABELS.items():
                if key in name:
                    for label in labels:
                        items.append(
                            SkillEvidenceItem(
                                skill=label,
                                evidence="inferred_from_subject",
                                source_subject=subject["subject_name"],
                                detail=(
                                    f"Inferred from {subject['subject_name']} at "
                                    f"{pct:.1f}% (not a confirmed real-world skill)."
                                ),
                            )
                        )
                    break
        items.sort(key=lambda item: (item.source_subject or "", item.skill))
        return items

    def _skill_gaps(
        self,
        preferences: dict[str, Any] | None,
        subjects: list[dict[str, Any]],
    ) -> list[SkillGapItem]:
        preferred_domain = (preferences or {}).get("preferred_domain") or None
        if not preferred_domain or not subjects:
            return []
        keywords = DOMAIN_SUBJECT_KEYWORDS.get(preferred_domain, [])
        if not keywords:
            return []
        gaps: list[SkillGapItem] = []
        for keyword in keywords:
            evidenced = any(
                subject["percentage"] is not None
                and subject["percentage"] >= _STRONG_MIN
                and keyword in subject["subject_name"].lower()
                for subject in subjects
            )
            if not evidenced:
                gaps.append(
                    SkillGapItem(
                        skill_area=keyword,
                        evidence="not_verified",
                        detail=(
                            f"No verified subject evidence for '{keyword}' "
                            f"within {preferred_domain}."
                        ),
                    )
                )
        gaps.sort(key=lambda item: item.skill_area)
        return gaps

    def _roadmap(
        self,
        skill_gaps: list[SkillGapItem],
        readiness: CareerReadiness,
    ) -> list[RoadmapItem]:
        items: list[RoadmapItem] = []
        for index, gap in enumerate(skill_gaps, start=1):
            items.append(
                RoadmapItem(
                    sequence=index,
                    focus_area=gap.skill_area,
                    current_evidence=(
                        f"No verified subject evidence found for '{gap.skill_area}'."
                    ),
                    priority="High",
                    recommended_step=(
                        f"Review the {gap.skill_area} subject area and strengthen "
                        f"the underlying concepts."
                    ),
                    milestone=f"Demonstrate {gap.skill_area} through a verified subject or practical project.",
                    next_action=(
                        f"Enroll in or review {gap.skill_area} coursework and "
                        "validate learning with a hands-on project."
                    ),
                    progress_tracking="not_available",
                    evidence="not_verified",
                )
            )
        for index, factor in enumerate(readiness.risk_factors, start=len(items) + 1):
            items.append(
                RoadmapItem(
                    sequence=index,
                    focus_area=factor,
                    current_evidence=(
                        f"Verified M4 risk factor for this student."
                    ),
                    priority="High",
                    recommended_step=(
                        f"Address the verified readiness factor: {factor}."
                    ),
                    milestone=(
                        f"Resolve the readiness factor '{factor}' before the next "
                        "placement cycle."
                    ),
                    next_action=(
                        f"Create a focused plan to address '{factor}' and track "
                        "improvement against verified data."
                    ),
                    progress_tracking="not_available",
                    evidence="verified_m4_evidence",
                )
            )
        return items

    def _limitations(
        self,
        preferences: dict[str, Any] | None,
        readiness: CareerReadiness,
        subjects: list[dict[str, Any]],
    ) -> tuple[LimitationItem, ...]:
        missing: list[LimitationItem] = []
        if not preferences:
            missing.append(
                LimitationItem(
                    kind="missing_data",
                    message=(
                        "No career survey data is available; declared-preference "
                        "sections are empty."
                    ),
                )
            )
        if not readiness.available:
            missing.append(
                LimitationItem(
                    kind="missing_data",
                    message=(
                        "No verified M4 career-readiness score is available."
                    ),
                )
            )
        if not subjects:
            missing.append(
                LimitationItem(
                    kind="missing_data",
                    message=(
                        "No verified subject performance is available; domain "
                        "evidence and skill inference are empty."
                    ),
                )
            )
        return _BASE_LIMITATIONS + tuple(missing)

    # ------------------------------------------------------------------
    # G0 boundary
    # ------------------------------------------------------------------

    def to_verified_context(
        self, result: StudentCareerCoachResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext.

        ``data`` carries only JSON-serializable, verified values plus clearly
        labeled inference. G0 ``ModelMetadata`` references the verified M4
        source when available. No SQL, session, repository, callable, or
        import path ever leaves the tool.
        """
        context = VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
            metadata={
                "intent": INTENT,
                "served_intents": list(SERVED_INTENTS),
                "advisory": True,
            },
            scope="own_student",
        )
        if result.career_readiness.available:
            context.model = ModelMetadata(
                model_id="m4",
                model_version=None,
                prediction_type="m4",
            )
        return context
