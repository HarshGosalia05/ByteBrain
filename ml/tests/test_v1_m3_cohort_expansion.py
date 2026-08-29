"""Focused tests for the M3 chronological (later academic-year) cohort analysis.

Purpose
-------
This step's question is: does a chronologically later academic-year cohort
exist in the REAL data such that M3's training/evaluation population can be
expanded with additional independent, outcome-derived at-risk labels?

These tests lock in the finding and the guard that enforces it:

1. Single-cohort reality: the real CSV mirror has exactly one admission year
   (2023), one current academic year (2026-27), 80 students, and therefore NO
   later cohort -> expansion is NOT possible and adds 0 positive students.
2. Forward-compatible detector: given synthetic tables with a genuine later
   admission year (2024) carrying its own positive outcomes, the SAME module
   reports expansion_possible=True and counts the added positive rows/students
   using the EXACT independent academic-outcome rule (FAIL/ATKT or backlog>0 at
   T+1).
3. ``academic_year`` is NOT a cohort trap: multiple calendar academic_year
   values in student_semester_summary for a single admission cohort must NOT be
   misreported as separate cohorts.
4. Deployment/label boundary correctness: the last semester per student (no
   T+1 outcome) is never counted as positive.

No DB writes, no ETL, no artifact mutation.  Read-only.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from features.v1_m3_cohort_expansion import (  # noqa: E402
    M3CohortExpansionAnalysis,
    _analyze_tables,
    analyze_m3_cohort_expansion,
    render_expansion_analysis,
)
from features.v1_label_builder import AT_RISK_RESULTS  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _students_frame(rows):
    """Build a students DataFrame in the real-table shape."""
    return pd.DataFrame(rows)


def _summary_frame(rows):
    """Build a summary DataFrame in the real-table shape."""
    return pd.DataFrame(rows)


def _single_cohort_tables():
    """Real-data shape: one 2023 admission cohort, 80 students."""
    students = _students_frame(
        [{"student_id": f"STU{i:06d}", "admission_year": 2023,
          "current_academic_year": "2026-27", "department_name": "CSE"}
         for i in range(1, 81)]
    )
    summary = _summary_frame([
        {"student_id": f"STU{i:06d}", "semester_no": s,
         "academic_year": year, "semester_result": "PASS", "backlog_count": 0.0}
        for i in range(1, 81)
        for s, year in [
            (1, "2023-24"), (2, "2023-24"), (3, "2024-25"),
            (4, "2024-25"), (5, "2025-26"), (6, "2025-26"), (7, "2026-27"),
        ]
    ])
    return {"students": students, "summary": summary}


def _multi_cohort_tables():
    """shape with a genuine later 2024 admission cohort carrying positives."""
    students = _students_frame([
        {"student_id": "STU000001", "admission_year": 2023,
         "current_academic_year": "2026-27", "department_name": "CSE"},
        {"student_id": "STU000101", "admission_year": 2024,
         "current_academic_year": "2025-26", "department_name": "CSE"},
    ])
    summary = _summary_frame([
        # baseline cohort: 3 semesters, third is unlabeled (deployment)
        {"student_id": "STU000001", "semester_no": 1, "academic_year": "2023-24",
         "semester_result": "PASS", "backlog_count": 0.0},
        {"student_id": "STU000001", "semester_no": 2, "academic_year": "2023-24",
         "semester_result": "PASS", "backlog_count": 0.0},
        {"student_id": "STU000001", "semester_no": 3, "academic_year": "2024-25",
         "semester_result": "PASS", "backlog_count": 0.0},
        # later cohort: 2024, sem 1 PASS, sem 2 ATKT -> sem1 is a positive label
        {"student_id": "STU000101", "semester_no": 1, "academic_year": "2024-25",
         "semester_result": "PASS", "backlog_count": 0.0},
        {"student_id": "STU000101", "semester_no": 2, "academic_year": "2024-25",
         "semester_result": "ATKT", "backlog_count": 2.0},
        {"student_id": "STU000101", "semester_no": 3, "academic_year": "2025-26",
         "semester_result": "PASS", "backlog_count": 0.0},
    ])
    return {"students": students, "summary": summary}


class TestRealDataSingleCohort(unittest.TestCase):
    """The actual finding: real data has one cohort, so no expansion."""

    def test_real_mirror_single_admission_year(self):
        a = analyze_m3_cohort_expansion()
        self.assertEqual(a.admission_years, [2023])
        self.assertEqual(a.n_students_total, 80)
        self.assertEqual(a.student_id_range, ("STU000001", "STU000080"))

    def test_real_mirror_no_later_cohort(self):
        a = analyze_m3_cohort_expansion()
        self.assertEqual(a.later_admission_years, [])
        self.assertEqual(a.later_student_ids, [])
        self.assertFalse(a.expansion_possible)

    def test_real_mirror_adds_zero_positive_students(self):
        a = analyze_m3_cohort_expansion()
        self.assertEqual(a.later_positive_rows, 0)
        self.assertEqual(a.later_positive_students, 0)
        self.assertTrue(a.all_labeled_rows_consumed)

    def test_render_is_not_empty_and_marks_false(self):
        a = analyze_m3_cohort_expansion()
        text = render_expansion_analysis(a)
        self.assertIn("Expansion possible: False", text)
        self.assertIn("single admission year", text)
        self.assertGreater(len(text), 100)


class TestForwardCompatibleDetection(unittest.TestCase):
    """If a later cohort ever arrives, the same module must detect it."""

    def test_detects_later_admission_year(self):
        a = _analyze_tables(
            _multi_cohort_tables()["summary"], _multi_cohort_tables()["students"]
        )
        self.assertEqual(a.admission_years, [2023, 2024])
        self.assertEqual(a.later_admission_years, [2024])
        self.assertEqual(a.later_student_ids, ["STU000101"])
        self.assertTrue(a.expansion_possible)

    def test_counts_positive_rows_and_students(self):
        a = _analyze_tables(
            _multi_cohort_tables()["summary"], _multi_cohort_tables()["students"]
        )
        # sem1(PASS)->sem2(ATKT) is a positive label for the later student.
        self.assertEqual(a.later_positive_rows, 1)
        self.assertEqual(a.later_positive_students, 1)

    def test_baseline_cohort_not_swallowed_into_later(self):
        a = _analyze_tables(
            _multi_cohort_tables()["summary"], _multi_cohort_tables()["students"]
        )
        self.assertEqual(a.current_cohort_year, 2023)
        self.assertIn("STU000001", a.current_student_ids)


class TestLabelRuleAndBoundary(unittest.TestCase):
    """The independent academic-outcome label rule + T+1 deployment boundary."""

    def test_label_result_contract(self):
        # The label definition must remain the shared at-risk rule.
        self.assertIn("FAIL", AT_RISK_RESULTS)
        self.assertIn("ATKT", AT_RISK_RESULTS)

    def test_last_semester_unlabeled_not_positive(self):
        # Later cohort student's final semester (sem3) has no T+1 -> unlabeled,
        # so it contributes 0 to the positive count (only sem1 is positive).
        a = _analyze_tables(
            _multi_cohort_tables()["summary"], _multi_cohort_tables()["students"]
        )
        self.assertEqual(a.later_summary_rows, 3)
        self.assertEqual(a.later_positive_rows, 1)

    def test_backlog_only_positive_still_counts(self):
        # Build a case where a later student's result is PASS but backlog > 0.
        students = _multi_cohort_tables()["students"]
        summary = _multi_cohort_tables()["summary"]
        extra = _summary_frame([
            {"student_id": "STU000102", "semester_no": 1, "academic_year": "2024-25",
             "semester_result": "PASS", "backlog_count": 0.0},
            {"student_id": "STU000102", "semester_no": 2, "academic_year": "2024-25",
             "semester_result": "PASS", "backlog_count": 3.0},
        ])
        students2 = pd.concat([students, _students_frame([
            {"student_id": "STU000102", "admission_year": 2024,
             "current_academic_year": "2025-26", "department_name": "BBA"}
        ])], ignore_index=True)
        summary2 = pd.concat([summary, extra], ignore_index=True)
        a = _analyze_tables(summary2, students2)
        # STU000101 sem1 + STU000102 sem1 both positive (2 positive rows).
        self.assertEqual(a.later_positive_rows, 2)
        self.assertEqual(a.later_positive_students, 2)


class TestAcademicYearIsNotACohort(unittest.TestCase):
    """Calendar academic_year must never be mistaken for a cohort."""

    def test_many_academic_years_still_one_cohort(self):
        tables = _single_cohort_tables()  # 4 calendar years, 1 admission year
        a = _analyze_tables(tables["summary"], tables["students"])
        self.assertEqual(a.admission_years, [2023])
        self.assertEqual(a.later_admission_years, [])
        self.assertFalse(a.expansion_possible)

    def test_academic_year_not_used_as_admission_year(self):
        tables = _single_cohort_tables()
        summary_years = sorted(tables["summary"]["academic_year"].unique())
        self.assertGreater(len(summary_years), 1)
        a = _analyze_tables(tables["summary"], tables["students"])
        # Multiple calendar years must not create a later 'admission' cohort.
        self.assertEqual(len(a.admission_years), 1)


class TestAnalysisShape(unittest.TestCase):
    def test_returns_dataclass(self):
        a = analyze_m3_cohort_expansion()
        self.assertIsInstance(a, M3CohortExpansionAnalysis)

    def test_current_academic_year_single(self):
        a = analyze_m3_cohort_expansion()
        self.assertEqual(a.current_academic_years, ["2026-27"])


if __name__ == "__main__":
    unittest.main()
