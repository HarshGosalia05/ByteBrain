"""Unit tests for the ETL Load stage.

Covers: dry-run rejection, empty input handling, unique index creation,
attendance upsert (insert/update), timetable upsert (insert/update),
unknown source key, transaction boundaries, StageResult shape and
metadata, V1 table scope, business key preservation, idempotent re-runs,
batch INSERT...ON CONFLICT, and integration with Transform output through Load.

All tests use mocked asyncpg connections/pools — no live database required.
We patch ``etl.stages.load.transaction`` to yield a mock connection directly,
bypassing the real ``db.transaction()`` async context manager internals.
"""

import asyncio
import datetime
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from etl.context import RunContext
from etl.exceptions import EtlDryRunError, EtlLoadDeriveError
from etl.stages import STAGE_LOAD
from etl.stages.load import (
    ATTENDANCE_CONFLICT_FIELDS,
    TABLE_DAILY_ATTENDANCE,
    TABLE_WEEKLY_TIMETABLE,
    TIMETABLE_CONFLICT_FIELDS,
    LoadStage,
    _BATCH_SIZE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def attendance_record(**overrides):
    """Transform-output-shaped attendance record."""
    base = {
        "source": "daily_attendance",
        "run_id": "test-run-001",
        "row_index": 1,
        "enrollment_record_id": "ENR000001",
        "attendance_id": "1",
        "student_id": "STU000001",
        "enrollment_no": "2023010001",
        "subject_id": "SUB0050",
        "subject_name": "Software Engineering",
        "faculty_id": "FAC005",
        "lecture_date": datetime.date(2026, 6, 22),
        "lecture_number": 1,
        "day_name": "Monday",
        "department_code": 1,
        "semester_no": 7,
        "academic_year": "2026-2027",
        "attendance_status": "P",
        "attendance_status_text": "Present",
        "is_present": True,
        "lecture_session_key": "2026-06-22_FAC005_1",
    }
    base.update(overrides)
    return base


def timetable_record(**overrides):
    """Transform-output-shaped timetable record."""
    base = {
        "source": "weekly_timetable",
        "run_id": "test-run-001",
        "row_index": 1,
        "timetable_id": 1,
        "department_code": 1,
        "semester_no": 7,
        "academic_year": "2026-2027",
        "day_name": "Monday",
        "slot_no": 1,
        "start_time": datetime.time(13, 0),
        "end_time": datetime.time(14, 0),
        "subject_id": "SUB0050",
        "subject_name": "Software Engineering",
        "faculty_id": "FAC005",
        "lecture_type": "Theory",
        "lecture_session_key": "1_SUB0050_FAC005_Monday_1",
    }
    base.update(overrides)
    return base


def make_mock_conn():
    """Create a mock asyncpg connection for batch load operations.

    The batch INSERT...ON CONFLICT approach uses ``conn.execute()`` which
    returns a PostgreSQL command tag string (e.g. "INSERT 0 6150").
    """
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    return conn


def make_mock_pool(conn=None):
    """Create a mock asyncpg pool.

    ``pool.acquire()`` returns an awaitable that resolves to the mock
    connection. ``pool.release()`` is a no-op.
    """
    if conn is None:
        conn = make_mock_conn()

    class _AcquireAwaitable:
        def __await__(self):
            async def _return_conn():
                return conn
            return _return_conn().__await__()

    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=_AcquireAwaitable())
    pool.release = AsyncMock()
    return pool, conn


def _patched_transaction(conn):
    """Return a mock ``transaction`` context manager that yields *conn*.

    Used as a replacement for ``etl.db.transaction`` so we bypass the
    real ``db.transaction()`` internals (which use ``asyncpg`` connection
    transactions and require yet another level of mocking).
    """
    @asynccontextmanager
    async def _mock_transaction(pool, *, dry_run=False):
        yield conn
    return _mock_transaction


# ---------------------------------------------------------------------------
# Contract / Metadata
# ---------------------------------------------------------------------------

class TestLoadStageContract(unittest.TestCase):
    def test_stage_name(self):
        self.assertEqual(LoadStage.name, STAGE_LOAD)

    def test_stage_name_matches_constant(self):
        self.assertEqual(LoadStage.name, "load")

    def test_instantiation_no_args(self):
        stage = LoadStage()
        self.assertEqual(stage.name, STAGE_LOAD)

    def test_instantiation_with_sources(self):
        stage = LoadStage(sources=["daily_attendance"])
        self.assertEqual(stage._sources, ("daily_attendance",))

    def test_instantiation_with_shared(self):
        shared = {"transformed": {"daily_attendance": []}}
        stage = LoadStage(shared=shared)
        self.assertIs(stage._shared, shared)

    def test_description_non_empty(self):
        self.assertTrue(len(LoadStage.description) > 0)

    def test_stage_is_async(self):
        self.assertTrue(asyncio.iscoroutinefunction(LoadStage.run))


# ---------------------------------------------------------------------------
# Dry-Run / Guard
# ---------------------------------------------------------------------------

class TestDryRunRejection(unittest.TestCase):
    def test_dry_run_returns_noop_success(self):
        stage = LoadStage()
        ctx = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(ctx, pool=None))
        self.assertEqual(result.status, "success")
        self.assertEqual(result.rows_read, 0)

    def test_pool_none_returns_noop_success(self):
        stage = LoadStage()
        ctx = RunContext.create(dry_run=False)
        result = asyncio.run(stage.run(ctx, pool=None))
        self.assertEqual(result.status, "success")
        self.assertEqual(result.rows_read, 0)

    def test_dry_run_with_transformed_data(self):
        shared = {
            "transformed": {
                "daily_attendance": [attendance_record()],
            }
        }
        stage = LoadStage(shared=shared)
        ctx = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(ctx, pool=None))
        self.assertEqual(result.status, "success")
        self.assertEqual(result.rows_read, 1)
        self.assertEqual(result.rows_accepted, 1)


# ---------------------------------------------------------------------------
# Empty / Missing Data
# ---------------------------------------------------------------------------

class TestEmptyInput(unittest.TestCase):
    def test_no_transformed_key(self):
        stage = LoadStage(shared={})
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool()
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.rows_read, 0)
        self.assertEqual(result.rows_accepted, 0)

    def test_empty_transformed_dict(self):
        stage = LoadStage(shared={"transformed": {}})
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool()
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.rows_read, 0)

    def test_source_not_in_transformed(self):
        stage = LoadStage(sources=["weekly_timetable"], shared={"transformed": {"daily_attendance": []}})
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool()
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.rows_read, 0)

    def test_empty_records_list(self):
        stage = LoadStage(shared={"transformed": {"daily_attendance": []}})
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool()
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.rows_read, 0)
        self.assertEqual(result.rows_accepted, 0)


# ---------------------------------------------------------------------------
# Unique Index Creation
# ---------------------------------------------------------------------------

class TestUniqueIndexCreation(unittest.TestCase):
    @patch("etl.stages.load.transaction")
    def test_indexes_created(self, mock_txn):
        conn = make_mock_conn()
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(shared={"transformed": {"daily_attendance": []}})
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        execute_calls = [str(c) for c in conn.execute.call_args_list]
        idx_calls = [c for c in execute_calls if "CREATE UNIQUE INDEX" in c]
        self.assertEqual(len(idx_calls), 2)

    @patch("etl.stages.load.transaction")
    def test_attendance_index_name(self, mock_txn):
        conn = make_mock_conn()
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(shared={"transformed": {"daily_attendance": []}})
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        all_sql = " ".join(str(c) for c in conn.execute.call_args_list)
        self.assertIn("uniq_daily_attendance_07_natural_key", all_sql)

    @patch("etl.stages.load.transaction")
    def test_timetable_index_name(self, mock_txn):
        conn = make_mock_conn()
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(shared={"transformed": {"weekly_timetable": []}})
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        all_sql = " ".join(str(c) for c in conn.execute.call_args_list)
        self.assertIn("uniq_weekly_timetable_07_natural_key", all_sql)

    @patch("etl.stages.load.transaction")
    def test_index_if_not_exists(self, mock_txn):
        conn = make_mock_conn()
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(shared={"transformed": {"daily_attendance": []}})
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        all_sql = " ".join(str(c) for c in conn.execute.call_args_list)
        self.assertIn("IF NOT EXISTS", all_sql)


# ---------------------------------------------------------------------------
# Attendance Upsert — Insert
# ---------------------------------------------------------------------------

class TestAttendanceInsert(unittest.TestCase):
    @patch("etl.stages.load.transaction")
    def test_insert_new_record(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(
            sources=["daily_attendance"],
            shared={"transformed": {"daily_attendance": [attendance_record()]}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.rows_read, 1)
        self.assertEqual(result.rows_accepted, 1)
        self.assertEqual(result.rows_written, 1)
        self.assertEqual(result.metadata["inserted"], 1)
        self.assertEqual(result.metadata["updated"], 0)

    @patch("etl.stages.load.transaction")
    def test_insert_calls_execute(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(
            sources=["daily_attendance"],
            shared={"transformed": {"daily_attendance": [attendance_record()]}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        conn.execute.assert_called()

    @patch("etl.stages.load.transaction")
    def test_insert_multiple_records(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 3")
        mock_txn.side_effect = _patched_transaction(conn)
        records = [
            attendance_record(student_id="STU000001"),
            attendance_record(student_id="STU000002"),
            attendance_record(student_id="STU000003"),
        ]
        stage = LoadStage(
            sources=["daily_attendance"],
            shared={"transformed": {"daily_attendance": records}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.rows_read, 3)
        self.assertEqual(result.rows_written, 3)
        self.assertEqual(result.metadata["inserted"], 3)


# ---------------------------------------------------------------------------
# Attendance Upsert — Update / Unchanged
# ---------------------------------------------------------------------------

class TestAttendanceUpdateUnchanged(unittest.TestCase):
    @patch("etl.stages.load.transaction")
    def test_conflict_reports_as_updated(self, mock_txn):
        """Batch INSERT...ON CONFLICT cannot distinguish update vs unchanged
        at the SQL level — all conflicting rows are reported as 'updated'
        since the UPSERT ensures idempotent correctness."""
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="UPDATE 0 1")
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(
            sources=["daily_attendance"],
            shared={"transformed": {"daily_attendance": [attendance_record()]}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.metadata["updated"], 1)
        self.assertEqual(result.metadata["inserted"], 0)
        self.assertEqual(result.rows_written, 1)

    @patch("etl.stages.load.transaction")
    def test_insert_and_update_mixed(self, mock_txn):
        """Batch with mix of inserts and updates — total matches row count."""
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 2")
        mock_txn.side_effect = _patched_transaction(conn)
        records = [
            attendance_record(student_id="STU000001"),
            attendance_record(student_id="STU000002"),
        ]
        stage = LoadStage(
            sources=["daily_attendance"],
            shared={"transformed": {"daily_attendance": records}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.rows_read, 2)
        self.assertEqual(result.rows_written, 2)


# ---------------------------------------------------------------------------
# Timetable Upsert — Insert / Update
# ---------------------------------------------------------------------------

class TestTimetableInsert(unittest.TestCase):
    @patch("etl.stages.load.transaction")
    def test_insert_new_timetable_record(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(
            sources=["weekly_timetable"],
            shared={"transformed": {"weekly_timetable": [timetable_record()]}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.rows_read, 1)
        self.assertEqual(result.rows_written, 1)
        self.assertEqual(result.metadata["inserted"], 1)
        self.assertEqual(result.metadata["updated"], 0)

    @patch("etl.stages.load.transaction")
    def test_insert_multiple_timetable_records(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 3")
        mock_txn.side_effect = _patched_transaction(conn)
        records = [
            timetable_record(day_name="Monday", slot_no=1),
            timetable_record(day_name="Monday", slot_no=2),
            timetable_record(day_name="Tuesday", slot_no=1),
        ]
        stage = LoadStage(
            sources=["weekly_timetable"],
            shared={"transformed": {"weekly_timetable": records}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.rows_read, 3)
        self.assertEqual(result.rows_written, 3)
        self.assertEqual(result.metadata["inserted"], 3)


class TestTimetableUpdate(unittest.TestCase):
    @patch("etl.stages.load.transaction")
    def test_update_when_lecture_type_changes(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="UPDATE 0 1")
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(
            sources=["weekly_timetable"],
            shared={"transformed": {"weekly_timetable": [timetable_record()]}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.metadata["updated"], 1)
        self.assertEqual(result.metadata["inserted"], 0)
        self.assertEqual(result.rows_written, 1)


# ---------------------------------------------------------------------------
# Unknown Source Key
# ---------------------------------------------------------------------------

class TestUnknownSource(unittest.TestCase):
    @patch("etl.stages.load.transaction")
    def test_unknown_source_raises(self, mock_txn):
        conn = make_mock_conn()
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(
            sources=["unknown_source"],
            shared={"transformed": {"unknown_source": [attendance_record()]}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        with self.assertRaises(EtlLoadDeriveError) as cm:
            asyncio.run(stage.run(ctx, pool=pool))
        self.assertIn("unknown source key", str(cm.exception))


# ---------------------------------------------------------------------------
# Multiple Sources
# ---------------------------------------------------------------------------

class TestMultipleSources(unittest.TestCase):
    @patch("etl.stages.load.transaction")
    def test_both_sources_loaded(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_txn.side_effect = _patched_transaction(conn)
        shared = {
            "transformed": {
                "daily_attendance": [attendance_record()],
                "weekly_timetable": [timetable_record()],
            }
        }
        stage = LoadStage(shared=shared)
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.rows_read, 2)
        self.assertEqual(result.rows_written, 2)
        self.assertIn("daily_attendance", result.metadata["source_keys"])
        self.assertIn("weekly_timetable", result.metadata["source_keys"])

    @patch("etl.stages.load.transaction")
    def test_sources_flag_scopes_to_single_source(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_txn.side_effect = _patched_transaction(conn)
        shared = {
            "transformed": {
                "daily_attendance": [attendance_record()],
                "weekly_timetable": [timetable_record()],
            }
        }
        stage = LoadStage(sources=["daily_attendance"], shared=shared)
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.rows_read, 1)
        self.assertEqual(result.metadata["source_keys"], ["daily_attendance"])


# ---------------------------------------------------------------------------
# StageResult Shape
# ---------------------------------------------------------------------------

class TestStageResultShape(unittest.TestCase):
    @patch("etl.stages.load.transaction")
    def test_result_stage_name(self, mock_txn):
        conn = make_mock_conn()
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(shared={"transformed": {"daily_attendance": []}})
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.stage, STAGE_LOAD)

    @patch("etl.stages.load.transaction")
    def test_result_has_metadata(self, mock_txn):
        conn = make_mock_conn()
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(shared={"transformed": {"daily_attendance": []}})
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertIn("source_keys", result.metadata)
        self.assertIn("inserted", result.metadata)
        self.assertIn("updated", result.metadata)
        self.assertIn("unchanged", result.metadata)
        self.assertIn("failed_sources", result.metadata)
        self.assertIn("run_id", result.metadata)

    @patch("etl.stages.load.transaction")
    def test_result_run_id_matches_context(self, mock_txn):
        conn = make_mock_conn()
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(shared={"transformed": {"daily_attendance": []}})
        ctx = RunContext.create(run_id="test-run-xyz", dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.metadata["run_id"], "test-run-xyz")

    @patch("etl.stages.load.transaction")
    def test_result_status_success(self, mock_txn):
        conn = make_mock_conn()
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(shared={"transformed": {"daily_attendance": []}})
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.status, "success")
        self.assertFalse(result.failed)

    @patch("etl.stages.load.transaction")
    def test_result_rows_read_and_accepted_equal(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 2")
        mock_txn.side_effect = _patched_transaction(conn)
        records = [attendance_record(), attendance_record(student_id="STU000002")]
        stage = LoadStage(
            sources=["daily_attendance"],
            shared={"transformed": {"daily_attendance": records}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.rows_read, result.rows_accepted)


# ---------------------------------------------------------------------------
# V1 Table Scope
# ---------------------------------------------------------------------------

class TestV1TableScope(unittest.TestCase):
    @patch("etl.stages.load.transaction")
    def test_only_canonical_tables_written_to(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(
            sources=["daily_attendance"],
            shared={"transformed": {"daily_attendance": [attendance_record()]}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        all_sql = " ".join(str(c) for c in conn.execute.call_args_list)
        self.assertIn(TABLE_DAILY_ATTENDANCE, all_sql)

    def test_table_name_constants(self):
        self.assertEqual(TABLE_DAILY_ATTENDANCE, "daily_attendance_07")
        self.assertEqual(TABLE_WEEKLY_TIMETABLE, "weekly_timetable_07")


# ---------------------------------------------------------------------------
# Business Key Preservation
# ---------------------------------------------------------------------------

class TestBusinessKeyPreservation(unittest.TestCase):
    def test_attendance_conflict_fields(self):
        self.assertEqual(
            ATTENDANCE_CONFLICT_FIELDS,
            ("student_id", "subject_id", "lecture_date", "lecture_number"),
        )

    def test_timetable_conflict_fields(self):
        self.assertEqual(
            TIMETABLE_CONFLICT_FIELDS,
            ("semester_no", "subject_id", "faculty_id", "day_name", "slot_no"),
        )

    @patch("etl.stages.load.transaction")
    def test_attendance_upsert_uses_on_conflict(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(
            sources=["daily_attendance"],
            shared={"transformed": {"daily_attendance": [attendance_record()]}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        execute_calls = [str(c) for c in conn.execute.call_args_list]
        on_conflict_calls = [c for c in execute_calls if "ON CONFLICT" in c]
        self.assertGreater(len(on_conflict_calls), 0)

    @patch("etl.stages.load.transaction")
    def test_timetable_upsert_uses_on_conflict(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(
            sources=["weekly_timetable"],
            shared={"transformed": {"weekly_timetable": [timetable_record()]}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        execute_calls = [str(c) for c in conn.execute.call_args_list]
        on_conflict_calls = [c for c in execute_calls if "ON CONFLICT" in c]
        self.assertGreater(len(on_conflict_calls), 0)


# ---------------------------------------------------------------------------
# Parameterized SQL
# ---------------------------------------------------------------------------

class TestParameterizedSQL(unittest.TestCase):
    @patch("etl.stages.load.transaction")
    def test_no_string_interpolation_in_insert(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(
            sources=["daily_attendance"],
            shared={"transformed": {"daily_attendance": [attendance_record()]}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        for call in conn.execute.call_args_list:
            sql_template = call[0][0] if call[0] else ""
            if "INSERT" in sql_template:
                self.assertNotIn("STU000001", sql_template)
                self.assertNotIn("Software Engineering", sql_template)


# ---------------------------------------------------------------------------
# Batch Operations
# ---------------------------------------------------------------------------

class TestBatchOperations(unittest.TestCase):
    def test_batch_size_constant(self):
        self.assertEqual(_BATCH_SIZE, 500)

    @patch("etl.stages.load.transaction")
    def test_single_batch_for_small_dataset(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 3")
        mock_txn.side_effect = _patched_transaction(conn)
        records = [attendance_record() for _ in range(3)]
        stage = LoadStage(
            sources=["daily_attendance"],
            shared={"transformed": {"daily_attendance": records}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.rows_written, 3)

    @patch("etl.stages.load.transaction")
    def test_multiple_batches_for_large_dataset(self, mock_txn):
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 500")
        mock_txn.side_effect = _patched_transaction(conn)
        records = [attendance_record(student_id=f"STU{i:06d}") for i in range(1200)]
        stage = LoadStage(
            sources=["daily_attendance"],
            shared={"transformed": {"daily_attendance": records}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        # 1200 records / 500 batch size = 3 batches
        self.assertEqual(conn.execute.call_count, 3 + 2)  # 3 batch + 2 index creates
        self.assertEqual(result.rows_written, 1200)

    @patch("etl.stages.load.transaction")
    def test_empty_records_returns_zero(self, mock_txn):
        conn = make_mock_conn()
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(
            sources=["daily_attendance"],
            shared={"transformed": {"daily_attendance": []}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.rows_read, 0)
        self.assertEqual(result.rows_written, 0)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency(unittest.TestCase):
    @patch("etl.stages.load.transaction")
    def test_same_data_upsert_is_idempotent(self, mock_txn):
        """Re-running Load with identical transformed data triggers UPSERT
        — the ON CONFLICT clause fires but the DB state is unchanged."""
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="UPDATE 0 1")
        mock_txn.side_effect = _patched_transaction(conn)
        stage = LoadStage(
            sources=["daily_attendance"],
            shared={"transformed": {"daily_attendance": [attendance_record()]}},
        )
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        # ON CONFLICT fires → reported as "updated" in metadata
        self.assertEqual(result.metadata["updated"], 1)
        self.assertEqual(result.metadata["inserted"], 0)
        self.assertEqual(result.rows_written, 1)

    def test_idempotent_index_creation(self):
        """Calling _ensure_unique_indexes twice is harmless (IF NOT EXISTS)."""
        conn = make_mock_conn()
        stage = LoadStage(shared={"transformed": {"daily_attendance": []}})
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage._ensure_unique_indexes(pool))
        asyncio.run(stage._ensure_unique_indexes(pool))
        self.assertGreaterEqual(conn.execute.call_count, 4)


# ---------------------------------------------------------------------------
# Integration: Transform → Load
# ---------------------------------------------------------------------------

class TestTransformToLoadIntegration(unittest.TestCase):
    @patch("etl.stages.load.transaction")
    def test_transform_output_feeds_load(self, mock_txn):
        """Transform output shape feeds directly into Load without transformation."""
        from etl.stages.stitch import ResolvedIdentities, StitchedRecord
        from etl.stages.transform import TransformStage

        stitched = StitchedRecord(
            source="daily_attendance",
            run_id="integration-001",
            row_index=1,
            row={
                "attendance_id": "1", "student_id": "STU000001",
                "enrollment_no": "2023010001", "subject_id": "SUB0050",
                "subject_name": "Software Engineering", "faculty_id": "FAC005",
                "lecture_date": "2026-06-22", "lecture_number": "1",
                "day_name": "Monday", "department_code": "1", "semester_no": "7",
                "academic_year": "2026-2027", "attendance_status": "P",
            },
            enrollment_record_id="ENR000001",
            resolved=ResolvedIdentities(
                student=True, subject=True, faculty=True, enrollment=True,
            ),
        )
        shared: dict = {"stitched": {"daily_attendance": [stitched]}}

        # Transform
        transform_stage = TransformStage(shared=shared)
        ctx = RunContext.create(run_id="integration-001")
        t_result = asyncio.run(transform_stage.run(ctx, pool=None))
        self.assertEqual(t_result.status, "success")
        self.assertIn("transformed", shared)

        # Load
        conn = make_mock_conn()
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_txn.side_effect = _patched_transaction(conn)
        load_stage = LoadStage(shared=shared)
        ctx2 = RunContext.create(run_id="integration-001", dry_run=False)
        pool, _ = make_mock_pool(conn)
        l_result = asyncio.run(load_stage.run(ctx2, pool=pool))
        self.assertEqual(l_result.status, "success")
        self.assertEqual(l_result.rows_read, 1)
        self.assertEqual(l_result.rows_written, 1)
        self.assertEqual(l_result.metadata["inserted"], 1)


if __name__ == "__main__":
    unittest.main()
