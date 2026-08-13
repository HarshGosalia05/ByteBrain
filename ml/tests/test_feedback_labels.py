"""Tests for ML-12 §12.4 feedback label rendering (pure, read-only).

Covers:
  - confirmed -> is_at_risk_label 1, dismissed -> 0
  - latest verdict wins per prediction (append-only source)
  - full audit history when latest_per_prediction=False
  - NULL note / model_version preserved (never coerced)
  - unknown actions skipped, deterministic ordering, summary counts
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from feedback_labels import labeled_dataset_summary, latest_verdicts, render_feedback_labels

_TS = {"old": "2026-08-01T10:00:00+00:00", "new": "2026-08-02T10:00:00+00:00"}


def row(prediction_id, action, *, when="2026-08-01T10:00:00+00:00", note=None,
        version="3.2.1", student_id="STU001", faculty_id="FAC001", fid=None):
    return {
        "feedback_id": fid or f"fb-{prediction_id}-{when[:10]}",
        "prediction_id": prediction_id,
        "student_id": student_id,
        "faculty_id": faculty_id,
        "feedback_action": action,
        "note": note,
        "model_version": version,
        "feedback_timestamp": when,
    }


def test_confirmed_maps_to_label_1():
    labels = render_feedback_labels([row("p1", "confirmed")])
    assert len(labels) == 1
    assert labels[0]["label"] == "confirmed"
    assert labels[0]["is_at_risk_label"] == 1


def test_dismissed_maps_to_label_0():
    labels = render_feedback_labels([row("p1", "dismissed")])
    assert labels[0]["label"] == "dismissed"
    assert labels[0]["is_at_risk_label"] == 0


def test_latest_verdict_wins_per_prediction():
    rows = [
        row("p1", "confirmed", when=_TS["old"]),
        row("p1", "dismissed", when=_TS["new"]),
    ]
    labels = render_feedback_labels(rows)
    assert len(labels) == 1
    assert labels[0]["feedback_timestamp"] == rows[1]["feedback_timestamp"]
    assert labels[0]["is_at_risk_label"] == 0


def test_latest_verdict_deterministic_on_equal_timestamps():
    rows = [
        row("p1", "dismissed", when=_TS["old"]),
        row("p1", "confirmed", when=_TS["old"]),
    ]
    labels = render_feedback_labels(rows)
    # Equal timestamps fall back to input order: the last row wins.
    assert len(labels) == 1
    assert labels[0]["is_at_risk_label"] == 1


def test_full_history_when_latest_per_prediction_false():
    rows = [
        row("p1", "confirmed", when=_TS["old"]),
        row("p1", "dismissed", when=_TS["new"]),
    ]
    labels = render_feedback_labels(rows, latest_per_prediction=False)
    assert len(labels) == 2


def test_null_note_and_version_preserved():
    labels = render_feedback_labels([row("p1", "confirmed", note=None, version=None)])
    assert labels[0]["note"] is None
    assert labels[0]["model_version"] is None


def test_unknown_action_skipped():
    rows = [row("p1", "confirmed"), {"prediction_id": "p2", "feedback_action": "override"}]
    labels = render_feedback_labels(rows, latest_per_prediction=False)
    assert [l["prediction_id"] for l in labels] == ["p1"]


def test_latest_verdicts_ignores_rows_without_prediction_id():
    rows = [row("p1", "confirmed"), {"feedback_action": "dismissed"}]
    verdicts = latest_verdicts(rows)
    assert len(verdicts) == 1
    assert verdicts[0]["prediction_id"] == "p1"


def test_summary_counts_are_deterministic():
    rows = [
        row("p1", "confirmed"),
        row("p2", "confirmed", version=None),
        row("p3", "dismissed"),
    ]
    summary = labeled_dataset_summary(render_feedback_labels(rows))
    assert summary == {
        "total": 3,
        "confirmed": 2,
        "dismissed": 1,
        "without_model_version": 1,
    }
