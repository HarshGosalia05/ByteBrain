"""Faculty Subjects Teaching Assignments tests.

Verifies the Subjects section's current/previous/history read model:

  1. get_current_subjects returns the current/live term's subject cards.
  2. get_previous_batch resolves the term immediately preceding the current
     term dynamically from the faculty's real teaching sequence (never
     hardcoded) and returns its subject cards.
  3. get_teaching_history groups every offering by (semester, academic_year)
     with per-term aggregates (subjects, students, avg attendance/performance
     and pass rate) and preserves current-term context.
  4. The three new routes are registered ahead of the catch-all
     /subjects/{subject_id} route so path-like words (current/previous/history)
     never get shadowed.
  5. No fabricated history: empty enrollment yields empty groups, and a
     sem-1-only faculty yields has_previous=False.

These tests exercise the service layer against a mocked repository plus the
router path ordering; no live DB is required.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from app.api.v1 import faculty as faculty_api
from app.repositories.faculty_repo import FacultyRepository
from app.schemas.faculty import FacultyClassCard
from app.services.faculty_service import FacultyService


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def fake_pool():
    return MagicMock()


def make_service(**repo_methods):
    pool = fake_pool()
    svc = FacultyService(pool)
    svc.repo.get_faculty_profile = AsyncMock(return_value={"faculty_id": "FAC001"})
    for name, impl in repo_methods.items():
        setattr(svc.repo, name, AsyncMock(return_value=impl))
    return svc


def card_row(subject_id="SUB0050", code="CSE701", name="Software Engineering",
             sem=7, year="2026-27", students=50, att=86.97, perf=None,
             pass_pct=None, grade_point=None):
    pass_count = int(students * pass_pct / 100) if pass_pct is not None else None
    performed_count = students if pass_pct is not None else None
    return {
        "subject_id": subject_id,
        "subject_code": code,
        "subject_name": name,
        "credits": 4,
        "semester_no": sem,
        "academic_year": year,
        "class_strength": students,
        "average_attendance": att,
        "average_percentage": perf,
        "highest_marks": 98.0,
        "lowest_marks": 35.0,
        "average_grade_point": grade_point,
        "pass_count": pass_count,
        "performed_count": performed_count,
    }


class TestCurrentSubjects(unittest.TestCase):
    def test_returns_current_term_subjects(self):
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2026-27"},
        )
        rows = [card_row(), card_row("SUB0053", "CSE704", "Deep Learning", 7, "2026-27", 50, 88.5)]
        svc.repo.get_subject_cards = AsyncMock(return_value=rows)

        res = run(svc.get_current_subjects("FAC001"))

        self.assertEqual(res.semester_no, 7)
        self.assertEqual(res.academic_year, "2026-27")
        self.assertEqual(len(res.subjects), 2)
        # Cards must be real FacultyClassCard instances with cardinal stats.
        self.assertTrue(all(isinstance(c, FacultyClassCard) for c in res.subjects))
        self.assertEqual(res.subjects[0].class_strength, 50)
        self.assertAlmostEqual(res.subjects[1].average_attendance, 88.5)
        # Card query is scoped to the current term only.
        call = svc.repo.get_subject_cards.call_args.args
        self.assertEqual(call[1], 7)
        self.assertEqual(call[2], "2026-27")

    def test_no_term_returns_empty(self):
        svc = make_service(get_current_term=None)
        res = run(svc.get_current_subjects("FAC001"))
        self.assertIsNone(res.semester_no)
        self.assertIsNone(res.academic_year)
        self.assertEqual(res.subjects, [])


class TestPreviousBatch(unittest.TestCase):
    def test_resolves_previous_term_dynamically(self):
        # Chronological sequence oldest -> newest. Current = sem 7 / 2026-27,
        # so previous must resolve to sem 6 / 2025-26 (the immediate predecessor).
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2026-27"},
            get_term_sequence=[
                {"semester_no": 5, "academic_year": "2025-26"},
                {"semester_no": 6, "academic_year": "2025-26"},
                {"semester_no": 7, "academic_year": "2026-27"},
            ],
        )
        rows = [card_row("SUB0044", "CSE601", "DBMS", 6, "2025-26", 50, 84.1)]
        svc.repo.get_subject_cards = AsyncMock(return_value=rows)

        res = run(svc.get_previous_batch("FAC001"))

        self.assertTrue(res.has_previous)
        self.assertEqual(res.semester_no, 6)
        self.assertEqual(res.academic_year, "2025-26")
        self.assertEqual(len(res.subjects), 1)
        call = svc.repo.get_subject_cards.call_args.args
        self.assertEqual(call[1], 6)
        self.assertEqual(call[2], "2025-26")

    def test_no_previous_returns_empty(self):
        # A faculty teaching only semester 1 has no preceding term.
        svc = make_service(
            get_current_term={"semester_no": 1, "academic_year": "2026-27"},
            get_term_sequence=[
                {"semester_no": 1, "academic_year": "2026-27"},
            ],
        )
        res = run(svc.get_previous_batch("FAC001"))
        self.assertFalse(res.has_previous)
        self.assertIsNone(res.semester_no)
        self.assertEqual(res.subjects, [])

    def test_no_current_term_returns_empty(self):
        svc = make_service(get_current_term=None)
        res = run(svc.get_previous_batch("FAC001"))
        self.assertFalse(res.has_previous)
        self.assertEqual(res.subjects, [])


class TestTeachingHistory(unittest.TestCase):
    def test_groups_offerings_by_term(self):
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2026-27"},
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[
            card_row("SUB0035", "CSE501", "OS", 5, "2025-26", 50, 82.0, perf=80.0, pass_pct=88.0),
            card_row("SUB0038", "CSE502", "CN", 5, "2025-26", 50, 90.0, perf=85.0, pass_pct=92.0),
            card_row("SUB0050", "CSE701", "SE", 7, "2026-27", 50, 86.97, perf=83.0, pass_pct=90.0),
        ])

        res = run(svc.get_teaching_history("FAC001"))

        self.assertEqual(res.current_semester, 7)
        self.assertEqual(res.current_academic_year, "2026-27")
        self.assertEqual([(t.semester_no, t.academic_year) for t in res.terms],
                         [(5, "2025-26"), (7, "2026-27")])
        term5 = res.terms[0]
        self.assertEqual(term5.subjects, 2)
        self.assertEqual(term5.students, 100)
        self.assertEqual(term5.average_attendance, 86.0)  # mean of 82.0, 90.0
        self.assertEqual(term5.average_performance, 82.5)  # mean of 80.0, 85.0
        self.assertAlmostEqual(term5.pass_percentage, 90.0)
        self.assertEqual(len(term5.subject_cards), 2)
        # Full-term query: both dims stay None (all offerings).
        call = svc.repo.get_subject_cards.call_args.args
        self.assertIsNone(call[1])
        self.assertIsNone(call[2])

    def test_no_history_returns_empty_terms(self):
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2026-27"},
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[])
        res = run(svc.get_teaching_history("FAC001"))
        self.assertEqual(res.terms, [])
        self.assertEqual(res.current_semester, 7)

    def test_missing_values_stay_none(self):
        svc = make_service(
            get_current_term={"semester_no": 7, "academic_year": "2026-27"},
        )
        svc.repo.get_subject_cards = AsyncMock(return_value=[
            card_row("SUB0050", "CSE701", "SE", 7, "2026-27", 50, att=None, perf=None, pass_pct=None),
        ])
        res = run(svc.get_teaching_history("FAC001"))
        term = res.terms[0]
        self.assertIsNone(term.average_attendance)
        self.assertIsNone(term.average_performance)
        self.assertIsNone(term.pass_percentage)


class TestTermSequenceRepo(unittest.TestCase):
    def setUp(self):
        self.repo = FacultyRepository(fake_pool())

    def _source(self, start, end):
        import inspect
        with open(inspect.getfile(FacultyRepository), encoding="utf-8") as fh:
            text = fh.read()
        return text[text.index(start):text.index(end)]

    def test_term_sequence_orders_chronologically(self):
        block = self._source("async def get_term_sequence", "async def get_term_overview")
        self.assertIn("student_subject_enrollment", block)
        self.assertIn("enrollment_status = 'Active'", block)
        self.assertIn("ORDER BY academic_year ASC, semester_no ASC", block)
        self.assertIn("DISTINCT", block)


class TestRouterOrdering(unittest.TestCase):
    def test_static_subject_routes_registered_before_catch_all(self):
        paths = [r.path for r in faculty_api.router.routes]
        self.assertLess(paths.index("/subjects/current"), paths.index("/subjects/{subject_id}"))
        self.assertLess(paths.index("/subjects/previous"), paths.index("/subjects/{subject_id}"))
        self.assertLess(paths.index("/subjects/history"), paths.index("/subjects/{subject_id}"))
        self.assertLess(paths.index("/subjects/history"), paths.index("/subjects/{subject_id}/history"))


if __name__ == "__main__":
    unittest.main()