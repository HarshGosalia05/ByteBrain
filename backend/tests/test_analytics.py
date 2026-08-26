"""Unit tests for the Analytics query layer.

Covers: A (student), B (subject), C (department/semester), D (at-risk).
All tests mock asyncpg — no live database required.

Verifies:
  - Correct SQL query execution (parameterized, read-only)
  - Correct result shaping / aggregation
  - Filtering (student, subject, semester, department, academic_year)
  - Empty-result behavior
  - Invalid/nonexistent ID handling
  - No database writes
  - Threshold/rule classification logic
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.repositories.analytics_repo import AnalyticsRepository


# ---------------------------------------------------------------------------
# Mock Helpers
# ---------------------------------------------------------------------------

class FakeRecord(dict):
    """Lightweight stand-in for an asyncpg Record."""
    pass


def make_pool(fetch_seq=None, fetchval_seq=None, fetchrow_seq=None):
    """Build a mock asyncpg.Pool with sequential canned responses.

    Each call to ``pool.acquire()`` yields a context-manager whose conn
    returns the next item from the corresponding sequence.
    """
    fetch_iter = iter(fetch_seq or [])
    fetchval_iter = iter(fetchval_seq or [])
    fetchrow_iter = iter(fetchrow_seq or [])

    conn = AsyncMock()

    async def _fetch(query, *args, **kwargs):
        return next(fetch_iter, [])

    async def _fetchval(query, *args, **kwargs):
        return next(fetchval_iter, None)

    async def _fetchrow(query, *args, **kwargs):
        return next(fetchrow_iter, None)

    conn.fetch = AsyncMock(side_effect=_fetch)
    conn.fetchval = AsyncMock(side_effect=_fetchval)
    conn.fetchrow = AsyncMock(side_effect=_fetchrow)
    conn.execute = AsyncMock(return_value="UPDATE 0")

    class _Ctx:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, *a):
            pass

    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=_Ctx())
    return pool, conn


# ---------------------------------------------------------------------------
# A. Student Analytics
# ---------------------------------------------------------------------------

class TestStudentAcademicProfile(unittest.TestCase):
    def test_existing_student(self):
        profile = FakeRecord(
            student_id="STU000001",
            full_name="Jay Shah",
            department_code=1,
            department_name="CSE",
            current_semester=7,
            current_academic_year="2026-27",
            overall_cgpa=8.5,
            latest_sgpa=9.0,
            total_backlogs=0,
            overall_attendance_percentage=87.35,
            total_subjects_enrolled=7,
            total_credits_registered=19,
        )
        pool, conn = make_pool(fetchrow_seq=[profile])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_student_academic_profile("STU000001")
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["student_id"], "STU000001")
        self.assertEqual(result["full_name"], "Jay Shah")
        self.assertEqual(result["total_subjects_enrolled"], 7)
        # Verify parameterized query was called
        conn.fetchrow.assert_called_once()
        call_args = conn.fetchrow.call_args
        self.assertIn("$1", call_args[0][0])

    def test_nonexistent_student(self):
        pool, conn = make_pool(fetchrow_seq=[None])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_student_academic_profile("STU999999")
        )
        self.assertIsNone(result)

    def test_no_writes(self):
        pool, conn = make_pool(fetchrow_seq=[None])
        repo = AnalyticsRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.get_student_academic_profile("STU000001")
        )
        conn.execute.assert_not_called()


class TestStudentSemesterHistory(unittest.TestCase):
    def test_basic_history(self):
        semesters = [
            FakeRecord(
                semester_no=1, academic_year="2023-2024",
                semester_sgpa=7.5, semester_percentage=72.0,
                semester_attendance_percentage=85.0,
                subjects_registered=6, credits_registered=18,
                credits_earned=18, backlog_count=0,
                semester_result="PASS", academic_standing="Good",
            ),
            FakeRecord(
                semester_no=2, academic_year="2024-2025",
                semester_sgpa=8.2, semester_percentage=78.5,
                semester_attendance_percentage=88.0,
                subjects_registered=7, credits_registered=19,
                credits_earned=19, backlog_count=0,
                semester_result="PASS", academic_standing="Good",
            ),
        ]
        pool, conn = make_pool(fetch_seq=[semesters])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_student_semester_history("STU000001")
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["semester_no"], 1)
        self.assertEqual(result[1]["semester_sgpa"], 8.2)

    def test_semester_filter(self):
        pool, conn = make_pool(fetch_seq=[[]])
        repo = AnalyticsRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.get_student_semester_history(
                "STU000001", semester_no=7
            )
        )
        call_args = conn.fetch.call_args
        query = call_args[0][0]
        self.assertIn("$3::int IS NULL OR sem.semester_no = $3", query)
        self.assertEqual(call_args[0][3], 7)

    def test_department_filter(self):
        pool, conn = make_pool(fetch_seq=[[]])
        repo = AnalyticsRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.get_student_semester_history(
                "STU000001", department_code=1
            )
        )
        call_args = conn.fetch.call_args
        self.assertEqual(call_args[0][2], 1)

    def test_empty_history(self):
        pool, conn = make_pool(fetch_seq=[[]])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_student_semester_history("STU000099")
        )
        self.assertEqual(result, [])


class TestStudentAttendanceSummary(unittest.TestCase):
    def test_aggregation(self):
        subjects = [
            FakeRecord(
                subject_id="SUB0050", subject_code="CS701",
                subject_name="Data Structures",
                total_classes=27, attended_classes=22,
                attendance_percentage=81.48,
                attendance_status="Good", eligibility_status="Eligible",
                shortage_flag="No",
            ),
            FakeRecord(
                subject_id="SUB0051", subject_code="CS702",
                subject_name="Algorithms",
                total_classes=25, attended_classes=18,
                attendance_percentage=72.0,
                attendance_status="Low", eligibility_status="Not Eligible",
                shortage_flag="Yes",
            ),
        ]
        pool, conn = make_pool(fetch_seq=[subjects])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_student_attendance_summary("STU000001", semester_no=7)
        )
        self.assertEqual(result["total_classes"], 52)
        self.assertEqual(result["attended_classes"], 40)
        self.assertAlmostEqual(result["overall_attendance_percentage"], 76.92, 1)
        self.assertEqual(result["at_risk_subjects"], 1)
        self.assertEqual(result["ineligible_subjects"], 1)

    def test_empty_attendance(self):
        pool, conn = make_pool(fetch_seq=[[]])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_student_attendance_summary("STU000099")
        )
        self.assertEqual(result["total_classes"], 0)
        self.assertIsNone(result["overall_attendance_percentage"])
        self.assertEqual(result["subjects"], [])

    def test_subject_filter(self):
        pool, conn = make_pool(fetch_seq=[[]])
        repo = AnalyticsRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.get_student_attendance_summary(
                "STU000001", subject_id="SUB0050"
            )
        )
        call_args = conn.fetch.call_args
        self.assertEqual(call_args[0][3], "SUB0050")


class TestStudentBacklogSummary(unittest.TestCase):
    def test_with_backlogs(self):
        backlogs = [
            FakeRecord(
                subject_id="SUB0050", subject_code="CS701",
                subject_name="Data Structures", semester_no=5,
                percentage=35.0, grade="F",
            ),
        ]
        student = FakeRecord(total_backlogs=3)
        pool, conn = make_pool(
            fetch_seq=[backlogs], fetchrow_seq=[student]
        )
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_student_backlog_summary("STU000005")
        )
        self.assertEqual(result["total_backlogs"], 3)
        self.assertEqual(len(result["backlogs"]), 1)
        self.assertEqual(result["backlogs"][0]["grade"], "F")

    def test_no_backlogs(self):
        pool, conn = make_pool(
            fetch_seq=[[]], fetchrow_seq=[FakeRecord(total_backlogs=0)]
        )
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_student_backlog_summary("STU000001")
        )
        self.assertEqual(result["total_backlogs"], 0)
        self.assertEqual(result["backlogs"], [])

    def test_nonexistent_student(self):
        pool, conn = make_pool(fetch_seq=[[]], fetchrow_seq=[None])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_student_backlog_summary("STU999999")
        )
        self.assertEqual(result["total_backlogs"], 0)


# ---------------------------------------------------------------------------
# B. Subject Analytics
# ---------------------------------------------------------------------------

class TestSubjectPerformanceSummary(unittest.TestCase):
    def test_existing_subject(self):
        base = FakeRecord(
            subject_id="SUB0050", subject_code="CS701",
            subject_name="Data Structures", semester_no=7,
            total_students=50, average_percentage=68.5,
            median_percentage=70.0, min_percentage=29.29,
            max_percentage=100.0, pass_count=45, fail_count=5,
        )
        grades = [
            FakeRecord(grade="O", count=3),
            FakeRecord(grade="A+", count=8),
            FakeRecord(grade="A", count=12),
            FakeRecord(grade="B+", count=10),
            FakeRecord(grade="B", count=7),
            FakeRecord(grade="C", count=5),
            FakeRecord(grade="F", count=5),
        ]
        pool, conn = make_pool(
            fetchrow_seq=[base], fetch_seq=[grades]
        )
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_subject_performance_summary("SUB0050", semester_no=7)
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["total_students"], 50)
        self.assertEqual(result["pass_count"], 45)
        self.assertEqual(result["fail_count"], 5)
        self.assertAlmostEqual(result["pass_rate"], 90.0, 1)
        self.assertEqual(len(result["grade_distribution"]), 7)

    def test_nonexistent_subject(self):
        pool, conn = make_pool(fetchrow_seq=[None])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_subject_performance_summary("SUB999999")
        )
        self.assertIsNone(result)

    def test_semester_filter(self):
        pool, conn = make_pool(fetchrow_seq=[None])
        repo = AnalyticsRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.get_subject_performance_summary(
                "SUB0050", semester_no=7
            )
        )
        call_args = conn.fetchrow.call_args
        query = call_args[0][0]
        self.assertIn("$2::int IS NULL OR p.semester_no = $2", query)
        self.assertEqual(call_args[0][2], 7)


class TestSubjectAttendanceSummary(unittest.TestCase):
    def test_existing_subject(self):
        row = FakeRecord(
            subject_id="SUB0050", subject_code="CS701",
            subject_name="Data Structures", semester_no=7,
            total_students=50, average_attendance_percentage=82.5,
            eligible_count=45, ineligible_count=5,
            at_risk_count=3, shortage_count=2,
        )
        pool, conn = make_pool(fetchrow_seq=[row])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_subject_attendance_summary("SUB0050", semester_no=7)
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["total_students"], 50)
        self.assertEqual(result["eligible_count"], 45)
        self.assertEqual(result["ineligible_count"], 5)

    def test_nonexistent_subject(self):
        pool, conn = make_pool(fetchrow_seq=[None])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_subject_attendance_summary("SUB999999")
        )
        self.assertIsNone(result)


class TestSubjectUnderperformers(unittest.TestCase):
    def test_below_threshold(self):
        students = [
            FakeRecord(
                student_id="STU000032", full_name="Riya Patel",
                percentage=35.0, grade="F", attendance_percentage=66.67,
            ),
            FakeRecord(
                student_id="STU000041", full_name="Amit Kumar",
                percentage=38.5, grade="F", attendance_percentage=72.0,
            ),
        ]
        pool, conn = make_pool(fetch_seq=[students])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_subject_underperformers(
                "SUB0050", semester_no=7, threshold=40.0
            )
        )
        self.assertEqual(result["total_flagged"], 2)
        self.assertEqual(result["students"][0]["percentage"], 35.0)
        self.assertEqual(result["threshold"], 40.0)

    def test_no_underperformers(self):
        pool, conn = make_pool(fetch_seq=[[]])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_subject_underperformers("SUB0050", threshold=40.0)
        )
        self.assertEqual(result["total_flagged"], 0)
        self.assertEqual(result["students"], [])

    def test_parameterized_threshold(self):
        pool, conn = make_pool(fetch_seq=[[]])
        repo = AnalyticsRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.get_subject_underperformers("SUB0050", threshold=50.0)
        )
        call_args = conn.fetch.call_args
        self.assertEqual(call_args[0][3], 50.0)


# ---------------------------------------------------------------------------
# C. Department / Semester Analytics
# ---------------------------------------------------------------------------

class TestDepartmentOverview(unittest.TestCase):
    def test_overview(self):
        row = FakeRecord(
            department_code=1, department_name="CSE",
            semester_no=7, academic_year="2026-2027",
            total_students=50, average_sgpa=7.8,
            average_percentage=72.5, average_attendance_percentage=82.0,
            total_backlogs=45, students_with_backlogs=20,
        )
        pool, conn = make_pool(fetchrow_seq=[row])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_department_overview(
                department_code=1, semester_no=7
            )
        )
        self.assertEqual(result["department_code"], 1)
        self.assertEqual(result["total_students"], 50)
        self.assertAlmostEqual(result["average_sgpa"], 7.8)

    def test_no_filters(self):
        pool, conn = make_pool(fetchrow_seq=[FakeRecord(
            department_code=None, department_name=None,
            semester_no=None, academic_year=None,
            total_students=80, average_sgpa=None,
            average_percentage=None, average_attendance_percentage=None,
            total_backlogs=0, students_with_backlogs=0,
        )])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_department_overview()
        )
        self.assertEqual(result["total_students"], 80)

    def test_null_optional_filter(self):
        pool, conn = make_pool(fetchrow_seq=[FakeRecord(
            department_code=1, department_name="CSE",
            semester_no=None, academic_year=None,
            total_students=50, average_sgpa=7.8,
            average_percentage=72.5, average_attendance_percentage=82.0,
            total_backlogs=45, students_with_backlogs=20,
        )])
        repo = AnalyticsRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.get_department_overview(department_code=1)
        )
        call_args = conn.fetchrow.call_args
        query = call_args[0][0]
        self.assertIn("$2::int IS NULL OR sem.semester_no = $2", query)
        self.assertIn("$3::text IS NULL OR sem.academic_year = $3", query)


class TestSemesterPerformanceDistribution(unittest.TestCase):
    def test_distribution(self):
        buckets = [
            FakeRecord(label="Top", count=5, percentage_of_total=10.0),
            FakeRecord(label="Above Average", count=15, percentage_of_total=30.0),
            FakeRecord(label="Average", count=20, percentage_of_total=40.0),
            FakeRecord(label="Below Average", count=8, percentage_of_total=16.0),
            FakeRecord(label="Low Performer", count=2, percentage_of_total=4.0),
        ]
        pool, conn = make_pool(
            fetch_seq=[buckets], fetchval_seq=[50]
        )
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_semester_performance_distribution(
                department_code=1, semester_no=7
            )
        )
        self.assertEqual(result["total_students"], 50)
        self.assertEqual(len(result["buckets"]), 5)
        self.assertEqual(result["buckets"][0]["label"], "Top")

    def test_empty_distribution(self):
        pool, conn = make_pool(fetch_seq=[[]], fetchval_seq=[0])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_semester_performance_distribution()
        )
        self.assertEqual(result["total_students"], 0)
        self.assertEqual(result["buckets"], [])


class TestAttendanceDistribution(unittest.TestCase):
    def test_distribution(self):
        buckets = [
            FakeRecord(band="Excellent", count=15, percentage_of_total=30.0),
            FakeRecord(band="Good", count=20, percentage_of_total=40.0),
            FakeRecord(band="Average", count=10, percentage_of_total=20.0),
            FakeRecord(band="Low", count=4, percentage_of_total=8.0),
            FakeRecord(band="Critical", count=1, percentage_of_total=2.0),
        ]
        pool, conn = make_pool(
            fetch_seq=[buckets], fetchval_seq=[50]
        )
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_attendance_distribution(
                department_code=1, semester_no=7
            )
        )
        self.assertEqual(result["total_students"], 50)
        self.assertEqual(len(result["buckets"]), 5)


class TestBacklogDistribution(unittest.TestCase):
    def test_distribution(self):
        buckets = [
            FakeRecord(backlog_range="0", count=30, percentage_of_total=60.0),
            FakeRecord(backlog_range="1-2", count=12, percentage_of_total=24.0),
            FakeRecord(backlog_range="3-5", count=5, percentage_of_total=10.0),
            FakeRecord(backlog_range="6-10", count=2, percentage_of_total=4.0),
            FakeRecord(backlog_range="11+", count=1, percentage_of_total=2.0),
        ]
        pool, conn = make_pool(
            fetch_seq=[buckets], fetchval_seq=[50, 20]
        )
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_backlog_distribution(department_code=1)
        )
        self.assertEqual(result["total_students"], 50)
        self.assertEqual(result["students_with_backlogs"], 20)
        self.assertEqual(len(result["buckets"]), 5)

    def test_no_backlogs(self):
        pool, conn = make_pool(
            fetch_seq=[[
                FakeRecord(backlog_range="0", count=50, percentage_of_total=100.0)
            ]],
            fetchval_seq=[50, 0],
        )
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_backlog_distribution()
        )
        self.assertEqual(result["students_with_backlogs"], 0)


# ---------------------------------------------------------------------------
# D. At-Risk / Academic Gap Analytics
# ---------------------------------------------------------------------------

class TestAtRiskStudents(unittest.TestCase):
    def test_flagged_students(self):
        students = [
            FakeRecord(
                student_id="STU000005", full_name="Poor Attendance",
                department_code=1, current_semester=7,
                overall_cgpa=5.5, latest_sgpa=4.5, total_backlogs=3,
                overall_attendance_percentage=65.0,
            ),
            FakeRecord(
                student_id="STU000001", full_name="Good Student",
                department_code=1, current_semester=7,
                overall_cgpa=9.0, latest_sgpa=9.0, total_backlogs=0,
                overall_attendance_percentage=90.0,
            ),
        ]
        # Simulate: STU000005 has 2 low-att subjects and 1 failed subject
        low_att_counts = [2, 0]  # STU000005 has 2, STU000001 has 0
        failed_counts = [1, 0]

        pool, conn = make_pool(
            fetch_seq=[students, [], []],  # students + 2 empty for semester checks
        )
        # Override fetchval to return counts
        call_count = [0]
        original_fetchval = conn.fetchval

        async def _fetchval_counting(query, *args, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            # First 2 fetchval calls are for STU000005 (low_att, failed)
            # Next 2 are for STU000001
            if idx < 2:
                return low_att_counts[0] if idx == 0 else failed_counts[0]
            else:
                return low_att_counts[1] if idx == 2 else failed_counts[1]

        conn.fetchval = AsyncMock(side_effect=_fetchval_counting)

        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_at_risk_students(
                department_code=1, semester_no=7
            )
        )
        self.assertEqual(result["total_flagged"], 1)
        flagged = result["students"][0]
        self.assertEqual(flagged["student_id"], "STU000005")
        self.assertTrue(len(flagged["risk_reasons"]) >= 2)
        self.assertIsNotNone(flagged["risk_score"])

    def test_no_flagged_students(self):
        students = [
            FakeRecord(
                student_id="STU000001", full_name="Good Student",
                department_code=1, current_semester=7,
                overall_cgpa=9.0, latest_sgpa=9.0, total_backlogs=0,
                overall_attendance_percentage=90.0,
            ),
        ]
        pool, conn = make_pool(fetch_seq=[students, [], []])
        conn.fetchval = AsyncMock(return_value=0)

        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_at_risk_students(department_code=1, semester_no=7)
        )
        self.assertEqual(result["total_flagged"], 0)
        self.assertEqual(result["students"], [])

    def test_empty_student_list(self):
        pool, conn = make_pool(fetch_seq=[[]])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_at_risk_students()
        )
        self.assertEqual(result["total_flagged"], 0)

    def test_no_writes(self):
        pool, conn = make_pool(fetch_seq=[[]])
        repo = AnalyticsRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.get_at_risk_students()
        )
        conn.execute.assert_not_called()


class TestStudentsBelowAttendanceThreshold(unittest.TestCase):
    def test_below_threshold(self):
        students = [
            FakeRecord(
                student_id="STU000032", full_name="Riya Patel",
                subject_id="SUB0050", subject_code="CS701",
                attendance_percentage=66.67,
                total_classes=27, attended_classes=18,
            ),
        ]
        pool, conn = make_pool(fetch_seq=[students])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_students_below_attendance_threshold(
                threshold=75.0, semester_no=7
            )
        )
        self.assertEqual(result["total_flagged"], 1)
        self.assertEqual(result["threshold"], 75.0)

    def test_above_threshold(self):
        pool, conn = make_pool(fetch_seq=[[]])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_students_below_attendance_threshold(threshold=75.0)
        )
        self.assertEqual(result["total_flagged"], 0)

    def test_custom_threshold(self):
        pool, conn = make_pool(fetch_seq=[[]])
        repo = AnalyticsRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.get_students_below_attendance_threshold(threshold=60.0)
        )
        call_args = conn.fetch.call_args
        self.assertEqual(call_args[0][1], 60.0)


class TestSubjectsNeedingAttention(unittest.TestCase):
    def test_flagged_subjects(self):
        subjects = [
            FakeRecord(
                subject_id="SUB0050", subject_code="CS701",
                subject_name="Data Structures", semester_no=7,
                total_students=50, average_percentage=45.0,
                fail_rate=25.0, average_attendance=70.0,
            ),
            FakeRecord(
                subject_id="SUB0051", subject_code="CS702",
                subject_name="Algorithms", semester_no=7,
                total_students=50, average_percentage=75.0,
                fail_rate=5.0, average_attendance=85.0,
            ),
        ]
        pool, conn = make_pool(fetch_seq=[subjects])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_subjects_needing_attention(
                department_code=1, semester_no=7
            )
        )
        self.assertEqual(result["total_flagged"], 1)
        flagged = result["subjects"][0]
        self.assertEqual(flagged["subject_id"], "SUB0050")
        self.assertTrue(len(flagged["reasons"]) >= 2)

    def test_no_flagged_subjects(self):
        subjects = [
            FakeRecord(
                subject_id="SUB0051", subject_code="CS702",
                subject_name="Algorithms", semester_no=7,
                total_students=50, average_percentage=75.0,
                fail_rate=5.0, average_attendance=85.0,
            ),
        ]
        pool, conn = make_pool(fetch_seq=[subjects])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_subjects_needing_attention(department_code=1)
        )
        self.assertEqual(result["total_flagged"], 0)

    def test_empty_result(self):
        pool, conn = make_pool(fetch_seq=[[]])
        repo = AnalyticsRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_subjects_needing_attention()
        )
        self.assertEqual(result["total_flagged"], 0)
        self.assertEqual(result["subjects"], [])


# ---------------------------------------------------------------------------
# Cross-cutting concerns
# ---------------------------------------------------------------------------

class TestNoDatabaseWrites(unittest.TestCase):
    """Verify the entire repository never calls execute()."""

    def test_all_read_methods(self):
        pool, conn = make_pool(
            fetch_seq=[None] * 20,
            fetchrow_seq=[None] * 20,
            fetchval_seq=[0] * 20,
        )
        repo = AnalyticsRepository(pool)
        loop = asyncio.get_event_loop()

        methods = [
            ("get_student_academic_profile", ("STU000001",), {}),
            ("get_student_semester_history", ("STU000001",), {}),
            ("get_student_attendance_summary", ("STU000001",), {}),
            ("get_student_backlog_summary", ("STU000001",), {}),
            ("get_subject_performance_summary", ("SUB0050",), {}),
            ("get_subject_attendance_summary", ("SUB0050",), {}),
            ("get_subject_underperformers", ("SUB0050",), {}),
            ("get_department_overview", (), {}),
            ("get_semester_performance_distribution", (), {}),
            ("get_attendance_distribution", (), {}),
            ("get_backlog_distribution", (), {}),
            ("get_at_risk_students", (), {}),
            ("get_students_below_attendance_threshold", (), {}),
            ("get_subjects_needing_attention", (), {}),
        ]
        for name, args, kwargs in methods:
            getattr(repo, name)(*args, **kwargs)

        conn.execute.assert_not_called()


class TestParameterizedQueries(unittest.TestCase):
    """Verify all queries use $N placeholders, never string interpolation."""

    def test_no_string_interpolation(self):
        pool, conn = make_pool(
            fetch_seq=[None] * 20,
            fetchrow_seq=[None] * 20,
            fetchval_seq=[0] * 20,
        )
        repo = AnalyticsRepository(pool)
        loop = asyncio.get_event_loop()

        methods = [
            ("get_student_academic_profile", ("STU000001",), {}),
            ("get_student_semester_history", ("STU000001",), {}),
            ("get_student_attendance_summary", ("STU000001",), {}),
            ("get_student_backlog_summary", ("STU000001",), {}),
            ("get_subject_performance_summary", ("SUB0050",), {}),
            ("get_subject_attendance_summary", ("SUB0050",), {}),
            ("get_subject_underperformers", ("SUB0050",), {}),
            ("get_department_overview", (), {}),
            ("get_semester_performance_distribution", (), {}),
            ("get_attendance_distribution", (), {}),
            ("get_backlog_distribution", (), {}),
            ("get_at_risk_students", (), {}),
            ("get_students_below_attendance_threshold", (), {}),
            ("get_subjects_needing_attention", (), {}),
        ]

        all_queries = []
        for name, args, kwargs in methods:
            getattr(repo, name)(*args, **kwargs)

        # Collect all queries that were executed
        for call in conn.fetch.call_args_list:
            all_queries.append(call[0][0])
        for call in conn.fetchrow.call_args_list:
            all_queries.append(call[0][0])
        for call in conn.fetchval.call_args_list:
            all_queries.append(call[0][0])

        for q in all_queries:
            if q:
                # Must not contain f-string patterns like {variable}
                self.assertNotIn("{", q,
                    f"Query may contain string interpolation: {q[:80]}...")

        # All queries should use $N placeholders
        for q in all_queries:
            if q:
                self.assertIn("$", q,
                    f"Query missing $N placeholders: {q[:80]}...")


if __name__ == "__main__":
    unittest.main()
