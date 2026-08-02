import asyncpg
from typing import List, Optional
from app.core.config import settings
from app.repositories.faculty_repo import FacultyRepository
from app.schemas.faculty import (
    FacultyProfile,
    FacultyProfileUpdate,
    FacultyDashboardSummary,
    DashboardSubjectSummary,
    NeedsAttentionItem,
)
from fastapi import HTTPException, status

class FacultyService:
    def __init__(self, pool: asyncpg.Pool):
        self.repo = FacultyRepository(pool)

    async def get_profile(self, faculty_id: str) -> FacultyProfile:
        profile_data = await self.repo.get_faculty_profile(faculty_id)
        if not profile_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty profile not found")
        return FacultyProfile(**profile_data)

    async def update_profile(self, faculty_id: str, update: FacultyProfileUpdate) -> FacultyProfile:
        existing = await self.repo.get_faculty_profile(faculty_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty profile not found")

        profile_data = await self.repo.update_faculty_contact(
            faculty_id,
            email=update.email,
            phone_number=update.phone_number,
        )
        if not profile_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty profile not found")
        return FacultyProfile(**profile_data)

    def _average(self, values: List[Optional[float]]) -> Optional[float]:
        present = [v for v in values if v is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 2)

    async def get_dashboard_summary(self, faculty_id: str) -> FacultyDashboardSummary:
        profile_data = await self.repo.get_faculty_profile(faculty_id)
        if not profile_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty profile not found")

        term = await self.repo.get_current_term(faculty_id)
        mentees = await self.repo.get_mentee_count(faculty_id)

        if not term:
            return FacultyDashboardSummary(
                faculty_id=faculty_id,
                full_name=profile_data["full_name"],
                designation=profile_data.get("designation"),
                department_name=profile_data.get("department_name"),
                semester_no=None,
                academic_year=None,
                subjects=0,
                students=0,
                mentees=mentees,
                average_attendance=None,
                average_performance=None,
                subject_breakdown=[],
                needs_attention=[],
            )

        semester_no = term["semester_no"]
        overview = await self.repo.get_term_overview(faculty_id, semester_no)
        breakdown_rows = await self.repo.get_term_subjects(faculty_id, semester_no)

        subject_breakdown = [
            DashboardSubjectSummary(
                subject_id=row["subject_id"],
                subject_code=row["subject_code"],
                subject_name=row["subject_name"],
                credits=row.get("credits"),
                students=int(row["students"]),
                average_attendance=float(row["average_attendance"]) if row.get("average_attendance") is not None else None,
                average_performance=float(row["average_performance"]) if row.get("average_performance") is not None else None,
            )
            for row in breakdown_rows
        ]

        needs_attention: List[NeedsAttentionItem] = []
        for subject in subject_breakdown:
            flags = []
            if subject.average_performance is not None and subject.average_performance < settings.FACULTY_PERFORMANCE_THRESHOLD:
                flags.append("performance")
            if subject.average_attendance is not None and subject.average_attendance < settings.FACULTY_ATTENDANCE_THRESHOLD:
                flags.append("attendance")
            if flags:
                needs_attention.append(
                    NeedsAttentionItem(
                        subject_id=subject.subject_id,
                        subject_code=subject.subject_code,
                        subject_name=subject.subject_name,
                        flags=flags,
                        average_attendance=subject.average_attendance,
                        average_performance=subject.average_performance,
                    )
                )

        return FacultyDashboardSummary(
            faculty_id=faculty_id,
            full_name=profile_data["full_name"],
            designation=profile_data.get("designation"),
            department_name=profile_data.get("department_name"),
            semester_no=semester_no,
            academic_year=term["academic_year"],
            subjects=int(overview["subjects"]),
            students=int(overview["students"]),
            mentees=mentees,
            average_attendance=self._average([s.average_attendance for s in subject_breakdown]),
            average_performance=self._average([s.average_performance for s in subject_breakdown]),
            subject_breakdown=subject_breakdown,
            needs_attention=needs_attention,
        )
