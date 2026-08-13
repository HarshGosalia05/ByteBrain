"""Service-level tests for ML-06 (MLPredictionService).

Uses a fake asyncpg pool (no live database). Verifies typed
validation of persisted outputs (pydantic per-type contract),
rejection of unknown types / malformed payloads, NULL metadata
preservation, and latest/history retrieval delegation.
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from app.services.ml_prediction_service import MLPredictionService


class _TransactionContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConn:
    def __init__(self, fetchrow_result=None, fetch_result=None):
        self.fetchrow_result = fetchrow_result
        self.fetch_result = fetch_result or []
        self.executed = []
        self.transactions = 0

    async def fetchrow(self, query, *args):
        self.executed.append(("fetchrow", query, args))
        return self.fetchrow_result

    async def fetch(self, query, *args):
        self.executed.append(("fetch", query, args))
        return self.fetch_result

    def transaction(self):
        self.transactions += 1
        return _TransactionContext(self)


class _AcquireContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _AcquireContext(self.conn)


def run(coro):
    return asyncio.run(coro)


def stored_row(**overrides):
    row = {
        "prediction_id": "22222222-2222-2222-2222-222222222222",
        "student_id": "STU000001",
        "prediction_type": "m1",
        "model_version": None,
        "prediction_value": {"subject_id": "SUB0050", "semester_no": 7,
                             "predicted_end_sem_marks": 58.5, "clipped": False},
        "input_row_count": None,
        "prediction_count": None,
        "generated_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }
    row.update(overrides)
    return row


def valid_value(prediction_type="m1"):
    return {
        "m1": {"subject_id": "SUB0050", "semester_no": 7,
               "predicted_end_sem_marks": 58.5, "clipped": False},
        "m2": {"semester_no": 7, "predicted_next_semester_sgpa": 8.25,
               "predicted_next_semester_percentage": 78.4},
        "m3": {"semester_no": 7, "is_at_risk_next_sem": 1},
        "m4": {"enrollment_no": "2023010001", "full_name": "Alice",
               "department_name": "CSE", "current_semester": 7,
               "career_readiness_score": 72.5, "career_readiness_level": "High",
               "positive_factors": "", "risk_factors": ""},
    }[prediction_type]


def make_service(conn):
    return MLPredictionService(FakePool(conn))


class TestPersistSingle(unittest.TestCase):
    def test_persist_m1_valid(self):
        conn = FakeConn(fetchrow_result=stored_row())
        svc = make_service(conn)

        result = run(svc.persist_single(
            "m1", student_id="STU000001", prediction_value=valid_value("m1"),
            model_version="1", input_row_count=1, prediction_count=1,
        ))

        self.assertEqual(result["student_id"], "STU000001")
        kind, query, args = conn.executed[0]
        self.assertIn("INSERT INTO ml_predictions", query)
        self.assertEqual(args[0], "STU000001")
        self.assertEqual(args[2], "1")
        self.assertIn('"predicted_end_sem_marks": 58.5', args[3])

    def test_persist_all_four_types(self):
        for ptype in ("m1", "m2", "m3", "m4"):
            conn = FakeConn(fetchrow_result=stored_row(prediction_type=ptype))
            svc = make_service(conn)
            result = run(svc.persist_single(
                ptype, student_id="STU000001", prediction_value=valid_value(ptype)
            ))
            self.assertEqual(result["prediction_type"], ptype)

    def test_null_metadata_preserved(self):
        conn = FakeConn(fetchrow_result=stored_row())
        svc = make_service(conn)
        run(svc.persist_single(
            "m1", student_id="STU000001", prediction_value=valid_value("m1"),
        ))
        kind, query, args = conn.executed[0]
        self.assertIsNone(args[2])  # model_version -> NULL
        self.assertIsNone(args[4])  # input_row_count -> NULL
        self.assertIsNone(args[5])  # prediction_count -> NULL

    def test_unknown_type_rejected_before_db(self):
        conn = FakeConn(fetchrow_result=stored_row())
        svc = make_service(conn)
        with self.assertRaises(ValueError):
            run(svc.persist_single(
                "m9", student_id="STU000001", prediction_value=valid_value("m1")
            ))
        self.assertEqual(conn.executed, [])

    def test_m3_non_binary_rejected(self):
        conn = FakeConn(fetchrow_result=stored_row())
        svc = make_service(conn)
        bad = valid_value("m3")
        bad["is_at_risk_next_sem"] = 2
        with self.assertRaises(ValidationError):
            run(svc.persist_single(
                "m3", student_id="STU000001", prediction_value=bad
            ))
        self.assertEqual(conn.executed, [])

    def test_missing_required_field_rejected(self):
        conn = FakeConn(fetchrow_result=stored_row())
        svc = make_service(conn)
        bad = valid_value("m1")
        del bad["subject_id"]
        with self.assertRaises(ValidationError):
            run(svc.persist_single(
                "m1", student_id="STU000001", prediction_value=bad
            ))
        self.assertEqual(conn.executed, [])

    def test_non_dict_value_rejected(self):
        conn = FakeConn()
        svc = make_service(conn)
        with self.assertRaises(TypeError):
            run(svc.persist_single(
                "m1", student_id="STU000001", prediction_value="not-a-dict"
            ))

    def test_m4_defaults_allowed(self):
        conn = FakeConn(fetchrow_result=stored_row(prediction_type="m4"))
        svc = make_service(conn)
        minimal = {
            "current_semester": 7,
            "career_readiness_score": 70.0,
            "career_readiness_level": "High",
        }
        run(svc.persist_single("m4", student_id="STU000001", prediction_value=minimal))
        kind, query, args = conn.executed[0]
        self.assertIn('"positive_factors": ""', args[3])


class TestPersistPredictions(unittest.TestCase):
    def test_batch_returns_count(self):
        conn = FakeConn(fetchrow_result=stored_row())
        svc = make_service(conn)
        items = [
            {"student_id": "STU000001", "prediction_value": valid_value("m1")},
            {"student_id": "STU000001", "prediction_value": valid_value("m1")},
        ]
        inserted = run(svc.persist_predictions(
            "m1", items, model_version="1", input_row_count=2, prediction_count=2
        ))
        self.assertEqual(inserted, 2)
        self.assertEqual(conn.transactions, 1)
        for kind, query, args in conn.executed:
            self.assertEqual(args[0], "STU000001")
            self.assertEqual(args[2], "1")

    def test_invalid_item_rejected(self):
        conn = FakeConn(fetchrow_result=stored_row())
        svc = make_service(conn)
        items = [
            {"student_id": "STU000001", "prediction_value": valid_value("m1")},
            {"prediction_value": valid_value("m1")},  # missing student_id
        ]
        with self.assertRaises(ValueError):
            run(svc.persist_predictions("m1", items))
        self.assertEqual(conn.transactions, 0)
        self.assertEqual(conn.executed, [])

    def test_unknown_type_rejected(self):
        conn = FakeConn(fetchrow_result=stored_row())
        svc = make_service(conn)
        with self.assertRaises(ValueError):
            run(svc.persist_predictions(
                "m9", [{"student_id": "STU000001",
                        "prediction_value": valid_value("m1")}]
            ))
        self.assertEqual(conn.executed, [])


class TestRetrieval(unittest.TestCase):
    def test_get_latest_delegates(self):
        conn = FakeConn(fetchrow_result=stored_row())
        svc = make_service(conn)
        result = run(svc.get_latest("STU000001", "m2"))
        self.assertEqual(result["prediction_type"], "m1")
        kind, query, args = conn.executed[0]
        self.assertIn("ORDER BY generated_at DESC", query)
        self.assertIn("LIMIT 1", query)
        self.assertEqual(args, ("STU000001", "m2"))

    def test_get_history_delegates(self):
        conn = FakeConn(fetch_result=[stored_row(), stored_row()])
        svc = make_service(conn)
        result = run(svc.get_history("STU000001", "m1", limit=10, offset=5))
        self.assertEqual(len(result), 2)
        kind, query, args = conn.executed[0]
        self.assertEqual(args, ("STU000001", "m1", 10, 5))

    def test_get_history_all_types(self):
        conn = FakeConn(fetch_result=[])
        svc = make_service(conn)
        result = run(svc.get_history("STU000001", limit=20, offset=0))
        self.assertEqual(result, [])
        kind, query, args = conn.executed[0]
        self.assertEqual(args, ("STU000001", 20, 0))


if __name__ == "__main__":
    unittest.main()
