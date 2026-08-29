"""Focused tests for the Integrated M1/M2/M3 ML Readiness / Consistency Audit.

Covers the genuine cross-model invariants that the per-model tests do NOT
verify simultaneously:

- Cross-model target separation (M1 target not in M2/M3 features; M2 targets
  not in M1/M3 features; M3 target not in M1/M2 features), at the actual
  encoded-DataFrame level AND at the contract level.
- Target-derived/source columns excluded from feature matrices.
- Temporal consistency across models (M2/M3 T+1 horizon, deployment = last
  semester / target NULL, M1 pre-end-semester signals).
- Forbidden-feature protection across all three models (incl. V1 union guard).
- Feature-contract order consistency across M2/M3 paths (12-column order).
- Grain/student-isolation integrity per each model's methodology.
- Deployment exclusion (deployment rows never carry ground-truth targets).
- Artifact integrity + registry/selected-model consistency (read-only).
- Reproducibility of repeated audit runs.

Read-only: no DB, no ETL, no training, no artifact writes.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from features.v1_ml_readiness_audit import (  # noqa: E402
    run_integrated_audit,
    render_report,
    TARGETS,
    SELECTED_MODELS,
)
from features import (  # noqa: E402
    M1_CONTRACT,
    M2_CONTRACT,
    M3_CONTRACT,
    get_contract,
)


def _audit():
    return run_integrated_audit()


class TestTargetSeparation(unittest.TestCase):

    def test_m1_target_not_in_m2_or_m3(self):
        res = _audit()
        self.assertTrue(res.target_separation["m1_tgt_not_in_m2"])
        self.assertTrue(res.target_separation["m1_tgt_not_in_m3"])

    def test_m2_targets_not_in_m1_or_m3(self):
        res = _audit()
        self.assertTrue(res.target_separation["m2_tgt_not_in_m1"])
        self.assertTrue(res.target_separation["m2_tgt_not_in_m3"])

    def test_m3_target_not_in_m1_or_m2(self):
        res = _audit()
        self.assertTrue(res.target_separation["m3_tgt_not_in_m1"])
        self.assertTrue(res.target_separation["m3_tgt_not_in_m2"])

    def test_forbidden_lists_contain_cross_targets(self):
        res = _audit()
        self.assertTrue(res.target_separation["m2_forbidden_has_m3_target"])
        self.assertTrue(res.target_separation["m3_forbidden_has_m2_targets"])

    def test_targets_are_distinct_across_models(self):
        t1 = set(TARGETS["m1"])
        t2 = set(TARGETS["m2"])
        t3 = set(TARGETS["m3"])
        self.assertTrue(t1.isdisjoint(t2))
        self.assertTrue(t1.isdisjoint(t3))
        self.assertTrue(t2.isdisjoint(t3))

    def test_no_target_name_is_a_feature_of_any_model(self):
        all_targets = set(TARGETS["m1"]) | set(TARGETS["m2"]) | set(TARGETS["m3"])
        m1_feats = set(M1_CONTRACT.raw_features)
        m2_feats = set(M2_CONTRACT.raw_features)
        m3_feats = set(M3_CONTRACT.raw_features)
        self.assertTrue(all_targets.isdisjoint(m1_feats))
        self.assertTrue(all_targets.isdisjoint(m2_feats))
        self.assertTrue(all_targets.isdisjoint(m3_feats))


class TestTemporalConsistency(unittest.TestCase):

    def test_m2_target_is_strictly_future_semester(self):
        res = _audit()
        self.assertTrue(res.temporal["m2_tgt_strictly_future"])

    def test_deployment_is_last_semester(self):
        res = _audit()
        self.assertTrue(res.temporal["deploy_is_last_semester"])

    def test_deployment_rows_do_not_carry_ground_truth(self):
        res = _audit()
        self.assertTrue(res.temporal["m1_deploy_no_target"])
        self.assertTrue(res.temporal["deploy_is_last_semester_null_future"])

    def test_m1_pre_end_semester_signals_only(self):
        res = _audit()
        self.assertTrue(res.temporal["m1_pre_end_signals"])


class TestFeatureConsistency(unittest.TestCase):

    def test_m2_and_m3_use_identical_12_feature_order(self):
        res = _audit()
        self.assertTrue(res.feature_consistency["m2_m3_identical"])
        self.assertTrue(res.feature_consistency["m2_order"])
        self.assertTrue(res.feature_consistency["m3_order"])

    def test_all_models_use_12_encoded_features(self):
        res = _audit()
        self.assertEqual(res.contracts["m1"].n_encoded, 12)
        self.assertEqual(res.contracts["m2"].n_encoded, 12)
        self.assertEqual(res.contracts["m3"].n_encoded, 12)

    def test_m2_m3_contracts_match(self):
        self.assertEqual(
            list(M2_CONTRACT.raw_features), list(M3_CONTRACT.raw_features)
        )
        self.assertEqual(
            list(M2_CONTRACT.categorical_features),
            list(M3_CONTRACT.categorical_features),
        )


class TestForbiddenProtection(unittest.TestCase):

    def test_no_forbidden_feature_in_encoded_matrices(self):
        res = _audit()
        for mid in ("m1", "m2", "m3"):
            self.assertTrue(res.forbidden_ok[mid], mid)

    def test_own_target_absent_from_own_features(self):
        res = _audit()
        for mid in ("m1", "m2", "m3"):
            self.assertTrue(res.forbidden_ok[f"{mid}_own_target_absent"], mid)

    def test_v1_forbidden_union_does_not_leak_into_m2_m3(self):
        res = _audit()
        self.assertTrue(res.forbidden_ok["m2_v1_forbidden_absent"])
        self.assertTrue(res.forbidden_ok["m3_v1_forbidden_absent"])


class TestGrainIsolation(unittest.TestCase):

    def test_grains_are_uniquely_defined(self):
        res = _audit()
        self.assertTrue(res.grain_ok["m1_unique"])
        self.assertTrue(res.grain_ok["m2_unique"])
        self.assertTrue(res.grain_ok["m3_unique"])

    def test_student_id_preserved_and_aligned(self):
        res = _audit()
        for k in ("m1", "m2", "m3"):
            self.assertTrue(res.grain_ok[f"{k}_student_present"], k)
            self.assertTrue(res.grain_ok[f"{k}_X_aligns"], k)


class TestReproducibility(unittest.TestCase):

    def test_audit_is_reproducible(self):
        self.assertTrue(_audit().reproducibility)

    def test_two_runs_identical(self):
        r1 = _audit()
        r2 = _audit()
        self.assertEqual(r1.passed, r2.passed)
        self.assertEqual(r1.issues, r2.issues)


class TestArtifactAndSelectedModel(unittest.TestCase):

    def test_all_artifacts_load(self):
        res = _audit()
        for mid in ("m1", "m2", "m3"):
            self.assertTrue(res.artifacts[mid].exists, mid)
            self.assertTrue(res.artifacts[mid].loads, mid)

    def test_selected_model_types_match_reports(self):
        res = _audit()
        self.assertEqual(res.artifacts["m1"].model_type, SELECTED_MODELS["m1"])
        self.assertEqual(res.artifacts["m2"].model_type, SELECTED_MODELS["m2"])
        self.assertEqual(res.artifacts["m3"].model_type, SELECTED_MODELS["m3"])

    def test_feature_count_matches_contract(self):
        res = _audit()
        for mid in ("m1", "m2", "m3"):
            a = res.artifacts[mid]
            self.assertEqual(a.n_features, 12, mid)
            self.assertTrue(a.feature_count_ok, mid)

    def test_artifacts_are_deterministic_and_unchanged(self):
        res = _audit()
        for mid in ("m1", "m2", "m3"):
            a = res.artifacts[mid]
            self.assertTrue(a.deterministic_pred, mid)
            self.assertTrue(a.unchanged, mid)

    def test_output_ranges_respected(self):
        res = _audit()
        self.assertTrue(res.artifacts["m1"].in_range)   # clipped [0,70]
        self.assertTrue(res.artifacts["m3"].in_range)   # binary {0,1}


class TestVerdict(unittest.TestCase):

    def test_integrated_audit_passes(self):
        res = _audit()
        self.assertTrue(res.passed, msg="\n".join(res.issues))

    def test_report_renders(self):
        res = _audit()
        report = render_report(res)
        self.assertIn("INTEGRATED M1/M2/M3 ML READINESS", report.upper())
        self.assertIn("VERDICT", report.upper())
        self.assertGreater(len(report), 200)


if __name__ == "__main__":
    unittest.main()
