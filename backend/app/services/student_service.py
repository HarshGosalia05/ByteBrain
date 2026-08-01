import asyncpg
from typing import Optional
from app.repositories.student_repo import StudentRepository
from app.schemas.student import StudentProfile, SemesterSummaryResponse, SubjectPerformanceResponse
from fastapi import HTTPException, status

class StudentService:
    def __init__(self, pool: asyncpg.Pool):
        self.repo = StudentRepository(pool)

    async def get_profile(self, student_id: str) -> StudentProfile:
        profile_data = await self.repo.get_student_profile(student_id)
        if not profile_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
        return StudentProfile(**profile_data)

    async def get_academic_summary(self, student_id: str) -> SemesterSummaryResponse:
        # Check if student exists first
        profile_data = await self.repo.get_student_profile(student_id)
        if not profile_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
            
        summaries = await self.repo.get_semester_summaries(student_id)
        return SemesterSummaryResponse(
            student_id=student_id,
            summaries=summaries
        )

    async def get_performance(self, student_id: str) -> SubjectPerformanceResponse:
        # Check if student exists first
        profile_data = await self.repo.get_student_profile(student_id)
        if not profile_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

        performance = await self.repo.get_subject_performance(student_id)
        return SubjectPerformanceResponse(
            student_id=student_id,
            performance=performance
        )
