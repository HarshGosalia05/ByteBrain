"""M2 v2 — Pytest test suite.

Run with:
    cd d:/KenexAi/ByteBrain/ml
    .venv/Scripts/pytest v2/m2_next_semester_prediction/tests/ -v

Covers:
    - Feature contract: no T+1/forbidden features
    - Leakage gate (fail-closed)
    - Target derivation (T -> T+1 within student)
    - Data integrity
    - Preprocessor (median imputation, fit-on-train)
    - CV / temporal holdout on synthetic data
    - Baselines incl. carry-forward
    - Artifact invariants (if present)
    - Predictor consistency without DB
"""
from __future__ import annotations

import asyncio

import numpy as np
import pandas as pd
import pytest

from v2.m2_next_semester_prediction import config
from v2.m2_next_semester_prediction.preprocessing.pipeline import M2Preprocessor, select_features


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures: synthetic mini-dataset with T -> T+1 targets
# ──────────────────────────────────────────────────────────────────────────────

def _make_mini_semester_summary(n_students: int = 20, n_sems: int = 6):
    rng = np.random.default_rng(7)
    rows = []
    for stu in range(n_students):
        student_id = f"STU6A{stu:04d}"
        base_sgpa = rng.uniform(6.5, 8.8)
        for sem in range(1, n_sems + 1):
            sgpa = float(np.clip(base_sgpa + rng.normal(0, 0.25), 5.0, 9.0))
            pct = float(np.clip((sgpa * 9) + rng.normal(0, 2), 45, 95))
            rows.append({
                "student_id": student_id,
                "semester_no": sem,
                "semester_sgpa": sgpa,
                "semester_percentage": pct,
                "semester_total_marks": float(sgpa * 100 + rng.normal(0, 20)),
                "semester_attendance_percentage": float(rng.uniform(60, 99)),
                "backlog_count": int(rng.integers(0, 2)),
                "cumulative_backlog_events": int(rng.integers(0, 5)),
                "credits_registered": float(rng.integers(20, 30)),
                "credits_earned": float(rng.integers(18, 30)),
                "subjects_registered": float(rng.integers(6, 9)),
                "previous_sem_sgpa": np.nan if sem == 1 else rows[-1]["semester_sgpa"],
                "sgpa_drift": np.nan if sem == 1 else rows[-1]["semester_sgpa"] - float(rows[-1]["previous_sem_sgpa"] or np.nan),
                "sgpa_rolling_mean_3": np.nan if sem == 1 else rows[-1]["semester_sgpa"],
                "previous_sem_backlog_count": 0 if sem == 1 else rows[-1]["backlog_count"],
                "backlog_change": 0,
                "attendance_aggregate_pct": float(rng.uniform(60, 99)),
                "gender": rng.choice(["Male", "Female"]),
                "mental_stress_level": rng.choice(["Low", "Medium", "High"]),
                "study_hours_per_week": float(rng.uniform(3, 20)),
                "target_available_if_completed": True,
            })
    return pd.DataFrame(rows)


def _build_targets(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["student_id", "semester_no"]).copy()
    df[config.TARGET_SGPA] = df.groupby("student_id")["semester_sgpa"].shift(-1)
    df[config.TARGET_PERCENTAGE] = df.groupby("student_id")["semester_percentage"].shift(-1)
    return df


def _complete_fact(n_students: int = 20, n_sems: int = 6):
    """Full feature matrix for T in TRAINING_TRANSITIONS with aggregate cols."""
    rng = np.random.default_rng(11)
    df = _make_mini_semester_summary(n_students, n_sems + 1)
    df = _build_targets(df)
    df = df[df["semester_no"].isin(config.TRAINING_TRANSITIONS)].dropna(
        subset=[config.TARGET_SGPA, config.TARGET_PERCENTAGE]
    ).copy()
    # dummy aggregate feature columns expected by select_features
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
    def test_targets(self):
        assert config.TARGETS == ["next_semester_sgpa", "next_semester_percentage"]
        assert config.TARGET_SGPA in config.TARGETS
        assert config.TARGET_PERCENTAGE in config.TARGETS

    def test_training_transitions_match_holdout_semantics(self):
        assert config.TEMPORAL_HOLDOUT_TRANSITION in config.TRAINING_TRANSITIONS
        assert config.TEMPORAL_HOLDOUT_TRANSITION + 1 <= config.MAX_ACADEMIC_SEMESTER

    def test_current_t_outcomes_allowed_as_features(self):
        # M2-SPECIFIC: current-T semester_sgpa/percentage ARE features, so they
        # must NOT be in the forbidden list (this is the key M2 vs M1 difference).
        assert "semester_sgpa" not in config.FORBIDDEN_FEATURES
        assert "semester_percentage" not in config.FORBIDDEN_FEATURES

    def test_next_outcomes_forbidden(self):
        for col in ["next_semester_sgpa", "next_semester_percentage",
                    "next_semester_marks", "next_semester_grade"]:
            assert col in config.FORBIDDEN_FEATURES, f"{col} must be forbidden"

    def test_forbidden_is_frozen(self):
        assert isinstance(config.FORBIDDEN_FEATURES, frozenset)


# ──────────────────────────────────────────────────────────────────────────────
# Target derivation
# ──────────────────────────────────────────────────────────────────────────────

class TestTargetDerivation:
    def test_next_semester_is_shift_within_student(self, mini_summary):
        df = _build_targets(mini_summary)
        stu = df[df["student_id"] == "STU6A0001"].sort_values("semester_no")
        for sem in range(1, len(stu)):
            row = stu[stu["semester_no"] == sem].iloc[0]
            nxt = stu[stu["semester_no"] == sem + 1].iloc[0]
            assert row[config.TARGET_SGPA] == pytest.approx(nxt["semester_sgpa"])
            assert row[config.TARGET_PERCENTAGE] == pytest.approx(nxt["semester_percentage"])

    def test_no_trailing_target_for_last_sem(self, mini_summary):
        df = _build_targets(mini_summary)
        last = df[df["semester_no"] == df["semester_no"].max()].iloc[0]
        assert pd.isna(last[config.TARGET_SGPA])
        assert pd.isna(last[config.TARGET_PERCENTAGE])


# ──────────────────────────────────────────────────────────────────────────────
# Feature selection + leakage
# ──────────────────────────────────────────────────────────────────────────────

class TestSelectFeatures:
    def test_no_target_in_features(self, mini_fact):
        X = select_features(mini_fact)
        for t in config.TARGETS:
            assert t not in X.columns

    def test_no_forbidden_in_features(self, mini_fact):
        X = select_features(mini_fact)
        for col in config.FORBIDDEN_FEATURES:
            assert col not in X.columns, f"LEAKAGE: {col}"

    def test_all_numeric(self, mini_fact):
        X = select_features(mini_fact)
        assert X.dtypes.apply(lambda d: np.issubdtype(d, np.number)).all()

    def test_no_object_columns(self, mini_fact):
        X = select_features(mini_fact)
        obj = X.select_dtypes(include="object").columns.tolist()
        assert obj == []

    def test_current_t_semster_sgpa_present(self, mini_fact):
        X = select_features(mini_fact)
        assert "semester_sgpa" in X.columns
        assert "semester_percentage" in X.columns

    def test_ohe_style_columns_absent_for_m2(self, mini_fact):
        X = select_features(mini_fact)
        assert not any(c.startswith("domain_") for c in X.columns)

    def test_grain_propagated(self, mini_fact):
        X = select_features(mini_fact)
        assert len(X) == len(mini_fact)


class TestLeakageGate:
    def test_clean_matrix_passes(self, mini_fact):
        from v2.m2_next_semester_prediction.features.leakage_gate import run_leakage_gate
        X = select_features(mini_fact)
        gate = run_leakage_gate(X, required_targets=config.TARGETS)
        assert gate["pass"] is True
        assert gate["forbidden_found"] == []

    def test_target_injection_fails_closed(self, mini_fact):
        from v2.m2_next_semester_prediction.features.leakage_gate import run_leakage_gate
        X = select_features(mini_fact)
        X = X.copy()
        X["next_semester_sgpa"] = 8.0
        with pytest.raises(ValueError, match="LEAKAGE GATE FAIL"):
            run_leakage_gate(X, required_targets=config.TARGETS)

    def test_forbidden_injection_fails_closed(self, mini_fact):
        from v2.m2_next_semester_prediction.features.leakage_gate import run_leakage_gate
        X = select_features(mini_fact)
        X = X.copy()
        X["next_semester_percentage"] = 70.0
        with pytest.raises(ValueError, match="LEAKAGE GATE FAIL"):
            run_leakage_gate(X, required_targets=config.TARGETS)

    def test_current_t_outcome_not_flagged(self, mini_fact):
        from v2.m2_next_semester_prediction.features.leakage_gate import _is_forbidden
        assert _is_forbidden("semester_sgpa") is False
        assert _is_forbidden("semester_percentage") is False
        assert _is_forbidden("next_semester_sgpa") is True


# ──────────────────────────────────────────────────────────────────────────────
# Preprocessor
# ──────────────────────────────────────────────────────────────────────────────

class TestM2Preprocessor:
    def test_fit_transform_array(self, mini_fact):
        X = select_features(mini_fact)
        pre = M2Preprocessor()
        out = pre.fit_transform(X)
        assert isinstance(out, np.ndarray)
        assert out.shape[0] == len(X)

    def test_transform_matches_fit_transform(self, mini_fact):
        X = select_features(mini_fact)
        pre = M2Preprocessor()
        a = pre.fit_transform(X)
        b = pre.transform(X)
        np.testing.assert_array_almost_equal(a, b)

    def test_transform_without_fit_raises(self, mini_fact):
        pre = M2Preprocessor()
        with pytest.raises(RuntimeError, match="not been fitted"):
            pre.transform(select_features(mini_fact))

    def test_nan_imputed(self, mini_fact):
        X = select_features(mini_fact)
        X = X.copy()
        X.iloc[:5, 0] = np.nan
        pre = M2Preprocessor()
        out = pre.fit_transform(X)
        assert not np.isnan(out).any()


# ──────────────────────────────────────────────────────────────────────────────
# CV / temporal / baselines
# ──────────────────────────────────────────────────────────────────────────────

class TestValidation:
    def test_group_kfold_no_student_leak(self, mini_fact):
        from sklearn.model_selection import GroupKFold
        X = select_features(mini_fact)
        y = mini_fact[config.TARGET_SGPA].astype(float)
        groups = mini_fact["student_id"]
        for tr, va in GroupKFold(n_splits=3).split(X, y, groups):
            assert len(set(groups.iloc[tr]) & set(groups.iloc[va])) == 0

    def test_cv_runs_both_targets(self, mini_fact):
        from v2.m2_next_semester_prediction.validation.cv import run_group_kfold_cv, CVResult
        X = select_features(mini_fact)
        groups = mini_fact["student_id"]
        for target in config.TARGETS:
            y = mini_fact[target].astype(float)
            res = run_group_kfold_cv(X, y, groups, algorithm="ridge", target=target,
                                     n_folds=3, seeds=[0])
            assert isinstance(res, CVResult)
            assert len(res.folds) == 3
            assert res.mae_mean > 0

    def test_temporal_holdout_runs(self, mini_fact):
        from v2.m2_next_semester_prediction.validation.cv import run_temporal_holdout
        X = select_features(mini_fact)
        res = run_temporal_holdout(
            fact=mini_fact, X_full=X,
            training_transitions=[1, 2, 3, 4], holdout_transition=5,
            algorithms=["ridge"], seed=42)
        assert res.checks["validation_after_training"] is True
        assert res.checks["targets_not_in_features"] is True
        assert res.checks["no_forbidden_features"] is True
        for target in config.TARGETS:
            assert "ridge" in res.by_target[target]

    def test_carryforward_baseline_uses_current_sem(self, mini_fact):
        from v2.m2_next_semester_prediction.validation.cv import baseline_carryforward
        res = baseline_carryforward(mini_fact, config.TARGET_SGPA)
        assert res["name"] == "prior_semester_carryforward"
        assert res["mae"] >= 0

    def test_carryforward_perfect_on_identity(self, mini_summary):
        # If target == current outcome exactly, carry-forward MAE must be ~0.
        from v2.m2_next_semester_prediction.validation.cv import baseline_carryforward
        df = _build_targets(mini_summary)
        df = df[df["semester_no"].isin(config.TRAINING_TRANSITIONS)].dropna(subset=[config.TARGET_SGPA])
        fake = df.copy()
        # Force target to equal current sgpa (simulate pure persistence)
        fake[config.TARGET_SGPA] = pd.to_numeric(fake["semester_sgpa"])
        res = baseline_carryforward(fake, config.TARGET_SGPA)
        assert res["mae"] < 1e-6


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

    def test_has_models_for_all_targets(self):
        art = self._load_artifact_or_skip()
        for t in config.TARGETS:
            assert t in art["models"]

    def test_shared_preprocessor_feature_names(self):
        art = self._load_artifact_or_skip()
        assert art["preprocessor"].feature_names == art["feature_names"]
        assert art["metadata"]["n_features"] == len(art["feature_names"])

    def test_leakage_metadata_pass(self):
        art = self._load_artifact_or_skip()
        assert art["metadata"]["leakage_check"]["pass"] is True


# ──────────────────────────────────────────────────────────────────────────────
# Predictor
# ──────────────────────────────────────────────────────────────────────────────

class TestPredictor:
    def _mini_artifact_dict(self):
        from v2.m2_next_semester_prediction.training.train import fit_final_model
        fact = _complete_fact(n_students=12, n_sems=4)
        X = select_features(fact)
        models = {}
        scalers = {}
        pre = None
        for target in config.TARGETS:
            y = fact[target].astype(float)
            pre, scaler, model = fit_final_model(X, y, "ridge")
            models[target] = model
            scalers[target] = scaler
        return {
            "models": models,
            "preprocessor": pre,
            "scalers": scalers,
            "feature_names": list(X.columns),
            "targets": list(config.TARGETS),
            "metadata": {"model_version": "2.0", "algorithm": {t: "ridge" for t in config.TARGETS}},
        }

    def test_predict_from_features_returns_both(self, mini_fact):
        from v2.m2_next_semester_prediction.inference.predictor import M2V2Predictor
        art = self._mini_artifact_dict()
        p = M2V2Predictor()
        p._models = art["models"]
        p._preprocessor = art["preprocessor"]
        p._scalers = art["scalers"]
        p._feature_names = art["feature_names"]
        p._metadata = art["metadata"]
        p._loaded = True
        X = select_features(mini_fact)
        preds = p.predict_from_features(X.iloc[:1])
        assert config.TARGET_SGPA in preds
        assert config.TARGET_PERCENTAGE in preds
        lo, hi = config.TARGET_BOUNDS[config.TARGET_SGPA]
        assert lo <= preds[config.TARGET_SGPA] <= hi
        lo, hi = config.TARGET_BOUNDS[config.TARGET_PERCENTAGE]
        assert lo <= preds[config.TARGET_PERCENTAGE] <= hi

    def test_predict_not_loaded_raises(self, mini_fact):
        from v2.m2_next_semester_prediction.inference.predictor import M2V2Predictor
        p = M2V2Predictor()
        with pytest.raises(RuntimeError, match="not loaded"):
            p.predict_from_features(select_features(mini_fact))

    # To make the observation-semester selection testable without a live DB,
    # stub the asyncpg connection with a tiny dispatcher and monkeypatch
    # predict_from_features (the artifact itself is not needed here).

    def _fake_loaded_predictor(self):
        from v2.m2_next_semester_prediction.inference.predictor import M2V2Predictor
        p = M2V2Predictor()
        p._metadata = {}
        p._loaded = True
        return p

    def _story_summary(self, n_completed: int, placeholder_sem: int):
        """Semesters 1..n_completed finalized (sgpa/pct > 0), then one
        in-progress placeholder semester with sgpa=0 / percentage=0."""
        rows = []
        for sem in range(1, n_completed + 1):
            rows.append({
                "semester_no": sem,
                "subjects_registered": 7,
                "credits_registered": 28,
                "credits_earned": 27,
                "semester_total_marks": 620.0 + sem,
                "semester_percentage": 88.0 + sem,
                "semester_sgpa": 9.0,
                "semester_attendance_percentage": 90.0,
                "backlog_count": 0,
                "previous_sem_sgpa": None if sem == 1 else 9.0,
                "sgpa_drift": None if sem == 1 else 0.0,
                "sgpa_rolling_mean_3": 9.0,
                "previous_sem_backlog_count": None if sem == 1 else 0,
                "backlog_change": 0,
                "cumulative_backlog_events": 0,
                "attendance_aggregate_pct": 90.0,
            })
        rows.append({
            "semester_no": placeholder_sem,
            "subjects_registered": 7,
            "credits_registered": 28,
            "credits_earned": 0,
            "semester_total_marks": 0,
            "semester_percentage": 0.0,
            "semester_sgpa": 0.0,
            "semester_attendance_percentage": 0.0,
            "backlog_count": 0,
            "previous_sem_sgpa": 9.0,
            "sgpa_drift": 0.0,
            "sgpa_rolling_mean_3": 9.0,
            "previous_sem_backlog_count": 0,
            "backlog_change": 0,
            "cumulative_backlog_events": 0,
            "attendance_aggregate_pct": 0.0,
        })
        return rows

    class _FakeConn:
        def __init__(self, profile, summaries):
            self._profile = profile
            self._summaries = summaries

        async def fetchrow(self, query, *args):
            if "FROM students" in query:
                return self._profile
            return None

        async def fetch(self, query, *args):
            if "FROM student_semester_summary" in query:
                return self._summaries
            return []

    def _predict_ready(self, predictor, conn, student_id):
        captured = {}

        def fake_predict(X):
            captured["T"] = int(X["semester_no"].iloc[0])
            return {"next_semester_sgpa": 9.6, "next_semester_percentage": 96.0}

        predictor.predict_from_features = fake_predict
        result = asyncio.run(
            predictor.predict_for_student(student_id, conn)
        )
        return result, captured

    def test_observation_uses_last_completed_not_placeholder_current(self):
        from v2.m2_next_semester_prediction.inference.predictor import M2V2Predictor
        profile = {
            "student_id": "STU-X",
            "gender": "Male",
            "current_semester": 7,
            "department_code": "CSE",
            "department_name": "Computer Science",
            "total_semesters": 8,
        }
        summaries = self._story_summary(n_completed=6, placeholder_sem=7)
        p = self._fake_loaded_predictor()
        result, captured = self._predict_ready(
            p, self._FakeConn(profile, summaries), "STU-X"
        )
        assert result["readiness_status"] == "READY"
        assert captured["T"] == 6
        assert result["observation_semester"] == 6
        assert result["prediction_takes_effect_semester"] == 8

    def test_observation_uses_current_when_finalized(self):
        from v2.m2_next_semester_prediction.inference.predictor import M2V2Predictor
        profile = {
            "student_id": "STU-Y",
            "gender": "Female",
            "current_semester": 6,
            "department_code": "CSE",
            "department_name": "Computer Science",
            "total_semesters": 8,
        }
        summaries = self._story_summary(n_completed=6, placeholder_sem=7)
        p = self._fake_loaded_predictor()
        result, captured = self._predict_ready(
            p, self._FakeConn(profile, summaries), "STU-Y"
        )
        assert result["readiness_status"] == "READY"
        assert captured["T"] == 6
        assert result["observation_semester"] == 6
        assert result["prediction_takes_effect_semester"] == 7

    def test_no_completed_semester_yields_no_data(self):
        from v2.m2_next_semester_prediction.inference.predictor import M2V2Predictor
        profile = {
            "student_id": "STU-Z",
            "gender": "Male",
            "current_semester": 1,
            "department_code": "CSE",
            "department_name": "Computer Science",
            "total_semesters": 8,
        }
        placeholder = self._story_summary(n_completed=0, placeholder_sem=1)
        p = self._fake_loaded_predictor()
        result = asyncio.run(
            p.predict_for_student("STU-Z", self._FakeConn(profile, placeholder))
        )
        assert result["readiness_status"] == "NO_DATA"
        assert "no completed semester" in result["reason"].lower()


class TestFitFinalModel:
    def test_ridge_has_scaler_other_not(self, mini_fact):
        from v2.m2_next_semester_prediction.training.train import fit_final_model
        X = select_features(mini_fact)
        y = mini_fact[config.TARGET_SGPA].astype(float)
        _, scaler, _ = fit_final_model(X, y, "ridge")
        assert scaler is not None
        _, s2, _ = fit_final_model(X, y, "hist_gbm")
        assert s2 is None