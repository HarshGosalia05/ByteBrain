"""Focused unit tests for ML-13 Slice 1: Feedback Dataset Extraction & Validation."""

from __future__ import annotations

import pandas as pd
import pytest

from ml.src.features import M3_CONTRACT
from ml.src.retrain_m3 import (
    FeedbackDatasetResult,
    extract_and_validate_feedback_dataset,
)


@pytest.fixture
def sample_m3_features():
    """Valid raw feature dictionary for a student."""
    return {
        "semester_no": 4,
        "subjects_registered": 6,
        "credits_registered": 24,
        "credits_earned": 24,
        "semester_total_marks": 580,
        "semester_percentage": 72.5,
        "semester_sgpa": 7.8,
        "semester_attendance_percentage": 85.0,
        "backlog_count": 0,
        "department_name": "CSE",
        "gender": "Male",
    }


def test_confirmed_and_dismissed_label_mapping(sample_m3_features):
    """Verify confirmed -> 1 and dismissed -> 0."""
    feedback_rows = [
        {
            "feedback_id": "fb-1",
            "prediction_id": "pred-1",
            "student_id": "STU001",
            "feedback_action": "confirmed",
            "feedback_timestamp": "2026-08-13T10:00:00Z",
        },
        {
            "feedback_id": "fb-2",
            "prediction_id": "pred-2",
            "student_id": "STU002",
            "feedback_action": "dismissed",
            "feedback_timestamp": "2026-08-13T10:05:00Z",
        },
    ]
    predictions_map = {
        "pred-1": {"prediction_id": "pred-1", "prediction_type": "m3"},
        "pred-2": {"prediction_id": "pred-2", "prediction_type": "m3"},
    }
    student_features_map = {
        "STU001": sample_m3_features,
        "STU002": sample_m3_features,
    }

    result = extract_and_validate_feedback_dataset(
        feedback_rows,
        predictions_map,
        student_features_map,
        min_samples=2,
    )

    assert result.status == "sufficient_data"
    assert result.can_retrain is True
    assert result.counts_summary["confirmed_records"] == 1
    assert result.counts_summary["dismissed_records"] == 1
    assert result.counts_summary["positive_labels"] == 1
    assert result.counts_summary["negative_labels"] == 1
    assert list(result.labels_series.values) == [1, 0]


def test_empty_feedback_dataset():
    """Verify empty feedback rows return insufficient_feedback_data cleanly."""
    result = extract_and_validate_feedback_dataset([], {}, {}, min_samples=30)
    assert result.status == "insufficient_feedback_data"
    assert result.can_retrain is False
    assert result.counts_summary["total_feedback_records"] == 0
    assert result.counts_summary["eligible_labeled_samples"] == 0


def test_insufficient_sample_threshold(sample_m3_features):
    """Verify sample counts below min_samples return insufficient_feedback_data."""
    feedback_rows = [
        {
            "feedback_id": "fb-1",
            "prediction_id": "pred-1",
            "student_id": "STU001",
            "feedback_action": "confirmed",
            "feedback_timestamp": "2026-08-13T10:00:00Z",
        }
    ]
    predictions_map = {"pred-1": {"prediction_id": "pred-1", "prediction_type": "m3"}}
    student_features_map = {"STU001": sample_m3_features}

    result = extract_and_validate_feedback_dataset(
        feedback_rows,
        predictions_map,
        student_features_map,
        min_samples=30,
    )

    assert result.status == "insufficient_feedback_data"
    assert result.can_retrain is False
    assert "below minimum threshold (30)" in result.reason
    assert result.counts_summary["eligible_labeled_samples"] == 1


def test_duplicate_and_conflicting_feedback_resolution(sample_m3_features):
    """Verify duplicate and conflicting reviews resolve to latest verdict."""
    feedback_rows = [
        {
            "feedback_id": "fb-old",
            "prediction_id": "pred-1",
            "student_id": "STU001",
            "feedback_action": "confirmed",
            "feedback_timestamp": "2026-08-13T10:00:00Z",
        },
        {
            "feedback_id": "fb-new",
            "prediction_id": "pred-1",
            "student_id": "STU001",
            "feedback_action": "dismissed",
            "feedback_timestamp": "2026-08-13T11:00:00Z",
        },
    ]
    predictions_map = {"pred-1": {"prediction_id": "pred-1", "prediction_type": "m3"}}
    student_features_map = {"STU001": sample_m3_features}

    result = extract_and_validate_feedback_dataset(
        feedback_rows,
        predictions_map,
        student_features_map,
        min_samples=1,
    )

    assert result.counts_summary["total_feedback_records"] == 2
    assert result.counts_summary["duplicate_feedback_cases"] == 1
    assert result.counts_summary["conflicting_feedback_cases"] == 1
    assert result.counts_summary["eligible_labeled_samples"] == 1
    # Latest verdict (dismissed) wins
    assert result.counts_summary["negative_labels"] == 1
    assert result.counts_summary["positive_labels"] == 0


def test_null_missing_feature_handling():
    """Verify missing feature values stay None/NaN and are not coerced to 0."""
    features_with_null = {
        "semester_no": 4,
        "subjects_registered": 6,
        "credits_registered": None,  # NULL feature
        "credits_earned": 24,
        "semester_total_marks": None,  # NULL feature
        "semester_percentage": 72.5,
        "semester_sgpa": 7.8,
        "semester_attendance_percentage": None,  # NULL feature
        "backlog_count": 0,
        "department_name": "CSE",
        "gender": "Female",
    }
    feedback_rows = [
        {
            "feedback_id": "fb-1",
            "prediction_id": "pred-1",
            "student_id": "STU001",
            "feedback_action": "confirmed",
            "feedback_timestamp": "2026-08-13T10:00:00Z",
        },
        {
            "feedback_id": "fb-2",
            "prediction_id": "pred-2",
            "student_id": "STU002",
            "feedback_action": "dismissed",
            "feedback_timestamp": "2026-08-13T10:05:00Z",
        },
    ]
    predictions_map = {
        "pred-1": {"prediction_id": "pred-1", "prediction_type": "m3"},
        "pred-2": {"prediction_id": "pred-2", "prediction_type": "m3"},
    }
    student_features_map = {
        "STU001": features_with_null,
        "STU002": features_with_null,
    }

    result = extract_and_validate_feedback_dataset(
        feedback_rows,
        predictions_map,
        student_features_map,
        min_samples=2,
    )

    assert result.status == "sufficient_data"
    X = result.features_df
    assert pd.isna(X.loc[0, "credits_registered"])
    assert pd.isna(X.loc[0, "semester_total_marks"])
    assert pd.isna(X.loc[0, "semester_attendance_percentage"])
    assert result.counts_summary["feature_completeness_pct"] < 100.0


def test_deterministic_ordering(sample_m3_features):
    """Verify extracted dataset rows are ordered deterministically by student_id."""
    feedback_rows = [
        {
            "feedback_id": "fb-b",
            "prediction_id": "pred-b",
            "student_id": "STU_B",
            "feedback_action": "dismissed",
            "feedback_timestamp": "2026-08-13T10:00:00Z",
        },
        {
            "feedback_id": "fb-a",
            "prediction_id": "pred-a",
            "student_id": "STU_A",
            "feedback_action": "confirmed",
            "feedback_timestamp": "2026-08-13T10:00:00Z",
        },
    ]
    predictions_map = {
        "pred-a": {"prediction_id": "pred-a", "prediction_type": "m3"},
        "pred-b": {"prediction_id": "pred-b", "prediction_type": "m3"},
    }
    student_features_map = {
        "STU_A": sample_m3_features,
        "STU_B": sample_m3_features,
    }

    result = extract_and_validate_feedback_dataset(
        feedback_rows,
        predictions_map,
        student_features_map,
        min_samples=2,
    )

    # First row must be STU_A, second STU_B
    assert list(result.features_df.index) == [0, 1]
    assert list(result.labels_series.values) == [1, 0]


def test_exact_m3_feature_contract_compatibility(sample_m3_features):
    """Verify extracted features match M3_CONTRACT.raw_features exactly."""
    feedback_rows = [
        {
            "feedback_id": "fb-1",
            "prediction_id": "pred-1",
            "student_id": "STU001",
            "feedback_action": "confirmed",
            "feedback_timestamp": "2026-08-13T10:00:00Z",
        },
        {
            "feedback_id": "fb-2",
            "prediction_id": "pred-2",
            "student_id": "STU002",
            "feedback_action": "dismissed",
            "feedback_timestamp": "2026-08-13T10:00:00Z",
        },
    ]
    predictions_map = {
        "pred-1": {"prediction_id": "pred-1", "prediction_type": "m3"},
        "pred-2": {"prediction_id": "pred-2", "prediction_type": "m3"},
    }
    student_features_map = {
        "STU001": sample_m3_features,
        "STU002": sample_m3_features,
    }

    result = extract_and_validate_feedback_dataset(
        feedback_rows,
        predictions_map,
        student_features_map,
        min_samples=2,
    )

    assert list(result.features_df.columns) == M3_CONTRACT.raw_features
