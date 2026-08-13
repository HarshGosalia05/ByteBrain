"""G2.5 Student Career Coach contracts.

Structured, VERIFIED-ONLY output for the combined Student Career Coach
capability (career/domain guidance + job-role guidance + skill-gap analysis
+ personalized learning roadmap).

Everything here is a data transport:
  * ``declared_preference``  - self-declared career survey values.
  * ``verified_m4_evidence`` - deterministic rule-based M4 readiness output.
  * ``mapped_subject_evidence`` - results of the approved
    ``DOMAIN_SUBJECT_KEYWORDS`` mapping over verified subject performance.
  * ``inferred_from_subject`` - academic-area skill labels inferred from
    strong subject performance (NEVER confirmed real-world skills).
  * ``not_verified``         - domain areas with no verified evidence.
  * ``unavailable``          - controlled absence.

No confidence, no placement probability, no fabricated completions, no
SQL / DB session / repository / callable / import path.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EvidenceType = Literal[
    "declared_preference",
    "verified_academic_evidence",
    "verified_m4_evidence",
    "mapped_subject_evidence",
    "inferred_from_subject",
    "not_verified",
    "unavailable",
]


class CareerPreference(BaseModel):
    """One self-declared career survey field (never an objective outcome)."""

    field: str
    value: Any | None = None
    evidence: EvidenceType = "declared_preference"

    model_config = ConfigDict(extra="forbid")


class CareerReadiness(BaseModel):
    """Verified M4 deterministic rule-based readiness (not a prediction)."""

    available: bool = False
    score: float | None = None
    level: str | None = None
    positive_factors: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    disclaimer: str | None = None

    model_config = ConfigDict(extra="forbid")


class DomainEvidenceItem(BaseModel):
    """Evidence-supported domain fit from the approved domain mapping."""

    domain: str
    matched_subjects: list[str] = Field(default_factory=list)
    matched_count: int = 0
    evidence: EvidenceType = "mapped_subject_evidence"
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


class RoleGuidance(BaseModel):
    """Declared dream role + controlled role-mapping availability."""

    declared_role: str | None = None
    declared_role_evidence: EvidenceType = "unavailable"
    mapping_available: bool = False
    note: str | None = None

    model_config = ConfigDict(extra="forbid")


class SkillEvidenceItem(BaseModel):
    """One skill-area label inferred from verified subject performance."""

    skill: str
    evidence: EvidenceType = "inferred_from_subject"
    source_subject: str | None = None
    detail: str | None = None

    model_config = ConfigDict(extra="forbid")


class SkillGapItem(BaseModel):
    """One domain subject-area with no verified evidence for the student."""

    skill_area: str
    evidence: EvidenceType = "not_verified"
    detail: str

    model_config = ConfigDict(extra="forbid")


class RoadmapItem(BaseModel):
    """One recommendation grounded in an identified gap. Never a tracker."""

    sequence: int
    focus_area: str
    current_evidence: str
    priority: Literal["High", "Medium", "Low"]
    recommended_step: str
    milestone: str
    next_action: str
    progress_tracking: Literal["available", "not_available"] = "not_available"
    evidence: EvidenceType

    model_config = ConfigDict(extra="forbid")


class LimitationItem(BaseModel):
    """An explicit honesty boundary for the advisory output."""

    kind: Literal["advisory", "inference", "missing_data", "not_tracked"]
    message: str

    model_config = ConfigDict(extra="forbid")


class StudentCareerCoachResult(BaseModel):
    """Combined career coach output for the authenticated student."""

    tool_name: str
    intent: str
    student_id: str
    data_available: bool
    career_preferences_available: bool = False
    career_preferences: list[CareerPreference] = Field(default_factory=list)
    career_readiness: CareerReadiness = Field(default_factory=CareerReadiness)
    domain_evidence: list[DomainEvidenceItem] = Field(default_factory=list)
    role_guidance: RoleGuidance = Field(default_factory=RoleGuidance)
    verified_skill_evidence: list[SkillEvidenceItem] = Field(default_factory=list)
    skill_gaps: list[SkillGapItem] = Field(default_factory=list)
    roadmap: list[RoadmapItem] = Field(default_factory=list)
    limitations: list[LimitationItem] = Field(default_factory=list)
    source: str
    generated_at: datetime
    note: str | None = None

    model_config = ConfigDict(extra="forbid")
