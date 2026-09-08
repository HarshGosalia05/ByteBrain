"""Student Career Guidance contracts (MD-06 presentation layer).

Composes the EXISTING verified G2.5 Student Career Coach output with a small
deterministic career-direction / skill-gap priority mapping and an OPTIONAL
G0-grounded GenAI narrative. No new ML model, no M4 changes, no schema
changes.

Evidence vocabulary is inherited from ``student_career_coach``:
  * ``declared_preference``      - self-declared career survey value.
  * ``mapped_subject_evidence``  - deterministic DOMAIN_SUBJECT_KEYWORDS match.
  * ``verified_m4_evidence``     - persisted rule-based M4 output (reused as-is).
  * ``inferred_from_subject``    - academic-area inference, never a confirmed skill.
  * ``not_verified`` / ``unavailable`` - controlled absence.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.student_career_coach import (
    CareerPreference,
    CareerReadiness,
    LimitationItem,
    RoadmapItem,
    SkillEvidenceItem,
)

DirectionSource = Literal[
    "declared_preference",
    "mapped_subject_evidence",
    "unavailable",
]

AiGuidanceError = Literal["unavailable", "rate_limited", "timeout"]


class CareerDirection(BaseModel):
    """Deterministically selected recommended career domain.

    Selection rules (no ML):
      1. A declared ``preferred_domain`` that exists in the approved domain
         mapping wins (source=declared_preference).
      2. Otherwise the known domain with the most matched completed subjects
         leads (source=mapped_subject_evidence) - evidence-based, never an
         invented interest.
      3. Otherwise the direction is unavailable with an explicit note; no
         preference is ever fabricated.
    """

    available: bool = False
    domain: str | None = None
    source: DirectionSource = "unavailable"
    matched_count: int = 0
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


class PrioritySkillGap(BaseModel):
    """One unmapped skill area of the chosen domain, deterministically ranked."""

    rank: int
    skill_area: str
    priority: Literal["High", "Medium"]
    detail: str
    evidence: Literal["not_verified"] = "not_verified"

    model_config = ConfigDict(extra="forbid")


class AiGuidance(BaseModel):
    """Optional grounded GenAI narrative. Failures degrade gracefully."""

    available: bool = False
    content: str | None = None
    provider: str | None = None
    model: str | None = None
    error: AiGuidanceError | None = None

    model_config = ConfigDict(extra="forbid")


class CareerPathRecommendation(BaseModel):
    """Domain-specific career path recommendation derived from verified data."""

    domain: str
    roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    relevant_subjects: list[str] = Field(default_factory=list)
    skill_gaps: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    project_suggestions: list[str] = Field(default_factory=list)
    personalized_next_steps: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "Recommendations are based on your declared preferences and verified "
        "academic records, not guaranteed career outcomes."
    )

    model_config = ConfigDict(extra="forbid")


class StudentCareerGuidanceResponse(BaseModel):
    """Combined Student career guidance payload for the ML Insights UI.

    ``career_readiness`` is the untouched persisted rule-based M4 output;
    everything else derives from the same verified sources via the existing
    G2.5 coach tool plus the deterministic direction/gap mapping above.
    """

    student_id: str
    data_available: bool
    career_preferences_available: bool
    career_preferences: list[CareerPreference] = Field(default_factory=list)
    career_readiness: CareerReadiness = Field(default_factory=CareerReadiness)
    career_direction: CareerDirection = Field(default_factory=CareerDirection)
    skill_strengths: list[SkillEvidenceItem] = Field(default_factory=list)
    skill_gaps: list[PrioritySkillGap] = Field(default_factory=list)
    roadmap: list[RoadmapItem] = Field(default_factory=list)
    limitations: list[LimitationItem] = Field(default_factory=list)
    ai_guidance: AiGuidance = Field(default_factory=AiGuidance)
    career_path: CareerPathRecommendation | None = None
    source: str
    generated_at: datetime

    model_config = ConfigDict(extra="forbid")
