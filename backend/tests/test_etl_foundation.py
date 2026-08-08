"""Unit tests for the ETL foundation (Phase 1).

Uses the standard library ``unittest``/``asyncio`` — no production credentials
or live database are required. All database interactions are mocked; dry runs
must never open a pool.
"""

import asyncio
import io
import unittest
from unittest import mock

from etl import EtlDryRunError, EtlRunner, RunContext, StageResult
from etl.context import _new_run_id
from etl.exceptions import (
    EXIT_LOAD_DERIVE_FAILURE,
    EXIT_SUCCESS,
    EtlStageError,
    to_exit_code,
)
from etl.keys import (
    ATTENDANCE_ROW_KEY_FIELDS,
    LECTURE_SESSION_KEY_FIELDS,
    business_key,
    business_key_str,
    dedupe_by_key,
)
from etl.logging import EtlLogger
from etl.stages import Stage


class FakeStage(Stage):
    """Test stage that records execution and can be configured to pass/fail."""

    def __init__(self, name, *, result=None, error=None, record=None, check_pool=None):
        self.name = name
        self.description = f"fake stage {name}"
        self._result = result
        self._error = error
        self._record = record if record is not None else []
        self._check_pool = check_pool

    async def run(self, context, pool=None):
        self._record.append(self.name)
        if self._check_pool is not None:
            self._check_pool(context, pool)
        if self._error is not None:
            raise self._error
        if self._result is not None:
            return self._result
        return StageResult(stage=self.name)


class CapturingLoggerFactory:
    """Builds EtlLoggers that write into an in-memory buffer per run."""

    def __init__(self):
        self.buffers = {}

    def __call__(self, run_id, log_level="INFO"):
        buffer = io.StringIO()
        self.buffers[run_id] = buffer
        return EtlLogger(run_id, log_level, stream=buffer)


class TestRunContext(unittest.TestCase):
    def test_create_sets_fields(self):
        ctx = RunContext.create(dry_run=True, sources=("a", "b"))
        self.assertTrue(ctx.dry_run)
        self.assertEqual(ctx.sources, ("a", "b"))
        self.assertEqual(ctx.current_stage, None)
        self.assertIsNotNone(ctx.started_at)
        self.assertTrue(ctx.run_id)

    def test_run_id_unique(self):
        first = RunContext.create()
        second = RunContext.create()
        self.assertNotEqual(first.run_id, second.run_id)

    def test_run_id_generator_is_unique(self):
        self.assertNotEqual(_new_run_id(), _new_run_id())

    def test_assert_writable_raises_in_dry_run(self):
        ctx = RunContext.create(dry_run=True)
        with self.assertRaises(EtlDryRunError):
            ctx.assert_writable()

    def test_assert_writable_allows_apply(self):
        ctx = RunContext.create(dry_run=False)
        ctx.assert_writable()


class TestBusinessKeys(unittest.TestCase):
    def test_locked_key_fields(self):
        self.assertEqual(
            LECTURE_SESSION_KEY_FIELDS,
            ("subject_id", "lecture_date", "lecture_number"),
        )
        self.assertEqual(
            ATTENDANCE_ROW_KEY_FIELDS,
            ("student_id", "subject_id", "lecture_date", "lecture_number"),
        )
        # The session key must NOT be conflated with the individual row key.
        self.assertNotEqual(LECTURE_SESSION_KEY_FIELDS, ATTENDANCE_ROW_KEY_FIELDS)
        self.assertEqual(
            set(LECTURE_SESSION_KEY_FIELDS),
            set(ATTENDANCE_ROW_KEY_FIELDS) - {"student_id"},
        )

    def test_business_key_deterministic(self):
        row = {"student_id": "STU000001", "subject_id": "SUB0050",
               "lecture_date": "2026-06-22", "lecture_number": 1}
        self.assertEqual(
            business_key(row, ATTENDANCE_ROW_KEY_FIELDS),
            business_key(row, ATTENDANCE_ROW_KEY_FIELDS),
        )
        self.assertEqual(
            business_key_str(row, ATTENDANCE_ROW_KEY_FIELDS),
            business_key_str(row, ATTENDANCE_ROW_KEY_FIELDS),
        )

    def test_business_key_missing_field_raises(self):
        row = {"student_id": "STU000001", "subject_id": "SUB0050",
               "lecture_date": "2026-06-22"}
        with self.assertRaises(ValueError):
            business_key(row, ATTENDANCE_ROW_KEY_FIELDS)

    def test_business_key_not_confused_with_run_metadata(self):
        row = {"student_id": "STU000001", "subject_id": "SUB0050",
               "lecture_date": "2026-06-22", "lecture_number": 3}
        run_metadata_a = {"run_id": RunContext.create().run_id, "timestamp": "x"}
        run_metadata_b = {"run_id": RunContext.create().run_id, "timestamp": "y"}
        # Different run metadata must never change the business key.
        key_a = business_key({**row, **run_metadata_a}, ATTENDANCE_ROW_KEY_FIELDS)
        key_b = business_key({**row, **run_metadata_b}, ATTENDANCE_ROW_KEY_FIELDS)
        self.assertEqual(key_a, key_b)

    def test_dedupe_by_key(self):
        base = {"subject_id": "SUB0050", "lecture_date": "2026-06-22"}
        rows = [
            {**base, "lecture_number": 1, "id": 1},
            {**base, "lecture_number": 1, "id": 2},
            {**base, "lecture_number": 2, "id": 3},
        ]
        unique, duplicates = dedupe_by_key(rows, LECTURE_SESSION_KEY_FIELDS)
        self.assertEqual(len(unique), 2)
        self.assertEqual([r["id"] for r in unique], [1, 3])
        self.assertEqual([r["id"] for r in duplicates], [2])


class TestStageResult(unittest.TestCase):
    def test_success_defaults(self):
        result = StageResult(stage="extract")
        self.assertFalse(result.failed)
        self.assertEqual(result.rows_read, 0)

    def test_add_error_marks_failed(self):
        result = StageResult(stage="validate")
        result.add_error("bad row")
        self.assertTrue(result.failed)

    def test_failure_factory(self):
        error = EtlStageError("boom")
        result = StageResult.failure("load", error)
        self.assertTrue(result.failed)
        self.assertIn("boom", result.errors[0])

    def test_to_dict_roundtrip(self):
        result = StageResult(stage="extract", rows_read=5, rows_accepted=4,
                             rows_rejected=1, metadata={"src": "csv"})
        data = result.to_dict()
        self.assertEqual(data["stage"], "extract")
        self.assertEqual(data["rows_read"], 5)
        self.assertEqual(data["metadata"], {"src": "csv"})


class TestRunner(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.logger_factory = CapturingLoggerFactory()

    def make_runner(self, stages):
        return EtlRunner(logger_factory=self.logger_factory).register_many(stages)

    async def test_stage_execution_order(self):
        order = []
        runner = self.make_runner(
            [FakeStage("a", record=order), FakeStage("b", record=order), FakeStage("c", record=order)]
        )
        summary = await runner.run(dry_run=True)
        self.assertEqual(order, ["a", "b", "c"])
        self.assertEqual([s.stage for s in summary.stages], ["a", "b", "c"])
        self.assertEqual(summary.exit_code, EXIT_SUCCESS)
        self.assertEqual(runner.stages, ("a", "b", "c"))

    async def test_successful_stage_result(self):
        result = StageResult(stage="extract", rows_read=10, rows_accepted=9, rows_rejected=1)
        runner = self.make_runner([FakeStage("extract", result=result)])
        summary = await runner.run(dry_run=True)
        self.assertTrue(summary.success)
        self.assertEqual(summary.stages[0].rows_read, 10)
        self.assertEqual(summary.stages[0].rows_accepted, 9)
        self.assertEqual(summary.stages[0].rows_rejected, 1)

    async def test_failed_stage_result_propagates(self):
        failed = StageResult(stage="validate", status="failed", errors=["quarantine exceeded"])
        order = []
        runner = self.make_runner(
            [FakeStage("validate", result=failed, record=order), FakeStage("load", record=order)]
        )
        summary = await runner.run(dry_run=True)
        self.assertFalse(summary.success)
        self.assertNotEqual(summary.exit_code, EXIT_SUCCESS)
        # Pipeline stops at the first failure; 'load' never runs.
        self.assertEqual(order, ["validate"])
        self.assertEqual([s.stage for s in summary.stages], ["validate"])

    async def test_stage_exception_propagates(self):
        order = []
        error = EtlStageError("load failed")
        runner = self.make_runner(
            [FakeStage("load", error=error, record=order), FakeStage("derive", record=order)]
        )
        summary = await runner.run(dry_run=True)
        self.assertFalse(summary.success)
        self.assertEqual(summary.exit_code, to_exit_code(error))
        self.assertEqual(order, ["load"])
        self.assertIn("STAGE_FAILED", self.logger_factory.buffers[summary.run_id].getvalue())
        self.assertIn("RUN_FAILED", self.logger_factory.buffers[summary.run_id].getvalue())

    async def test_stage_failure_stops_remaining_stages(self):
        order = []
        runner = self.make_runner(
            [
                FakeStage("a", record=order),
                FakeStage("b", error=EtlStageError("boom"), record=order),
                FakeStage("c", record=order),
            ]
        )
        summary = await runner.run(dry_run=True)
        self.assertEqual(order, ["a", "b"])

    async def test_dry_run_passes_no_pool(self):
        seen = []
        runner = self.make_runner([FakeStage("extract", check_pool=lambda ctx, p: seen.append(p))])
        summary = await runner.run(dry_run=True)
        self.assertTrue(summary.dry_run)
        self.assertEqual(seen, [None])

    async def test_dry_run_never_creates_pool(self):
        with mock.patch("etl.runner.etl_db.create_pool", side_effect=AssertionError("pool created in dry run")) as create:
            runner = self.make_runner([FakeStage("extract")])
            summary = await runner.run(dry_run=True)
            create.assert_not_called()
            self.assertTrue(summary.success)

    async def test_apply_creates_pool(self):
        fake_pool = mock.MagicMock()
        fake_pool.close = mock.AsyncMock()
        seen = []
        with mock.patch("etl.runner.etl_db.create_pool", return_value=fake_pool) as create:
            runner = self.make_runner([FakeStage("load", check_pool=lambda ctx, p: seen.append(p))])
            summary = await runner.run(dry_run=False)
            create.assert_called_once()
            self.assertIs(seen[0], fake_pool)
            fake_pool.close.assert_awaited_once()

    async def test_run_id_flows_to_stages_and_logs(self):
        captured = {}
        def check(context, pool=None):
            captured["run_id"] = context.run_id
        runner = self.make_runner([FakeStage("a", check_pool=check)])
        summary = await runner.run(dry_run=True)
        self.assertEqual(captured["run_id"], summary.run_id)
        log = self.logger_factory.buffers[summary.run_id].getvalue()
        self.assertIn("RUN_STARTED", log)
        self.assertIn("RUN_COMPLETED", log)
        self.assertIn(summary.run_id, log)

    async def test_explicit_run_id_and_versions(self):
        runner = self.make_runner([FakeStage("a")])
        summary = await runner.run(
            dry_run=True,
            run_id="my-run-1",
            pipeline_version="9.9.9",
            environment="test",
            sources=("daily_attendance",),
        )
        self.assertEqual(summary.run_id, "my-run-1")
        self.assertEqual(summary.pipeline_version, "9.9.9")
        self.assertEqual(summary.environment, "test")

    async def test_business_result_stable_across_runs(self):
        row = {"student_id": "STU000001", "subject_id": "SUB0050",
               "lecture_date": "2026-06-22", "lecture_number": 7}
        keys = []

        def record_key(context, pool=None):
            keys.append((context.run_id, business_key(row, ATTENDANCE_ROW_KEY_FIELDS)))

        runner = self.make_runner([FakeStage("a", check_pool=record_key)])
        first = await runner.run(dry_run=True)
        second = await runner.run(dry_run=True)
        self.assertNotEqual(first.run_id, second.run_id)
        self.assertEqual(keys[0][1], keys[1][1])

    async def test_duplicate_stage_registration_rejected(self):
        runner = self.make_runner([FakeStage("a")])
        with self.assertRaises(ValueError):
            runner.register(FakeStage("a"))

    async def test_unexpected_exception_is_wrapped(self):
        class Boom(RuntimeError):
            pass
        runner = self.make_runner([FakeStage("a", error=Boom("kaboom"))])
        summary = await runner.run(dry_run=True)
        self.assertEqual(summary.exit_code, 5)
        self.assertIn("failed unexpectedly", summary.stages[0].errors[0])


class TestDryRunGuard(unittest.IsolatedAsyncioTestCase):
    async def test_stage_writing_in_dry_run_fails_loud(self):
        class WritingStage(Stage):
            name = "load"

            async def run(self, context, pool=None):
                context.assert_writable()
                return StageResult(stage=self.name)

        runner = EtlRunner().register(WritingStage())
        summary = await runner.run(dry_run=True)
        self.assertFalse(summary.success)
        self.assertEqual(summary.exit_code, EXIT_LOAD_DERIVE_FAILURE)
        self.assertIn("not permitted in dry-run", summary.stages[0].errors[0])


if __name__ == "__main__":
    unittest.main()
