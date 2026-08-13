"""Tests for ML-01: Model Registry + Safe Model Loader.

Focused tests covering:
- Successful load of each registered model (M1, M2, M3, M4)
- Missing artifact error handling
- Invalid/corrupt artifact error handling
- Registry resolution (lookup, listing, status)
- Cache behavior (avoiding unnecessary repeated reloads)
- Correct M4 handling (rule-based, no .joblib)
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import joblib
import numpy as np
import pandas as pd

# Ensure ml/src is on sys.path for imports
_ML_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _ML_SRC not in sys.path:
    sys.path.insert(0, _ML_SRC)

from registry import (  # noqa: E402
    ModelEntry,
    ModelType,
    artifact_exists,
    clear_cache,
    get_entry,
    list_models,
    load_model,
    registry_status,
    _loaded_cache,
    _ARTIFACT_DIR,
)


class TestRegistryMetadata(unittest.TestCase):
    """Verify registry contains correct entries for M1-M4."""

    def test_list_models_returns_all_four(self):
        models = list_models()
        self.assertEqual(len(models), 4)

    def test_all_model_ids_present(self):
        ids = {m.model_id for m in list_models()}
        self.assertEqual(ids, {"m1", "m2", "m3", "m4"})

    def test_get_entry_m1(self):
        entry = get_entry("m1")
        self.assertEqual(entry.model_id, "m1")
        self.assertEqual(entry.model_type, ModelType.JOBLIB)
        self.assertEqual(entry.task, "regression")
        self.assertEqual(entry.target, "end_sem_marks")

    def test_get_entry_m2(self):
        entry = get_entry("m2")
        self.assertEqual(entry.model_id, "m2")
        self.assertEqual(entry.model_type, ModelType.JOBLIB)
        self.assertEqual(entry.task, "multi_target_regression")
        self.assertEqual(entry.target, ["next_semester_percentage", "next_semester_sgpa"])

    def test_get_entry_m3(self):
        entry = get_entry("m3")
        self.assertEqual(entry.model_id, "m3")
        self.assertEqual(entry.model_type, ModelType.JOBLIB)
        self.assertEqual(entry.task, "binary_classification")
        self.assertEqual(entry.target, "is_at_risk_next_sem")

    def test_get_entry_m4_rule_based(self):
        entry = get_entry("m4")
        self.assertEqual(entry.model_id, "m4")
        self.assertEqual(entry.model_type, ModelType.RULE_BASED)
        self.assertEqual(entry.task, "scoring")
        self.assertIsNone(entry.artifact_path)

    def test_get_entry_unknown_raises_key_error(self):
        with self.assertRaises(KeyError) as ctx:
            get_entry("m99")
        self.assertIn("m99", str(ctx.exception))
        self.assertIn("not registered", str(ctx.exception))


class TestArtifactExists(unittest.TestCase):
    """Check artifact_exists for real and missing artifacts."""

    def test_m1_artifact_exists(self):
        entry = get_entry("m1")
        self.assertTrue(entry.artifact_path.exists())
        self.assertTrue(artifact_exists("m1"))

    def test_m2_artifact_exists(self):
        entry = get_entry("m2")
        self.assertTrue(entry.artifact_path.exists())
        self.assertTrue(artifact_exists("m2"))

    def test_m3_artifact_exists(self):
        entry = get_entry("m3")
        self.assertTrue(entry.artifact_path.exists())
        self.assertTrue(artifact_exists("m3"))

    def test_m4_rule_based_always_exists(self):
        self.assertTrue(artifact_exists("m4"))


class TestSuccessfulLoad(unittest.TestCase):
    """Load each real model artifact and verify basic shape."""

    def setUp(self):
        clear_cache()

    def test_load_m1_returns_dict_with_expected_keys(self):
        obj = load_model("m1")
        self.assertIsInstance(obj, dict)
        self.assertIn("model", obj)
        self.assertIn("preprocess", obj)
        self.assertIn("feature_names", obj)
        self.assertIn("metadata", obj)
        self.assertIsInstance(obj["feature_names"], list)
        self.assertIsInstance(obj["metadata"], dict)

    def test_load_m2_returns_dict_of_pipelines(self):
        obj = load_model("m2")
        self.assertIsInstance(obj, dict)
        self.assertIn("next_semester_percentage", obj)
        self.assertIn("next_semester_sgpa", obj)
        self.assertTrue(hasattr(obj["next_semester_percentage"], "predict"))

    def test_load_m3_returns_pipeline_with_predict(self):
        obj = load_model("m3")
        self.assertTrue(hasattr(obj, "predict"))

    def test_load_m4_returns_career_readiness_engine(self):
        obj = load_model("m4")
        self.assertEqual(type(obj).__name__, "CareerReadinessEngine")
        self.assertTrue(hasattr(obj, "score"))
        self.assertTrue(hasattr(obj, "version"))


class TestCacheBehavior(unittest.TestCase):
    """Verify caching avoids unnecessary repeated reloads."""

    def setUp(self):
        clear_cache()

    def test_first_load_populates_cache(self):
        load_model("m3")
        self.assertIn("m3", _loaded_cache)

    def test_second_load_returns_same_object(self):
        obj1 = load_model("m3")
        obj2 = load_model("m3")
        self.assertIs(obj1, obj2)

    def test_force_reload_creates_new_object(self):
        obj1 = load_model("m3")
        obj2 = load_model("m3", force_reload=True)
        # Same type, but different object identity after force reload
        self.assertIsNot(obj1, obj2)
        self.assertTrue(hasattr(obj2, "predict"))

    def test_clear_cache_single_model(self):
        load_model("m3")
        self.assertIn("m3", _loaded_cache)
        clear_cache("m3")
        self.assertNotIn("m3", _loaded_cache)

    def test_clear_cache_all(self):
        load_model("m1")
        load_model("m3")
        self.assertTrue(len(_loaded_cache) >= 2)
        clear_cache()
        self.assertEqual(len(_loaded_cache), 0)


class TestMissingArtifact(unittest.TestCase):
    """Verify FileNotFoundError when artifact is missing."""

    def setUp(self):
        clear_cache()

    def test_missing_artifact_raises(self):
        entry = get_entry("m1")
        original_path = entry.artifact_path
        try:
            # Temporarily point to a non-existent path
            object.__setattr__(entry, "artifact_path", Path("/nonexistent/m1.joblib"))
            with self.assertRaises(FileNotFoundError) as ctx:
                load_model("m1")
            self.assertIn("not found", str(ctx.exception))
        finally:
            object.__setattr__(entry, "artifact_path", original_path)


class TestCorruptArtifact(unittest.TestCase):
    """Verify ValueError when artifact is corrupt."""

    def setUp(self):
        clear_cache()

    def test_corrupt_joblib_raises_value_error(self):
        entry = get_entry("m3")
        original_path = entry.artifact_path
        try:
            with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as f:
                f.write(b"this is not a valid joblib file")
                f.flush()
                corrupt_path = Path(f.name)

            object.__setattr__(entry, "artifact_path", corrupt_path)
            with self.assertRaises(ValueError) as ctx:
                load_model("m3")
            self.assertIn("corrupt", str(ctx.exception).lower())
        finally:
            object.__setattr__(entry, "artifact_path", original_path)
            corrupt_path.unlink(missing_ok=True)


class TestShapeValidation(unittest.TestCase):
    """Verify shape validation catches wrong artifact structure."""

    def setUp(self):
        clear_cache()

    def test_m1_wrong_shape_raises_type_error(self):
        entry = get_entry("m1")
        original_path = entry.artifact_path
        try:
            with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as f:
                # Save a plain string instead of expected dict
                joblib.dump("not a model dict", f.name)
                corrupt_path = Path(f.name)

            object.__setattr__(entry, "artifact_path", corrupt_path)
            with self.assertRaises(TypeError) as ctx:
                load_model("m1")
            self.assertIn("dict", str(ctx.exception))
        finally:
            object.__setattr__(entry, "artifact_path", original_path)
            corrupt_path.unlink(missing_ok=True)

    def test_m2_missing_targets_raises_type_error(self):
        entry = get_entry("m2")
        original_path = entry.artifact_path
        try:
            with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as f:
                # Save dict missing expected target keys
                joblib.dump({"wrong_target": "dummy"}, f.name)
                corrupt_path = Path(f.name)

            object.__setattr__(entry, "artifact_path", corrupt_path)
            with self.assertRaises(TypeError) as ctx:
                load_model("m2")
            self.assertIn("missing expected targets", str(ctx.exception))
        finally:
            object.__setattr__(entry, "artifact_path", original_path)
            corrupt_path.unlink(missing_ok=True)

    def test_m3_no_predict_method_raises_type_error(self):
        entry = get_entry("m3")
        original_path = entry.artifact_path
        try:
            with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as f:
                # Save a dict without predict method
                joblib.dump({"not_a_pipeline": True}, f.name)
                corrupt_path = Path(f.name)

            object.__setattr__(entry, "artifact_path", corrupt_path)
            with self.assertRaises(TypeError) as ctx:
                load_model("m3")
            self.assertIn("predict", str(ctx.exception))
        finally:
            object.__setattr__(entry, "artifact_path", original_path)
            corrupt_path.unlink(missing_ok=True)


class TestRegistryStatus(unittest.TestCase):
    """Verify registry_status returns complete information."""

    def test_status_covers_all_models(self):
        status = registry_status()
        self.assertEqual(len(status), 4)
        ids = {s["model_id"] for s in status}
        self.assertEqual(ids, {"m1", "m2", "m3", "m4"})

    def test_status_shows_artifact_exists(self):
        status = registry_status()
        for s in status:
            self.assertIn("artifact_exists", s)
            self.assertTrue(s["artifact_exists"])

    def test_status_shows_cached_field(self):
        clear_cache()
        status = registry_status()
        for s in status:
            self.assertFalse(s["cached"])

        load_model("m3")
        status = registry_status()
        m3_status = next(s for s in status if s["model_id"] == "m3")
        self.assertTrue(m3_status["cached"])

    def test_m4_status_has_no_artifact_path(self):
        status = registry_status()
        m4_status = next(s for s in status if s["model_id"] == "m4")
        self.assertIsNone(m4_status["artifact_path"])
        self.assertEqual(m4_status["model_type"], "rule_based")


class TestM4RuleBasedHandling(unittest.TestCase):
    """Verify M4 is handled correctly as rule-based (no .joblib)."""

    def setUp(self):
        clear_cache()

    def test_m4_entry_has_no_artifact_path(self):
        entry = get_entry("m4")
        self.assertIsNone(entry.artifact_path)
        self.assertEqual(entry.model_type, ModelType.RULE_BASED)

    def test_m4_load_returns_engine_instance(self):
        obj = load_model("m4")
        self.assertTrue(hasattr(obj, "score"))
        self.assertTrue(hasattr(obj, "aggregate_academic"))
        self.assertTrue(hasattr(obj, "level_thresholds"))

    def test_m4_engine_has_expected_weights(self):
        obj = load_model("m4")
        self.assertIn("academic_performance", obj.weights)
        self.assertIn("growth_trend", obj.weights)
        self.assertIn("career_preparedness", obj.weights)
        self.assertIn("lifestyle_discipline", obj.weights)
        self.assertEqual(sum(obj.weights.values()), 100)


class TestUnsupportedModelType(unittest.TestCase):
    """Verify error when model type is unsupported."""

    def test_unknown_model_id_raises_key_error(self):
        with self.assertRaises(KeyError):
            load_model("nonexistent_model")


if __name__ == "__main__":
    unittest.main()
