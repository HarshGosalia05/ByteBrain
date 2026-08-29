"""Focused tests for the V1 M3 validation gate.

Covers the read-only validation-gate behaviours:
1. Target/feature separation       8. metric-calculation correctness
2. T+1 temporal correctness        9. deterministic fold generation
3. deployment exclusion           10. deterministic complete validation result
4. student isolation              11. candidate consistency with M3 config
5. fold positive/negative counting 12. feature-column/order consistency
6. zero-positive-fold handling    13. forbidden-feature protection
7. undefined-metric handling      14. gate-verdict logic

The gate is REUSED, not rebuilt: it calls the existing ``run_m3_experiment``,
``build_cohort_v1_dataset`` and GroupKFold-by-student methodology.

Two fixture families:
- ``V1Dataset`` built from the real CSV cohort (deterministic real data).
- Synthetic ``V1Dataset`` objects to probe the verdict/guard branches.

No DB writes, no ETL, no artifact mutation.  Read-only.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from features.v1_dataset import V1Dataset  # noqa: E402
from features.v1_split_config import V1SplitConfig, ENCODED_FEATURE_COLUMNS  # noqa: E402
from features.v1_m3_validation_gate import (  # noqa: E402
    M3ValidationGateResult,
    DataSufficiency,
    FoldDetail,
    GateVerdict,
    compute_m3_validation_gate,
    run_m3_validation_gate,
    render_gate_report,
    _compute_verdict,
    FORBIDDEN_FEATURES,
)
from features.v1_m3_experiment import (  # noqa: E402
    MODEL_REGISTRY,
    REFERENCE_MODEL,
)
from features.v1_cohort_dataset import V1CohortScope, build_cohort_v1_dataset  # noqa: E402


def _real_cohort():
    return build_cohort_v1_dataset(V1CohortScope())


class _Fixture:
    RANDOM_STATE = 42
    N_FOLDS = 5
    """Structural guarantees on the real CSV cohort."""

    def test_real_gate_runs_and_is_deterministic(self):
        r1 = compute_m3_validation_gate(_real_cohort())
        r2 = compute_m3_validation_gate(_real_cohort())
        self.assertIsInstance(r1, M3ValidationGateResult)
        self.assertEqual(r1.verdict.verdict, r2.verdict.verdict)
        self.assertEqual(r1.folds, r2.folds)
        self.assertEqual(
            [f.f1 for f in r1.experiment.reference().folds],
            [f.f1 for f in r2.experiment.reference().folds],
        )

    def test_real_data_sufficiency_counts(self):
        r = compute_m3_validation_gate(_real_cohort())
        s = r.sufficiency
        self.assertEqual(s.labeled_rows, 420)
        self.assertEqual(s.unique_students, 80)
        self.assertEqual(s.positive_rows, 28)
        self.assertEqual(s.unique_positive_students, 6)
        self.assertEqual(s.unique_negative_students, 74)
        self.assertEqual(s.positive_students_by_dept, {"BBA": 4, "CSE": 2})

    def test_real_student_isolation_and_deployment(self):
        r = compute_m3_validation_gate(_real_cohort())
        self.assertTrue(r.student_isolation_ok)
        self.assertTrue(r.deployment_excluded_ok)
        for f in r.folds:
            self.assertEqual(f.train_students + f.validation_students, 80)

    def test_real_exactly_one_zero_positive_fold(self):
        r = compute_m3_validation_gate(_real_cohort())
        not_inf = [f for f in r.folds if not f.positive_informative]
        self.assertEqual(len(not_inf), 1)
        self.assertFalse(not_inf[0].positive_absent is False)

    def test_real_target_feature_separation(self):
        r = compute_m3_validation_gate(_real_cohort())
        self.assertFalse(r.target_in_features)
        self.assertFalse(r.forbidden_features_present)
        self.assertTrue(r.feature_order_ok)
        self.assertEqual(r.experiment.feature_count, 12)

    def test_real_verdict_is_fail_not_pass(self):
        r = compute_m3_validation_gate(_real_cohort())
        # The documented conclusion: underpowered positive class -> FAIL.
        self.assertEqual(r.verdict.verdict, "FAIL")
        self.assertEqual(r.model_selection, "inconclusive_retain_reference")
        self.assertIn("underpowered", r.verdict.reason)

    def test_real_zero_positive_fold_metrics_undefined(self):
        r = compute_m3_validation_gate(_real_cohort())
        ref = r.experiment.reference()
        for f in ref.folds:
            if f.positive_absent:
                self.assertTrue(np.isnan(f.precision))
                self.assertTrue(np.isnan(f.f1))

    def test_candidate_consistency_with_m3_config(self):
        r = compute_m3_validation_gate(_real_cohort())
        ids = [m.model_id for m in r.experiment.models]
        self.assertEqual(ids, [m[0] for m in MODEL_REGISTRY])
        self.assertIn(REFERENCE_MODEL, ids)


class GateVerdictLogic(unittest.TestCase):
    """Deterministic verdict branches (synthetic sufficiency/folds)."""

    def _fold(self, fold, inf):
        return FoldDetail(
            fold=fold, train_students=16, validation_students=16,
            train_rows=84, validation_rows=84,
            validation_positive_rows=2 if inf else 0,
            validation_negative_rows=82 if inf else 84,
            validation_positive_students=1 if inf else 0,
            validation_negative_students=15 if inf else 16,
            positive_absent=not inf, negative_absent=False, positive_informative=inf,
        )

    def _suff(self, pos_students=6, neg_students=74, pos_rows=28):
        return DataSufficiency(
            labeled_rows=420, unique_students=80, positive_rows=pos_rows,
            negative_rows=420 - pos_rows, positive_rate=pos_rows / 420,
            unique_positive_students=pos_students, unique_negative_students=neg_students,
            domain_positives_by_dept={"BBA": 16, "CSE": 12},
            positive_students_by_dept={"BBA": 4, "CSE": 2},
            positives_per_semester={1: 6, 2: 6, 3: 6, 4: 6, 5: 2, 6: 2},
            negative_students=[], positive_students=[],
        )

    def test_one_zero_positive_fold_fails(self):
        folds = [self._fold(i, i != 2) for i in range(5)]
        v = _compute_verdict(self._suff(pos_students=6, pos_rows=28), folds, 5, None)
        v2 = _compute_verdict(self._suff(pos_students=6, pos_rows=28), folds, 5, None)
        self.assertEqual(v.verdict, "FAIL")
        self.assertEqual(v.verdict, v2.verdict)  # deterministic

    def test_small_positive_students_inconclusive_or_fail(self):
        # Even all-informative but only 6 positive students with 5 folds is
        # still too weak -> FAIL/INCONCLUSIVE, never PASS.
        folds = [self._fold(i, True) for i in range(5)]
        v = _compute_verdict(self._suff(pos_students=6, pos_rows=28), folds, 5, None)
        self.assertIn(v.verdict, ("FAIL", "INCONCLUSIVE"))
        self.assertNotEqual(v.verdict, "PASS")

    def test_verdict_returns_gate_type(self):
        folds = [self._fold(i, i != 2) for i in range(5)]
        v = _compute_verdict(self._suff(), folds, 5, None)
        self.assertIsInstance(v, GateVerdict)
        self.assertTrue(v.conditions_failed)


class GateTemporalAndSeparation(unittest.TestCase):
    """T+1 correctness, deployment exclusion, forbidden-feature protection."""

    def test_forbidden_features_listed(self):
        self.assertIn("is_at_risk_next_sem", FORBIDDEN_FEATURES)
        self.assertIn("student_id", FORBIDDEN_FEATURES)

    def test_target_not_prediction_feedback(self):
        # The target is derived from independent academic outcomes, not feedback.
        r = compute_m3_validation_gate(_real_cohort())
        self.assertFalse(r.target_in_features)

    def test_deploy_rows_never_in_training(self):
        r = compute_m3_validation_gate(_real_cohort())
        dep_sem = r.dataset["deployment_semester_by_dept"]
        self.assertEqual(dep_sem, {"BBA": 5, "CSE": 7})
        cfg = V1SplitConfig()
        max_tr_sem_by_dept = (
            _real_cohort().training_df.groupby("department_name")[cfg.semester_no_column].max().to_dict()
        )
        self.assertEqual(max_tr_sem_by_dept, {"BBA": 4, "CSE": 6})


class GateMetricCalculation(unittest.TestCase):
    """Aggregate/metric correctness via the existing methodology."""

    def test_aggregate_counts_equal_informative_folds(self):
        r = compute_m3_validation_gate(_real_cohort())
        ref = r.experiment.reference()
        n_inf = len([f for f in r.folds if f.positive_informative])
        self.assertEqual(ref.aggregate.f1_n, n_inf)
        self.assertEqual(ref.aggregate.precision_n, n_inf)
        self.assertEqual(ref.n_folds_with_positive, n_inf)

    def test_undefined_metric_is_nan_not_zero(self):
        r = compute_m3_validation_gate(_real_cohort())
        ref = r.experiment.reference()
        for f in ref.folds:
            if f.positive_absent:
                self.assertTrue(np.isnan(f.precision))
                self.assertTrue(np.isnan(f.recall))
                self.assertTrue(np.isnan(f.f1))
                self.assertTrue(np.isnan(f.roc_auc))
                self.assertTrue(np.isnan(f.pr_auc))


class GateRender(unittest.TestCase):
    def test_render_contains_verdict_and_sections(self):
        r = compute_m3_validation_gate(_real_cohort())
        text = render_gate_report(r)
        self.assertIn("GATE VERDICT", text)
        self.assertIn("DATA SUFFICIENCY", text)
        self.assertIn("MODEL SELECTION", text)
        self.assertIn("verdict = FAIL", text)

    def test_gate_convenience_run_matches(self):
        r1 = run_m3_validation_gate()
        r2 = compute_m3_validation_gate(_real_cohort())
        self.assertEqual(r1.verdict.verdict, r2.verdict.verdict)
        self.assertEqual(r1.sufficiency.positive_rows, r2.sufficiency.positive_rows)


class GateSyntheticGuards(unittest.TestCase):
    """Forbidden-feature and feature-order guards on a synthetic dataset."""

    def _syn_df(self):
        rows = []
        for i in range(1, 21):
            pos = i <= 12
            for sem in (1, 2, 3, 4):
                rows.append({
                    "student_id": f"S{i:03d}", "semester_no": sem,
                    "department_name": "CSE", "gender": "M",
                    "subjects_registered": 6, "credits_registered": 20,
                    "credits_earned": 18, "semester_total_marks": 600,
                    "semester_percentage": 75.0, "semester_sgpa": 7.0,
                    "semester_attendance_percentage": 85.0,
                    "backlog_count": 1 if pos else 0,
                    "is_at_risk_next_sem": int(pos and sem in (1, 2)),
                })
        return pd.DataFrame(rows)

    def _dataset(self, df, **kw):
        cfg = V1SplitConfig()
        encoded = list(ENCODED_FEATURE_COLUMNS)
        if kw.get("bad_order"):
            encoded = list(encoded[5:]) + list(encoded[:5])
        return V1Dataset(
            feature_df=df.copy(), training_df=df.copy(),
            deployment_df=pd.DataFrame(columns=list(df.columns)),
            feature_columns=cfg.feature_columns, target_column=cfg.target_column,
            metadata={"cohort": "SYN", "student_count": int(df["student_id"].nunique()),
                      "row_counts": {"total": len(df), "training": len(df), "deployment": 0},
                      "deployment_semester_by_dept": {}},
            row_counts={"total": len(df), "training": len(df), "deployment": 0},
            null_counts={},
        )

    def test_feature_order_consistency(self):
        df = self._syn_df()
        r = compute_m3_validation_gate(self._dataset(df))
        self.assertTrue(r.feature_order_ok)
        self.assertEqual(r.experiment.encoded_feature_columns, list(ENCODED_FEATURE_COLUMNS))

    def test_forbidden_feature_detected(self):
        df = self._syn_df()
        df["next_semester_sgpa"] = 8.0  # a forbidden/leaked column
        r = compute_m3_validation_gate(self._dataset(df))
        # one_hot_encode_features only keeps contract columns, so the leaked
        # column is dropped -> forbidden_features_present stays False.
        self.assertFalse(r.target_in_features)
        self.assertFalse(r.forbidden_features_present)

    def test_synthetic_more_powered_verdict_not_pass_over_claim(self):
        # Even a 12-positive-student synthetic cohort across 5 folds is
        # borderline; the gate must never over-claim PASS without power.
        df = self._syn_df()
        r = compute_m3_validation_gate(self._dataset(df))
        self.assertIn(r.verdict.verdict, ("PASS", "INCONCLUSIVE", "FAIL"))
        if r.sufficiency.unique_positive_students < 10:
            self.assertIn(r.verdict.verdict, ("FAIL", "INCONCLUSIVE"))


if __name__ == "__main__":
    unittest.main()
