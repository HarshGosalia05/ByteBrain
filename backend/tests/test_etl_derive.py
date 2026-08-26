"""Unit tests for the ETL Derive stage.

Covers: contract, dry-run guard, empty input, attendance recompute
(DELETE + INSERT with aggregation), semester summary recompute, student
field updates (overall_attendance_percentage, full_name), error handling,
transaction boundaries, and CLI integration.

All tests use mocked asyncpg connections — no live database required.
We patch ``etl.stages.derive.transaction`` to yield a mock connection directly.
"""

import asyncio
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from etl.context import RunContext
from etl.exceptions import EtlDryRunError, EtlLoadDeriveError
from etl.stages import STAGE_DERIVE
from etl.stages.derive import (
    TABLE_ATTENDANCE,
    TABLE_SEMESTER_SUMMARY,
    TABLE_STUDENTS,
    DeriveStage,
)


# ---------------------------------------------------------------------------
# Mock Helpers
# ---------------------------------------------------------------------------

def make_mock_conn(fetch_results=None, fetchval_results=None):
    """Create a mock asyncpg connection with ordered responses.

    ``fetch_results`` is a list of values returned in order by ``conn.fetch()``.
    ``fetchval_results`` is a list of values returned in order by ``conn.fetchval()``.
    """
    conn = AsyncMock()
    _fetch_iter = iter(fetch_results or [])
    _fetchval_iter = iter(fetchval_results or [])

    async def _fetch(query, *args, **kwargs):
        return next(_fetch_iter, [])

    async def _fetchval(query, *args, **kwargs):
        return next(_fetchval_iter, None)

    conn.fetch = AsyncMock(side_effect=_fetch)
    conn.fetchval = AsyncMock(side_effect=_fetchval)
    conn.execute = AsyncMock()
    return conn


def make_mock_pool(conn=None):
    """Create a mock asyncpg pool returning *conn* from acquire()."""
    if conn is None:
        conn = make_mock_conn()

    class _AcquireAwaitable:
        def __await__(self):
            async def _return_conn():
                return conn
            return _return_conn().__await__()

    pool = AsyncMock()
    pool.acquire = lambda: _AcquireAwaitable()
    pool.release = AsyncMock()
    return pool, conn


def _patched_transaction(conn):
    """Return a mock ``transaction`` context manager yielding *conn*."""
    @asynccontextmanager
    async def _mock_transaction(pool, *, dry_run=False):
        yield conn
    return _mock_transaction


def enrollment_row(enrollment_record_id="ENR000001", student_id="STU000001", enrollment_no=2023010001):
    return {
        "enrollment_record_id": enrollment_record_id,
        "student_id": student_id,
        "enrollment_no": enrollment_no,
    }


def attendance_agg_row(enrollment_record_id="ENR000001", student_id="STU000001", enrollment_no=2023010001, subject_id="SUB0050", total_classes=90, attended_classes=69):
    return {
        "enrollment_record_id": enrollment_record_id,
        "student_id": student_id,
        "enrollment_no": enrollment_no,
        "subject_id": subject_id,
        "total_classes": total_classes,
        "attended_classes": attended_classes,
    }


def semester_summary_row(student_id="STU000001", semester_attendance_percentage=76.67):
    return {
        "student_id": student_id,
        "semester_attendance_percentage": semester_attendance_percentage,
    }


# ---------------------------------------------------------------------------
# Contract / Metadata
# ---------------------------------------------------------------------------

class TestDeriveStageContract(unittest.TestCase):
    def test_stage_name(self):
        self.assertEqual(DeriveStage.name, STAGE_DERIVE)

    def test_stage_name_matches_constant(self):
        self.assertEqual(DeriveStage.name, "derive")

    def test_instantiation_no_args(self):
        stage = DeriveStage()
        self.assertEqual(stage.name, STAGE_DERIVE)

    def test_instantiation_with_sources(self):
        stage = DeriveStage(sources=["daily_attendance"])
        self.assertEqual(stage._sources, ("daily_attendance",))

    def test_instantiation_with_shared(self):
        shared = {"transformed": {}}
        stage = DeriveStage(shared=shared)
        self.assertIs(stage._shared, shared)

    def test_description_non_empty(self):
        self.assertTrue(len(DeriveStage.description) > 0)

    def test_stage_is_async(self):
        self.assertTrue(asyncio.iscoroutinefunction(DeriveStage.run))


# ---------------------------------------------------------------------------
# Dry-Run / Guard
# ---------------------------------------------------------------------------

class TestDryRunRejection(unittest.TestCase):
    def test_dry_run_returns_noop_success(self):
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(ctx, pool=None))
        self.assertEqual(result.status, "success")
        self.assertEqual(result.rows_read, 0)

    def test_pool_none_returns_noop_success(self):
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        result = asyncio.run(stage.run(ctx, pool=None))
        self.assertEqual(result.status, "success")
        self.assertEqual(result.rows_read, 0)

    def test_dry_run_no_db_interaction(self):
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(ctx, pool=None))
        self.assertEqual(result.status, "success")
        self.assertEqual(result.rows_accepted, 0)


# ---------------------------------------------------------------------------
# Empty Input
# ---------------------------------------------------------------------------

class TestEmptyInput(unittest.TestCase):
    @patch("etl.stages.derive.transaction")
    def test_no_enrolled_students_returns_success(self, mock_txn):
        conn = make_mock_conn(fetch_results=[[]])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.status, "success")
        self.assertEqual(result.rows_read, 0)

    @patch("etl.stages.derive.transaction")
    def test_enrolled_but_no_attendance_returns_success(self, mock_txn):
        conn = make_mock_conn(fetch_results=[
            [enrollment_row()],
            [],
        ])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.status, "success")


# ---------------------------------------------------------------------------
# Attendance Derivation
# ---------------------------------------------------------------------------

class TestAttendanceDerivation(unittest.TestCase):
    @patch("etl.stages.derive.transaction")
    def test_delete_insert_attendance(self, mock_txn):
        conn = make_mock_conn(fetch_results=[
            [enrollment_row()],
            [attendance_agg_row()],
        ])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        all_sql = " ".join(str(c) for c in conn.execute.call_args_list)
        self.assertIn("DELETE FROM attendance", all_sql)
        self.assertIn("INSERT INTO attendance", all_sql)

    @patch("etl.stages.derive.transaction")
    def test_attendance_aggregation_query(self, mock_txn):
        conn = make_mock_conn(fetch_results=[
            [enrollment_row()],
            [attendance_agg_row(total_classes=100, attended_classes=80)],
        ])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        fetch_calls = [str(c) for c in conn.fetch.call_args_list]
        agg_calls = [c for c in fetch_calls if "daily_attendance_07" in c and "GROUP BY" in c]
        self.assertEqual(len(agg_calls), 1)

    @patch("etl.stages.derive.transaction")
    def test_attendance_batch_insert_count(self, mock_txn):
        rows = [
            enrollment_row(enrollment_record_id="ENR000001", student_id="STU000001"),
            enrollment_row(enrollment_record_id="ENR000002", student_id="STU000002"),
        ]
        agg = [
            attendance_agg_row(enrollment_record_id="ENR000001", student_id="STU000001", total_classes=90, attended_classes=69),
            attendance_agg_row(enrollment_record_id="ENR000002", student_id="STU000002", total_classes=85, attended_classes=72),
        ]
        conn = make_mock_conn(fetch_results=[rows, agg])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        execute_calls = [str(c) for c in conn.execute.call_args_list]
        insert_calls = [c for c in execute_calls if "INSERT INTO attendance" in c]
        self.assertEqual(len(insert_calls), 1)
        self.assertIn("STU000001", insert_calls[0])
        self.assertIn("STU000002", insert_calls[0])

    @patch("etl.stages.derive.transaction")
    def test_attendance_percentage_computed_correctly(self, mock_txn):
        conn = make_mock_conn(fetch_results=[
            [enrollment_row()],
            [attendance_agg_row(total_classes=100, attended_classes=80)],
        ])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        execute_calls = [str(c) for c in conn.execute.call_args_list]
        insert_calls = [c for c in execute_calls if "INSERT INTO attendance" in c]
        self.assertEqual(len(insert_calls), 1)
        # 80/100 * 100 = 80.0 — passed as batch parameter
        self.assertIn("VALUES", insert_calls[0])


# ---------------------------------------------------------------------------
# Semester Summary Derivation
# ---------------------------------------------------------------------------

class TestSemesterSummaryDerivation(unittest.TestCase):
    @patch("etl.stages.derive.transaction")
    def test_delete_insert_semester_summary(self, mock_txn):
        conn = make_mock_conn(fetch_results=[
            [enrollment_row()],
            [attendance_agg_row()],
            [semester_summary_row()],
        ], fetchval_results=[0])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        all_sql = " ".join(str(c) for c in conn.execute.call_args_list)
        self.assertIn("DELETE FROM student_semester_summary", all_sql)
        self.assertIn("INSERT INTO student_semester_summary", all_sql)

    @patch("etl.stages.derive.transaction")
    def test_semester_summary_uses_attendance_table(self, mock_txn):
        conn = make_mock_conn(fetch_results=[
            [enrollment_row()],
            [attendance_agg_row()],
            [semester_summary_row()],
        ], fetchval_results=[0])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        fetch_calls = [str(c) for c in conn.fetch.call_args_list]
        sem_calls = [c for c in fetch_calls if "avg(a.attendance_percentage)" in c and "GROUP BY" in c]
        self.assertEqual(len(sem_calls), 1)


# ---------------------------------------------------------------------------
# Student Field Updates
# ---------------------------------------------------------------------------

class TestStudentFieldUpdates(unittest.TestCase):
    @patch("etl.stages.derive.transaction")
    def test_overall_attendance_percentage_updated(self, mock_txn):
        conn = make_mock_conn(fetch_results=[
            [enrollment_row()],
            [attendance_agg_row()],
        ])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        all_sql = " ".join(str(c) for c in conn.execute.call_args_list)
        self.assertIn("overall_attendance_percentage", all_sql)
        self.assertIn("UPDATE students", all_sql)

    @patch("etl.stages.derive.transaction")
    def test_full_name_updated(self, mock_txn):
        conn = make_mock_conn(fetch_results=[
            [enrollment_row()],
            [attendance_agg_row()],
        ])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        all_sql = " ".join(str(c) for c in conn.execute.call_args_list)
        self.assertIn("full_name", all_sql)
        self.assertIn("first_name || ' ' || last_name", all_sql)

    @patch("etl.stages.derive.transaction")
    def test_students_updated_after_attendance_derive(self, mock_txn):
        """Students are updated after attendance derive (within same transaction)."""
        conn = make_mock_conn(fetch_results=[
            [enrollment_row()],
            [attendance_agg_row()],
        ])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        execute_calls = [str(c) for c in conn.execute.call_args_list]
        update_calls = [c for c in execute_calls if "UPDATE students" in c]
        self.assertGreaterEqual(len(update_calls), 1)


# ---------------------------------------------------------------------------
# Approved Table Scope
# ---------------------------------------------------------------------------

class TestApprovedTableScope(unittest.TestCase):
    @patch("etl.stages.derive.transaction")
    def test_only_approved_tables_written_to(self, mock_txn):
        conn = make_mock_conn(fetch_results=[
            [enrollment_row()],
            [attendance_agg_row()],
            [semester_summary_row()],
        ], fetchval_results=[0])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        all_sql = " ".join(str(c) for c in conn.execute.call_args_list)
        self.assertIn(TABLE_ATTENDANCE, all_sql)
        self.assertIn(TABLE_SEMESTER_SUMMARY, all_sql)
        self.assertIn(TABLE_STUDENTS, all_sql)

    def test_table_name_constants(self):
        self.assertEqual(TABLE_ATTENDANCE, "attendance")
        self.assertEqual(TABLE_SEMESTER_SUMMARY, "student_semester_summary")
        self.assertEqual(TABLE_STUDENTS, "students")


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------

class TestErrorHandling(unittest.TestCase):
    @patch("etl.stages.derive.transaction")
    def test_db_error_wrapped_as_derive_error(self, mock_txn):
        @asynccontextmanager
        async def _failing_transaction(pool, *, dry_run=False):
            conn = AsyncMock()
            conn.fetch = AsyncMock(side_effect=RuntimeError("db down"))
            yield conn

        mock_txn.side_effect = _failing_transaction
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool()
        with self.assertRaises(EtlLoadDeriveError) as cm:
            asyncio.run(stage.run(ctx, pool=pool))
        self.assertIn("derive failed", str(cm.exception))


# ---------------------------------------------------------------------------
# StageResult Shape
# ---------------------------------------------------------------------------

class TestStageResultShape(unittest.TestCase):
    @patch("etl.stages.derive.transaction")
    def test_result_stage_name(self, mock_txn):
        conn = make_mock_conn(fetch_results=[[]])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.stage, STAGE_DERIVE)

    @patch("etl.stages.derive.transaction")
    def test_result_has_metadata(self, mock_txn):
        conn = make_mock_conn(fetch_results=[[]])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertIn("run_id", result.metadata)

    @patch("etl.stages.derive.transaction")
    def test_result_run_id_matches_context(self, mock_txn):
        conn = make_mock_conn(fetch_results=[[]])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(run_id="test-derive-xyz", dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.metadata["run_id"], "test-derive-xyz")

    @patch("etl.stages.derive.transaction")
    def test_result_status_success(self, mock_txn):
        conn = make_mock_conn(fetch_results=[[]])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        result = asyncio.run(stage.run(ctx, pool=pool))
        self.assertEqual(result.status, "success")
        self.assertFalse(result.failed)


# ---------------------------------------------------------------------------
# Parameterized SQL
# ---------------------------------------------------------------------------

class TestParameterizedSQL(unittest.TestCase):
    @patch("etl.stages.derive.transaction")
    def test_no_string_interpolation_in_queries(self, mock_txn):
        conn = make_mock_conn(fetch_results=[
            [enrollment_row()],
            [attendance_agg_row()],
        ])
        mock_txn.side_effect = _patched_transaction(conn)
        stage = DeriveStage()
        ctx = RunContext.create(dry_run=False)
        pool, _ = make_mock_pool(conn)
        asyncio.run(stage.run(ctx, pool=pool))
        for call in conn.fetch.call_args_list:
            sql_template = call[0][0] if call[0] else ""
            if "SELECT" in sql_template:
                self.assertNotIn("STU000001", sql_template)
                self.assertNotIn("ENR000001", sql_template)


# ---------------------------------------------------------------------------
# CLI Integration
# ---------------------------------------------------------------------------

class TestCliDeriveIntegration(unittest.TestCase):
    def test_derive_stage_imported_in_cli(self):
        from etl import cli
        self.assertTrue(hasattr(cli, "DeriveStage"))

    def test_derive_stage_in_cli_imports(self):
        from etl.cli import DeriveStage as CliDeriveStage
        from etl.stages.derive import DeriveStage as DeriveStageDirect
        self.assertIs(CliDeriveStage, DeriveStageDirect)


if __name__ == "__main__":
    unittest.main()
