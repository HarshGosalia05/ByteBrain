"""Repository-level tests for ML-06 (ml_predictions persistence).

Uses a fake asyncpg pool that records executed SQL, so no live
database is required (same pattern as the existing backend suites).
Verifies the append-only write path, the latest/history read shapes,
NULL preservation, invalid-type rejection, and student scoping.
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone

from app.repositories.ml_prediction_repo import MLPredictionRepository


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
        self.executed = []  # (kind, query, args)
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
        self.acquisitions = 0

    def acquire(self):
        self.acquisitions += 1
        return _AcquireContext(self.conn)


def run(coro):
    return asyncio.run(coro)


def stored_row(**overrides):
    row = {
        "prediction_id": "11111111-1111-1111-1111-111111111111",
        "student_id": "STU000001",
        "prediction_type": "m1",
        "model_version": "1",
        "prediction_value": {"subject_id": "SUB0050", "semester_no": 7,
                             "predicted_end_sem_marks": 58.5, "clipped": False},
        "input_row_count": 1,
        "prediction_count": 1,
        "generated_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }
    row.update(overrides)
    return row


def sample_value(prediction_type="m1"):
    values = {
        "m1": {"subject_id": "SUB0050", "semester_no": 7,
               "predicted_end_sem_marks": 58.5, "clipped": False},
        "m2": {"source_semester": 6, "target_semester": 7,
               "theory_prediction_pct": 72.5, "practical_prediction_pct": 68.0},
        "m3": {"semester_no": 7, "is_at_risk_next_sem": 1},
        "m4": {"enrollment_no": "2023010001", "full_name": "Alice",
               "department_name": "CSE", "current_semester": 7,
               "career_readiness_score": 72.5, "career_readiness_level": "High",
               "positive_factors": "", "risk_factors": ""},
    }
    return values[prediction_type]


class TestInsertPrediction(unittest.TestCase):
    def test_insert_prediction_m1(self):
        conn = FakeConn(fetchrow_result=stored_row())
        pool = FakePool(conn)
        repo = MLPredictionRepository(pool)

        result = run(repo.insert_prediction(
            student_id="STU000001", prediction_type="m1",
            prediction_value=sample_value("m1"), model_version="1",
            input_row_count=1, prediction_count=1,
        ))

        self.assertEqual(result["student_id"], "STU000001")
        self.assertEqual(result["prediction_type"], "m1")
        self.assertEqual(pool.acquisitions, 1)
        kind, query, args = conn.executed[0]
        self.assertEqual(kind, "fetchrow")
        self.assertIn("INSERT INTO ml_predictions", query)
        self.assertIn("RETURNING", query)
        # Args: student_id, type, model_version, json payload, counts, ts
        self.assertEqual(args[0], "STU000001")
        self.assertEqual(args[1], "m1")
        self.assertEqual(args[2], "1")
        self.assertIn('"predicted_end_sem_marks": 58.5', args[3])
        self.assertEqual(args[4], 1)
        self.assertEqual(args[5], 1)

    def test_insert_prediction_null_model_version(self):
        conn = FakeConn(fetchrow_result=stored_row(model_version=None))
        pool = FakePool(conn)
        repo = MLPredictionRepository(pool)

        run(repo.insert_prediction(
            student_id="STU000001", prediction_type="m1",
            prediction_value=sample_value("m1"),
        ))
        kind, query, args = conn.executed[0]
        # model_version omitted -> NULL is passed (None), not a fake value
        self.assertIsNone(args[2])
        self.assertIsNone(args[4])
        self.assertIsNone(args[5])

    def test_insert_prediction_json_safe_nan_to_null(self):
        conn = FakeConn(fetchrow_result=stored_row())
        pool = FakePool(conn)
        repo = MLPredictionRepository(pool)
        value = sample_value("m1")
        value["predicted_end_sem_marks"] = float("nan")

        run(repo.insert_prediction(
            student_id="STU000001", prediction_type="m1",
            prediction_value=value,
        ))
        kind, query, args = conn.executed[0]
        self.assertNotIn("nan", args[3].lower())
        self.assertIn("null", args[3])

    def test_insert_prediction_unknown_type_rejected(self):
        conn = FakeConn(fetchrow_result=stored_row())
        pool = FakePool(conn)
        repo = MLPredictionRepository(pool)

        with self.assertRaises(ValueError):
            run(repo.insert_prediction(
                student_id="STU000001", prediction_type="m5",
                prediction_value=sample_value("m1"),
            ))
        self.assertEqual(conn.executed, [])
        self.assertEqual(pool.acquisitions, 0)

    def test_insert_prediction_non_dict_value_rejected(self):
        pool = FakePool(FakeConn())
        repo = MLPredictionRepository(pool)
        with self.assertRaises(TypeError):
            run(repo.insert_prediction(
                student_id="STU000001", prediction_type="m1",
                prediction_value="not-a-dict",
            ))


class TestInsertPredictions(unittest.TestCase):
    def test_batch_insert_returns_count(self):
        conn = FakeConn(fetchrow_result=stored_row())
        pool = FakePool(conn)
        repo = MLPredictionRepository(pool)

        rows = [
            {"student_id": "STU000001", "prediction_type": "m1",
             "prediction_value": sample_value("m1"), "model_version": "1",
             "input_row_count": 1, "prediction_count": 1},
            {"student_id": "STU000001", "prediction_type": "m1",
             "prediction_value": sample_value("m1"), "model_version": "1",
             "input_row_count": 1, "prediction_count": 1},
        ]
        inserted = run(repo.insert_predictions(rows))

        self.assertEqual(inserted, 2)
        self.assertEqual(conn.transactions, 1)
        self.assertEqual(len(conn.executed), 2)
        for kind, query, _ in conn.executed:
            self.assertIn("INSERT INTO ml_predictions", query)

    def test_empty_batch_is_noop(self):
        pool = FakePool(FakeConn())
        repo = MLPredictionRepository(pool)
        self.assertEqual(run(repo.insert_predictions([])), 0)
        self.assertEqual(pool.acquisitions, 0)

    def test_invalid_row_rejected_before_insert(self):
        conn = FakeConn(fetchrow_result=stored_row())
        pool = FakePool(conn)
        repo = MLPredictionRepository(pool)
        rows = [
            {"student_id": "STU000001", "prediction_type": "m1",
             "prediction_value": sample_value("m1")},
            {"student_id": "STU000002", "prediction_type": "m9",
             "prediction_value": sample_value("m1")},
        ]
        with self.assertRaises(ValueError):
            run(repo.insert_predictions(rows))
        # Validation happens before any insert / transaction
        self.assertEqual(conn.transactions, 0)
        self.assertEqual(conn.executed, [])

    def test_missing_required_key_rejected(self):
        pool = FakePool(FakeConn())
        repo = MLPredictionRepository(pool)
        with self.assertRaises(ValueError):
            run(repo.insert_predictions(
                [{"student_id": "STU000001", "prediction_value": {}}]
            ))


class TestGetLatest(unittest.TestCase):
    def test_get_latest_returns_row(self):
        conn = FakeConn(fetchrow_result=stored_row())
        pool = FakePool(conn)
        repo = MLPredictionRepository(pool)

        result = run(repo.get_latest("STU000001", "m1"))

        self.assertIsNotNone(result)
        self.assertEqual(result["student_id"], "STU000001")
        kind, query, args = conn.executed[0]
        self.assertEqual(kind, "fetchrow")
        self.assertIn("FROM ml_predictions", query)
        self.assertIn("WHERE student_id = $1 AND prediction_type = $2", query)
        self.assertIn("ORDER BY generated_at DESC", query)
        self.assertIn("LIMIT 1", query)
        self.assertEqual(args, ("STU000001", "m1"))

    def test_get_latest_none_when_missing(self):
        pool = FakePool(FakeConn(fetchrow_result=None))
        repo = MLPredictionRepository(pool)
        self.assertIsNone(run(repo.get_latest("STU999999", "m2")))

    def test_get_latest_invalid_type_rejected(self):
        pool = FakePool(FakeConn())
        repo = MLPredictionRepository(pool)
        with self.assertRaises(ValueError):
            run(repo.get_latest("STU000001", "m9"))


class TestGetHistory(unittest.TestCase):
    def test_history_with_type_filter(self):
        conn = FakeConn(fetch_result=[stored_row()])
        pool = FakePool(conn)
        repo = MLPredictionRepository(pool)

        result = run(repo.get_history("STU000001", "m3", limit=5, offset=10))

        self.assertEqual(len(result), 1)
        kind, query, args = conn.executed[0]
        self.assertEqual(kind, "fetch")
        self.assertIn("WHERE student_id = $1 AND prediction_type = $2", query)
        self.assertIn("ORDER BY generated_at DESC", query)
        self.assertEqual(args, ("STU000001", "m3", 5, 10))

    def test_history_all_types(self):
        conn = FakeConn(fetch_result=[stored_row()])
        pool = FakePool(conn)
        repo = MLPredictionRepository(pool)

        run(repo.get_history("STU000001", limit=20, offset=0))

        kind, query, args = conn.executed[0]
        self.assertIn("WHERE student_id = $1", query)
        self.assertNotIn("prediction_type", query.split("WHERE")[1].split("ORDER")[0])
        self.assertEqual(args, ("STU000001", 20, 0))

    def test_history_invalid_pagination_rejected(self):
        pool = FakePool(FakeConn())
        repo = MLPredictionRepository(pool)
        with self.assertRaises(ValueError):
            run(repo.get_history("STU000001", limit=0))
        with self.assertRaises(ValueError):
            run(repo.get_history("STU000001", offset=-1))

    def test_history_invalid_type_rejected(self):
        pool = FakePool(FakeConn())
        repo = MLPredictionRepository(pool)
        with self.assertRaises(ValueError):
            run(repo.get_history("STU000001", "m9"))


if __name__ == "__main__":
    unittest.main()
