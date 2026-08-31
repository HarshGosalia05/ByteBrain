"""Faculty Subjects batch (student admission cohort) filter tests.

The Subjects page gains a "Batch" filter that scopes analytics to the
students' admission cohort (admission_year -> "2021-22" style batch label).
This is a *student* dimension, distinct from the academic_year/semester
*offering* dimensions.

Scenarios covered:
  1. Batch options are derived dynamically from live students data.
  2. Batch option label format (admission_year + 1, "2021-22").
  3. "All Batches" default -> no batch predicate (None forwarded).
  4. A specific batch filters cards, summary, KPI and attendance population.
  5. "all"/empty batch normalizes to None (no predicate).
  6. A nonexistent batch is not present in available options.
  7. Batch + term dimension combinations forward jointly.
  8. Student count stays COUNT(DISTINCT student_id) while batch-scoped.
  9. Attendance / performance KPIs respect the batch predicate (SQL text).
 10. No hardcoded student/subject counts, no cross-cohort double counting.
 11. Repo SQL joins students and predicates on st.admission_year.
"""
from __future__ import annotations

import asyncio
import inspect
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
                sem=7, year="2025-26", students=120, att=82.0,
                perf=80.0, pass_pct=90.0):
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


def filters_with_batches(batches):
    return FacultySubjectsFilters(
        semesters=[6, 7],
        academic_years=["2024-25", "2025-26"],
        batches=batches,
    )


class TestBatchOptionDerivation(unittest.TestCase):
    def test_batch_label_format(self):
        # admission_year 2021 -> "2021-22" (project batch display format).
        self.assertEqual(FacultyRepository.year_to_batch(2021), "2021-22")
        self.assertEqual(FacultyRepository.year_to_batch(2023), "2023-24")
        self.assertIsNone(FacultyRepository.year_to_batch(None))

    def test_batch_to_year_parses_label(self):
        self.assertEqual(FacultyRepository.batch_to_year("2021-22"), 2021)
        self.assertEqual(FacultyRepository.batch_to_year("2023-24"), 2023)
        self.assertIsNone(FacultyRepository.batch_to_year(None))
        self.assertIsNone(FacultyRepository.batch_to_year(""))
        self.assertIsNone(FacultyRepository.batch_to_year("not-a-batch"))

    def test_available_options_come_from_live_students(self):
        # get_subject_filters must surface batches derived from the (CSE)
        # student admission data, not hardcoded.
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 240},
            get_subject_filters={
                "semesters": [7],
                "academic_years": ["2025-26"],
                "batches": ["2021-22", "2022-23", "2023-24"],
            },
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[{**sample_card().model_dump()}])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc"))
        self.assertEqual(res.filters.batches, ["2021-22", "2022-23", "2023-24"])

    def test_nonexistent_batch_not_in_options(self):
        # A batch that exists nowhere (e.g. 2099-00) is never offered.
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 240},
            get_subject_filters={
                "semesters": [7],
                "academic_years": ["2025-26"],
                "batches": ["2021-22", "2022-23"],
            },
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[{**sample_card().model_dump()}])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc"))
        self.assertNotIn("2099-00", res.filters.batches)


class TestBatchDefaultAndSend(unittest.TestCase):
    def test_all_batches_default_no_predicate(self):
        # Default: no batch selected -> forwarded as None (All Batches).
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 240},
            get_subject_filters={
                "semesters": [7],
                "academic_years": ["2025-26"],
                "batches": ["2021-22", "2022-23", "2023-24"],
            },
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[{**sample_card().model_dump()}])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc"))
        summary_args = svc.repo.get_subjects_summary.call_args.args
        self.assertEqual(summary_args[3], None)
        self.assertIsNone(res.applied.batch)

    def test_specific_batch_forwarded_everywhere(self):
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 240},
            get_subject_filters={
                "semesters": [7],
                "academic_years": ["2025-26"],
                "batches": ["2021-22", "2022-23", "2023-24"],
            },
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[{**sample_card().model_dump()}])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc", batch="2022-23"))

        self.assertEqual(res.applied.batch, "2022-23")
        self.assertEqual(svc.repo.get_subjects_summary.call_args.args[3], "2022-23")
        self.assertEqual(
            svc.repo.get_subjects_weighted_attendance.call_args.args[3], "2022-23"
        )
        self.assertEqual(svc.repo.count_subject_cards.call_args.args[4], "2022-23")
        # KPI/card-attendance call (term_cards) also batch-scoped.
        term_cards_batch = [
            c.kwargs.get("batch")
            for c in svc.repo.get_subject_cards.call_args_list
        ]
        self.assertTrue(all(b == "2022-23" for b in term_cards_batch))

    def test_all_sentinel_normalized_to_none(self):
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 240},
            get_subject_filters={
                "semesters": [7],
                "academic_years": ["2025-26"],
                "batches": ["2021-22", "2022-23"],
            },
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[{**sample_card().model_dump()}])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc", batch="all"))
        self.assertIsNone(res.applied.batch)
        self.assertEqual(svc.repo.get_subjects_summary.call_args.args[3], None)

    def test_blank_batch_sentinel_normalized_to_none(self):
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 240},
            get_subject_filters={
                "semesters": [7],
                "academic_years": ["2025-26"],
                "batches": ["2021-22", "2022-23"],
            },
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[{**sample_card().model_dump()}])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc", batch="   "))
        self.assertIsNone(res.applied.batch)


class TestBatchCombinesWithTermFilters(unittest.TestCase):
    def test_batch_plus_year_and_semester_forwarded_jointly(self):
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2026-27"},
            get_subjects_summary={"total_subjects": 1, "total_students": 50},
            get_subject_filters={
                "semesters": [6, 7],
                "academic_years": ["2024-25", "2025-26"],
                "batches": ["2021-22", "2022-23"],
            },
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[{**sample_card().model_dump()}])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        res = run(svc.get_subjects(
            "FAC001", 7, "2025-26", None, 1, 50, "name", "asc", batch="2021-22"
        ))
        self.assertEqual(res.applied.semester, 7)
        self.assertEqual(res.applied.academic_year, "2025-26")
        self.assertEqual(res.applied.batch, "2021-22")
        # count/subset cards receive all three dimensions (batch positional).
        count_args = svc.repo.count_subject_cards.call_args.args
        self.assertEqual(count_args[2], "2025-26")
        self.assertEqual(count_args[3], None)
        self.assertEqual(count_args[4], "2021-22")

    def test_current_term_default_preserved_with_batch(self):
        # Selecting only a batch (no year/sem) must NOT defeat the current-term
        # default: offerings stay on the current term while students are batch-scoped.
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 120},
            get_subject_filters={
                "semesters": [6, 7],
                "academic_years": ["2024-25", "2025-26"],
                "batches": ["2021-22", "2022-23", "2023-24"],
            },
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[{**sample_card().model_dump()}])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc", batch="2022-23"))
        self.assertEqual(res.applied.semester, 7)
        self.assertEqual(res.applied.academic_year, "2025-26")
        self.assertEqual(res.applied.batch, "2022-23")


class TestRepoBatchSQL(unittest.TestCase):
    def setUp(self):
        self.repo = FacultyRepository(fake_pool())

    def _source(self, start, end):
        with open(inspect.getfile(FacultyRepository), encoding="utf-8") as fh:
            text = fh.read()
        return text[text.index(start):text.index(end)]

    def test_cards_join_students_for_batch_predicate(self):
        block = self._source("async def get_subject_cards", "async def get_subject_term")
        self.assertIn("JOIN students st ON st.student_id = sse.student_id", block)

    def test_summary_join_students_for_batch_predicate(self):
        block = self._source("async def get_subjects_summary", "async def get_subjects_weighted")
        self.assertIn("JOIN students st ON st.student_id = sse.student_id", block)

    def test_where_predicates_on_admission_year(self):
        where_block = self._source("def _subject_cards_where(", "async def count_subject_cards")
        self.assertIn("st.admission_year = ${", where_block)
        self.assertIn("sse.faculty_id = $1", where_block)
        self.assertIn("sse.enrollment_status = 'Active'", where_block)

    def test_weighted_attendance_batch_scoped(self):
        block = self._source("async def get_subjects_weighted_attendance", "async def get_subject_filters")
        self.assertIn("JOIN students st ON st.student_id = sse.student_id", block)
        self.assertIn("st.admission_year = ${", block)

    def test_filters_distinct_admission_year(self):
        block = self._source("async def get_subject_filters", "async def get_subject_cards")
        self.assertIn("DISTINCT st.admission_year", block)
        self.assertIn("JOIN students st ON st.student_id = sse.student_id", block)

    def test_where_predicate_uses_year_not_academic_year_string(self):
        # The batch predicate must target the integer admission_year, not the
        # string academic_year (they are semantically distinct dimensions).
        where_block = self._source("def _subject_cards_where(", "async def count_subject_cards")
        self.assertIn("st.admission_year", where_block)
        self.assertNotIn("st.admission_year = sse.academic_year", where_block)


class TestBatchKpiAndCounts(unittest.TestCase):
    def test_student_count_stays_distinct_batch_scoped(self):
        # Batch-scoped card still reports COUNT(DISTINCT student_id).
        card = sample_card(students=50)
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 1, "total_students": 50},
            get_subject_filters={
                "semesters": [7],
                "academic_years": ["2025-26"],
                "batches": ["2022-23"],
            },
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[{**card.model_dump()}])
        svc.repo.count_subject_cards = AsyncMock(return_value=1)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc", batch="2022-23"))
        self.assertEqual(res.cards[0].class_strength, 50)
        self.assertEqual(res.summary.total_students, 50)

    def test_no_hardcoded_counts(self):
        # Options must be derived from data, not fixed to 1200/80/1280.
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2025-26"},
            get_subjects_summary={"total_subjects": 0, "total_students": 0},
            get_subject_filters={
                "semesters": [7],
                "academic_years": ["2025-26"],
                "batches": ["2022-23"],
            },
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[])
        svc.repo.count_subject_cards = AsyncMock(return_value=0)
        res = run(svc.get_subjects("FAC001", None, None, None, 1, 50, "name", "asc", batch="2022-23"))
        # Empty-state: batch-selected but no students -> 0 subjects, no fabrication.
        self.assertEqual(res.cards, [])
        self.assertEqual(res.summary.total_subjects, 0)
        self.assertEqual(res.summary.total_students, 0)


if __name__ == "__main__":
    unittest.main()
