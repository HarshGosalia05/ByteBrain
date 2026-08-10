import asyncpg
from typing import Optional
from app.repositories.student_repo import StudentRepository
from app.schemas.student import (
    StudentProfile,
    AcademicOverview,
    SemesterSummaryResponse,
    SubjectPerformanceResponse,
)
from app.schemas.student_analytics import (
    AttemptHistoryItem,
    BenchmarkItem,
    LearningGapItem,
    NeedsAttentionItem,
    PerformanceTrends,
    StrengthItem,
    StudentAnalyticsResponse,
    WhatIfResponse,
)
from app.services.student_analytics_rules import (
    compute_attempt_history,
    compute_benchmark,
    compute_learning_gaps,
    compute_needs_attention,
    compute_strengths,
    compute_trends,
)
from app.services.faculty_service import derive_marks_fields
from fastapi import HTTPException, status


class StudentService:
    def __init__(self, pool: asyncpg.Pool):
        self.repo = StudentRepository(pool)

    async def get_profile(self, student_id: str) -> StudentProfile:
        profile_data = await self.repo.get_student_profile(student_id)
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found"
            )
        return StudentProfile(**profile_data)

    async def get_academic_summary(self, student_id: str) -> SemesterSummaryResponse:
        # Check if student exists first
        profile_data = await self.repo.get_student_profile(student_id)
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found"
            )

        summaries = await self.repo.get_semester_summaries(student_id)
        overview = AcademicOverview(
            current_semester=profile_data.get("current_semester"),
            current_academic_year=profile_data.get("current_academic_year"),
            latest_sgpa=profile_data.get("latest_sgpa"),
            overall_cgpa=profile_data.get("overall_cgpa"),
            overall_percentage=profile_data.get("overall_percentage"),
            total_credits_registered=profile_data.get("total_credits_registered"),
            total_credits_earned=profile_data.get("total_credits_earned"),
            total_backlogs=profile_data.get("total_backlogs"),
            academic_standing=profile_data.get("academic_standing"),
        )
        return SemesterSummaryResponse(
            student_id=student_id,
            overview=overview,
            summaries=summaries,
        )

    async def get_performance(
        self, student_id: str, semester: Optional[int] = None
    ) -> SubjectPerformanceResponse:
        # Check if student exists first
        profile_data = await self.repo.get_student_profile(student_id)
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found"
            )

        performance = await self.repo.get_subject_performance(student_id, semester)
        return SubjectPerformanceResponse(
            student_id=student_id,
            performance=performance,
        )

    async def get_analytics(self, student_id: str) -> StudentAnalyticsResponse:
        """MD-03 deterministic performance analytics (read-only, no writes)."""
        profile_data = await self.repo.get_student_profile(student_id)
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found"
            )

        summaries = await self.repo.get_semester_summaries(student_id)
        performance = await self.repo.get_subject_performance(student_id)

        subject_ids = sorted(
            {row["subject_id"] for row in performance if row.get("percentage") is not None}
        )
        department_code = profile_data.get("department_code")
        class_averages = []
        if subject_ids and department_code:
            class_averages = await self.repo.get_class_benchmark_averages(
                department_code, student_id, subject_ids
            )

        return StudentAnalyticsResponse(
            student_id=student_id,
            trends=PerformanceTrends(**compute_trends(summaries)),
            strengths=[StrengthItem(**item) for item in compute_strengths(performance)],
            needs_attention=[
                NeedsAttentionItem(**item) for item in compute_needs_attention(performance)
            ],
            learning_gaps=[
                LearningGapItem(**item) for item in compute_learning_gaps(performance)
            ],
            class_benchmark=[
                BenchmarkItem(**item) for item in compute_benchmark(performance, class_averages)
            ],
            attempt_history=[
                AttemptHistoryItem(**item) for item in compute_attempt_history(performance)
            ],
        )

    def simulate_marks(
        self,
        internal_marks: Optional[int],
        mid_sem_marks: Optional[int],
        end_sem_marks: Optional[int],
    ) -> WhatIfResponse:
        """MD-03 marks simulator.

        Purely a simulation — reuses the exact canonical derivation used by
        Faculty (``derive_marks_fields``) and never touches the database.
        """
        derived = derive_marks_fields(internal_marks, mid_sem_marks, end_sem_marks)
        complete = all(
            value is not None for value in (internal_marks, mid_sem_marks, end_sem_marks)
        )
        return WhatIfResponse(
            internal_marks=internal_marks,
            mid_sem_marks=mid_sem_marks,
            end_sem_marks=end_sem_marks,
            complete=complete,
            total_marks=derived["total_marks"],
            percentage=derived["percentage"],
            grade=derived["grade"],
            grade_point=derived["grade_point"],
            result_status=derived["result_status"],
            performance_category=derived["performance_category"],
        )