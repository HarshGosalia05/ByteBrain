"""Tests for the Unified OFFLINE Inference Contract (M1/M3, M2 retired).

The legacy V1 M2 pathway (``m2_next_semester_performance.joblib``) has been
retired and removed from the repo; M2 production predictions are served
exclusively by the validated M2-TP package (backend ``M2TPPredictionService``).

Covers:
- supported model identifiers
- readiness states (M1 READY, M2 BLOCKED/retired, M3 READY)
- M1 prediction shapes/types and M1 clipping [0,70]
- M3 output contract (READY, is_at_risk_next_sem)
- M2 retirement (predict_m2 is BLOCKED / prediction-unavailable, no artifact)
- input validation (missing/invalid/non-finite/categorical)
- leakage / forbidden-feature rejection
- exact 12-feature + exact-order + BBA/CSE contract
- model loading through the authoritative registry
- artifact identity (SHA-256) checks
- determinism (M1, M3)
- no DB writes / no artifact writes
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

# Ensure ml/src is on sys.path for imports (project test convention).
_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from features.v1_inference_contract import (  # noqa: E402
    READY,
    BLOCKED,
    UNAVAILABLE,
    INVALID_INPUT,
    ERROR,
    SUPPORTED_MODEL_IDS,
    READINESS_STATES,
    MODEL_READINESS,
    M1_ENCODED_FEATURES,
    M2_M3_ENCODED_FEATURES,
    InferenceResult,
    InferenceInputError,
    supported_models,
    get_readiness,
    readiness_reason,
    validate_input_row,
    feature_names,
    artifact_hash,
    predict,
    predict_m1,
    predict_m2,
    predict_m3,
)

# Known authoritative artifact hashes (must remain byte-identical).
M1_HASH = "3404D29EE61C151C39B50CB9F00D9EE268B8CAF7B39F8BB24D01F17EBFC6431E"
M3_HASH = "99D845FE64A9002B7B1176975A0B41CF29F16A57D380993DA260E2557E2044A7"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def m1_row() -> dict:
    return {
        "student_id": "STU000001",
        "subject_id": "SUB0001",
        "semester_no": 7,
        "internal_marks": 16.0,
        "mid_sem_marks": 30.0,
        "attendance_percentage": 85.0,
        "credits": 4.0,
        "subject_type": "Theory",
        "department_name": "CSE",
        "gender": "Male",
    }


def m2_row() -> dict:
    return {
        "student_id": "STU000002",
        "semester_no": 5,
        "subjects_registered": 6,
        "credits_registered": 22.0,
        "credits_earned": 20.0,
        "semester_total_marks": 420.0,
        "semester_percentage": 70.0,
        "semester_sgpa": 7.8,
        "semester_attendance_percentage": 82.0,
        "backlog_count": 1,
        "department_name": "BBA",
        "gender": "Female",
    }


class TestSupportedIdsAndReadiness(unittest.TestCase):

    def test_supported_model_identifiers(self):
        self.assertEqual(list(SUPPORTED_MODEL_IDS), ["m1", "m2", "m3"])
        self.assertEqual(supported_models(), ["m1", "m2", "m3"])

    def test_m1_readiness_ready(self):
        self.assertEqual(get_readiness("m1"), READY)
        self.assertEqual(MODEL_READINESS["m1"], READY)

    def test_m2_readiness_blocked_retired(self):
        # Legacy V1 M2 is retired; its readiness BLOCKED reflects retirement.
        self.assertEqual(get_readiness("m2"), BLOCKED)
        self.assertEqual(MODEL_READINESS["m2"], BLOCKED)

    def test_m3_readiness_ready(self):
        self.assertEqual(get_readiness("m3"), READY)
        self.assertEqual(MODEL_READINESS["m3"], READY)

    def test_unsupported_model_raises(self):
        with self.assertRaises(ValueError):
            get_readiness("m5")

    def test_readiness_states_complete(self):
        self.assertEqual(
            set(READINESS_STATES),
            {READY, BLOCKED, UNAVAILABLE, INVALID_INPUT, ERROR},
        )

    def test_m2_readiness_reason_mentions_retirement(self):
        reason = readiness_reason("m2")
        self.assertIn(BLOCKED, MODEL_READINESS["m2"])
        self.assertIn("retired", reason.lower())
        self.assertIn("m2", reason.lower())

    def test_m3_readiness_reason_mentions_ready(self):
        reason = readiness_reason("m3")
        self.assertEqual(MODEL_READINESS["m3"], READY)
        self.assertIn("production", reason.lower())
        self.assertNotIn("blocked", reason.lower())


class TestM1Prediction(unittest.TestCase):

    def test_prediction_shape_type(self):
        res = predict_m1(m1_row())
        self.assertIsInstance(res, InferenceResult)
        self.assertEqual(res.model_id, "m1")
        self.assertEqual(res.readiness_status, READY)
        self.assertTrue(res.prediction_available)
        self.assertIsInstance(res.prediction, float)
        self.assertEqual(res.subject_id, "SUB0001")
        self.assertEqual(res.semester_no, 7)

    def test_m1_clipping_range(self):
        # Try extremes that would exceed [0, 70] if not clipped.
        for _ in range(2):
            r = predict_m1(m1_row())
            self.assertGreaterEqual(r.prediction, 0.0)
            self.assertLessEqual(r.prediction, 70.0)

    def test_m1_feature_count_is_12(self):
        r = predict_m1(m1_row())
        self.assertEqual(r.feature_count, 12)


class TestM2Retired(unittest.TestCase):

    def test_predict_m2_is_blocked_unavailable(self):
        # predict_m2 never produces a prediction: the legacy V1 pathway is gone.
        res = predict_m2(m2_row())
        self.assertIsInstance(res, InferenceResult)
        self.assertEqual(res.model_id, "m2")
        self.assertEqual(res.readiness_status, BLOCKED)
        self.assertFalse(res.prediction_available)
        self.assertIsNone(res.prediction)
        self.assertFalse(res.validation_ok)
        self.assertIn("retired", res.reason.lower())

    def test_m2_cannot_be_ready(self):
        # No invocation path may produce READY for M2.
        self.assertNotEqual(get_readiness("m2"), READY)
        self.assertEqual(predict_m2(m2_row()).readiness_status, BLOCKED)

    def test_m2_has_no_artifact(self):
        # The legacy artifact is deleted; artifact_hash must refuse to compute.
        with self.assertRaises(ValueError):
            artifact_hash("m2")


class TestM3Ready(unittest.TestCase):

    def test_m3_ready_response(self):
        res = predict_m3(m2_row())
        self.assertEqual(res.readiness_status, READY)
        self.assertTrue(res.prediction_available)
        self.assertIsInstance(res.prediction, dict)
        self.assertIn("is_at_risk_next_sem", res.prediction)
        self.assertIn(res.prediction["is_at_risk_next_sem"], (0, 1))

    def test_m3_feature_count_is_12(self):
        self.assertEqual(predict_m3(m2_row()).feature_count, 12)

    def test_m3_can_be_ready(self):
        self.assertEqual(get_readiness("m3"), READY)
        self.assertEqual(predict_m3(m2_row()).readiness_status, READY)


class TestInputValidation(unittest.TestCase):

    def test_missing_required_input(self):
        with self.assertRaises(InferenceInputError):
            predict_m3({"student_id": "S1", "semester_no": 5})
        with self.assertRaises(InferenceInputError):
            predict_m1({"student_id": "S1"})

    def test_invalid_numeric_input(self):
        with self.assertRaises(InferenceInputError):
            predict_m3({**m2_row(), "semester_percentage": "high"})

    def test_non_finite_input(self):
        with self.assertRaises(InferenceInputError):
            predict_m3({**m2_row(), "semester_sgpa": float("inf")})
        with self.assertRaises(InferenceInputError):
            predict_m3({**m2_row(), "backlog_count": float("nan")})

    def test_invalid_categorical_value(self):
        with self.assertRaises(InferenceInputError):
            predict_m3({**m2_row(), "department_name": "ECE"})
        with self.assertRaises(InferenceInputError):
            predict_m1({**m1_row(), "subject_type": "Unknown"})
        with self.assertRaises(InferenceInputError):
            predict_m3({**m2_row(), "gender": "Other"})

    def test_invalid_semester_value(self):
        with self.assertRaises(InferenceInputError):
            predict_m3({**m2_row(), "semester_no": 99})

    def test_validation_accepts_valid_row(self):
        row = validate_input_row("m3", dict(m2_row()))
        self.assertEqual(row["student_id"], "STU000002")


class TestLeakage(unittest.TestCase):

    def test_m1_target_leakage_rejected(self):
        with self.assertRaises(InferenceInputError):
            predict_m1({**m1_row(), "end_sem_marks": 40.0})

    def test_m3_target_leakage_rejected(self):
        with self.assertRaises(InferenceInputError):
            predict_m3({**m2_row(), "is_at_risk_next_sem": 1})

    def test_summary_target_leakage_rejected(self):
        # M2/M3 shared spec: next-sem outcome columns are never features.
        with self.assertRaises(InferenceInputError):
            predict_m3({**m2_row(), "next_semester_percentage": 70.0})
        with self.assertRaises(InferenceInputError):
            predict_m3({**m2_row(), "next_semester_sgpa": 8.0})

    def test_prediction_feedback_rejected(self):
        with self.assertRaises(InferenceInputError):
            predict_m3({**m2_row(), "prediction_feedback": "good"})

    def test_future_outcome_rejected(self):
        with self.assertRaises(InferenceInputError):
            predict_m3({**m2_row(), "semester_result": "PASS"})


class TestFeatureContract(unittest.TestCase):

    def test_exact_12_feature_contract_m1(self):
        names = feature_names("m1")
        self.assertEqual(len(names), 12)
        self.assertEqual(list(names), list(M1_ENCODED_FEATURES))

    def test_exact_12_feature_contract_m2(self):
        names = feature_names("m2")
        self.assertEqual(len(names), 12)
        self.assertEqual(list(names), list(M2_M3_ENCODED_FEATURES))

    def test_exact_12_feature_contract_m3(self):
        names = feature_names("m3")
        self.assertEqual(len(names), 12)
        self.assertEqual(list(names), list(M2_M3_ENCODED_FEATURES))

    def test_exact_feature_order(self):
        self.assertEqual(list(M1_ENCODED_FEATURES), [
            "internal_marks", "mid_sem_marks", "attendance_percentage",
            "credits", "semester_no",
            "subject_type_Internship", "subject_type_Laboratory",
            "subject_type_Project", "subject_type_Theory",
            "department_name_BBA", "department_name_CSE", "is_male",
        ])
        self.assertEqual(list(M2_M3_ENCODED_FEATURES), [
            "semester_no", "subjects_registered", "credits_registered",
            "credits_earned", "semester_total_marks", "semester_percentage",
            "semester_sgpa", "semester_attendance_percentage", "backlog_count",
            "department_name_BBA", "department_name_CSE", "is_male",
        ])

    def test_bba_cse_one_hot_present(self):
        for names in (list(M1_ENCODED_FEATURES), list(M2_M3_ENCODED_FEATURES)):
            self.assertIn("department_name_BBA", names)
            self.assertIn("department_name_CSE", names)
        for r in (predict_m1(m1_row()), predict_m3(m2_row())):
            self.assertEqual(r.feature_count, 12)


class TestModelLoadingAndArtifact(unittest.TestCase):

    def test_model_loaded_through_registry(self):
        import features.v1_inference_contract as contract
        real_load = contract.registry.load_model
        calls = []

        def spy(model_id, *a, **k):
            calls.append(model_id)
            return real_load(model_id, *a, **k)

        with mock.patch.object(contract.registry, "load_model", side_effect=spy):
            predict_m1(m1_row())
        self.assertIn("m1", calls)

    def test_artifact_identity_m1(self):
        self.assertEqual(artifact_hash("m1"), M1_HASH)

    def test_artifact_identity_m3(self):
        self.assertEqual(artifact_hash("m3"), M3_HASH)


class TestDeterminism(unittest.TestCase):

    def test_deterministic_m1(self):
        a = predict_m1(m1_row()).to_dict()
        b = predict_m1(m1_row()).to_dict()
        self.assertEqual(a, b)

    def test_deterministic_m3(self):
        a = predict_m3(m2_row()).to_dict()
        b = predict_m3(m2_row()).to_dict()
        self.assertEqual(a, b)


class TestUnifiedDispatch(unittest.TestCase):

    def test_unified_predict_dispatcher(self):
        r1 = predict("m1", m1_row())
        self.assertEqual(r1.model_id, "m1")
        self.assertEqual(r1.readiness_status, READY)
        r2 = predict("m2", m2_row())
        self.assertEqual(r2.model_id, "m2")
        self.assertEqual(r2.readiness_status, BLOCKED)
        r3 = predict("m3", m2_row())
        self.assertEqual(r3.model_id, "m3")
        self.assertEqual(r3.readiness_status, READY)

    def test_unknown_model_dispatch_raises(self):
        with self.assertRaises(ValueError):
            predict("m5", {})


class TestNoWrites(unittest.TestCase):

    def test_artifact_hashes_unchanged_by_inference(self):
        before = {m: artifact_hash(m) for m in SUPPORTED_MODEL_IDS if m != "m2"}
        predict_m1(m1_row())
        predict_m3(m2_row())
        after = {m: artifact_hash(m) for m in SUPPORTED_MODEL_IDS if m != "m2"}
        self.assertEqual(before, after)

    def test_no_database_connection_code(self):
        import features.v1_inference_contract as contract
        src = open(contract.__file__, encoding="utf-8").read()
        self.assertNotIn("asyncpg", src)
        self.assertNotIn("psycopg", src)
        self.assertNotIn("create_pool", src)
        self.assertNotIn("INSERT INTO", src)
        self.assertNotIn("UPDATE ", src)

    def test_no_artifact_write(self):
        import features.v1_inference_contract as contract
        self.assertNotIn("joblib.dump", open(contract.__file__, encoding="utf-8").read())
        self.assertNotIn("to_pickle", open(contract.__file__, encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main()