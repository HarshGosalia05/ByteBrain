from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


class CareerComponent(BaseModel):
    available: bool
    score: Optional[float] = None
    weight: float
    reason: str


class CareerReadinessResponse(BaseModel):
    student_id: str
    available: bool
    score: Optional[float] = None
    band: Optional[str] = None
    preferred_domain: Optional[str] = None
    dream_job_role: Optional[str] = None
    components: Dict[str, CareerComponent]
    reasons: List[str]
    generated_at: datetime


class CareerAlignmentSubject(BaseModel):
    subject_id: str
    subject_code: Optional[str] = None
    subject_name: str
    semester: Optional[int] = None
    percentage: Optional[float] = None
    relevant: bool
    reason: str


class CareerAlignmentResponse(BaseModel):
    student_id: str
    preferred_domain: Optional[str] = None
    dream_job_role: Optional[str] = None
    available: bool
    score: Optional[float] = None
    band: Optional[str] = None
    aligned_subjects: List[CareerAlignmentSubject]
    other_subjects: List[CareerAlignmentSubject]
    aligned_count: int
    total_completed: int
    generated_at: datetime
