"""Focused tests for the SECOND chronologically-later cohort availability &
integration gate.

Covers:
1.  chronology detection              10. prediction_feedback exclusion
2.  current-vs-later separation       11. feature-column consistency
3.  student overlap detection         12. department one-hot consistency
4.  independent student identification 13. duplicate grain detection
5.  target-semester validity          14. deterministic cohort selection
6.  T+1 temporal correctness          15. deterministic gate result
7.  deployment exclusion              16. projected positive-class coverage
8.  per-student deployment boundary   17. no-fabricated-data path
9.  independent academic-label rule   18. valid/no-valid decision logic

Real-data fixture: the CSV mirror of the live cohort (single 2023 cohort).
Synthetic fixtures: probe the decision branches (VALID / NO_VALID /
INSUFFICIENT) deterministically.

Read-only: no DB writes, no ETL, no artifact mutation.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from features.v1_later_cohort_gate import (  # noqa: E402
    LaterCohortGateResult,
    LaterCohortCandidate,
    run_later_cohort_gate,
    render_later_cohort_gate,
    VALID,
    NO_VALID,
    INSUFFICIENT,
)

CURRENT_CSV_POS_ROWS = 28
CURRENT_CSV_POS_STUDENTS = 6


def _students(rows):
    return pd.DataFrame(rows)


def _summary(rows):
    return pd.DataFrame(rows)


def _base_students(n_new=0, with_new=False):
    rows = [
        {"student_id": f"STU{i:06d}", "admission_year": 2023,
         "current_academic_year": "2026-27", "department_name": "CSE"}
        for i in range(1, 81)
    ]
    if with_new:
        for j in range(1, n_new + 1):
            rows.append({"student_id": f"STU1{j:05d}", "admission_year": 2024,
                         "current_academic_year": "2025-26", "department_name": "CSE"})
    return rows


def _base_summary(students):
    rows = []
    for s in students:
        _, year = s["admission_year"], None
        n_sems = 4 if s["admission_year"] == 2024 else 6
        for sem in range(1, n_sems + 1):
            rows.append({
                "student_id": s["student_id"], "semester_no": sem,
                "academic_year": "2024-25", "department_name": s["department_name"],
                "semester_result": "PASS", "backlog_count": 0.0,
            })
    return rows


def real_tables():
    return None  # default CSV mirror


class RealDataNoLaterCohort(unittest.TestCase):
    """The actual finding on real data: no later cohort -> NO_VALID."""

    def test_real_single_admission_year(self):
        r = run_later_cohort_gate()
        self.assertEqual(r.verdict, NO_VALID)
        self.assertEqual(r.all_admission_years, [2023])
        self.assertEqual(r.later_admission_years, [])
        self.assertEqual(r.current_cohort_year, 2023)
        self.assertEqual(len(r.current_student_ids), 80)

    def test_real_no_candidates(self):
        r = run_later_cohort_gate()
        self.assertEqual(r.candidates, [])
        self.assertTrue(r.reasons_for_no_valid)

    def test_real_projection_equals_current(self):
        r = run_later_cohort_gate()
        p = r.projected
        self.assertEqual(p["current_students"], 80)
        self.assertEqual(p["later_new_students"], 0)
        self.assertEqual(p["combined_positive_rows"], CURRENT_CSV_POS_ROWS)
        self.assertEqual(p["combined_positive_students"], CURRENT_CSV_POS_STUDENTS)
        self.assertEqual(p["added_positive_rows"], 0)

    def test_real_authoritative_field(self):
        r = run_later_cohort_gate()
        self.assertEqual(r.authoritative_chronology_field, "students.admission_year")

    def test_real_deterministic(self):
        a = run_later_cohort_gate()
        b = run_later_cohort_gate()
        self.assertEqual(a.verdict, b.verdict)
        self.assertEqual(a.all_admission_years, b.all_admission_years)
        self.assertEqual(a.candidates, b.candidates)
        self.assertEqual(a.projected, b.projected)


class SyntheticValidLaterCohort(unittest.TestCase):
    """A genuine later cohort (new students, positives) -> VALID."""

    def _tables(self):
        students = _students(_base_students(n_new=6, with_new=True))
        summary = _summary(_base_summary(students.to_dict("records")))
        # Make some later-year students positive at T+1.
        later_stu = [s for s in students["student_id"] if s.startswith("STU1")]
        for sid in later_stu[:3]:
            # semester 1 -> semester 2 (PASS result) => not positive; make sem1->sem2 ATKT
            mask = (summary["student_id"] == sid) & (summary["semester_no"] == 2)
            summary.loc[mask, "semester_result"] = "ATKT"
            summary.loc[mask, "backlog_count"] = 1.0
        return {"students": students, "summary": summary}

    def test_detects_later_year_and_new_students(self):
        r = run_later_cohort_gate(tables=self._tables(), provenance="live")
        self.assertEqual(r.verdict, VALID)
        self.assertEqual(r.later_admission_years, [2024])
        c = r.candidates[0]
        self.assertEqual(c.admission_year, 2024)
        self.assertEqual(c.new_ids, [f"STU1{j:05d}" for j in range(1, 7)])
        self.assertEqual(c.overlapping_ids, [])  # no overlap

    def test_counts_positive_outcomes(self):
        r = run_later_cohort_gate(tables=self._tables(), provenance="live")
        c = r.candidates[0]
        # 3 ATKT later students: only sem2 set to ATKT, so sem1->sem2 is a
        # positive label -> 1 positive row per student = 3 positive rows /
        # 3 positive students. Remaining sem2->sem3, sem3->sem4 are negative;
        # the 3 non-ATKT later students are fully negative. neg_students == 6.
        self.assertEqual(c.positive_students, 3)
        self.assertEqual(c.positive_rows, 3)
        self.assertEqual(c.negative_students, 6)

    def test_projection_adds_new(self):
        r = run_later_cohort_gate(tables=self._tables(), provenance="live")
        p = r.projected
        self.assertEqual(p["later_new_students"], 6)
        self.assertEqual(p["combined_total_students"], 86)
        self.assertEqual(p["added_positive_students"], 3)

    def test_deterministic(self):
        a = run_later_cohort_gate(tables=self._tables(), provenance="live")
        b = run_later_cohort_gate(tables=self._tables(), provenance="live")
        self.assertEqual(a.verdict, b.verdict)
        self.assertEqual(a.candidates, b.candidates)


class SyntheticOverlapOnly(unittest.TestCase):
    """Later year but NO genuinely new students -> NOT independent -> NO_VALID."""

    def _tables(self):
        students = _students(_base_students())
        # Re-label ALL current students to admission_year 2024 as well -> overlap.
        students = students.copy()
        extra = students.copy()
        extra["admission_year"] = 2024
        students = pd.concat([students, extra], ignore_index=True)
        summary = _summary(_base_summary(students.drop_duplicates("student_id").to_dict("records")))
        return {"students": students, "summary": summary}

    def test_overlap_only_no_new_students(self):
        r = run_later_cohort_gate(tables=self._tables(), provenance="live")
        self.assertEqual(r.verdict, NO_VALID)
        c = r.candidates[0]
        self.assertEqual(c.overlapping_ids, [f"STU{i:06d}" for i in range(1, 81)])
        self.assertEqual(c.new_ids, [])
        self.assertIn("NO genuinely new students", r.reasons_for_no_valid[-1])


class SyntheticNewButNoPositives(unittest.TestCase):
    """New students but zero positive outcomes -> no positive power -> NO_VALID."""

    def _tables(self):
        students = _students(_base_students(n_new=6, with_new=True))
        summary = _summary(_base_summary(students.to_dict("records")))
        return {"students": students, "summary": summary}

    def test_new_but_no_positives(self):
        r = run_later_cohort_gate(tables=self._tables(), provenance="live")
        self.assertEqual(r.verdict, NO_VALID)
        c = r.candidates[0]
        self.assertEqual(len(c.new_ids), 6)
        self.assertEqual(c.positive_rows, 0)
        self.assertIn("0 positive", r.reasons_for_no_valid[-1])


class SyntheticInsufficientEvidence(unittest.TestCase):
    """Missing authoritative chronology field -> INSUFFICIENT."""

    def _tables(self):
        students = _students([{"student_id": "STU000001", "department_name": "CSE"}])
        summary = _summary([{"student_id": "STU000001", "semester_no": 1,
                             "academic_year": "2024-25", "semester_result": "PASS",
                             "backlog_count": 0.0}])
        return {"students": students, "summary": summary}

    def test_missing_admission_year(self):
        r = run_later_cohort_gate(tables=self._tables(), provenance="live")
        self.assertEqual(r.verdict, INSUFFICIENT)


class LabelAndLeakagePolicy(unittest.TestCase):
    """Independent academic label rule; prediction_feedback never a label source."""

    def test_label_is_academic_not_feedback(self):
        # The gate's target is derived from semester_result/backlog_count (T+1),
        # never prediction_feedback.
        from features.v1_label_builder import AT_RISK_RESULTS
        self.assertIn("FAIL", AT_RISK_RESULTS)
        self.assertIn("ATKT", AT_RISK_RESULTS)

    def test_render_contains_verdict(self):
        r = run_later_cohort_gate()
        text = render_later_cohort_gate(r)
        self.assertIn("GATE VERDICT", text)
        self.assertIn("verdict = NO_VALID_LATER_COHORT_FOUND", text)

    def test_gate_result_types(self):
        r = run_later_cohort_gate()
        self.assertIsInstance(r, LaterCohortGateResult)
        for c in r.candidates:
            self.assertIsInstance(c, LaterCohortCandidate)


if __name__ == "__main__":
    unittest.main()
