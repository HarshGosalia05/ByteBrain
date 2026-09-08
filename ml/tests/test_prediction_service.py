"""Tests for ML-05: Prediction Serving API.

Focused tests covering:
- PredictionService behavior with mock pool
- Data fetching and feature preparation integration
- Inference engine integration (M1-M4)
- Caching correctness
- Error handling for missing student data

All tests must be runnable using the ML environment without requiring FastAPI.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pandas as pd
import pytest

# Ensure ml/src is on sys.path for imports
_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

# _fetch_student_semester_summary imports ``app.repositories.student_repo``
# (backend package); add the repo root + backend so this file is runnable
# standalone (not only in a full-suite run).
for p in (str(Path(__file__).resolve().parents[2]),
          str(Path(__file__).resolve().parents[2] / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

from decimal import Decimal

from unittest.mock import MagicMock, patch, AsyncMock  # noqa: E402

from prediction_service import (  # noqa: E402
    PredictionService,
    fetch_m1_raw_data,
    fetch_m2m3_raw_data,
    fetch_m4_raw_data,
    _fetch_student_profile,
    _fetch_student_semester_summary,
    _fetch_career_preferences,
    _fetch_lifestyle_survey,
    _fetch_subject_type,
    _fetch_student_performance,
    _fetch_student_attendance,
)
from inference import (  # noqa: E402
    PredictionResult,
    M1Prediction,
    M3Prediction,
    M4Score,
)


# ---------------------------------------------------------------------------
# Mock pool and data fixtures
# ---------------------------------------------------------------------------


class AcquireContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class MockPool:
    """Minimal mock asyncpg Pool for testing."""

    def __init__(self):
        self._data: dict[str, Any] = {}

    def acquire(self):
        return AcquireContext(self)

    def transaction(self):
        return AcquireContext(self)

    async def fetch(self, *args, **kwargs):
        return []

    async def fetchrow(self, *args, **kwargs):
        return None

    async def fetchval(self, *args, **kwargs):
        return None

    async def execute(self, *args, **kwargs):
        return ""


def _make_mock_pool(student_data: dict | None = None,
                    performance_data: list | None = None,
                    semester_data: list | None = None,
                    career_data: dict | None = None,
                    lifestyle_data: dict | None = None) -> MockPool:
    """Create a MockPool with predefined data returns."""

    pool = MockPool()

    # Student profile
    if student_data is None:
        student_data = {
            "student_id": "STU000001",
            "enrollment_no": "EN001",
            "full_name": "Alice",
            "department_name": "CSE",
            "current_semester": 3,
            "gender": "Female",
        }
    pool._data["profile"] = student_data

    # Semester summaries
    if semester_data is None:
        semester_data = [
            {
                "semester": 1,
                "sgpa": 8.5,
                "total_credits_earned": 22,
                "attendance_percentage": 88.0,
                "active_backlogs": 0,
                "academic_year": "2024-25",
                "subjects_registered": 6,
                "credits_registered": 22,
                "semester_total_marks": 807.0,
                "semester_percentage": 75.0,
                "semester_grade": "A",
                "semester_result": "PASS",
                "academic_standing": "Good",
            }
        ]
    pool._data["semester"] = semester_data

    # Subject performance
    if performance_data is None:
        performance_data = [
            {
                "semester": 1,
                "subject_id": "SUB1",
                "subject_code": "CSE101",
                "subject_name": "Introduction to Programming",
                "credits": 4,
                "internal_marks": 20.0,
                "mid_sem_marks": 25.0,
                "end_sem_marks": None,
                "total_marks": 100.0,
                "percentage": 45.0,
                "grade": "C",
                "grade_point": 5.0,
                "result_status": "ATKT",
                "attempt_number": 1,
                "performance_category": "Third Class",
                "remarks": None,
                "updated_at": None,
                "attendance_percentage": 85.0,
                "enrollment_record_id": "REC1",
            }
        ]
    pool._data["performance"] = performance_data

    # Career preferences
    if career_data is None:
        career_data = {
            "student_id": "STU000001",
            "preferred_domain": "Software",
            "dream_job_role": "Software Engineer",
            "preferred_industry": "IT",
            "preferred_work_mode": "Remote",
            "target_package_lpa": None,
            "higher_studies_interest": "Yes",
            "entrepreneurship_interest": "No",
            "certification_interest": "AWS Solutions Architect",
            "internship_completed": "Yes",
            "placement_readiness_level": None,
            "survey_date": "2024-08-01",
        }
    pool._data["career"] = career_data

    # Lifestyle survey
    if lifestyle_data is None:
        lifestyle_data = {
            "student_id": "STU000001",
            "daily_study_hours": 6,
            "attendance_commitment": "Good",
            "mental_wellbeing": "Good",
            "stress_level": "Low",
            "average_sleep_hours": 7.5,
            "physical_activity": "Moderate",
        }
    pool._data["lifestyle"] = lifestyle_data

    # Subject type mapping
    pool._data["subject_type"] = [
        {"subject_id": "SUB1", "subject_type": "core", "credits": 4.0}
    ]

    async def fetchrow_side_effect(query, *args, **kwargs):
        """Mock fetchrow based on known query patterns."""
        q = query.lower()
        if "semester_summary" in q or "student_semester_summary" in q:
            return semester_data[0] if semester_data else None
        if "career_preferences" in q:
            return career_data
        if "lifestyle_survey" in q:
            return lifestyle_data
        if "subject_type" in q:
            return pool._data.get("subject_type")
        if "attendance" in q:
            return {"enrollment_record_id": "REC1", "attendance_percentage": 85.0}
        if "students" in q:
            return student_data
        return None

    async def fetch_side_effect(query, *args, **kwargs):
        """Mock fetch based on known query patterns."""
        q = query.lower()
        if "semester_summary" in q or "student_semester_summary" in q:
            return semester_data
        if "career_preferences" in q:
            return [career_data]
        if "lifestyle_survey" in q:
            return [lifestyle_data]
        if "subject_type" in q:
            return pool._data.get("subject_type")
        if "subject_performance" in q or "student_subject_enrollment" in q:
            return performance_data
        if "attendance" in q:
            return [{"enrollment_record_id": "REC1", "attendance_percentage": 85.0}]
        if "students" in q:
            return [student_data]
        return []

    pool.fetchrow = fetchrow_side_effect
    pool.fetch = fetch_side_effect

    return pool


# ---------------------------------------------------------------------------
# PredictionService Tests
# ---------------------------------------------------------------------------


class TestPredictionServiceInitialization:
    """Verify PredictionService can be instantiated and has all methods."""

    def test_service_instantiation_with_pool(self):
        pool = MockPool()
        svc = PredictionService(pool)
        assert svc is not None
        assert svc.pool is pool
        assert svc._inference is not None
        assert hasattr(svc, "predict_m1_for_student")
        assert hasattr(svc, "predict_m3_for_student")
        assert hasattr(svc, "predict_m4_for_student")
        assert hasattr(svc, "clear_cache")
        assert hasattr(svc, "clear_student_cache")
        # M2 is served by the validated M2-TP package through the backend
        # M2TPPredictionService, NOT through PredictionService/InferenceService.
        assert not hasattr(svc, "predict_m2_for_student")

    def test_service_cache_isolated_per_instance(self):
        pool1 = MockPool()
        pool2 = MockPool()
        svc1 = PredictionService(pool1)
        svc2 = PredictionService(pool2)
        # Caches are independent
        assert svc1._cache is not svc2._cache


class TestPredictionServiceM1:
    """M1 prediction service tests."""

    def test_predict_m1_service_path(self):
        """Test that predict_m1_for_student is callable and returns result."""
        pool = _make_mock_pool()
        svc = PredictionService(pool)

        # Verify method exists and is callable
        assert callable(getattr(svc, "predict_m1_for_student", None))

    def test_predict_m1_returns_prediction_result(self):
        """Test M1 service returns proper PredictionResult structure."""
        pool = _make_mock_pool()
        svc = PredictionService(pool)
        result = asyncio.run(svc.predict_m1_for_student("STU000001"))
        assert result is not None
        assert result.model_id == "m1"
        assert hasattr(result, "predictions")
        assert hasattr(result, "input_row_count")
        assert hasattr(result, "prediction_count")


class TestPredictionServiceM3:
    """M3 prediction service tests."""

    def test_predict_m3_service_path(self):
        pool = _make_mock_pool()
        svc = PredictionService(pool)
        assert callable(getattr(svc, "predict_m3_for_student", None))


class TestPredictionServiceM4:
    """M4 prediction service tests."""

    def test_predict_m4_service_path(self):
        pool = _make_mock_pool()
        svc = PredictionService(pool)
        assert callable(getattr(svc, "predict_m4_for_student", None))

    def test_predict_m4_with_missing_lifestyle(self):
        """M4 should be callable even if lifestyle data is incomplete."""
        pool = MockPool()
        # Remove lifestyle data from pool
        pool._data = {k: v for k, v in pool._data.items() if k != "lifestyle"}

        svc = PredictionService(pool)
        assert callable(getattr(svc, "predict_m4_for_student", None))

    def test_predict_m4_returns_structured_result(self):
        pool = _make_mock_pool()
        svc = PredictionService(pool)
        result = asyncio.run(svc.predict_m4_for_student("STU000001"))
        assert result is not None
        assert result.model_id == "m4"
        assert hasattr(result, "predictions")
        if result.predictions:
            pred = result.predictions[0]
            assert hasattr(pred, "career_readiness_score")
            assert hasattr(pred, "career_readiness_level")
            assert hasattr(pred, "positive_factors")
            assert hasattr(pred, "risk_factors")


# ---------------------------------------------------------------------------
# Data Fetcher Tests
# ---------------------------------------------------------------------------


class TestDataFetchers:
    """Test the low-level data fetching helpers."""

    def test_fetch_student_profile_returns_dataframe(self):
        pool = _make_mock_pool()
        result = asyncio.run(_fetch_student_profile(pool, "STU000001"))
        assert isinstance(result, pd.DataFrame)
        assert result["student_id"].iloc[0] == "STU000001"

    def test_fetch_student_semester_summary_returns_dataframe(self):
        pool = _make_mock_pool()
        result = asyncio.run(_fetch_student_semester_summary(pool, "STU000001"))
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result["semester_no"].iloc[0] == 1

    def test_fetch_semester_summary_populates_semester_total_marks(self):
        """semester_total_marks must come from real DB data, never default 0.0.

        Regression: StudentRepository.get_semester_summaries did not SELECT
        semester_total_marks, so serving silently fed the trained model a
        constant 0.0. This test fails if the value is missing, NaN, or 0.0
        while the mock DB row provides it.
        """
        pool = _make_mock_pool()
        result = asyncio.run(_fetch_student_semester_summary(pool, "STU000001"))
        assert "semester_total_marks" in result.columns
        value = result["semester_total_marks"].iloc[0]
        assert not pd.isna(value), "semester_total_marks silently became NA"
        assert value != 0.0, "semester_total_marks silently defaulted to 0.0"
        assert value == 807.0

    def test_fetch_semester_summary_maps_attendance_percentage(self):
        """attendance_percentage must be mapped to semester_attendance_percentage.

        Regression: the repo aliases semester_attendance_percentage AS
        attendance_percentage, and the service never remapped it, so the M2/M3
        feature was always NA (imputer median). This test fails if the mapped
        value is missing, NaN, or 0.0 while the mock DB row provides it.
        """
        pool = _make_mock_pool()
        result = asyncio.run(_fetch_student_semester_summary(pool, "STU000001"))
        assert "semester_attendance_percentage" in result.columns
        value = result["semester_attendance_percentage"].iloc[0]
        assert not pd.isna(value), "semester_attendance_percentage silently became NA"
        assert value != 0.0, "semester_attendance_percentage silently defaulted to 0.0"
        assert value == 88.0

    def test_fetch_career_preferences_returns_dataframe(self):
        pool = _make_mock_pool()
        result = asyncio.run(_fetch_career_preferences(pool, "STU000001"))
        assert isinstance(result, pd.DataFrame)
        assert result["internship_completed"].iloc[0] == "Yes"

    def test_fetch_lifestyle_survey_returns_dataframe(self):
        pool = _make_mock_pool()
        result = asyncio.run(_fetch_lifestyle_survey(pool, "STU000001"))
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    def test_fetch_lifestyle_survey_returns_empty_when_missing(self):
        """Empty DataFrame when no lifestyle survey exists."""
        pool = MockPool()
        result = asyncio.run(_fetch_lifestyle_survey(pool, "STU999999"))
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_fetch_lifestyle_survey_normalizes_decimal_numerics(self):
        """asyncpg returns NUMERIC as decimal.Decimal; numeric columns must be
        normalized to float so the M4 rule engine never mixes Decimal + float."""
        lifestyle_data = {
            "student_id": "STU000001",
            "daily_study_hours": Decimal("6.0"),
            "attendance_commitment": "Good",
            "mental_wellbeing": "Good",
            "stress_level": "Low",
            "average_sleep_hours": Decimal("7.5"),
            "physical_activity": "Moderate",
        }
        pool = _make_mock_pool(lifestyle_data=lifestyle_data)
        result = asyncio.run(_fetch_lifestyle_survey(pool, "STU000001"))
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        for col in ("daily_study_hours", "average_sleep_hours"):
            assert pd.api.types.is_float_dtype(result[col]), (
                f"{col} should be float, got {result[col].dtype}"
            )
            assert not isinstance(result[col].iloc[0], Decimal)

    def test_predict_m4_works_with_decimal_lifestyle_values(self):
        """End-to-end M4 flow must succeed when lifestyle survey numerics are
        returned as decimal.Decimal (the real asyncpg behavior)."""
        lifestyle_data = {
            "student_id": "STU000001",
            "daily_study_hours": Decimal("6.0"),
            "attendance_commitment": "Good",
            "mental_wellbeing": "Good",
            "stress_level": "Low",
            "average_sleep_hours": Decimal("7.5"),
            "physical_activity": "Moderate",
        }
        pool = _make_mock_pool(lifestyle_data=lifestyle_data)
        svc = PredictionService(pool)
        result = asyncio.run(svc.predict_m4_for_student("STU000001"))
        assert result is not None
        assert result.model_id == "m4"
        assert result.predictions

    def test_fetch_subject_type_returns_dataframe(self):
        pool = _make_mock_pool()
        result = asyncio.run(_fetch_subject_type(pool, "STU000001"))
        assert isinstance(result, pd.DataFrame)
        # Should have subject_type column
        if "subject_type" in result.columns:
            assert result["subject_type"].iloc[0] == "core"


# ---------------------------------------------------------------------------
# Integration-Style Tests (with mocked DB)
# ---------------------------------------------------------------------------


class TestServiceIntegration:
    """Integration-style tests with mocked database access."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.pool = _make_mock_pool()
        self.svc = PredictionService(self.pool)

    def test_m1_full_service_flow(self):
        """Test M1 service flow from data fetch to inference result."""
        result = asyncio.run(self.svc.predict_m1_for_student("STU000001"))
        assert result is not None
        assert result.model_id == "m1"
        assert hasattr(result, "predictions")
        assert hasattr(result, "input_row_count")
        assert hasattr(result, "prediction_count")

    def test_m3_full_service_flow(self):
        """Test M3 service flow from data fetch to inference result."""
        result = asyncio.run(self.svc.predict_m3_for_student("STU000001"))
        assert result is not None
        assert result.model_id == "m3"
        assert hasattr(result, "predictions")
        if result.predictions:
            pred = result.predictions[0]
            assert hasattr(pred, "is_at_risk_next_sem")
            # Should be 0 or 1
            assert pred.is_at_risk_next_sem in (0, 1)

    def test_m4_full_service_flow(self):
        """Test M4 service flow from data fetch to inference result."""
        result = asyncio.run(self.svc.predict_m4_for_student("STU000001"))
        assert result is not None
        assert result.model_id == "m4"
        assert hasattr(result, "predictions")
        if result.predictions:
            pred = result.predictions[0]
            assert hasattr(pred, "career_readiness_score")
            assert hasattr(pred, "career_readiness_level")
            assert hasattr(pred, "positive_factors")
            assert hasattr(pred, "risk_factors")


# ---------------------------------------------------------------------------
# Caching Tests
# ---------------------------------------------------------------------------


class TestCaching:
    """Test prediction caching behavior."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.pool = _make_mock_pool()
        self.svc = PredictionService(self.pool)

    def test_cache_stores_m1_result(self):
        """First call fetches and caches; second call returns cached result."""
        result1 = asyncio.run(self.svc.predict_m1_for_student("STU000001"))
        assert ("m1", "STU000001") in self.svc._cache
        result2 = asyncio.run(self.svc.predict_m1_for_student("STU000001"))
        assert result1.model_id == result2.model_id
        assert result1.predictions == result2.predictions

    def test_cache_key_includes_model_type(self):
        """Distinct model types must not share a cache entry for one student."""
        m1 = asyncio.run(self.svc.predict_m1_for_student("STU000001"))
        m3 = asyncio.run(self.svc.predict_m3_for_student("STU000001"))
        assert m1.model_id == "m1"
        assert m3.model_id == "m3"
        assert ("m1", "STU000001") in self.svc._cache
        assert ("m3", "STU000001") in self.svc._cache

    def test_clear_cache(self):
        """Clear all cached predictions."""
        asyncio.run(self.svc.predict_m1_for_student("STU000001"))
        assert len(self.svc._cache) > 0
        self.svc.clear_cache()
        assert len(self.svc._cache) == 0

    def test_clear_student_cache(self):
        """Clear cache for a specific student (all model types)."""
        asyncio.run(self.svc.predict_m1_for_student("STU000001"))
        assert ("m1", "STU000001") in self.svc._cache
        self.svc.clear_student_cache("STU000001")
        assert ("m1", "STU000001") not in self.svc._cache


# ---------------------------------------------------------------------------
# Error Handling Tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test error handling for missing student data."""

    @pytest.fixture(autouse=True)
    def _setup_no_data(self):
        pool = MockPool()  # Empty pool - no data
        self.svc = PredictionService(pool)

    def test_m1_raises_when_no_data(self):
        """M1 should raise ValueError when no student data found."""
        import asyncio
        try:
            asyncio.run(self.svc.predict_m1_for_student("STU_NONEXISTENT"))
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "No data found" in str(e)

    def test_m3_raises_when_no_data(self):
        """M3 should raise ValueError when no student data found."""
        import asyncio
        try:
            asyncio.run(self.svc.predict_m3_for_student("STU_NONEXISTENT"))
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "No data found" in str(e)

    def test_m4_raises_when_no_data(self):
        """M4 should raise ValueError when no student data found."""
        import asyncio
        try:
            asyncio.run(self.svc.predict_m4_for_student("STU_NONEXISTENT"))
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "No data found" in str(e)


# ---------------------------------------------------------------------------
# Raw Data Parameter Tests
# ---------------------------------------------------------------------------


class TestRawDataParam:
    """Test optional raw data parameters in M1-M4 prediction methods."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.pool = _make_mock_pool()
        self.svc = PredictionService(self.pool)

    def test_m1_with_raw_data(self):
        perf = asyncio.run(_fetch_student_performance(self.pool, "STU000001"))
        att = asyncio.run(_fetch_student_attendance(self.pool, "STU000001"))
        subs = asyncio.run(_fetch_subject_type(self.pool, "STU000001"))
        students = asyncio.run(_fetch_student_profile(self.pool, "STU000001"))
        
        raw = (perf, att, subs, students)
        empty_pool = MockPool()
        svc_empty = PredictionService(empty_pool)
        
        res = asyncio.run(svc_empty.predict_m1_for_student("STU000001", raw=raw))
        assert res.model_id == "m1"
        assert len(res.predictions) > 0
        
        svc_empty.clear_cache()
        with pytest.raises(ValueError) as exc:
            asyncio.run(svc_empty.predict_m1_for_student("STU000001", raw=(perf, att)))
        assert "m1 raw data must be" in str(exc.value)

    def test_m3_with_raw_data(self):
        summary = asyncio.run(_fetch_student_semester_summary(self.pool, "STU000001"))
        students = asyncio.run(_fetch_student_profile(self.pool, "STU000001"))
        raw = (summary, students)
        empty_pool = MockPool()
        svc_empty = PredictionService(empty_pool)
        
        res = asyncio.run(svc_empty.predict_m3_for_student("STU000001", raw=raw))
        assert res.model_id == "m3"
        
        svc_empty.clear_cache()
        with pytest.raises(ValueError):
            asyncio.run(svc_empty.predict_m3_for_student("STU000001", raw=(summary,)))

    def test_m4_with_raw_data(self):
        students = asyncio.run(_fetch_student_profile(self.pool, "STU000001"))
        semester = asyncio.run(_fetch_student_semester_summary(self.pool, "STU000001"))
        career = asyncio.run(_fetch_career_preferences(self.pool, "STU000001"))
        lifestyle = asyncio.run(_fetch_lifestyle_survey(self.pool, "STU000001"))
        
        raw = (students, semester, career, lifestyle)
        empty_pool = MockPool()
        svc_empty = PredictionService(empty_pool)
        
        res = asyncio.run(svc_empty.predict_m4_for_student("STU000001", raw=raw))
        assert res.model_id == "m4"
        
        svc_empty.clear_cache()
        with pytest.raises(ValueError):
            asyncio.run(svc_empty.predict_m4_for_student("STU000001", raw=(students, semester)))


# Run tests from CLI: python -m pytest test_prediction_service.py -v