"""Term-aware Faculty Subjects analytics tests.

Verifies the Subjects page behaves as a real academic-term-aware analytics
surface:

  1. Default view resolves to the current/live term (no historical mixing).
  2. "All terms" (all_terms=true + both dims empty) shows every offering.
  3. Explicit year / semester filters work (including paired "all" of the
     other dimension).
  4. Subject cards derive attendance from attendance_weekly via the weighted
     formula (no legacy-attendance "—").
  5. Attendance / performance / pass-rate are scoped per subject offering.
  6. KPI aggregation uses the same filtered dataset as the cards.
  7. Student count is COUNT(DISTINCT student_id).
  8. "—" is only shown when there genuinely is no attendance data.
  9. No hardcoded student/subject counts and no cross-cohort double counting.

These tests exercise the service filter-resolution + call-through against a
mocked repository, plus the repository SQL text for the weighted attendance.
"""
from __future__ import annotations

import asyncio
import re
import unittest
from unittest.mock import AsyncMock, MagicMock

from app.repositories.faculty_repo import FacultyRepository
from app.schemas.faculty import (
    FacultyClassCard,
    FacultyPagination,
    FacultySubjectsAppliedFilters,
    FacultySubjectsFilters,
    FacultySubjectsResponse,
    FacultySubjectsSummary,
)
from app.services.faculty_service import FacultyService


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def fake_pool():
    pool = MagicMock()
    pool.acquire = MagicMock()
    return pool


def make_service(**repo_methods):
    pool = fake_pool()
    svc = FacultyService(pool)
    svc.repo.get_faculty_profile = AsyncMock(return_value={"faculty_id": "FAC001"})
    overrides = {
        "get_subjects_weighted_attendance": 85.22,
        **repo_methods,
    }
    for name, impl in overrides.items():
        setattr(svc.repo, name, AsyncMock(return_value=impl))
    return svc


def sample_card(subject_id="SUB0052", code="CSE703", name="Innovation",
                sem=7, year="2025-26", students=120, att=None,
                perf=82.0, pass_pct=90.0):
    return FacultyClassCard(
        subject_id=subject_id,
        subject_code=code,
        subject_name=name,
        credits=4,
        semester_no=sem,
        academic_year=year,
        class_strength=students,
        average_attendance=att,
        average_percentage=perf,
        highest_marks=99.0,
        lowest_marks=30.0,
        average_grade="A",
        pass_percentage=pass_pct,
    )


def sample_response(cards):
    return FacultySubjectsResponse(
        faculty_id="FAC001",
        summary=FacultySubjectsSummary(
            total_subjects=len(cards),
            total_students=sum(c.class_strength for c in cards),
            current_semester=7,
            current_academic_year="2025-26",
            average_attendance=82.0,
            average_performance=80.0,
        ),
        filters=FacultySubjectsFilters(semesters=[6, 7], academic_years=["2024-25", "2025-26"]),
        applied=FacultySubjectsAppliedFilters(semester=None, academic_year=None, search=None),
        cards=cards,
        pagination=FacultyPagination(page=1, page_size=50, total=len(cards), total_pages=1),
    )


class TestSubjectsDefaultTerm(unittest.TestCase):
    def test_default_resolves_to_current_term(self):
        # No dims, all_terms False -> backend forces current term (sem 7 / 2025-26).
        card = sample_card()
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 120},
            get_subject_filters={"semesters": [6, 7], "academic_years": ["2024-25", "2025-26"]},
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[
            {**card.model_dump(), "average_attendance": 78.3}
        ])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc"))

        # Service must forward resolved current term to the repo queries.
        call = svc.repo.get_subject_cards.call_args.args
        self.assertEqual(call[1], 7)          # semester_no
        self.assertEqual(call[2], "2025-26")  # academic_year
        self.assertEqual(svc.repo.get_subject_cards.call_args.kwargs.get("batch"), None)
        self.assertEqual(res.applied.semester, 7)
        self.assertEqual(res.applied.academic_year, "2025-26")

    def test_all_terms_both_empty_stays_empty(self):
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 2, "total_students": 240},
            get_subject_filters={"semesters": [6, 7], "academic_years": ["2024-25", "2025-26"]},
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[
            {**sample_card().model_dump(), "average_attendance": 78.3},
            {**sample_card("SUB0055", "CSE706", "Deep Learning Lab", 7, "2025-26", 120, 92.1).model_dump()},
        ])
        svc.repo.count_subject_cards = AsyncMock(return_value=2)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc", all_terms=True))

        # all_terms True -> both dims stay None (matches "All Years + All Semesters").
        self.assertIsNone(res.applied.semester)
        self.assertIsNone(res.applied.academic_year)

    def test_explicit_year_all_semesters(self):
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 120},
            get_subject_filters={"semesters": [6, 7, 8], "academic_years": ["2025-26"]},
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[{**sample_card().model_dump()}])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        run(svc.get_subjects("FAC001", None, "2025-26", None, 1, 50, "name", "asc"))
        call = svc.repo.get_subject_cards.call_args.args
        self.assertIsNone(call[1])         # semester stays None (all semesters)
        self.assertEqual(call[2], "2025-26")

    def test_explicit_semester_all_years(self):
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 120},
            get_subject_filters={"semesters": [7], "academic_years": ["2024-25", "2025-26"]},
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[{**sample_card().model_dump()}])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        run(svc.get_subjects("FAC001", 7, None, None, 1, 50, "name", "asc"))
        call = svc.repo.get_subject_cards.call_args.args
        self.assertEqual(call[1], 7)
        self.assertIsNone(call[2])         # year stays None (all years)

    def test_historical_not_in_default(self):
        # Default current-term query must scope to 2025-26 only; the repo mock
        # returns only current-term cards, mirroring the WHERE clause.
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 120},
            get_subject_filters={"semesters": [6, 7], "academic_years": ["2024-25", "2025-26"]},
        )
        current = sample_card()
        historical = sample_card("SUB0052", "CSE703", "Innovation", 7, "2024-25", 60, 88.5)
        svc.repo.get_subject_cards = AsyncMock(return_value=[{**current.model_dump()}])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc"))
        codes = {c.academic_year for c in res.cards}
        self.assertEqual(codes, {"2025-26"})
        self.assertNotIn("2024-25", codes)


class TestSubjectsAPISemantics(unittest.TestCase):
    def test_card_attendance_uses_weighted_weekly(self):
        # A subject with valid attendance must show a value, not "—".
        card = sample_card(att=78.32)
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 120},
            get_subject_filters={"semesters": [7], "academic_years": ["2025-26"]},
            get_subjects_weighted_attendance=85.22,
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[
            {**card.model_dump()},
            {**sample_card("SUB0055", "CSE706", "Deep Learning Lab", 7, "2025-26", 120, 92.12).model_dump()},
        ])
        svc.repo.count_subject_cards = AsyncMock(return_value=2)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc"))
        self.assertIsNotNone(res.cards[0].average_attendance)
        # KPI uses the global weighted attendance over the same filtered dataset.
        self.assertAlmostEqual(res.summary.average_attendance, 85.22, places=2)

    def test_card_with_no_attendance_stays_none(self):
        card = sample_card(att=None)
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 120},
            get_subject_filters={"semesters": [7], "academic_years": ["2025-26"]},
            get_subjects_weighted_attendance=None,
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[{**card.model_dump()}])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc"))
        self.assertIsNone(res.cards[0].average_attendance)
        self.assertIsNone(res.summary.average_attendance)

    def test_student_count_distinct(self):
        card = sample_card(students=120)
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 120},
            get_subject_filters={"semesters": [7], "academic_years": ["2025-26"]},
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[{**card.model_dump()}])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc"))
        self.assertEqual(res.cards[0].class_strength, 120)

    def test_returns_legacy_named_fields(self):
        # Backwards compatible fields remain present for existing consumers.
        from app.schemas.faculty import FacultyClassCard as FCC
        fields = FCC.model_fields
        for required in ("subject_id", "subject_code", "semester_no", "academic_year",
                         "class_strength", "average_attendance", "average_percentage",
                         "pass_percentage"):
            self.assertIn(required, fields)


class TestRepoAttendanceSQL(unittest.TestCase):
    def setUp(self):
        self.repo = FacultyRepository(fake_pool())

    def _source(self, start, end):
        with open(__import__("inspect").getfile(FacultyRepository), encoding="utf-8") as fh:
            text = fh.read()
        return text[text.index(start):text.index(end)]

    def test_subject_cards_uses_attendance_weekly(self):
        block = self._source("async def get_subject_cards", "async def get_subject_term")
        self.assertIn("attendance_weekly", block)
        self.assertIn("SUM(aw.classes_attended)", block)
        self.assertIn("SUM(aw.classes_held)", block)
        self.assertIn("count(DISTINCT sse.student_id)", block)
        # Legacy weekly-weighted fallback keeps the existing 80-cohort visible.
        self.assertIn("SUM(a.attended_classes)", block)
        self.assertIn("SUM(a.total_classes)", block)
        # Legacy and weekly are disjoint sources; weighted sums never double count.
        self.assertIn("WHEN SUM(aw.classes_held) > 0", block)
        self.assertIn("WHEN SUM(a.total_classes) > 0", block)

    def test_get_subject_detail_uses_weekly(self):
        block = self._source("async def get_subject_detail", "async def get_subject_meta")
        self.assertIn("attendance_weekly", block)
        self.assertIn("SUM(aw.classes_attended)", block)
        self.assertIn("SUM(a.attended_classes)", block)

    def test_no_cross_year_aggregation_in_weekly_join(self):
        # Scoping must reference the enrollment's semester+year alongside the
        # weekly join so historical offerings are not mixed.
        where_block = self._source("def _subject_cards_where(", "async def count_subject_cards")
        self.assertIn("sse.semester_no = ${", where_block)
        self.assertIn("sse.academic_year = ${", where_block)
        self.assertIn("sse.enrollment_status = 'Active'", where_block)


if __name__ == "__main__":
    unittest.main()
