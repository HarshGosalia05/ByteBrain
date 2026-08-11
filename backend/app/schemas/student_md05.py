from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


class HealthComponent(BaseModel):
    available: bool
    score: Optional[float] = None
    weight: float
    reason: str


class HealthScoreResponse(BaseModel):
    student_id: str
    available: bool
    score: Optional[float] = None
    band: Optional[str] = None
    components: Dict[str, HealthComponent]
    reasons: List[str]
    generated_at: datetime


class PriorityItem(BaseModel):
    rank: int
    signal: str
    severity: int
    title: str
    reason: str
    action: str
    subject: Optional[str] = None
    metric: Optional[str] = None


class PrioritiesResponse(BaseModel):
    student_id: str
    items: List[PriorityItem]


class StudentGoal(BaseModel):
    goal_id: str
    goal_type: str
    target_value: float
    current_value: Optional[float] = None
    achieved: Optional[bool] = None
    status: str
    created_at: datetime
    updated_at: datetime


class GoalsResponse(BaseModel):
    student_id: str
    goals: List[StudentGoal]


class GoalCreate(BaseModel):
    goal_type: Literal["target_sgpa", "target_percentage", "target_attendance"]
    target_value: float


class GoalUpdate(BaseModel):
    target_value: Optional[float] = None
    status: Optional[Literal["Active", "Inactive"]] = None


class NotificationItem(BaseModel):
    message_id: str
    message_type: str
    title: str
    message_body: str
    subject: Optional[str] = None
    priority: str
    status: str
    created_at: datetime


class NotificationsResponse(BaseModel):
    student_id: str
    items: List[NotificationItem]
    total: int
    page: int
    page_size: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    student_id: str
    unread_count: int


class MarkAllReadResponse(BaseModel):
    student_id: str
    updated_count: int


class ClearAllResponse(BaseModel):
    student_id: str
    cleared_count: int
