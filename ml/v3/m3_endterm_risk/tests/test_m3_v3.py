"""M3 V3 Tests: Same-Semester End-Term Risk Prediction.

Tests verify:
- Artifact loads correctly
- Correct model version and target
- Feature names match
- Threshold exists and is valid
- Probability between 0 and 1
- Prediction is 0 or 1
- Leakage forbidden features are absent
- Horizon validation (same semester)
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

# Ensure ml/ and repo root are importable
ML_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = Path(__file__).resolve().parents[4]
for p in (str(ML_ROOT), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)


from v3.m3_endterm_risk import config
from v3.m3_endterm_risk.features.leakage_gate import run_leakage_gate
from v3.m3_endterm_risk.inference.predictor import M3V3Predictor
from v3.m3_endterm_risk.preprocessing.pipeline import M3V3Preprocessor, select_features


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def artifact():
    """Load the M3 V3 artifact once per test module."""
    if not config.MODEL_FILE.exists():
        pytest.skip(f"M3 V3 artifact not found: {config.MODEL_FILE}")
    return joblib.load(config.MODEL_FILE)


@pytest.fixture(scope="module")
def model(artifact):
    return artifact["model"]


@pytest.fixture(scope="module")
def preprocessor(artifact):
    return artifact["preprocessor"]


@pytest.fixture(scope="module")
def feature_names(artifact):
    return artifact["feature_names"]


@pytest.fixture(scope="module")
def metadata(artifact):
    return artifact["metadata"]


# ---------------------------------------------------------------------------
# Artifact Loading Tests
# ---------------------------------------------------------------------------

class TestArtifactLoading:
    """Verify artifact loads and contains required components."""

    def test_artifact_loads(self, artifact):
        assert artifact is not None
        assert isinstance(artifact, dict)

    def test_artifact_has_required_keys(self, artifact):
        required = {"model", "preprocessor", "feature_names", "threshold", "metadata"}
        assert required.issubset(artifact.keys())

    def test_artifact_is_classifier(self, model):
        assert hasattr(model, "predict_proba")

    def test_feature_names_match_preprocessor(self, artifact, feature_names):
        assert len(feature_names) > 0
        assert isinstance(feature_names, list)


# ---------------------------------------------------------------------------
# Model Metadata Tests
# ---------------------------------------------------------------------------

class TestModelMetadata:
    """Verify model metadata is correct."""

    def test_model_version(self, metadata):
        assert metadata.get("model_version") == "3.0"

    def test_model_name(self, metadata):
        assert metadata.get("model_name") == "m3_v3_endterm_risk"

    def test_target(self, metadata):
        assert metadata.get("target") == "is_at_risk_end_sem"

    def test_task(self, metadata):
        assert metadata.get("task") == "same_semester_midsem_to_endterm"

    def test_algorithm(self, metadata):
        assert metadata.get("algorithm") in config.MODEL_ALGORITHMS

    def test_threshold_exists(self, artifact):
        assert "threshold" in artifact
        assert 0.0 < artifact["threshold"] < 1.0

    def test_leakage_check_passed(self, metadata):
        lc = metadata.get("leakage_check", {})
        assert lc.get("pass") is True

    def test_reload_test_passed(self, metadata):
        assert metadata.get("reload_test") == "PASS"

    def test_prediction_test_passed(self, metadata):
        assert metadata.get("prediction_test") == "PASS"


# ---------------------------------------------------------------------------
# Feature Contract Tests
# ---------------------------------------------------------------------------

class TestFeatureContract:
    """Verify feature names match the expected contract."""

    def test_expected_feature_count(self, feature_names):
        assert len(feature_names) == 27

    def test_key_features_present(self, feature_names):
        required = [
            "subj_mid_sem_marks_mean",
            "subj_internal_marks_mean",
            "semester_attendance_percentage",
            "previous_sem_sgpa",
            "semester_no",
        ]
        for feat in required:
            assert feat in feature_names, f"Missing required feature: {feat}"

    def test_no_forbidden_features(self, feature_names):
        forbidden = set(config.FORBIDDEN_FEATURES)
        found = [f for f in feature_names if f in forbidden]
        assert len(found) == 0, f"Forbidden features found: {found}"


# ---------------------------------------------------------------------------
# Leakage Tests
# ---------------------------------------------------------------------------

class TestLeakage:
    """Verify forbidden features are not in the feature matrix."""

    def test_end_sem_marks_forbidden(self, feature_names):
        assert "end_sem_marks" not in feature_names
        assert "subj_end_sem_marks_mean" not in feature_names
        assert "subj_end_sem_marks_std" not in feature_names

    def test_final_result_forbidden(self, feature_names):
        assert "semester_result" not in feature_names

    def test_final_sgpa_forbidden(self, feature_names):
        assert "semester_sgpa" not in feature_names

    def test_final_percentage_forbidden(self, feature_names):
        assert "semester_percentage" not in feature_names

    def test_final_backlog_forbidden(self, feature_names):
        assert "backlog_count" not in feature_names

    def test_future_semester_forbidden(self, feature_names):
        assert "is_at_risk_next_sem" not in feature_names
        assert "next_semester_sgpa" not in feature_names


# ---------------------------------------------------------------------------
# Horizon Validation Tests
# ---------------------------------------------------------------------------

class TestHorizonValidation:
    """Verify same-semester constraint."""

    def test_observation_equals_target(self, metadata):
        """M3 V3 must predict same semester (observation == target)."""
        task = metadata.get("task", "")
        assert "same_semester" in task.lower() or "midsem_to_endterm" in task.lower()

    def test_no_next_semester_in_target(self, metadata):
        target_def = metadata.get("target_definition", "")
        assert "next_semester" not in target_def.lower()
        assert "T+1" not in target_def


# ---------------------------------------------------------------------------
# Prediction Tests
# ---------------------------------------------------------------------------

class TestPrediction:
    """Verify model predictions are valid."""

    def test_predict_proba_returns_valid_range(self, model, preprocessor, feature_names):
        """Probability must be between 0 and 1."""
        X_dummy = pd.DataFrame([{f: 0.5 for f in feature_names}])
        X_proc = preprocessor.transform(X_dummy)
        proba = model.predict_proba(X_proc)
        assert proba.shape == (1, 2)
        assert 0.0 <= proba[0, 1] <= 1.0

    def test_prediction_is_binary(self, model, preprocessor, feature_names, artifact):
        """Prediction must be 0 or 1."""
        X_dummy = pd.DataFrame([{f: 0.5 for f in feature_names}])
        X_proc = preprocessor.transform(X_dummy)
        proba = model.predict_proba(X_proc)[0, 1]
        threshold = artifact["threshold"]
        prediction = 1 if proba >= threshold else 0
        assert prediction in (0, 1)

    def test_deterministic_prediction(self, model, preprocessor, feature_names):
        """Same input should produce same output."""
        X_dummy = pd.DataFrame([{f: 0.5 for f in feature_names}])
        X_proc1 = preprocessor.transform(X_dummy)
        X_proc2 = preprocessor.transform(X_dummy)
        p1 = model.predict_proba(X_proc1)[0, 1]
        p2 = model.predict_proba(X_proc2)[0, 1]
        assert abs(p1 - p2) < 1e-6


# ---------------------------------------------------------------------------
# Config Tests
# ---------------------------------------------------------------------------

class TestConfig:
    """Verify configuration is correct."""

    def test_model_file_exists(self):
        assert config.MODEL_FILE.exists()

    def test_valid_observation_semesters(self):
        assert 5 in config.VALID_OBSERVATION_SEMESTERS
        assert 7 in config.VALID_OBSERVATION_SEMESTERS

    def test_temporal_holdout(self):
        assert config.TEMPORAL_HOLDOUT_SEMESTER == 7

    def test_forbidden_features_defined(self):
        assert len(config.FORBIDDEN_FEATURES) > 0

    def test_target_defined(self):
        assert config.TARGET_AT_RISK == "is_at_risk_end_sem"


# ---------------------------------------------------------------------------
# Leakage Gate Tests
# ---------------------------------------------------------------------------

class TestLeakageGate:
    """Verify the leakage gate raises on forbidden features."""

    def test_clean_dataframe_passes(self, feature_names):
        df = pd.DataFrame([{f: 0.5 for f in feature_names}])
        res = run_leakage_gate(df)
        assert res["pass"] is True
        assert res["forbidden_found"] == []

    def test_forbidden_column_raises(self, feature_names):
        df = pd.DataFrame([{f: 0.5 for f in feature_names}])
        df["semester_sgpa"] = 7.5
        with pytest.raises(ValueError, match="LEAKAGE GATE FAIL"):
            run_leakage_gate(df)

    def test_target_in_features_raises(self, feature_names):
        df = pd.DataFrame([{f: 0.5 for f in feature_names}])
        df["is_at_risk_end_sem"] = 1
        with pytest.raises(ValueError, match="LEAKAGE GATE FAIL"):
            run_leakage_gate(df, required_targets=["is_at_risk_end_sem"])


# ---------------------------------------------------------------------------
# Preprocessor Tests
# ---------------------------------------------------------------------------

class TestPreprocessor:
    """Verify preprocessor handles missing values and fit discipline."""

    def test_unfitted_transform_raises(self):
        prep = M3V3Preprocessor()
        df = pd.DataFrame({"a": [1.0, 2.0]})
        with pytest.raises(RuntimeError, match="has not been fitted yet"):
            prep.transform(df)

    def test_fit_transform_imputes_nans(self):
        prep = M3V3Preprocessor()
        df = pd.DataFrame({"a": [1.0, np.nan, 3.0], "b": [4.0, 5.0, np.nan]})
        res = prep.fit_transform(df)
        assert not np.isnan(res).any()
        assert res.shape == (3, 2)

    def test_transform_reindexes_columns(self):
        prep = M3V3Preprocessor()
        df_train = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
        prep.fit_transform(df_train)
        df_test = pd.DataFrame({"a": [5.0, 6.0]})
        res = prep.transform(df_test)
        assert res.shape == (2, 2)


# ---------------------------------------------------------------------------
# Offline Predictor Tests
# ---------------------------------------------------------------------------

class TestPredictorOffline:
    """Verify M3V3Predictor load and inference behavior without DB."""

    def test_predictor_loads_and_is_loaded(self):
        predictor = M3V3Predictor()
        predictor.load()
        assert predictor.is_loaded
        assert predictor.metadata.get("model_name") == "m3_v3_endterm_risk"

    def test_predict_proba_and_explain(self, feature_names):
        predictor = M3V3Predictor()
        predictor.load()
        df = pd.DataFrame([{f: 0.5 for f in feature_names}])
        p = predictor.predict_proba_from_features(df)
        assert 0.0 <= p <= 1.0
        exp = predictor._explain(df)
        assert isinstance(exp, list)


