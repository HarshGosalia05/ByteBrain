import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.schemas.admin_notifications import (
    CreateAnnouncementRequest,
    CreateAnnouncementResponse,
    AdminAnnouncementsResponse,
    ExecutiveSummaryResponse,
)
from app.services.admin_service import AdminService


def run(coro):
    return asyncio.run(coro)


class TestAdminNotificationsService:

    def test_create_announcement_students(self):
        mock_admin_repo = MagicMock()
        mock_admin_repo.create_announcement = AsyncMock()
        admin_service = AdminService(pool=MagicMock())
        admin_service.repo = mock_admin_repo

        now = datetime.now()
        mock_admin_repo.create_announcement.return_value = {
            "announcement_id": "announcement:12345:6789",
            "title": "Semester Exam Schedule",
            "type": "ACADEMIC_NOTICE",
            "target_audience": "students",
            "recipients_notified": 80,
            "created_at": now,
        }

        req = CreateAnnouncementRequest(
            title="Semester Exam Schedule",
            message="Final exam schedule has been published.",
            type="ACADEMIC_NOTICE",
            target_audience="students",
            priority="High",
        )
        res = run(admin_service.create_announcement(req))

        assert isinstance(res, CreateAnnouncementResponse)
        assert res.announcement_id == "announcement:12345:6789"
        assert res.title == "Semester Exam Schedule"
        assert res.type == "ACADEMIC_NOTICE"
        assert res.recipients_notified == 80

        mock_admin_repo.create_announcement.assert_called_once_with(
            title="Semester Exam Schedule",
            message_body="Final exam schedule has been published.",
            message_type="ACADEMIC_NOTICE",
            target_audience="students",
            department_code=None,
            priority="High",
        )

    def test_get_admin_announcements_history(self):
        mock_admin_repo = MagicMock()
        mock_admin_repo.get_admin_announcements = AsyncMock()
        admin_service = AdminService(pool=MagicMock())
        admin_service.repo = mock_admin_repo

        now = datetime.now()
        mock_admin_repo.get_admin_announcements.return_value = [
            {
                "title": "Holiday Notice",
                "message": "Campus closed tomorrow.",
                "type": "HOLIDAY",
                "target_audience": "both",
                "priority": "Normal",
                "recipient_count": 92,
                "created_at": now,
            }
        ]

        res = run(admin_service.get_admin_announcements())

        assert isinstance(res, AdminAnnouncementsResponse)
        assert res.total_count == 1
        assert res.announcements[0].title == "Holiday Notice"
        assert res.announcements[0].recipient_count == 92

    def test_get_executive_summary(self):
        mock_admin_repo = MagicMock()
        mock_admin_repo.get_executive_summary = AsyncMock()
        admin_service = AdminService(pool=MagicMock())
        admin_service.repo = mock_admin_repo

        mock_admin_repo.get_executive_summary.return_value = {
            "strongest_department": {
                "department_code": 1,
                "department_name": "Computer Science and Engineering",
                "student_count": 40,
                "avg_cgpa": 8.25,
                "avg_percentage": 82.5,
            },
            "weakest_department": {
                "department_code": 2,
                "department_name": "Bachelor of Business Administration",
                "student_count": 40,
                "avg_cgpa": 7.10,
                "avg_percentage": 71.0,
            },
            "weakest_subject": {
                "subject_code": "SUB0001",
                "subject_name": "Data Structures",
                "avg_percentage": 58.4,
                "student_count": 40,
            },
            "attendance_concern_department": "Bachelor of Business Administration",
            "attendance_shortage_count": 12,
            "total_at_risk_students": 15,
            "high_risk_count": 10,
            "critical_risk_count": 5,
            "top_risk_department": "Computer Science and Engineering",
            "total_students": 80,
            "overall_avg_cgpa": 7.68,
            "overall_attendance_pct": 78.4,
            "internship_completion_rate": 62.5,
            "insights": [
                "Strongest Department: Computer Science and Engineering leads academic performance with an average CGPA of 8.25.",
                "Academic Focus Area: Data Structures (SUB0001) shows the lowest average score across enrollments (58.4%).",
                "Attendance Concern: Bachelor of Business Administration has the lowest attendance average, with 12 students below 75% threshold.",
                "Risk Early Warning: 15 students are currently flagged At-Risk (10 High Risk, 5 Critical Risk).",
                "Recommended Administrative Action: Prioritize academic counseling for high-risk students.",
            ],
        }

        res = run(admin_service.get_executive_summary())

        assert isinstance(res, ExecutiveSummaryResponse)
        assert res.total_students == 80
        assert res.strongest_department.department_name == "Computer Science and Engineering"
        assert res.weakest_subject.subject_code == "SUB0001"
        assert res.total_at_risk_students == 15
        assert len(res.insights) == 5
        assert "Computer Science and Engineering" in res.insights[0]
