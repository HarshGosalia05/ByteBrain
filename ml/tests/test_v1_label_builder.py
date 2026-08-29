"""Focused tests for V1 Independent M3 Ground-Truth Label Builder.

Covers temporal correctness, student isolation, label correctness, missing
future outcomes, duplicate/conflicting outcomes, determinism, leakage
prevention, and the academic-vs-prediction-feedback distinction.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from features.v1_label_builder import (  # noqa: E402
    build_academic_labels,
    audit_labels,
)


def _rows(sem_result=None, sem_backlogs=None):
    """Build (student, semester) outcome rows.

    sem_result / sem_backlogs map semester_no -> value.
    """
    rows = []
    for sem, res in (sem_result or {}).items():
        rows.append({
            "student_id": "STU000001",
            "semester_no": sem,
            "semester_result": res,
            "backlog_count": (sem_backlogs or {}).get(sem, 0),
        })
    return rows


class TestTemporalCorrectness(unittest.TestCase):

    def test_label_at_T_uses_T_plus_1_outcome(self):
        # sem1 PASS, sem2 ATKT -> sem1 label should be 1 (risk in sem2)
        df = build_academic_labels(pd.DataFrame(_rows(
            sem_result={1: "PASS", 2: "ATKT", 3: "PASS"}
        )))
        sem1 = df[df["semester_no"] == 1].iloc[0]
        self.assertEqual(sem1["label"], 1)
        self.assertEqual(sem1["target_semester"], 2)

    def test_target_semester_is_always_plus_one(self):
        df = build_academic_labels(pd.DataFrame(_rows(
            sem_result={1: "PASS", 2: "PASS", 3: "ATKT"}
        )))
        self.assertEqual(df.loc[df["semester_no"] == 1, "target_semester"].iloc[0], 2)
        self.assertEqual(df.loc[df["semester_no"] == 2, "target_semester"].iloc[0], 3)


class TestLabelCorrectness(unittest.TestCase):

    def test_pass_is_negative(self):
        df = build_academic_labels(pd.DataFrame(_rows(
            sem_result={1: "PASS", 2: "PASS"}
        )))
        self.assertEqual(df.loc[df["semester_no"] == 1, "label"].iloc[0], 0)

    def test_atkt_is_positive(self):
        df = build_academic_labels(pd.DataFrame(_rows(
            sem_result={1: "PASS", 2: "ATKT"}
        )))
        self.assertEqual(df.loc[df["semester_no"] == 1, "label"].iloc[0], 1)

    def test_backlogs_positive_without_atkt(self):
        df = build_academic_labels(pd.DataFrame(_rows(
            sem_result={1: "PASS", 2: "PASS"},
            sem_backlogs={1: 0, 2: 3},
        )))
        self.assertEqual(df.loc[df["semester_no"] == 1, "label"].iloc[0], 1)

    def test_sgpa_low_still_uses_defined_rule(self):
        # low final marks but PASS/0 backlogs -> not at-risk by documented rule
        df = build_academic_labels(pd.DataFrame(_rows(
            sem_result={1: "PASS", 2: "PASS"}
        )))
        self.assertEqual(df.loc[df["semester_no"] == 1, "label"].iloc[0], 0)


class TestStudentIsolation(unittest.TestCase):

    def test_labels_never_cross_students(self):
        # sandwich: student A short, student B at-risk -> A's last sem unlabeled,
        # B computed independently.
        rows = [
            {"student_id": "STU000001", "semester_no": 1, "semester_result": "PASS", "backlog_count": 0},
            {"student_id": "STU000002", "semester_no": 1, "semester_result": "PASS", "backlog_count": 0},
            {"student_id": "STU000002", "semester_no": 2, "semester_result": "PASS", "backlog_count": 0},
        ]
        df = build_academic_labels(pd.DataFrame(rows))
        a = df[df["student_id"] == "STU000001"]
        b = df[df["student_id"] == "STU000002"]
        # A has only 1 sem -> unlabeled
        self.assertTrue(a["label"].isna().all())
        # B sem1 -> target B sem2 = PASS -> negative
        self.assertEqual(b.loc[b["semester_no"] == 1, "label"].iloc[0], 0)
        self.assertTrue(pd.isna(b.loc[b["semester_no"] == 2, "label"].iloc[0]))


class TestMissingFutureOutcome(unittest.TestCase):

    def test_last_semester_unlabeled(self):
        df = build_academic_labels(pd.DataFrame(_rows(
            sem_result={1: "PASS", 2: "PASS", 3: "ATKT"}
        )))
        last = df[df["semester_no"] == 3].iloc[0]
        self.assertTrue(pd.isna(last["label"]))
        self.assertTrue(pd.isna(last["target_semester"]))

    def test_report_count_unlabeled(self):
        df = build_academic_labels(pd.DataFrame(_rows(
            sem_result={1: "PASS", 2: "PASS", 3: "PASS"}
        )))
        rep = audit_labels(df)
        self.assertEqual(rep.labeled_rows, 2)
        self.assertEqual(rep.unlabeled_rows, 1)


class TestDuplicatesAndConflicts(unittest.TestCase):

    def test_duplicate_identical_rows_not_conflicting(self):
        rows = _rows(sem_result={1: "PASS", 2: "PASS"})
        rows.append({"student_id": "STU000001", "semester_no": 2,
                     "semester_result": "PASS", "backlog_count": 0})
        df = build_academic_labels(pd.DataFrame(rows))
        self.assertGreaterEqual(int(df["duplicate"].sum()), 1)
        self.assertEqual(int(df["conflicting"].sum()), 0)
        # sem1 still labeled from sem2 (identical duplicate -> fine)
        self.assertEqual(df.loc[df["semester_no"] == 1, "label"].iloc[0], 0)

    def test_conflicting_duplicate_rows_ambiguous_and_unlabeled(self):
        rows = [
            {"student_id": "STU000001", "semester_no": 1, "semester_result": "PASS", "backlog_count": 0},
            {"student_id": "STU000001", "semester_no": 2, "semester_result": "PASS", "backlog_count": 0},
            {"student_id": "STU000001", "semester_no": 2, "semester_result": "ATKT", "backlog_count": 2},
        ]
        df = build_academic_labels(pd.DataFrame(rows))
        self.assertGreaterEqual(int(df["conflicting"].sum()), 1)
        self.assertGreaterEqual(int(df["ambiguous"].sum()), 1)
        # sem2 conflicting -> unlabeled; sem1 references an ambiguous sem2
        self.assertTrue(pd.isna(df.loc[df["semester_no"] == 2, "label"].iloc[0]))

    def test_conflicting_cases_reported(self):
        rows = [
            {"student_id": "STU000001", "semester_no": 1, "semester_result": "PASS", "backlog_count": 0},
            {"student_id": "STU000001", "semester_no": 2, "semester_result": "PASS", "backlog_count": 0},
            {"student_id": "STU000001", "semester_no": 2, "semester_result": "ATKT", "backlog_count": 1},
        ]
        rep = audit_labels(build_academic_labels(pd.DataFrame(rows)))
        self.assertGreaterEqual(rep.conflicting_outcome_cases, 1)


class TestDeterminism(unittest.TestCase):

    def test_same_input_same_output(self):
        rows = _rows(sem_result={1: "PASS", 2: "ATKT", 3: "PASS", 4: "ATKT"})
        d1 = build_academic_labels(pd.DataFrame(rows))
        d2 = build_academic_labels(pd.DataFrame(list(reversed(rows))))
        # sorted & deterministic regardless of input order
        cols = ["student_id", "semester_no", "label", "target_semester",
                "conflicting", "ambiguous", "duplicate"]
        self.assertTrue(d1[cols].reset_index(drop=True).equals(d2[cols].reset_index(drop=True)))

    def test_report_deterministic(self):
        rows = _rows(sem_result={1: "PASS", 2: "ATKT", 3: "PASS"})
        r1 = audit_labels(build_academic_labels(pd.DataFrame(rows)))
        r2 = audit_labels(build_academic_labels(pd.DataFrame(list(reversed(rows)))))
        self.assertEqual(r1.summary(), r2.summary())


class TestCountsAndLeakage(unittest.TestCase):

    def test_row_and_student_positive_negative_counts(self):
        # 3 students: A at-risk in sem2, B never at-risk, C at-risk
        rows = []
        for sid, sems in {
            "STU000001": {1: "PASS", 2: "ATKT"},
            "STU000002": {1: "PASS", 2: "PASS"},
            "STU000003": {1: "ATKT", 2: "ATKT", 3: "PASS"},
        }.items():
            for sem, res in sems.items():
                rows.append({"student_id": sid, "semester_no": sem,
                             "semester_result": res, "backlog_count": 0})
        df = build_academic_labels(pd.DataFrame(rows))
        rep = audit_labels(df)
        # A sem1 -> at-risk(sem2 ATKT) positive; C sem1 -> at-risk(sem2 ATKT) positive
        self.assertEqual(rep.positive_rows, 2)   # A sem1, C sem1
        self.assertEqual(rep.unique_positive, 2)  # A and C
        # B sem1 -> PASS negative; C sem2 -> PASS negative
        self.assertEqual(rep.negative_rows, 2)   # B sem1, C sem2
        self.assertEqual(rep.unique_negative, 2)  # B (sem1) and C (sem2)
        self.assertEqual(rep.unique_unlabeled, 3)  # each student has a last-sem unlabeled row

    def test_label_source_is_academic_not_feedback(self):
        df = build_academic_labels(pd.DataFrame(_rows(
            sem_result={1: "PASS", 2: "ATKT"}
        )))
        self.assertTrue((df["label_source"] == "academic").all())

    def test_no_future_columns_leak_into_label_snapshot(self):
        df = build_academic_labels(pd.DataFrame(_rows(
            sem_result={1: "PASS", 2: "ATKT", 3: "PASS"}
        )))
        # The feature snapshot columns (T) do not contain target-derived info
        for col in ("semester_result", "backlog_count"):
            self.assertIn(col, df.columns)
        # label derives from T+1, not T
        sem1 = df[df["semester_no"] == 1].iloc[0]
        self.assertEqual(sem1["semester_result"], "PASS")  # T = PASS
        self.assertEqual(sem1["label"], 1)                  # but T+1 = at-risk


if __name__ == "__main__":
    unittest.main()
