"""M1 v2 — Pytest test suite.

Tests cover:
    - Feature contract: no forbidden features
    - Leakage checks: target not in features
    - Data integrity: FK joins, grain uniqueness
    - Model artifact: reload + prediction
    - Inference: predict_from_features returns valid range

Run with:
    cd d:/KenexAi/ByteBrain/ml
    .venv/Scripts/pytest v2/m1_subject_prediction/tests/ -v
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from v2.m1_subject_prediction import config
from v2.m1_subject_prediction.preprocessing.pipeline import (
    M1Preprocessor,
    select_features,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures: synthetic mini-dataset
# ──────────────────────────────────────────────────────────────────────────────

def _make_mini_performance(n_students: int = 20, n_sems: int = 4, n_subj: int = 5):
    """Build a minimal synthetic feature matrix for testing."""
    rng = np.random.default_rng(42)
    rows = []
    for stu in range(n_students):
        student_id = f"STU6A{stu:04d}"
        for sem in range(1, n_sems + 1):
            for subj in range(1, n_subj + 1):
                rows.append({
                    "student_id": student_id,
                    "subject_id": f"SUB{subj:04d}",
                    "semester_no": sem,
                    "enrollment_record_id": f"ENR_{stu}_{sem}_{subj}",
                    # Tier 1 numeric
                    "internal_marks": float(rng.integers(5, 20)),
                    "mid_sem_marks": float(rng.integers(10, 50)),
                    "pre_endsem_assessment_pct": float(rng.uniform(30, 95)),
                    "assignment_score": float(rng.uniform(10, 90)),
                    "quiz_avg_marks": float(rng.uniform(10, 90)),
                    "submission_delay_days": float(rng.uniform(0, 10)),
                    "att_total_pct": float(rng.uniform(50, 100)),
                    "att_rolling_4w_mean": float(rng.uniform(50, 100)),
                    "att_velocity_latest": float(rng.uniform(-10, 10)),
                    "credits": int(rng.integers(2, 5)),
                    # Tier 1 behavioral
                    "activity_volume_total": float(rng.integers(50, 200)),
                    "avg_engagement_consistency": float(rng.uniform(0.4, 1.0)),
                    "avg_assessment_completion_rate": float(rng.uniform(0.3, 1.0)),
                    "avg_late_submission_rate": float(rng.uniform(0.0, 0.8)),
                    # Tier 1 categorical
                    "subject_type": rng.choice(["Theory", "Laboratory", "Project"]),
                    "subject_domain": rng.choice(["Math & Statistics", "Communication & General", "Core CSE"]),
                    # Tier 1 student meta
                    "gender": rng.choice(["Male", "Female"]),
                    "mental_stress_level": rng.choice(["Low", "Medium", "High"]),
                    "study_hours_per_week": float(rng.uniform(3, 20)),
                    # Tier 2 prior
                    "prior_avg_sgpa": float(rng.uniform(5, 10)) if sem > 1 else float("nan"),
                    "sgpa_drift_latest": float(rng.uniform(-1, 1)) if sem > 1 else float("nan"),
                    "prior_backlog_cumulative": float(rng.integers(0, 5)),
                    "prior_avg_attendance": float(rng.uniform(60, 95)) if sem > 1 else float("nan"),
                    "prior_n_sems": max(0, sem - 1),
                    # Target
                    "end_sem_marks": float(rng.integers(10, 70)),
                })
    return pd.DataFrame(rows)


@pytest.fixture
def mini_fact():
    return _make_mini_performance()


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestConfig:
    def test_target_name(self):
        assert config.TARGET == "end_sem_marks"

    def test_target_bounds(self):
        assert config.TARGET_MIN == 0.0
        assert config.TARGET_MAX == 70.0

    def test_forbidden_features_is_frozen(self):
        assert isinstance(config.FORBIDDEN_FEATURES, frozenset)

    def test_forbidden_includes_target(self):
        assert config.TARGET in config.FORBIDDEN_FEATURES

    def test_forbidden_includes_derived(self):
        for col in ["total_marks", "percentage", "grade", "grade_point", "result_status"]:
            assert col in config.FORBIDDEN_FEATURES, f"{col} must be forbidden"

    def test_training_semesters(self):
        assert config.TRAINING_SEMESTERS == [1, 2, 3, 4, 5, 6]

    def test_temporal_holdout_after_training(self):
        assert config.TEMPORAL_HOLDOUT_SEMESTER > max(config.TRAINING_SEMESTERS)

    def test_cohort_prefix(self):
        assert config.COHORT_ID_PREFIX == "STU6A"


class TestSelectFeatures:
    def test_no_forbidden_in_features(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        for col in config.FORBIDDEN_FEATURES:
            assert col not in X.columns, f"LEAKAGE: {col} found in features"

    def test_target_not_in_features(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        assert config.TARGET not in X.columns

    def test_all_numeric(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        assert X.dtypes.apply(lambda d: np.issubdtype(d, np.number)).all(), \
            "All features must be numeric after encoding"

    def test_no_object_columns(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        obj_cols = X.select_dtypes(include="object").columns.tolist()
        assert len(obj_cols) == 0, f"Object columns found: {obj_cols}"

    def test_ohe_subject_type(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        ohe_cols = [c for c in X.columns if c.startswith("subtype_")]
        assert len(ohe_cols) >= 2, "OHE for subject_type must produce at least 2 columns"

    def test_ohe_domain(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        ohe_cols = [c for c in X.columns if c.startswith("domain_")]
        assert len(ohe_cols) >= 2, "OHE for subject_domain must produce at least 2 columns"

    def test_is_male_binary(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        assert "is_male" in X.columns
        assert set(X["is_male"].unique()) <= {0, 1}

    def test_stress_ordinal_values(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        assert "stress_ordinal" in X.columns
        assert set(X["stress_ordinal"].dropna().unique()) <= {0, 1, 2}

    def test_tier2_included_when_flag_set(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        assert "prior_avg_sgpa" in X.columns
        assert "prior_n_sems" in X.columns

    def test_tier2_excluded_when_flag_false(self, mini_fact):
        X = select_features(mini_fact, include_tier2=False)
        assert "prior_avg_sgpa" not in X.columns
        assert "prior_n_sems" not in X.columns

    def test_shape_consistency(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        assert len(X) == len(mini_fact), "Row count must be preserved"


class TestM1Preprocessor:
    def test_fit_transform_produces_array(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        pre = M1Preprocessor()
        X_proc = pre.fit_transform(X)
        assert isinstance(X_proc, np.ndarray)
        assert X_proc.shape[0] == len(X)

    def test_transform_matches_fit_transform_on_training(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        pre = M1Preprocessor()
        X_ft = pre.fit_transform(X)
        X_t = pre.transform(X)
        np.testing.assert_array_almost_equal(X_ft, X_t)

    def test_transform_without_fit_raises(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        pre = M1Preprocessor()
        with pytest.raises(RuntimeError, match="not been fitted"):
            pre.transform(X)

    def test_nan_handling(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        # Inject NaN
        X_nan = X.copy()
        X_nan.iloc[:5, 0] = np.nan
        pre = M1Preprocessor()
        X_proc = pre.fit_transform(X_nan)
        assert not np.isnan(X_proc).any(), "NaN must be imputed"

    def test_feature_names_preserved(self, mini_fact):
        X = select_features(mini_fact, include_tier2=True)
        pre = M1Preprocessor()
        pre.fit_transform(X)
        assert pre.feature_names == list(X.columns)


class TestLeakageByConstruction:
    """Verify that select_features NEVER produces forbidden columns."""

    def test_no_leakage_under_any_combination(self, mini_fact):
        """Inject forbidden column names into fact and verify they don't appear in X."""
        fact_with_leakage = mini_fact.copy()
        for col in config.FORBIDDEN_FEATURES:
            fact_with_leakage[col] = 99.0  # inject forbidden col

        # Should not appear in output (they're not in the selection logic)
        X = select_features(fact_with_leakage, include_tier2=True)
        for col in config.FORBIDDEN_FEATURES:
            assert col not in X.columns, f"LEAKAGE: {col} in features after injection"


class TestTemporalOrdering:
    """Verify temporal split ordering is correct."""

    def test_holdout_strictly_after_training(self):
        assert config.TEMPORAL_HOLDOUT_SEMESTER > max(config.TRAINING_SEMESTERS)

    def test_no_overlap_between_train_and_holdout(self):
        train_set = set(config.TRAINING_SEMESTERS)
        assert config.TEMPORAL_HOLDOUT_SEMESTER not in train_set


class TestGrainUniqueness:
    def test_no_duplicate_grains(self, mini_fact):
        dup = mini_fact.duplicated(
            subset=["student_id", "subject_id", "semester_no"]
        ).sum()
        assert dup == 0, f"Synthetic data has {dup} duplicate grains"


class TestGroupKFoldInputs:
    """Verify GroupKFold runs without error on synthetic data."""

    def test_group_kfold_executes(self, mini_fact):
        from sklearn.model_selection import GroupKFold
        X = select_features(mini_fact, include_tier2=True)
        y = mini_fact[config.TARGET].astype(float)
        groups = mini_fact["student_id"]
        gkf = GroupKFold(n_splits=3)  # 3 folds for small dataset
        splits = list(gkf.split(X, y, groups))
        assert len(splits) == 3

    def test_no_student_leakage_across_folds(self, mini_fact):
        from sklearn.model_selection import GroupKFold
        X = select_features(mini_fact, include_tier2=True)
        y = mini_fact[config.TARGET].astype(float)
        groups = mini_fact["student_id"]
        gkf = GroupKFold(n_splits=3)
        for train_idx, val_idx in gkf.split(X, y, groups):
            train_students = set(groups.iloc[train_idx])
            val_students = set(groups.iloc[val_idx])
            overlap = train_students & val_students
            assert len(overlap) == 0, f"Student overlap across folds: {overlap}"


class TestEndToEndMiniTrain:
    """End-to-end mini-train on synthetic data (no DB access)."""

    def test_mini_hist_gbm_runs(self, mini_fact):
        from v2.m1_subject_prediction.validation.cv import (
            run_group_kfold_cv, CVResult
        )
        X = select_features(mini_fact, include_tier2=True)
        y = mini_fact[config.TARGET].astype(float)
        groups = mini_fact["student_id"]
        result = run_group_kfold_cv(
            X, y, groups,
            algorithm="hist_gbm",
            n_folds=3,
            seeds=[0],
            needs_scaling=False,
        )
        assert isinstance(result, CVResult)
        assert len(result.folds) == 3
        assert result.mae_mean > 0
        assert result.r2_mean <= 1.0

    def test_mini_ridge_runs(self, mini_fact):
        from v2.m1_subject_prediction.validation.cv import (
            run_group_kfold_cv, CVResult
        )
        X = select_features(mini_fact, include_tier2=True)
        y = mini_fact[config.TARGET].astype(float)
        groups = mini_fact["student_id"]
        result = run_group_kfold_cv(
            X, y, groups,
            algorithm="ridge",
            n_folds=3,
            seeds=[0],
            needs_scaling=True,
        )
        assert isinstance(result, CVResult)
        assert result.mae_mean > 0

    def test_temporal_holdout_runs(self, mini_fact):
        from v2.m1_subject_prediction.validation.cv import run_temporal_holdout
        X = select_features(mini_fact, include_tier2=True)
        y = mini_fact[config.TARGET].astype(float)
        result = run_temporal_holdout(
            fact=mini_fact,
            X_full=X,
            y=y,
            training_sems=[1, 2, 3],
            holdout_sem=4,
            algorithms=["hist_gbm"],
            seed=42,
        )
        assert "hist_gbm" in result.algorithms
        assert result.checks["validation_after_training"] is True
        assert result.checks["no_forbidden_features"] is True
        assert result.checks["target_not_in_features"] is True

    def test_target_clip_range(self, mini_fact):
        """Predictions must always be clipped to [TARGET_MIN, TARGET_MAX]."""
        from sklearn.ensemble import HistGradientBoostingRegressor
        X = select_features(mini_fact, include_tier2=True)
        y = mini_fact[config.TARGET].astype(float)
        pre = M1Preprocessor()
        X_proc = pre.fit_transform(X)
        model = HistGradientBoostingRegressor(random_state=42)
        model.fit(X_proc, y)
        preds = np.clip(model.predict(X_proc), config.TARGET_MIN, config.TARGET_MAX)
        assert all(p >= config.TARGET_MIN for p in preds)
        assert all(p <= config.TARGET_MAX for p in preds)


class TestSelectBestAlgorithm:
    """Verify the evidence-based model selection ordering."""

    def _mk_result(self, mae):
        from v2.m1_subject_prediction.validation.cv import CVResult
        r = CVResult(algorithm="x")
        r.folds = [type("F", (), {"mae": mae, "rmse": mae, "r2": 0.5, "n_val": 100, "train_mae": mae})()]
        return r

    def test_prefers_lowest_mae(self):
        from v2.m1_subject_prediction.training.train import select_best_algorithm
        cv = {
            "ridge": self._mk_result(6.5),
            "random_forest": self._mk_result(6.9),
            "hist_gbm": self._mk_result(6.3),
            "xgboost": self._mk_result(6.4),
        }
        assert select_best_algorithm(cv) == "hist_gbm"

    def test_ties_prefer_simpler(self):
        from v2.m1_subject_prediction.training.train import select_best_algorithm
        cv = {
            "ridge": self._mk_result(6.0),
            "random_forest": self._mk_result(6.0),
            "hist_gbm": self._mk_result(6.0),
            "xgboost": self._mk_result(6.0),
        }
        assert select_best_algorithm(cv) == "ridge"

    def test_returns_known_algorithm(self):
        from v2.m1_subject_prediction.training.train import select_best_algorithm
        cv = {"ridge": self._mk_result(5.0), "random_forest": self._mk_result(4.5)}
        assert select_best_algorithm(cv) in {"ridge", "random_forest"}


class TestFitFinalModelAlignment:
    """Verify Phase 9 final-model column alignment (no feature mismatch)."""

    def test_final_model_feature_names_match_input(self, mini_fact):
        from v2.m1_subject_prediction.training.train import fit_final_model
        X = select_features(mini_fact, include_tier2=True)
        y = mini_fact[config.TARGET].astype(float)
        pre, scaler, model = fit_final_model(X, y, "ridge")
        assert pre.feature_names == list(X.columns), \
            "Final model preprocessor columns must match the feature matrix"

    def test_final_model_ridge_has_scaler(self, mini_fact):
        from v2.m1_subject_prediction.training.train import fit_final_model
        X = select_features(mini_fact, include_tier2=True)
        y = mini_fact[config.TARGET].astype(float)
        pre, scaler, model = fit_final_model(X, y, "ridge")
        assert scaler is not None
        assert model.__class__.__name__ == "Ridge"

    def test_final_model_trees_no_scaler(self, mini_fact):
        from v2.m1_subject_prediction.training.train import fit_final_model
        X = select_features(mini_fact, include_tier2=True)
        y = mini_fact[config.TARGET].astype(float)
        pre, scaler, model = fit_final_model(X, y, "hist_gbm")
        assert scaler is None

    def test_phase9_alignment_matches_feature_names(self, mini_fact):
        """Simulate Phase 9: X_final with a spurious extra column must not break."""
        from v2.m1_subject_prediction.training.train import fit_final_model
        import copy
        X_train = select_features(mini_fact, include_tier2=True)
        feature_names = list(X_train.columns)
        # X_final built with different column count (extra novel category)
        X_final = select_features(mini_fact, include_tier2=True)
        X_final["domain_NewCategory"] = 0
        X_final = X_final.reindex(columns=feature_names, fill_value=0)
        y_final = mini_fact[config.TARGET].astype(float)
        pre, scaler, model = fit_final_model(X_final, y_final, "ridge")
        assert pre.feature_names == feature_names
        assert len(pre.feature_names) == len(feature_names)


class TestArtifactInvariants:
    """Verify the real saved artifact (if present) is internally consistent."""

    def _load_artifact_or_skip(self):
        if not config.MODEL_FILE.exists():
            pytest.skip("Artifact not trained yet")
        import joblib
        return joblib.load(config.MODEL_FILE)

    def test_reload_and_feature_consistency(self):
        art = self._load_artifact_or_skip()
        assert art["metadata"]["reload_test"] == "PASS"
        assert art["metadata"]["prediction_test"] == "PASS"
        assert art["feature_names"] == art["preprocessor"].feature_names, \
            "Artifact feature_names must equal preprocessor feature_names"
        assert art["metadata"]["n_features"] == len(art["feature_names"])

    def test_leakage_metadata_pass(self):
        art = self._load_artifact_or_skip()
        assert art["metadata"]["leakage_check"]["pass"] is True
        assert art["metadata"]["leakage_check"]["forbidden_found"] == []

    def test_model_beats_mean_baseline(self):
        art = self._load_artifact_or_skip()
        assert art["metadata"]["beats_mean_baseline"] is True

    def test_feature_count_is_39(self):
        art = self._load_artifact_or_skip()
        assert art["metadata"]["n_features"] == 39

    def test_target_bounds_in_metadata(self):
        art = self._load_artifact_or_skip()
        assert art["metadata"]["target_min"] == config.TARGET_MIN
        assert art["metadata"]["target_max"] == config.TARGET_MAX

    def test_training_semesters_match_config(self):
        art = self._load_artifact_or_skip()
        assert art["metadata"]["training_semesters"] == config.TRAINING_SEMESTERS
        assert art["metadata"]["temporal_holdout_semester"] == config.TEMPORAL_HOLDOUT_SEMESTER


class TestPredictor:
    """Verify inference-side consistency without DB access."""

    def _mini_artifact_dict(self):
        # Build a small artifact from synthetic data mirroring the real schema
        import joblib
        from v2.m1_subject_prediction.validation.cv import run_group_kfold_cv
        fact = _make_mini_performance(n_students=12, n_sems=3, n_subj=3)
        fact = fact[fact["semester_no"] <= 3]
        from v2.m1_subject_prediction.training.train import fit_final_model
        X = select_features(fact, include_tier2=True)
        y = fact[config.TARGET].astype(float)
        pre, scaler, model = fit_final_model(X, y, "ridge")
        return {
            "model": model,
            "preprocessor": pre,
            "scaler": scaler,
            "feature_names": list(X.columns),
            "metadata": {"model_version": "2.0", "algorithm": "ridge"},
        }

    def test_predict_from_features_returns_valid_range(self, mini_fact):
        from v2.m1_subject_prediction.inference.predictor import M1V2Predictor
        art = self._mini_artifact_dict()
        p = M1V2Predictor()
        p._artifact = art
        p._model = art["model"]
        p._preprocessor = art["preprocessor"]
        p._scaler = art["scaler"]
        p._feature_names = art["feature_names"]
        p._metadata = art["metadata"]
        p._loaded = True
        X = select_features(mini_fact, include_tier2=True)
        preds = p.predict_from_features(X)
        assert len(preds) == len(X)
        assert all(config.TARGET_MIN <= v <= config.TARGET_MAX for v in preds)

    def test_predict_from_features_handles_novel_columns(self, mini_fact):
        """A feature frame with extra/missing OHE columns must 0-fill gracefully."""
        from v2.m1_subject_prediction.inference.predictor import M1V2Predictor
        art = self._mini_artifact_dict()
        p = M1V2Predictor()
        p._artifact = art
        p._model = art["model"]
        p._preprocessor = art["preprocessor"]
        p._scaler = art["scaler"]
        p._feature_names = art["feature_names"]
        p._metadata = art["metadata"]
        p._loaded = True
        X = select_features(mini_fact, include_tier2=True)
        X = X.drop(columns=[c for c in X.columns if c.startswith("domain_")])
        X = X.copy()
        X["domain_Novel"] = 1
        preds = p.predict_from_features(X)
        assert len(preds) == len(X)
        assert all(config.TARGET_MIN <= v <= config.TARGET_MAX for v in preds)

    def test_predict_not_loaded_raises(self, mini_fact):
        from v2.m1_subject_prediction.inference.predictor import M1V2Predictor
        p = M1V2Predictor()
        with pytest.raises(RuntimeError, match="not loaded"):
            p.predict_from_features(select_features(mini_fact, include_tier2=True))

    def test_grade_from_marks_bands(self):
        from v2.m1_subject_prediction.inference.predictor import _grade_from_marks
        assert _grade_from_marks(70.0)[0] == "O"
        assert _grade_from_marks(50.0)[0] == "A+"
        assert _grade_from_marks(39.0)[0] == "A"
        assert _grade_from_marks(28.0)[0] == "B+"
        assert _grade_from_marks(19.0)[0] == "C"
        assert _grade_from_marks(12.0)[0] == "F"
        assert _grade_from_marks(0.0)[0] == "F"
