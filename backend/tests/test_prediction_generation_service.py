"""ML-07 service tests: PredictionGenerationService orchestration.

Runs in the backend environment (no pandas required): all heavy
dependencies are injected fakes and the ML-side converter / version
resolver are monkeypatched at the module boundary.

Verifies the explicit generate -> validate -> persist -> return flow:
  * M1-M4 dispatch and metadata preservation (model_version, counts)
  * invalid prediction / model failure persist nothing
  * unknown type / missing student id rejected before any work
  * repeated generation appends history (ML-06 append-only contract)
  * latest/history retrieval decodes the JSONB prediction_value
  * model_version resolution (M1 metadata, M4 engine, M2/M3 NULL)
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services import prediction_generation_service as pgs  # noqa: E402
from app.services.prediction_generation_service import (  # noqa: E402
    PredictionGenerationService,
    resolve_model_version,
)


def run(coro):
    return asyncio.run(coro)


class FakeResult:
    """Stand-in for inference.PredictionResult (attributes only)."""

    def __init__(self, model_id, input_row_count=3, prediction_count=3):
        self.model_id = model_id
        self.input_row_count = input_row_count
        self.prediction_count = prediction_count


class FakeGeneration:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def _run(self, student_id):
        self.calls.append(student_id)
        if self.error is not None:
            raise self.error
        return self.result

    async def predict_m1_for_student(self, student_id):
        return await self._run(student_id)

    async def predict_m2_for_student(self, student_id):
        return await self._run(student_id)

    async def predict_m3_for_student(self, student_id):
        return await self._run(student_id)

    async def predict_m4_for_student(self, student_id):
        return await self._run(student_id)


class FakePersistence:
    def __init__(self, latest=None):
        self.rows = []
        self.latest_override = latest
        self.persist_calls = []
        self.latest_calls = []
        self.history_calls = []

    async def persist_predictions(self, prediction_type, items, **kwargs):
        self.persist_calls.append((prediction_type, items, kwargs))
        for i in items:
            self.rows.append({**i, "prediction_type": prediction_type})
        return len(items)

    async def get_latest(self, student_id, prediction_type):
        self.latest_calls.append((student_id, prediction_type))
        if self.latest_override is not None:
            return self.latest_override
        return self.rows[-1] if self.rows else None

    async def get_history(self, student_id, prediction_type=None, *, limit=20, offset=0):
        self.history_calls.append((student_id, prediction_type, limit, offset))
        return list(reversed(self.rows))


def make_service(generation, persistence):
    return PredictionGenerationService(
        pool=None, generation_service=generation, persistence_service=persistence
    )


class TestGenerateAndPersist(unittest.TestCase):
    def setUp(self):
        self.gen = FakeGeneration(result=FakeResult("m1", 5, 5))
        self.persist = FakePersistence()
        self.service = make_service(self.gen, self.persist)
        self.rows = [{"student_id": "STU000001", "prediction_type": "m1",
                      "prediction_value": {"subject_id": "SUB0050"}}]

    def test_m1_flow(self):
        ts = datetime(2026, 8, 13, 6, 0, 0, tzinfo=timezone.utc)
        with mock.patch.object(pgs, "to_persistence_rows", return_value=self.rows), \
             mock.patch.object(pgs, "resolve_model_version", return_value="1"), \
             mock.patch.object(pgs, "utc_now", return_value=ts):
            out = run(self.service.generate_and_persist("m1", "STU000001"))

        self.assertEqual(self.gen.calls, ["STU000001"])
        self.assertEqual(len(self.persist.persist_calls), 1)
        ptype, items, kwargs = self.persist.persist_calls[0]
        self.assertEqual(ptype, "m1")
        self.assertEqual(items, self.rows)
        self.assertEqual(kwargs["model_version"], "1")
        self.assertEqual(kwargs["input_row_count"], 5)
        self.assertEqual(kwargs["prediction_count"], 5)
        self.assertEqual(kwargs["generated_at"], ts)
        self.assertEqual(self.persist.latest_calls, [("STU000001", "m1")])
        self.assertEqual(out["persisted_rows"], 1)
        self.assertEqual(out["model_id"], "m1")
        self.assertIs(out["result"], self.gen.result)

    def test_all_four_types_dispatch(self):
        versions = {"m1": "1", "m2": None, "m3": None, "m4": "1.0"}
        for ptype in ("m1", "m2", "m3", "m4"):
            gen = FakeGeneration(result=FakeResult(ptype))
            persist = FakePersistence()
            service = make_service(gen, persist)
            with mock.patch.object(pgs, "to_persistence_rows",
                                   return_value=[{"student_id": "STU000001",
                                                  "prediction_value": {}}]), \
                 mock.patch.object(pgs, "resolve_model_version",
                                   side_effect=lambda t: versions[t]):
                out = run(service.generate_and_persist(ptype, "STU000001"))
            self.assertEqual(out["model_id"], ptype)
            self.assertEqual(out["model_version"], versions[ptype])
            self.assertEqual(persist.persist_calls[0][0], ptype)
            self.assertEqual(gen.calls, ["STU000001"])

    def test_invalid_prediction_not_persisted(self):
        with mock.patch.object(pgs, "to_persistence_rows",
                               side_effect=ValueError("unexpected model_id m9")):
            with self.assertRaises(ValueError):
                run(self.service.generate_and_persist("m1", "STU000001"))
        self.assertEqual(self.persist.persist_calls, [])

    def test_model_failure_not_persisted(self):
        gen = FakeGeneration(result=None, error=RuntimeError("model load failed"))
        persist = FakePersistence()
        service = make_service(gen, persist)
        with self.assertRaises(RuntimeError):
            run(service.generate_and_persist("m1", "STU000001"))
        self.assertEqual(persist.persist_calls, [])

    def test_unknown_type_rejected(self):
        with self.assertRaises(ValueError):
            run(self.service.generate_and_persist("m9", "STU000001"))
        self.assertEqual(self.gen.calls, [])
        self.assertEqual(self.persist.persist_calls, [])

    def test_empty_student_id_rejected(self):
        with self.assertRaises(ValueError):
            run(self.service.generate_and_persist("m1", "   "))
        self.assertEqual(self.gen.calls, [])
        self.assertEqual(self.persist.persist_calls, [])

    def test_repeated_generation_appends_history(self):
        ts1 = datetime(2026, 8, 13, 6, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 8, 13, 6, 30, 0, tzinfo=timezone.utc)
        for ts in (ts1, ts2):
            with mock.patch.object(pgs, "to_persistence_rows", return_value=self.rows), \
                 mock.patch.object(pgs, "resolve_model_version", return_value=None), \
                 mock.patch.object(pgs, "utc_now", return_value=ts):
                run(self.service.generate_and_persist("m1", "STU000001"))

        self.assertEqual(len(self.persist.persist_calls), 2)
        self.assertEqual(self.persist.persist_calls[0][2]["generated_at"], ts1)
        self.assertEqual(self.persist.persist_calls[1][2]["generated_at"], ts2)
        self.assertEqual(len(self.persist.rows), 2)
        history = run(self.service.get_history("STU000001", "m1"))
        self.assertEqual(len(history), 2)


class TestRetrieval(unittest.TestCase):
    def test_get_latest_decodes_jsonb_string(self):
        persist = FakePersistence(latest={
            "prediction_id": "1", "student_id": "STU000001", "prediction_type": "m1",
            "model_version": "1", "prediction_value": '{"subject_id": "SUB0050"}',
            "input_row_count": 1, "prediction_count": 1,
            "generated_at": datetime(2026, 8, 13, tzinfo=timezone.utc),
            "created_at": datetime(2026, 8, 13, tzinfo=timezone.utc),
        })
        service = make_service(FakeGeneration(), persist)
        row = run(service.get_latest("STU000001", "m1"))
        self.assertEqual(row["prediction_value"], {"subject_id": "SUB0050"})

    def test_get_history_decodes(self):
        persist = FakePersistence()
        persist.rows = [
            {"prediction_id": "2", "student_id": "STU000001", "prediction_type": "m1",
             "model_version": None, "prediction_value": '{"a": 1}',
             "input_row_count": None, "prediction_count": None,
             "generated_at": None, "created_at": None},
            {"prediction_id": "1", "student_id": "STU000001", "prediction_type": "m1",
             "model_version": None, "prediction_value": '{"a": 2}',
             "input_row_count": None, "prediction_count": None,
             "generated_at": None, "created_at": None},
        ]
        service = make_service(FakeGeneration(), persist)
        rows = run(service.get_history("STU000001", "m1", limit=5, offset=0))
        # FakePersistence reverses the list -> newest-first: row 2 ({"a": 2})
        self.assertEqual(rows[0]["prediction_value"], {"a": 2})
        self.assertEqual(persist.history_calls, [("STU000001", "m1", 5, 0)])

    def test_get_latest_unknown_type(self):
        service = make_service(FakeGeneration(), FakePersistence())
        with self.assertRaises(ValueError):
            run(service.get_latest("STU000001", "m9"))


class TestResolveModelVersion(unittest.TestCase):
    def test_m2_m3_returns_none_without_loading(self):
        self.assertIsNone(resolve_model_version("m2"))
        self.assertIsNone(resolve_model_version("m3"))

    def test_m1_from_artifact_metadata(self):
        with mock.patch("ml.src.registry.load_model",
                        return_value={"metadata": {"version": 7}}) as m:
            self.assertEqual(resolve_model_version("m1"), "7")
            m.assert_called_once_with("m1")

    def test_m1_no_version_metadata(self):
        with mock.patch("ml.src.registry.load_model",
                        return_value={"metadata": {}}):
            self.assertIsNone(resolve_model_version("m1"))

    def test_m1_load_error_returns_none(self):
        with mock.patch("ml.src.registry.load_model",
                        side_effect=RuntimeError("boom")):
            self.assertIsNone(resolve_model_version("m1"))

    def test_m4_from_engine_version(self):
        engine = mock.Mock()
        engine.version = "2.5"
        with mock.patch("ml.src.registry.load_model", return_value=engine) as m:
            self.assertEqual(resolve_model_version("m4"), "2.5")
            m.assert_called_once_with("m4")


if __name__ == "__main__":
    unittest.main()
