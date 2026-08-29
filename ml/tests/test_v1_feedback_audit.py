"""Focused tests for V1 Feedback-Label Quality Audit.

Covers:
  - valid feedback label extraction (confirmed/dismissed -> candidate 0/1)
  - invalid / unrecognized labels rejected
  - duplicate feedback (latest verdict wins) resolution
  - conflicting feedback handling
  - student mapping
  - semester/time mapping (prediction_value.semester_no -> target semester)
  - temporal leakage prevention (deployment/training isolation)
  - model-generated prediction vs human feedback distinction
  - deterministic output
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from features.v1_feedback_audit import (  # noqa: E402
    audit_prediction_feedback_labels,
    BoundLabel,
)


def _fb(fid, pid, sid, action, ts):
    return {
        "feedback_id": fid,
        "prediction_id": pid,
        "student_id": sid,
        "faculty_id": "FAC001",
        "feedback_action": action,
        "note": None,
        "model_version": "3.2.1",
        "feedback_timestamp": ts,
    }


def _m3_pred(pid, sem, is_risk):
    return {
        "prediction_id": pid,
        "student_id": None,
        "prediction_type": "m3",
        "model_version": "3.2.1",
        "prediction_value": {"semester_no": sem, "is_at_risk_next_sem": is_risk},
    }


def _non_m3_pred(pid):
    return {"prediction_id": pid, "prediction_type": "m1"}


def _outcomes(sids=(1, 2, 3)):
    # default: all PASS/no backlog -> not at risk
    om = {}
    for s in sids:
        om[f"STU{s:06d}"] = {
            sem: {"semester_result": "PASS", "backlog_count": 0}
            for sem in (1, 2, 3, 4, 5, 6)
        }
    return om


_OUTCOMES = _outcomes((1, 2, 3))


class TestValidExtraction(unittest.TestCase):

    def test_confirmed_maps_to_candidate_1(self):
        rows = [_fb("f1", "p1", "STU000001", "confirmed", "2026-08-01T00:00:00Z")]
        preds = {"p1": _m3_pred("p1", 1, 1)}
        rep = audit_prediction_feedback_labels(rows, predictions_map=preds, outcome_map=_OUTCOMES)
        bl = rep.bound_labels[0]
        self.assertEqual(bl.feedback_action, "confirmed")
        self.assertEqual(bl.candidate_label, 1)
        self.assertEqual(bl.student_id, "STU000001")

    def test_dismissed_maps_to_candidate_0(self):
        rows = [_fb("f1", "p1", "STU000001", "dismissed", "2026-08-01T00:00:00Z")]
        preds = {"p1": _m3_pred("p1", 1, 1)}
        rep = audit_prediction_feedback_labels(rows, predictions_map=preds, outcome_map=_OUTCOMES)
        self.assertEqual(rep.bound_labels[0].candidate_label, 0)

    def test_prediction_semester_and_target_mapping(self):
        # pred semester 1 -> target semester 2
        rows = [_fb("f1", "p1", "STU000001", "confirmed", "2026-08-01T00:00:00Z")]
        preds = {"p1": _m3_pred("p1", 1, 1)}
        rep = audit_prediction_feedback_labels(rows, predictions_map=preds, outcome_map=_OUTCOMES)
        bl = rep.bound_labels[0]
        self.assertEqual(bl.prediction_semester, 1)
        self.assertEqual(bl.target_semester, 2)
        self.assertEqual(bl.actual_at_risk, 0)


class TestInvalidRejection(unittest.TestCase):

    def test_unrecognized_action_skipped_not_mislabeled(self):
        rows = [_fb("f1", "p1", "STU000001", "bogus", "2026-08-01T00:00:00Z")]
        preds = {"p1": _m3_pred("p1", 1, 0)}
        rep = audit_prediction_feedback_labels(rows, predictions_map=preds, outcome_map=_OUTCOMES)
        self.assertEqual(rep.bound_labels, [])
        self.assertEqual(rep.invalid_action_values, 1)
        self.assertGreaterEqual(len(rep.rejected_rows), 1)

    def test_missing_prediction_record_rejected(self):
        rows = [_fb("f1", "p1", "STU000001", "confirmed", "2026-08-01T00:00:00Z")]
        rep = audit_prediction_feedback_labels(rows, predictions_map={}, outcome_map=_OUTCOMES)
        self.assertEqual(rep.bound_labels, [])
        self.assertTrue(any("missing_prediction_record" in r["reason"] for r in rep.rejected_rows))

    def test_non_m3_prediction_rejected(self):
        rows = [_fb("f1", "p1", "STU000001", "confirmed", "2026-08-01T00:00:00Z")]
        rep = audit_prediction_feedback_labels(
            rows, predictions_map={"p1": _non_m3_pred("p1")}, outcome_map=_OUTCOMES
        )
        self.assertEqual(rep.bound_labels, [])
        self.assertEqual(rep.non_m3_prediction_rows, 1)
        self.assertTrue(any("non_m3" in r["reason"] for r in rep.rejected_rows))

    def test_missing_prediction_period_rejected_as_unusable(self):
        pred = _m3_pred("p1", 1, 0)
        pred["prediction_value"] = {"is_at_risk_next_sem": 0}  # no semester_no
        rows = [_fb("f1", "p1", "STU000001", "confirmed", "2026-08-01T00:00:00Z")]
        rep = audit_prediction_feedback_labels(rows, predictions_map={"p1": pred}, outcome_map=_OUTCOMES)
        self.assertEqual(rep.missing_prediction_period, 1)
        self.assertTrue(any("missing_prediction_period" in r["reason"] for r in rep.rejected_rows))


class TestDuplicatesAndConflicts(unittest.TestCase):

    def test_latest_verdict_wins_on_duplicate_prediction(self):
        rows = [
            _fb("f1", "p1", "STU000001", "confirmed", "2026-08-01T00:00:00Z"),
            _fb("f2", "p1", "STU000001", "dismissed", "2026-08-02T00:00:00Z"),
        ]
        preds = {"p1": _m3_pred("p1", 1, 0)}
        rep = audit_prediction_feedback_labels(rows, predictions_map=preds, outcome_map=_OUTCOMES)
        # two rows for one prediction -> one resolved verdict (latest = dismissed)
        bound = [b for b in rep.bound_labels if b.prediction_id == "p1"]
        self.assertEqual(len(bound), 1)
        self.assertEqual(bound[0].feedback_action, "dismissed")
        self.assertEqual(rep.duplicate_cases, 1)

    def test_conflicting_verdicts_detected(self):
        rows = [
            _fb("f1", "p1", "STU000001", "confirmed", "2026-08-01T00:00:00Z"),
            _fb("f2", "p1", "STU000001", "dismissed", "2026-08-02T00:00:00Z"),
        ]
        rep = audit_prediction_feedback_labels(rows, predictions_map={"p1": _m3_pred("p1", 1, 0)}, outcome_map=_OUTCOMES)
        self.assertEqual(rep.conflicting_feedback_cases, 1)


class TestStudentAndTemporal(unittest.TestCase):

    def test_deployment_target_semester_not_usable(self):
        # pred semester 6 -> target semester 7 (deployment) -> not observable
        rows = [_fb("f1", "p1", "STU000001", "confirmed", "2026-08-01T00:00:00Z")]
        preds = {"p1": _m3_pred("p1", 6, 1)}
        rep = audit_prediction_feedback_labels(rows, predictions_map=preds, outcome_map=_OUTCOMES)
        bl = rep.bound_labels[0]
        self.assertFalse(bl.temporal_usable)
        self.assertEqual(bl.actual_at_risk, None)
        self.assertEqual(bl.agrees_with_ground_truth, None)

    def test_prediction_period_at_deployment_not_usable(self):
        rows = [_fb("f1", "p1", "STU000001", "confirmed", "2026-08-01T00:00:00Z")]
        preds = {"p1": _m3_pred("p1", 7, 1)}
        rep = audit_prediction_feedback_labels(rows, predictions_map=preds, outcome_map=_OUTCOMES)
        self.assertFalse(rep.bound_labels[0].temporal_usable)

    def test_conflicting_label_flagged(self):
        # dismissed but actual at-risk -> conflict
        om = {"STU000001": {sem: {"semester_result": "PASS", "backlog_count": 0}
                            for sem in (1, 2, 3, 4, 5, 6)}}
        om["STU000001"][2] = {"semester_result": "ATKT", "backlog_count": 2}
        rows = [_fb("f1", "p1", "STU000001", "dismissed", "2026-08-01T00:00:00Z")]
        rep = audit_prediction_feedback_labels(rows, predictions_map={"p1": _m3_pred("p1", 1, 1)}, outcome_map=om)
        bl = rep.bound_labels[0]
        self.assertTrue(bl.temporal_usable)
        self.assertEqual(bl.actual_at_risk, 1)
        self.assertFalse(bl.agrees_with_ground_truth)  # dismissed vs at-risk -> conflict

    def test_agreeing_label_flagged_consistent(self):
        om = {"STU000001": {sem: {"semester_result": "PASS", "backlog_count": 0}
                            for sem in (1, 2, 3, 4, 5, 6)}}
        om["STU000001"][2] = {"semester_result": "ATKT", "backlog_count": 1}
        rows = [_fb("f1", "p1", "STU000001", "confirmed", "2026-08-01T00:00:00Z")]
        rep = audit_prediction_feedback_labels(rows, predictions_map={"p1": _m3_pred("p1", 1, 1)}, outcome_map=om)
        bl = rep.bound_labels[0]
        self.assertTrue(bl.agrees_with_ground_truth)


class TestModelVsHumanDistinction(unittest.TestCase):

    def test_feedback_action_is_human_not_prediction_value(self):
        # prediction_value says at_risk=1, but human action differs and drives candidate
        rows = [_fb("f1", "p1", "STU000001", "dismissed", "2026-08-01T00:00:00Z")]
        preds = {"p1": _m3_pred("p1", 1, 1)}  # model predicted at-risk = 1
        rep = audit_prediction_feedback_labels(rows, predictions_map=preds, outcome_map=_OUTCOMES)
        bl = rep.bound_labels[0]
        # candidate label follows the HUMAN action (dismissed->0), not model's 1
        self.assertEqual(bl.candidate_label, 0)


class TestDeterminism(unittest.TestCase):

    def test_identical_inputs_identical_outputs(self):
        rows = [
            _fb("f1", "p1", "STU000001", "confirmed", "2026-08-01T00:00:00Z"),
            _fb("f2", "p2", "STU000002", "dismissed", "2026-08-01T00:00:00Z"),
        ]
        preds = {"p1": _m3_pred("p1", 1, 1), "p2": _m3_pred("p2", 3, 0)}
        r1 = audit_prediction_feedback_labels(rows, predictions_map=preds, outcome_map=_OUTCOMES)
        r2 = audit_prediction_feedback_labels(list(reversed(rows)), predictions_map=preds, outcome_map=_OUTCOMES)
        self.assertEqual(r1.summary(), r2.summary())
        self.assertEqual(
            [(b.student_id, b.prediction_id, b.candidate_label) for b in r1.bound_labels],
            [(b.student_id, b.prediction_id, b.candidate_label) for b in r2.bound_labels],
        )


if __name__ == "__main__":
    unittest.main()
