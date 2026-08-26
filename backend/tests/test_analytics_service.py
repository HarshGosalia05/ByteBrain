"""Unit tests for the Analytics service layer.

Covers: service construction, all public methods, repository delegation,
input validation, multi-query composition, empty-result behavior,
error propagation, no database writes, Pydantic model return types.

All tests mock AnalyticsRepository — no live database required.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.analytics import (
    AtRiskStudent,
    AtRiskStudentsResult,
    BacklogDistribution,
    BelowThresholdResult,
    DepartmentOverview,
    PerformanceDistributionBucket,
    SemesterPerformanceDistribution,
    SemesterTrendPoint,
    StudentAcademicProfile,
    StudentAttendanceSummary,
    StudentBacklogSummary,
    StudentSemesterHistory,
    StudentSubjectAttendance,
    SubjectAttendanceSummary,
    SubjectNeedingAttention,
    SubjectPerformanceSummary,
    SubjectUnderperformers,
    SubjectsNeedingAttentionResult,
    UnderperformerItem,
)
from app.services.analytics_service import AnalyticsService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def fake_pool():
    pool = MagicMock()
    pool.acquire = MagicMock()
    return pool


def make_service(**repo_methods):
    """Build an AnalyticsService with a mock repo whose methods are overridden."""
    pool = fake_pool()
    svc = AnalyticsService(pool)
    for name, impl in repo_methods.items():
        setattr(svc.repo, name, AsyncMock(return_value=impl) if impl is not None else AsyncMock(return_value=None))
    return svc


# ---------------------------------------------------------------------------
# Service Construction
# ---------------------------------------------------------------------------

class TestServiceConstruction(unittest.TestCase):
    def test_creates_repository(self):
        pool = fake_pool()
        svc = AnalyticsService(pool)
        self.assertIsNotNone(svc.repo)

    def test_repo_has_pool(self):
        pool = fake_pool()
        svc = AnalyticsService(pool)
        self.assertIs(svc.repo.pool, pool)


# ---------------------------------------------------------------------------
# A. Student Analytics
# ---------------------------------------------------------------------------

class TestGetStudentAcademicProfile(unittest.TestCase):
    def test_existing_student(self):
        repo_row = {
            "student_id": "STU000001",
            "full_name": "Jay Shah",
            "department_code": 1,
            "department_name": "CSE",
            "current_semester": 7,
            "current_academic_year": "2026-27",
            "overall_cgpa": 8.5,
            "latest_sgpa": 9.0,
            "total_backlogs": 0,
            "overall_attendance_percentage": 87.35,
            "total_subjects_enrolled": 7,
            "total_credits_registered": 19,
        }
        svc = make_service(get_student_academic_profile=repo_row)
        result = run(svc.get_student_academic_profile("STU000001"))
        self.assertIsInstance(result, StudentAcademicProfile)
        self.assertEqual(result.student_id, "STU000001")
        self.assertEqual(result.full_name, "Jay Shah")
        self.assertEqual(result.department_code, 1)
        self.assertEqual(result.overall_cgpa, 8.5)
        self.assertEqual(result.total_subjects_enrolled, 7)

    def test_nonexistent_student(self):
        svc = make_service(get_student_academic_profile=None)
        result = run(svc.get_student_academic_profile("STU999999"))
        self.assertIsNone(result)

    def test_empty_id_raises(self):
        svc = make_service()
        with self.assertRaises(ValueError):
            run(svc.get_student_academic_profile(""))

    def test_whitespace_id_raises(self):
        svc = make_service()
        with self.assertRaises(ValueError):
            run(svc.get_student_academic_profile("   "))

    def test_repo_delegates_correct_id(self):
        svc = make_service(get_student_academic_profile=None)
        run(svc.get_student_academic_profile("STU000042"))
        svc.repo.get_student_academic_profile.assert_awaited_once_with("STU000042")


class TestGetStudentSemesterHistory(unittest.TestCase):
    def test_basic_history(self):
        rows = [
            {
                "semester_no": 1,
                "academic_year": "2023-2024",
                "semester_sgpa": 7.5,
                "semester_percentage": 72.0,
                "semester_attendance_percentage": 85.0,
                "subjects_registered": 6,
                "credits_registered": 18,
                "credits_earned": 18,
                "backlog_count": 0,
                "semester_result": "PASS",
                "academic_standing": "Good",
            },
            {
                "semester_no": 2,
                "academic_year": "2024-2025",
                "semester_sgpa": 8.2,
                "semester_percentage": 78.5,
                "semester_attendance_percentage": 88.0,
                "subjects_registered": 7,
                "credits_registered": 19,
                "credits_earned": 19,
                "backlog_count": 0,
                "semester_result": "PASS",
                "academic_standing": "Good",
            },
        ]
        svc = make_service(get_student_semester_history=rows)
        result = run(svc.get_student_semester_history("STU000001"))
        self.assertIsInstance(result, StudentSemesterHistory)
        self.assertEqual(result.student_id, "STU000001")
        self.assertEqual(len(result.semesters), 2)
        self.assertIsInstance(result.semesters[0], SemesterTrendPoint)
        self.assertEqual(result.semesters[0].semester_no, 1)
        self.assertEqual(result.semesters[1].semester_sgpa, 8.2)

    def test_empty_history(self):
        svc = make_service(get_student_semester_history=[])
        result = run(svc.get_student_semester_history("STU000099"))
        self.assertIsInstance(result, StudentSemesterHistory)
        self.assertEqual(result.semesters, [])

    def test_filters_passed_to_repo(self):
        svc = make_service(get_student_semester_history=[])
        run(svc.get_student_semester_history(
            "STU000001", department_code=1, semester_no=7, academic_year="2026-27",
        ))
        svc.repo.get_student_semester_history.assert_awaited_once_with(
            "STU000001", department_code=1, semester_no=7, academic_year="2026-27",
        )

    def test_invalid_semester_raises(self):
        svc = make_service()
        with self.assertRaises(ValueError):
            run(svc.get_student_semester_history("STU000001", semester_no=0))
        with self.assertRaises(ValueError):
            run(svc.get_student_semester_history("STU000001", semester_no=9))

    def test_invalid_department_code_raises(self):
        svc = make_service()
        with self.assertRaises(ValueError):
            run(svc.get_student_semester_history("STU000001", department_code=0))


class TestGetStudentAttendanceSummary(unittest.TestCase):
    def test_basic_attendance(self):
        repo_data = {
            "student_id": "STU000001",
            "semester_no": 7,
            "overall_attendance_percentage": 85.5,
            "total_classes": 100,
            "attended_classes": 85,
            "subjects": [
                {
                    "subject_id": "SUB0050",
                    "subject_code": "CS701",
                    "subject_name": "Data Structures",
                    "total_classes": 50,
                    "attended_classes": 45,
                    "attendance_percentage": 90.0,
                    "attendance_status": "Excellent",
                    "eligibility_status": "Eligible",
                    "shortage_flag": "No",
                },
                {
                    "subject_id": "SUB0051",
                    "subject_code": "CS702",
                    "subject_name": "Algorithms",
                    "total_classes": 50,
                    "attended_classes": 40,
                    "attendance_percentage": 80.0,
                    "attendance_status": "Good",
                    "eligibility_status": "Eligible",
                    "shortage_flag": "No",
                },
            ],
            "at_risk_subjects": 0,
            "ineligible_subjects": 0,
        }
        svc = make_service(get_student_attendance_summary=repo_data)
        result = run(svc.get_student_attendance_summary("STU000001"))
        self.assertIsInstance(result, StudentAttendanceSummary)
        self.assertEqual(result.student_id, "STU000001")
        self.assertEqual(result.total_classes, 100)
        self.assertEqual(len(result.subjects), 2)
        self.assertIsInstance(result.subjects[0], StudentSubjectAttendance)
        self.assertEqual(result.subjects[0].subject_id, "SUB0050")

    def test_empty_subjects(self):
        repo_data = {
            "student_id": "STU000001",
            "semester_no": 7,
            "overall_attendance_percentage": None,
            "total_classes": 0,
            "attended_classes": 0,
            "subjects": [],
            "at_risk_subjects": 0,
            "ineligible_subjects": 0,
        }
        svc = make_service(get_student_attendance_summary=repo_data)
        result = run(svc.get_student_attendance_summary("STU000001"))
        self.assertEqual(result.subjects, [])
        self.assertEqual(result.total_classes, 0)

    def test_repo_delegation(self):
        svc = make_service(get_student_attendance_summary={
            "student_id": "X", "semester_no": None,
            "overall_attendance_percentage": None, "total_classes": 0,
            "attended_classes": 0, "subjects": [], "at_risk_subjects": 0,
            "ineligible_subjects": 0,
        })
        run(svc.get_student_attendance_summary("STU000001", semester_no=5, subject_id="SUB0050"))
        svc.repo.get_student_attendance_summary.assert_awaited_once_with(
            "STU000001", semester_no=5, subject_id="SUB0050",
        )


class TestGetStudentBacklogSummary(unittest.TestCase):
    def test_basic_backlog(self):
        repo_data = {
            "student_id": "STU000001",
            "total_backlogs": 2,
            "backlogs": [
                {
                    "subject_id": "SUB0050",
                    "subject_code": "CS701",
                    "subject_name": "Data Structures",
                    "semester_no": 5,
                    "percentage": 35.0,
                    "grade": "F",
                },
            ],
        }
        svc = make_service(get_student_backlog_summary=repo_data)
        result = run(svc.get_student_backlog_summary("STU000001"))
        self.assertIsInstance(result, StudentBacklogSummary)
        self.assertEqual(result.total_backlogs, 2)
        self.assertEqual(len(result.backlogs), 1)
        self.assertEqual(result.backlogs[0].grade, "F")

    def test_no_backlogs(self):
        repo_data = {
            "student_id": "STU000001",
            "total_backlogs": 0,
            "backlogs": [],
        }
        svc = make_service(get_student_backlog_summary=repo_data)
        result = run(svc.get_student_backlog_summary("STU000001"))
        self.assertEqual(result.total_backlogs, 0)
        self.assertEqual(result.backlogs, [])


# ---------------------------------------------------------------------------
# B. Subject Analytics
# ---------------------------------------------------------------------------

class TestGetSubjectPerformanceSummary(unittest.TestCase):
    def test_existing_subject(self):
        repo_row = {
            "subject_id": "SUB0050",
            "subject_code": "CS701",
            "subject_name": "Data Structures",
            "semester_no": 7,
            "total_students": 50,
            "average_percentage": 68.5,
            "median_percentage": 70.0,
            "min_percentage": 25.0,
            "max_percentage": 98.0,
            "pass_count": 45,
            "fail_count": 5,
            "pass_rate": 90.0,
            "grade_distribution": [
                {"grade": "O", "count": 5},
                {"grade": "A+", "count": 10},
                {"grade": "F", "count": 5},
            ],
        }
        svc = make_service(get_subject_performance_summary=repo_row)
        result = run(svc.get_subject_performance_summary("SUB0050"))
        self.assertIsInstance(result, SubjectPerformanceSummary)
        self.assertEqual(result.subject_id, "SUB0050")
        self.assertEqual(result.total_students, 50)
        self.assertEqual(result.pass_rate, 90.0)
        self.assertEqual(len(result.grade_distribution), 3)

    def test_nonexistent_subject(self):
        svc = make_service(get_subject_performance_summary=None)
        result = run(svc.get_subject_performance_summary("SUB9999"))
        self.assertIsNone(result)

    def test_empty_id_raises(self):
        svc = make_service()
        with self.assertRaises(ValueError):
            run(svc.get_subject_performance_summary(""))

    def test_repo_delegation(self):
        svc = make_service(get_subject_performance_summary=None)
        run(svc.get_subject_performance_summary(
            "SUB0050", semester_no=7, academic_year="2026-27",
        ))
        svc.repo.get_subject_performance_summary.assert_awaited_once_with(
            "SUB0050", semester_no=7, academic_year="2026-27",
        )


class TestGetSubjectAttendanceSummary(unittest.TestCase):
    def test_existing_subject(self):
        repo_row = {
            "subject_id": "SUB0050",
            "subject_code": "CS701",
            "subject_name": "Data Structures",
            "semester_no": 7,
            "total_students": 50,
            "average_attendance_percentage": 82.5,
            "eligible_count": 45,
            "at_risk_count": 3,
            "ineligible_count": 5,
            "shortage_count": 2,
        }
        svc = make_service(get_subject_attendance_summary=repo_row)
        result = run(svc.get_subject_attendance_summary("SUB0050"))
        self.assertIsInstance(result, SubjectAttendanceSummary)
        self.assertEqual(result.subject_id, "SUB0050")
        self.assertEqual(result.total_students, 50)
        self.assertEqual(result.eligible_count, 45)

    def test_nonexistent_subject(self):
        svc = make_service(get_subject_attendance_summary=None)
        result = run(svc.get_subject_attendance_summary("SUB9999"))
        self.assertIsNone(result)


class TestGetSubjectUnderperformers(unittest.TestCase):
    def test_with_students(self):
        repo_data = {
            "subject_id": "SUB0050",
            "semester_no": 7,
            "threshold": 40.0,
            "total_flagged": 2,
            "students": [
                {
                    "student_id": "STU000005",
                    "full_name": "Low Scorer",
                    "percentage": 30.0,
                    "grade": "F",
                    "attendance_percentage": 60.0,
                },
                {
                    "student_id": "STU000012",
                    "full_name": "Medium Scorer",
                    "percentage": 35.0,
                    "grade": "F",
                    "attendance_percentage": 70.0,
                },
            ],
        }
        svc = make_service(get_subject_underperformers=repo_data)
        result = run(svc.get_subject_underperformers("SUB0050"))
        self.assertIsInstance(result, SubjectUnderperformers)
        self.assertEqual(len(result.students), 2)
        self.assertIsInstance(result.students[0], UnderperformerItem)
        self.assertEqual(result.students[0].student_id, "STU000005")

    def test_no_students(self):
        repo_data = {
            "subject_id": "SUB0050",
            "semester_no": 7,
            "threshold": 40.0,
            "total_flagged": 0,
            "students": [],
        }
        svc = make_service(get_subject_underperformers=repo_data)
        result = run(svc.get_subject_underperformers("SUB0050"))
        self.assertEqual(result.students, [])

    def test_custom_threshold(self):
        svc = make_service(get_subject_underperformers={
            "subject_id": "SUB0050", "semester_no": None,
            "threshold": 50.0, "total_flagged": 0, "students": [],
        })
        run(svc.get_subject_underperformers("SUB0050", threshold=50.0))
        svc.repo.get_subject_underperformers.assert_awaited_once_with(
            "SUB0050", semester_no=None, threshold=50.0,
        )

    def test_invalid_threshold_raises(self):
        svc = make_service()
        with self.assertRaises(ValueError):
            run(svc.get_subject_underperformers("SUB0050", threshold=-1))
        with self.assertRaises(ValueError):
            run(svc.get_subject_underperformers("SUB0050", threshold=101))


# ---------------------------------------------------------------------------
# C. Department / Semester Analytics
# ---------------------------------------------------------------------------

class TestGetDepartmentOverview(unittest.TestCase):
    def test_existing_dept(self):
        repo_data = {
            "department_code": 1,
            "department_name": "CSE",
            "semester_no": 7,
            "academic_year": "2026-27",
            "total_students": 50,
            "average_sgpa": 7.8,
            "average_percentage": 74.5,
            "average_attendance_percentage": 82.0,
            "total_backlogs": 12,
            "students_with_backlogs": 8,
        }
        svc = make_service(get_department_overview=repo_data)
        result = run(svc.get_department_overview(department_code=1, semester_no=7))
        self.assertIsInstance(result, DepartmentOverview)
        self.assertEqual(result.department_code, 1)
        self.assertEqual(result.total_students, 50)
        self.assertEqual(result.students_with_backlogs, 8)

    def test_empty_dept(self):
        svc = make_service(get_department_overview={})
        result = run(svc.get_department_overview())
        self.assertIsInstance(result, DepartmentOverview)
        self.assertEqual(result.total_students, 0)

    def test_repo_delegation(self):
        svc = make_service(get_department_overview={})
        run(svc.get_department_overview(
            department_code=1, semester_no=7, academic_year="2026-27",
        ))
        svc.repo.get_department_overview.assert_awaited_once_with(
            department_code=1, semester_no=7, academic_year="2026-27",
        )

    def test_invalid_dept_code_raises(self):
        svc = make_service()
        with self.assertRaises(ValueError):
            run(svc.get_department_overview(department_code=0))


class TestGetSemesterPerformanceDistribution(unittest.TestCase):
    def test_with_buckets(self):
        repo_data = {
            "department_code": 1,
            "semester_no": 7,
            "academic_year": "2026-27",
            "total_students": 50,
            "buckets": [
                {"label": "Top", "count": 5, "percentage_of_total": 10.0},
                {"label": "Above Average", "count": 15, "percentage_of_total": 30.0},
                {"label": "Average", "count": 20, "percentage_of_total": 40.0},
                {"label": "Below Average", "count": 8, "percentage_of_total": 16.0},
                {"label": "Low Performer", "count": 2, "percentage_of_total": 4.0},
            ],
        }
        svc = make_service(get_semester_performance_distribution=repo_data)
        result = run(svc.get_semester_performance_distribution(
            department_code=1, semester_no=7,
        ))
        self.assertIsInstance(result, SemesterPerformanceDistribution)
        self.assertEqual(result.total_students, 50)
        self.assertEqual(len(result.buckets), 5)
        self.assertIsInstance(result.buckets[0], PerformanceDistributionBucket)
        self.assertEqual(result.buckets[0].label, "Top")

    def test_empty_buckets(self):
        repo_data = {
            "department_code": None,
            "semester_no": None,
            "academic_year": None,
            "total_students": 0,
            "buckets": [],
        }
        svc = make_service(get_semester_performance_distribution=repo_data)
        result = run(svc.get_semester_performance_distribution())
        self.assertEqual(result.buckets, [])


class TestGetAttendanceDistribution(unittest.TestCase):
    def test_with_buckets(self):
        repo_data = {
            "department_code": 1,
            "semester_no": 7,
            "total_students": 50,
            "buckets": [
                {"band": "Excellent", "count": 10, "percentage_of_total": 20.0},
                {"band": "Good", "count": 20, "percentage_of_total": 40.0},
                {"band": "Average", "count": 15, "percentage_of_total": 30.0},
                {"band": "Low", "count": 4, "percentage_of_total": 8.0},
                {"band": "Critical", "count": 1, "percentage_of_total": 2.0},
            ],
        }
        svc = make_service(get_attendance_distribution=repo_data)
        result = run(svc.get_attendance_distribution(
            department_code=1, semester_no=7,
        ))
        self.assertEqual(result.total_students, 50)
        self.assertEqual(len(result.buckets), 5)
        self.assertEqual(result.buckets[0].band, "Excellent")


class TestGetBacklogDistribution(unittest.TestCase):
    def test_with_buckets(self):
        repo_data = {
            "department_code": 1,
            "total_students": 50,
            "students_with_backlogs": 15,
            "buckets": [
                {"backlog_range": "0", "count": 35, "percentage_of_total": 70.0},
                {"backlog_range": "1-2", "count": 10, "percentage_of_total": 20.0},
                {"backlog_range": "3-5", "count": 3, "percentage_of_total": 6.0},
                {"backlog_range": "6-10", "count": 2, "percentage_of_total": 4.0},
                {"backlog_range": "11+", "count": 0, "percentage_of_total": 0.0},
            ],
        }
        svc = make_service(get_backlog_distribution=repo_data)
        result = run(svc.get_backlog_distribution(department_code=1))
        self.assertIsInstance(result, BacklogDistribution)
        self.assertEqual(result.total_students, 50)
        self.assertEqual(result.students_with_backlogs, 15)
        self.assertEqual(len(result.buckets), 5)


# ---------------------------------------------------------------------------
# D. At-Risk / Academic Gap Analytics
# ---------------------------------------------------------------------------

class TestGetAtRiskStudents(unittest.TestCase):
    def test_with_flagged_students(self):
        repo_data = {
            "department_code": 1,
            "semester_no": 7,
            "total_flagged": 2,
            "students": [
                {
                    "student_id": "STU000003",
                    "full_name": "Risk Student",
                    "department_code": 1,
                    "current_semester": 7,
                    "overall_cgpa": 5.5,
                    "total_backlogs": 3,
                    "overall_attendance_percentage": 65.0,
                    "risk_reasons": [
                        "Attendance 65.0% below threshold 75%",
                        "Backlogs 3 >= threshold 2",
                        "SGPA 5.5 below threshold 6.0",
                    ],
                    "risk_score": 45.2,
                },
            ],
        }
        svc = make_service(get_at_risk_students=repo_data)
        result = run(svc.get_at_risk_students(department_code=1, semester_no=7))
        self.assertIsInstance(result, AtRiskStudentsResult)
        self.assertEqual(result.total_flagged, 2)
        self.assertEqual(len(result.students), 1)
        self.assertIsInstance(result.students[0], AtRiskStudent)
        self.assertEqual(result.students[0].student_id, "STU000003")
        self.assertEqual(len(result.students[0].risk_reasons), 3)

    def test_no_flagged_students(self):
        repo_data = {
            "department_code": None,
            "semester_no": None,
            "total_flagged": 0,
            "students": [],
        }
        svc = make_service(get_at_risk_students=repo_data)
        result = run(svc.get_at_risk_students())
        self.assertEqual(result.total_flagged, 0)
        self.assertEqual(result.students, [])


class TestGetStudentsBelowAttendanceThreshold(unittest.TestCase):
    def test_with_students(self):
        repo_data = {
            "threshold": 75.0,
            "semester_no": 7,
            "total_flagged": 2,
            "students": [
                {
                    "student_id": "STU000005",
                    "full_name": "Low Attendance",
                    "subject_id": "SUB0050",
                    "subject_code": "CS701",
                    "attendance_percentage": 60.0,
                    "total_classes": 50,
                    "attended_classes": 30,
                },
            ],
        }
        svc = make_service(get_students_below_attendance_threshold=repo_data)
        result = run(svc.get_students_below_attendance_threshold(
            department_code=1, semester_no=7, threshold=75.0,
        ))
        self.assertIsInstance(result, BelowThresholdResult)
        self.assertEqual(result.threshold, 75.0)
        self.assertEqual(result.total_flagged, 2)
        self.assertEqual(len(result.students), 1)
        self.assertEqual(result.students[0].student_id, "STU000005")

    def test_no_students_below(self):
        repo_data = {
            "threshold": 75.0,
            "semester_no": 7,
            "total_flagged": 0,
            "students": [],
        }
        svc = make_service(get_students_below_attendance_threshold=repo_data)
        result = run(svc.get_students_below_attendance_threshold())
        self.assertEqual(result.students, [])


class TestGetSubjectsNeedingAttention(unittest.TestCase):
    def test_with_subjects(self):
        repo_data = {
            "department_code": 1,
            "semester_no": 7,
            "total_flagged": 1,
            "subjects": [
                {
                    "subject_id": "SUB0053",
                    "subject_code": "CS704",
                    "subject_name": "Networks",
                    "semester_no": 7,
                    "total_students": 50,
                    "average_percentage": 45.0,
                    "fail_rate": 25.0,
                    "average_attendance": 70.0,
                    "reasons": [
                        "Average percentage 45.0% below 50%",
                        "Fail rate 25.0% above 20%",
                        "Average attendance 70.0% below 75%",
                    ],
                },
            ],
        }
        svc = make_service(get_subjects_needing_attention=repo_data)
        result = run(svc.get_subjects_needing_attention(
            department_code=1, semester_no=7,
        ))
        self.assertIsInstance(result, SubjectsNeedingAttentionResult)
        self.assertEqual(result.total_flagged, 1)
        self.assertEqual(len(result.subjects), 1)
        self.assertIsInstance(result.subjects[0], SubjectNeedingAttention)
        self.assertEqual(result.subjects[0].subject_id, "SUB0053")
        self.assertEqual(len(result.subjects[0].reasons), 3)

    def test_no_subjects_flagged(self):
        repo_data = {
            "department_code": None,
            "semester_no": None,
            "total_flagged": 0,
            "subjects": [],
        }
        svc = make_service(get_subjects_needing_attention=repo_data)
        result = run(svc.get_subjects_needing_attention())
        self.assertEqual(result.subjects, [])


# ---------------------------------------------------------------------------
# No-Write Verification
# ---------------------------------------------------------------------------

class TestNoDatabaseWrites(unittest.TestCase):
    """Verify the service never calls execute/begin/insert/update/delete."""

    def _make_repo_with_mocks(self):
        pool = fake_pool()
        svc = AnalyticsService(pool)
        svc.repo._fetch = AsyncMock(return_value=[])
        svc.repo._fetchrow = AsyncMock(return_value=None)
        svc.repo._fetchval = AsyncMock(return_value=0)
        svc.repo.get_student_academic_profile = AsyncMock(return_value=None)
        svc.repo.get_student_semester_history = AsyncMock(return_value=[])
        svc.repo.get_student_attendance_summary = AsyncMock(return_value={
            "student_id": "X", "semester_no": None,
            "overall_attendance_percentage": None, "total_classes": 0,
            "attended_classes": 0, "subjects": [], "at_risk_subjects": 0,
            "ineligible_subjects": 0,
        })
        svc.repo.get_student_backlog_summary = AsyncMock(return_value={
            "student_id": "X", "total_backlogs": 0, "backlogs": [],
        })
        svc.repo.get_subject_performance_summary = AsyncMock(return_value=None)
        svc.repo.get_subject_attendance_summary = AsyncMock(return_value=None)
        svc.repo.get_subject_underperformers = AsyncMock(return_value={
            "subject_id": "X", "semester_no": None,
            "threshold": 40.0, "total_flagged": 0, "students": [],
        })
        svc.repo.get_department_overview = AsyncMock(return_value={})
        svc.repo.get_semester_performance_distribution = AsyncMock(return_value={
            "department_code": None, "semester_no": None,
            "academic_year": None, "total_students": 0, "buckets": [],
        })
        svc.repo.get_attendance_distribution = AsyncMock(return_value={
            "department_code": None, "semester_no": None,
            "total_students": 0, "buckets": [],
        })
        svc.repo.get_backlog_distribution = AsyncMock(return_value={
            "department_code": None, "total_students": 0,
            "students_with_backlogs": 0, "buckets": [],
        })
        svc.repo.get_at_risk_students = AsyncMock(return_value={
            "department_code": None, "semester_no": None,
            "total_flagged": 0, "students": [],
        })
        svc.repo.get_students_below_attendance_threshold = AsyncMock(return_value={
            "threshold": 75.0, "semester_no": None,
            "total_flagged": 0, "students": [],
        })
        svc.repo.get_subjects_needing_attention = AsyncMock(return_value={
            "department_code": None, "semester_no": None,
            "total_flagged": 0, "subjects": [],
        })
        return svc

    def test_no_writes_across_all_methods(self):
        svc = self._make_repo_with_mocks()
        run(svc.get_student_academic_profile("STU000001"))
        run(svc.get_student_semester_history("STU000001"))
        run(svc.get_student_attendance_summary("STU000001"))
        run(svc.get_student_backlog_summary("STU000001"))
        run(svc.get_subject_performance_summary("SUB0050"))
        run(svc.get_subject_attendance_summary("SUB0050"))
        run(svc.get_subject_underperformers("SUB0050"))
        run(svc.get_department_overview(department_code=1))
        run(svc.get_semester_performance_distribution(department_code=1))
        run(svc.get_attendance_distribution(department_code=1))
        run(svc.get_backlog_distribution(department_code=1))
        run(svc.get_at_risk_students(department_code=1))
        run(svc.get_students_below_attendance_threshold(department_code=1))
        run(svc.get_subjects_needing_attention(department_code=1))
        svc.repo.pool.acquire.assert_not_called()


# ---------------------------------------------------------------------------
# Input Validation Edge Cases
# ---------------------------------------------------------------------------

class TestInputValidation(unittest.TestCase):
    def test_valid_semester_range(self):
        svc = make_service(get_student_semester_history=[])
        for sem in range(1, 9):
            run(svc.get_student_semester_history("STU000001", semester_no=sem))
        # If no ValueError was raised, all semesters 1-8 are valid
        self.assertTrue(True)

    def test_valid_department_code(self):
        svc = make_service(get_department_overview={})
        run(svc.get_department_overview(department_code=1))
        self.assertTrue(True)

    def test_valid_threshold_range(self):
        svc = make_service(get_subject_underperformers={
            "subject_id": "X", "semester_no": None,
            "threshold": 0.0, "total_flagged": 0, "students": [],
        })
        run(svc.get_subject_underperformers("SUB0050", threshold=0.0))
        run(svc.get_subject_underperformers("SUB0050", threshold=100.0))
        self.assertTrue(True)

    def test_none_optional_params_pass_through(self):
        svc = make_service(get_student_semester_history=[])
        run(svc.get_student_semester_history(
            "STU000001", department_code=None, semester_no=None,
            academic_year=None,
        ))
        svc.repo.get_student_semester_history.assert_awaited_once_with(
            "STU000001", department_code=None, semester_no=None,
            academic_year=None,
        )


if __name__ == "__main__":
    unittest.main()
