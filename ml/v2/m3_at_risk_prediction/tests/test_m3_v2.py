"""M3 v2 — Pytest test suite.

Run with:
    cd d:/KenexAi/ByteBrain/ml
    .venv/Scripts/pytest v2/m3_at_risk_prediction/tests/ -v

Covers:
    - Feature contract: no T+1 / forbidden / placement features
    - Leakage gate (fail-closed)
    - At-risk target derivation (T -> T+1 within student)
    - Data integrity / grain uniqueness
    - Preprocessor (median imputation, fit-on-train)
    - CV / temporal holdout on synthetic data
    - Baselines incl. prior-backlog rule
    - Artifact invariants (if present)
    - Predictor consistency without DB
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from v2.m3_at_risk_prediction import config
from v2.m3_at_risk_prediction.preprocessing.pipeline import M3Preprocessor, select_features


# ──────────────────────────────────────────────────────────────────────────────
# Synthetic mini-dataset with T -> T+1 at-risk labels
# ──────────────────────────────────────────────────────────────────────────────

def _make_mini_semester_summary(n_students: int = 24, n_sems: int = 6):
    rng = np.random.default_rng(7)
    rows = []
    for stu in range(n_students):
        student_id = f"STU6A{stu:04d}"
        base_sgpa = rng.uniform(6.0, 8.8)
        for sem in range(1, n_sems + 1):
            sgpa = float(np.clip(base_sgpa + rng.normal(0, 0.3), 4.5, 9.0))
            backlog = int(1 if sgpa < 6.0 else rng.integers(0, 2))
            rows.append({
                "student_id": student_id,
                "semester_no": sem,
                "semester_sgpa": sgpa,
                "semester_percentage": float(np.clip(sgpa * 9 + rng.normal(0, 2), 40, 95)),
                "semester_total_marks": float(sgpa * 100 + rng.normal(0, 20)),
                "semester_attendance_percentage": float(rng.uniform(55, 99)),
                "backlog_count": backlog,
                "cumulative_backlog_events": int(rng.integers(0, 5)),
                "credits_registered": float(rng.integers(20, 30)),
                "credits_earned": float(rng.integers(18, 30)),
                "subjects_registered": float(rng.integers(6, 9)),
                "previous_sem_sgpa": np.nan,
                "sgpa_drift": np.nan,
                "sgpa_rolling_mean_3": np.nan,
                "previous_sem_backlog_count": 0,
                "backlog_change": 0,
                "attendance_aggregate_pct": float(rng.uniform(55, 99)),
                "gender": rng.choice(["Male", "Female"]),
                "mental_stress_level": rng.choice(["Low", "Medium", "High"]),
                "study_hours_per_week": float(rng.uniform(3, 20)),
                "target_available_if_completed": True,
            })
        # backfill point-in-time history within student
        prev_sgpa = np.nan
        prev_backlog = 0
        for r in rows:
            if r["student_id"] != student_id:
                continue
            r["previous_sem_sgpa"] = prev_sgpa
            r["sgpa_drift"] = np.nan if prev_sgpa != prev_sgpa else r["semester_sgpa"] - prev_sgpa
            r["sgpa_rolling_mean_3"] = prev_sgpa
            r["previous_sem_backlog_count"] = prev_backlog
            r["backlog_change"] = r["backlog_count"] - prev_backlog
            prev_sgpa = r["semester_sgpa"]
            prev_backlog = r["backlog_count"]
    return pd.DataFrame(rows)


def _build_targets(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["student_id", "semester_no"]).copy()
    df[config.TARGET_AT_RISK] = df.groupby("student_id")["backlog_count"].transform(
        lambda s: s.shift(-1).gt(0).astype(float)
    ).fillna(0.0).astype(int)
    return df


def _complete_fact(n_students: int = 24, n_sems: int = 6):
    """Full feature matrix for T in TRAINING_TRANSITIONS with aggregate cols."""
    rng = np.random.default_rng(11)
    df = _make_mini_semester_summary(n_students, n_sems)
    df = _build_targets(df)
    df = df[df["semester_no"].isin(config.TRAINING_TRANSITIONS)].copy()
    agg_feats = (config.TIER1_SUBJECT_AGG + config.TIER1_ATTENDANCE_AGG
                 + config.TIER1_LEARNING_AGG)
    for c in agg_feats:
        df[c] = rng.uniform(0, 100, size=len(df))
    return df


@pytest.fixture
def mini_summary():
    return _make_mini_semester_summary()


@pytest.fixture
def mini_fact():
    return _complete_fact()


# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

class TestConfig:
    def test_target_definition(self):
        assert config.TARGETS == ["is_at_risk_next_sem"]
        assert config.TARGET_AT_RISK in config.TARGETS

    def test_training_transitions_match_holdout_semantics(self):
        assert config.TEMPORAL_HOLDOUT_TRANSITION in config.TRAINING_TRANSITIONS
        assert config.TEMPORAL_HOLDOUT_TRANSITION + 1 <= config.MAX_ACADEMIC_SEMESTER

    def test_current_t_outcomes_allowed_as_features(self):
        # M3-SPECIFIC: current-T semester_sgpa/backlog ARE features (T complete),
        # so they must NOT be in the forbidden list.
        assert "semester_sgpa" not in config.FORBIDDEN_FEATURES
        assert "backlog_count" not in config.FORBIDDEN_FEATURES

    def test_next_outcomes_forbidden(self):
        for col in ["is_at_risk_next_sem", "next_semester_sgpa", "next_semester_grade",
                    "next_semester_result", "next_backlog_count"]:
            assert col in config.FORBIDDEN_FEATURES, f"{col} must be forbidden"

    def test_placement_forbidden(self):
        for col in ["placement_status", "package_lpa", "package_tier",
                    "placement_domain", "placement_date"]:
            assert col in config.FORBIDDEN_FEATURES, f"{col} must be forbidden"

    def test_no_synthetic_oversampling(self):
        assert config.IMBALANCE_HANDLING.startswith("class_weight=")

    def test_forbidden_is_frozen(self):
        assert isinstance(config.FORBIDDEN_FEATURES, frozenset)


# ──────────────────────────────────────────────────────────────────────────────
# At-risk target derivation
# ──────────────────────────────────────────────────────────────────────────────

class TestTargetDerivation:
    def test_next_backlog_shifts_within_student(self, mini_summary):
        df = _build_targets(mini_summary)
        stu = df[df["student_id"] == "STU6A0001"].sort_values("semester_no")
        for i in range(len(stu) - 1):
            row = stu.iloc[i]
            nxt = stu.iloc[i + 1]
            # last semester (T=max) has no target -> treats fillna(0) but T is
            # filtered out by TRAINING_TRANSITIONS downstream; here only assert
            # the mapping for semesters with a defined next.
            expected = 1 if nxt["backlog_count"] > 0 else 0
            assert row[config.TARGET_AT_RISK] == expected

    def test_target_is_binary(self, mini_summary):
        df = _build_targets(mini_summary)
        assert set(df[config.TARGET_AT_RISK].unique()) <= {0, 1}


# ──────────────────────────────────────────────────────────────────────────────
# Feature selection + leakage
# ──────────────────────────────────────────────────────────────────────────────

class TestSelectFeatures:
    def test_no_target_in_features(self, mini_fact):
        X = select_features(mini_fact)
        assert config.TARGET_AT_RISK not in X.columns

    def test_no_forbidden_in_features(self, mini_fact):
        X = select_features(mini_fact)
        for col in config.FORBIDDEN_FEATURES:
            assert col not in X.columns, f"LEAKAGE: {col}"

    def test_all_numeric(self, mini_fact):
        X = select_features(mini_fact)
        assert X.dtypes.apply(lambda d: np.issubdtype(d, np.number)).all()

    def test_encoded_meta_present(self, mini_fact):
        X = select_features(mini_fact)
        assert "is_male" in X.columns
        assert "stress_ordinal" in X.columns
        assert "gender" not in X.columns
        assert "mental_stress_level" not in X.columns

    def test_current_t_backlog_present(self, mini_fact):
        X = select_features(mini_fact)
        assert "semester_sgpa" in X.columns
        assert "backlog_count" in X.columns

    def test_grain_propagated(self, mini_fact):
        X = select_features(mini_fact)
        assert len(X) == len(mini_fact)


class TestLeakageGate:
    def test_clean_matrix_passes(self, mini_fact):
        from v2.m3_at_risk_prediction.features.leakage_gate import run_leakage_gate
        X = select_features(mini_fact)
        gate = run_leakage_gate(X, required_targets=config.TARGETS)
        assert gate["pass"] is True
        assert gate["forbidden_found"] == []

    def test_target_injection_fails_closed(self, mini_fact):
        from v2.m3_at_risk_prediction.features.leakage_gate import run_leakage_gate
        X = select_features(mini_fact).copy()
        X["is_at_risk_next_sem"] = 1
        with pytest.raises(ValueError, match="LEAKAGE GATE FAIL"):
            run_leakage_gate(X, required_targets=config.TARGETS)

    def test_next_outcome_injection_fails_closed(self, mini_fact):
        from v2.m3_at_risk_prediction.features.leakage_gate import run_leakage_gate
        X = select_features(mini_fact).copy()
        X["next_semester_result"] = "ATKT"
        with pytest.raises(ValueError, match="LEAKAGE GATE FAIL"):
            run_leakage_gate(X, required_targets=config.TARGETS)

    def test_placement_injection_fails_closed(self, mini_fact):
        from v2.m3_at_risk_prediction.features.leakage_gate import run_leakage_gate
        X = select_features(mini_fact).copy()
        X["placement_status"] = "Placed"
        with pytest.raises(ValueError, match="LEAKAGE GATE FAIL"):
            run_leakage_gate(X, required_targets=config.TARGETS)

    def test_is_forbidden_semantics(self, mini_fact):
        from v2.m3_at_risk_prediction.features.leakage_gate import _is_forbidden
        assert _is_forbidden("semester_sgpa") is False
        assert _is_forbidden("backlog_count") is False
        assert _is_forbidden("next_semester_sgpa") is True
        assert _is_forbidden("placement_status") is True


# ──────────────────────────────────────────────────────────────────────────────
# Preprocessor
# ──────────────────────────────────────────────────────────────────────────────

class TestM3Preprocessor:
    def test_fit_transform_array(self, mini_fact):
        X = select_features(mini_fact)
        pre = M3Preprocessor()
        out = pre.fit_transform(X)
        assert isinstance(out, np.ndarray)
        assert out.shape[0] == len(X)

    def test_transform_matches_fit_transform(self, mini_fact):
        X = select_features(mini_fact)
        pre = M3Preprocessor()
        a = pre.fit_transform(X)
        b = pre.transform(X)
        np.testing.assert_array_almost_equal(a, b)

    def test_transform_without_fit_raises(self, mini_fact):
        pre = M3Preprocessor()
        with pytest.raises(RuntimeError, match="not been fitted"):
            pre.transform(select_features(mini_fact))

    def test_nan_imputed(self, mini_fact):
        X = select_features(mini_fact).copy()
        X.iloc[:5, 0] = np.nan
        pre = M3Preprocessor()
        out = pre.fit_transform(X)
        assert not np.isnan(out).any()


# ──────────────────────────────────────────────────────────────────────────────
# CV / temporal / baselines
# ──────────────────────────────────────────────────────────────────────────────

class TestValidation:
    def test_group_kfold_no_student_leak(self, mini_fact):
        from sklearn.model_selection import GroupKFold
        from v2.m3_at_risk_prediction.validation.cv import make_model
        X = select_features(mini_fact)
        y = mini_fact[config.TARGET_AT_RISK].astype(int)
        groups = mini_fact["student_id"]
        for tr, va in GroupKFold(n_splits=3).split(X, y, groups):
            assert len(set(groups.iloc[tr]) & set(groups.iloc[va])) == 0

    def test_cv_runs(self, mini_fact):
        from v2.m3_at_risk_prediction.validation.cv import CVResult, run_group_kfold_cv
        X = select_features(mini_fact)
        y = mini_fact[config.TARGET_AT_RISK].astype(int)
        groups = mini_fact["student_id"]
        res = run_group_kfold_cv(X, y, groups, algorithm="logistic_regression",
                                 n_folds=3, seeds=[0])
        assert isinstance(res, CVResult)
        assert len(res.folds) == 3
        assert res.metric_mean("recall") >= 0.0

    def test_temporal_holdout_runs(self, mini_fact):
        from v2.m3_at_risk_prediction.validation.cv import run_temporal_holdout
        X = select_features(mini_fact)
        res = run_temporal_holdout(
            fact=mini_fact, X_full=X,
            training_transitions=[1, 2, 3, 4], holdout_transition=5,
            algorithms=["logistic_regression"], seed=42)
        assert res.checks["validation_after_training"] is True
        assert res.checks["target_not_in_features"] is True
        assert res.checks["no_forbidden_features"] is True
        assert "logistic_regression" in res.by_algorithm

    def test_select_threshold_returns_bounded_probs(self, mini_fact):
        from v2.m3_at_risk_prediction.validation.cv import select_threshold
        y = mini_fact[config.TARGET_AT_RISK].astype(int).values
        proba = np.random.default_rng(0).uniform(0, 1, size=len(y))
        thr = select_threshold(y, proba)
        assert thr["threshold"] is not None
        assert 0.0 <= thr["recall"] <= 1.0
        assert 0.0 <= thr["precision"] <= 1.0

    def test_prior_backlog_rule_baseline(self, mini_fact):
        from v2.m3_at_risk_prediction.validation.cv import baseline_prior_backlog_rule
        fact_val = mini_fact[mini_fact["semester_no"] == 5].copy()
        res = baseline_prior_backlog_rule(fact_val)
        assert res["name"] == "prior_backlog_rule"
        m = res["_metrics_clf_like"]
        assert 0.0 <= m["recall"] <= 1.0
        assert 0.0 <= m["precision"] <= 1.0

    def test_majority_class_baseline(self, mini_fact):
        from v2.m3_at_risk_prediction.validation.cv import baseline_majority_class
        y = mini_fact[config.TARGET_AT_RISK].astype(int)
        res = baseline_majority_class(y)
        assert res["name"] == "majority_class"
        assert res["_metrics_clf_like"]["recall"] == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Artifact invariants
# ──────────────────────────────────────────────────────────────────────────────

class TestArtifactInvariants:
    def _load_artifact_or_skip(self):
        if not config.MODEL_FILE.exists():
            pytest.skip("Artifact not trained yet")
        import joblib
        return joblib.load(config.MODEL_FILE)

    def test_reload_and_prediction_ok(self):
        art = self._load_artifact_or_skip()
        assert art["metadata"]["reload_test"] == "PASS"
        assert art["metadata"]["prediction_test"] == "PASS"

    def test_model_and_preprocessor_present(self):
        art = self._load_artifact_or_skip()
        assert art["model"] is not None
        assert art["preprocessor"] is not None
        assert "feature_names" in art

    def test_preprocessor_feature_names(self):
        art = self._load_artifact_or_skip()
        assert list(art["preprocessor"].feature_names) == list(art["feature_names"])
        assert art["metadata"]["n_features"] == len(art["feature_names"])

    def test_leakage_metadata_pass(self):
        art = self._load_artifact_or_skip()
        assert art["metadata"]["leakage_check"]["pass"] is True

    def test_threshold_bounded(self):
        art = self._load_artifact_or_skip()
        assert 0.0 <= art["threshold"] <= 1.0

    def test_target_definition_present(self):
        art = self._load_artifact_or_skip()
        assert "is_at_risk_next_sem" in art["metadata"]["target_definition"]

    def test_features_never_include_forbidden(self):
        art = self._load_artifact_or_skip()
        feat = set(art["feature_names"])
        overlap = feat & set(config.FORBIDDEN_FEATURES)
        assert overlap == set(), f"artifact features leak: {overlap}"


# ──────────────────────────────────────────────────────────────────────────────
# Predictor
# ──────────────────────────────────────────────────────────────────────────────

class TestPredictor:
    def _mini_artifact_dict(self):
        from v2.m3_at_risk_prediction.training.train import fit_final_model
        fact = _complete_fact(n_students=16, n_sems=4)
        X = select_features(fact)
        y = fact[config.TARGET_AT_RISK].astype(int)
        pre, scaler, model = fit_final_model(X, y, "logistic_regression", seed=42)
        return {
            "model": model,
            "preprocessor": pre,
            "scaler": scaler,
            "threshold": 0.5,
            "feature_names": list(X.columns),
            "metadata": {"model_version": "2.0", "algorithm": "logistic_regression"},
        }

    def test_predict_proba_from_features(self, mini_fact):
        from v2.m3_at_risk_prediction.inference.predictor import M3V2Predictor
        art = self._mini_artifact_dict()
        p = M3V2Predictor()
        p._model = art["model"]
        p._preprocessor = art["preprocessor"]
        p._scaler = art["scaler"]
        p._threshold = art["threshold"]
        p._feature_names = art["feature_names"]
        p._metadata = art["metadata"]
        p._loaded = True
        X = select_features(mini_fact)
        proba = p.predict_proba_from_features(X.iloc[:1])
        assert 0.0 <= proba <= 1.0
        assert p.predict_proba_from_features(X.iloc[:1]) == proba

    def test_explain_logistic_returns_contributions(self, mini_fact):
        from v2.m3_at_risk_prediction.inference.predictor import M3V2Predictor
        art = self._mini_artifact_dict()
        p = M3V2Predictor()
        p._model = art["model"]
        p._preprocessor = art["preprocessor"]
        p._scaler = art["scaler"]
        p._threshold = art["threshold"]
        p._feature_names = art["feature_names"]
        p._metadata = art["metadata"]
        p._loaded = True
        X = select_features(mini_fact)
        sig = p._explain(X.iloc[:1])
        assert len(sig) > 0
        assert "feature" in sig[0]

    def test_predict_not_loaded_raises(self, mini_fact):
        from v2.m3_at_risk_prediction.inference.predictor import M3V2Predictor
        p = M3V2Predictor()
        with pytest.raises(RuntimeError, match="not loaded"):
            p.predict_proba_from_features(select_features(mini_fact))

    def test_threshold_default_and_classify(self, mini_fact):
        from v2.m3_at_risk_prediction.inference.predictor import M3V2Predictor
        art = self._mini_artifact_dict()
        p = M3V2Predictor()
        p._model = art["model"]
        p._preprocessor = art["preprocessor"]
        p._scaler = art["scaler"]
        p._feature_names = art["feature_names"]
        p._metadata = art["metadata"]
        p._threshold = art["threshold"]
        p._loaded = True
        X = select_features(mini_fact)
        proba = p.predict_proba_from_features(X.iloc[:1])
        assert (proba >= 0.5) == (proba >= p._threshold)


class TestFitFinalModel:
    def test_logistic_has_scaler(self, mini_fact):
        from v2.m3_at_risk_prediction.training.train import fit_final_model
        X = select_features(mini_fact)
        y = mini_fact[config.TARGET_AT_RISK].astype(int)
        _, scaler, model = fit_final_model(X, y, "logistic_regression", seed=42)
        assert scaler is not None
        # class_weight='balanced' is set for logistic
        assert model.class_weight == "balanced"

    def test_tree_no_scaler(self, mini_fact):
        from v2.m3_at_risk_prediction.training.train import fit_final_model
        X = select_features(mini_fact)
        y = mini_fact[config.TARGET_AT_RISK].astype(int)
        _, s2, model = fit_final_model(X, y, "random_forest", seed=42)
        assert s2 is None
        assert model.class_weight == "balanced"