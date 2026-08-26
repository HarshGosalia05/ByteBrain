"""Unit tests for the ETL Stage slice.

Covers: in-memory staging of validated rows, run_id attachment, deterministic
ordering, preservation of input data, database write prevention, empty input
handling, and error reporting using existing ETL conventions.
"""

import asyncio
import unittest
from unittest import mock

from etl import EtlRunner, RunContext, StageResult, ValidationOutcome
from etl.stages import STAGE_STAGE
from etl.stages.extract import ExtractStage
from etl.stages.stage import StageStage, StagedRecord
from etl.stages.validate import ValidateStage


def attendance_row(**overrides):
    base = {
        "attendance_id": "1", "student_id": "STU000001", "enrollment_no": "2023010001",
        "subject_id": "SUB0050", "subject_name": "Software Engineering",
        "faculty_id": "FAC005", "lecture_date": "2026-06-22", "lecture_number": "1",
        "day_name": "Monday", "department_code": "1", "semester_no": "7",
        "academic_year": "2026-2027", "attendance_status": "P",
    }
    base.update(overrides)
    return base


def timetable_row(**overrides):
    base = {
        "timttable_id": "1", "department_code": "1", "semester_no": "7",
        "academic_year": "2026-2027", "day_name": "Monday", "slot_no": "1",
        "start_time": "13:00:00", "end_time": "14:00:00", "subject_id": "SUB0050",
        "subject_name": "Software Engineering", "faculty_id": "FAC005",
        "lecture_type": "Theory",
    }
    base.update(overrides)
    return base


class TestStagedRecord(unittest.TestCase):
    def test_staged_record_fields(self):
        row = attendance_row()
        record = StagedRecord(source="daily_attendance", run_id="run-123",
                              row_index=1, row=row)
        self.assertEqual(record.source, "daily_attendance")
        self.assertEqual(record.run_id, "run-123")
        self.assertEqual(record.row_index, 1)
        self.assertEqual(record.row, row)

    def test_staged_record_is_frozen(self):
        row = attendance_row()
        record = StagedRecord(source="daily_attendance", run_id="run-123",
                              row_index=1, row=row)
        with self.assertRaises(AttributeError):
            record.source = "changed"


class TestStageStage(unittest.TestCase):
    def test_stage_name(self):
        stage = StageStage()
        self.assertEqual(stage.name, STAGE_STAGE)

    def test_stage_accepts_validated_input(self):
        outcome = ValidationOutcome(
            source="daily_attendance",
            accepted=[attendance_row()],
            quarantined=[],
        )
        shared = {"validated": {"daily_attendance": outcome}}
        stage = StageStage(shared=shared)
        context = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(context))
        self.assertEqual(result.rows_read, 1)
        self.assertEqual(result.rows_accepted, 1)
        self.assertEqual(result.rows_rejected, 0)

    def test_stage_preserves_row_count(self):
        rows = [attendance_row() for _ in range(10)]
        outcome = ValidationOutcome(
            source="daily_attendance",
            accepted=rows,
            quarantined=[],
        )
        shared = {"validated": {"daily_attendance": outcome}}
        stage = StageStage(shared=shared)
        context = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(context))
        self.assertEqual(result.rows_read, 10)
        self.assertEqual(result.rows_accepted, 10)
        staged = shared["staged"]["daily_attendance"]
        self.assertEqual(len(staged), 10)

    def test_stage_attaches_run_id(self):
        row = attendance_row()
        outcome = ValidationOutcome(
            source="daily_attendance",
            accepted=[row],
            quarantined=[],
        )
        shared = {"validated": {"daily_attendance": outcome}}
        stage = StageStage(shared=shared)
        context = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(context))
        staged = shared["staged"]["daily_attendance"]
        self.assertEqual(len(staged), 1)
        self.assertEqual(staged[0].run_id, context.run_id)

    def test_stage_preserves_row_data(self):
        row = attendance_row(student_id="STU000099", attendance_status="A")
        outcome = ValidationOutcome(
            source="daily_attendance",
            accepted=[row],
            quarantined=[],
        )
        shared = {"validated": {"daily_attendance": outcome}}
        stage = StageStage(shared=shared)
        context = RunContext.create(dry_run=True)
        asyncio.run(stage.run(context))
        staged = shared["staged"]["daily_attendance"]
        self.assertEqual(staged[0].row, row)
        self.assertEqual(staged[0].row["student_id"], "STU000099")
        self.assertEqual(staged[0].row["attendance_status"], "A")

    def test_stage_preserves_deterministic_ordering(self):
        rows = [attendance_row(student_id=f"STU{i:06d}") for i in range(1, 6)]
        outcome = ValidationOutcome(
            source="daily_attendance",
            accepted=rows,
            quarantined=[],
        )
        shared = {"validated": {"daily_attendance": outcome}}
        stage = StageStage(shared=shared)
        context = RunContext.create(dry_run=True)
        asyncio.run(stage.run(context))
        staged = shared["staged"]["daily_attendance"]
        for i, record in enumerate(staged):
            self.assertEqual(record.row_index, i + 1)
            self.assertEqual(record.row["student_id"], rows[i]["student_id"])

    def test_stage_does_not_modify_input(self):
        row = attendance_row()
        original = dict(row)
        outcome = ValidationOutcome(
            source="daily_attendance",
            accepted=[row],
            quarantined=[],
        )
        shared = {"validated": {"daily_attendance": outcome}}
        stage = StageStage(shared=shared)
        context = RunContext.create(dry_run=True)
        asyncio.run(stage.run(context))
        self.assertEqual(row, original)

    def test_stage_does_not_write_to_database(self):
        row = attendance_row()
        outcome = ValidationOutcome(
            source="daily_attendance",
            accepted=[row],
            quarantined=[],
        )
        shared = {"validated": {"daily_attendance": outcome}}
        stage = StageStage(shared=shared)
        context = RunContext.create(dry_run=True)
        pool = mock.MagicMock()
        result = asyncio.run(stage.run(context, pool=pool))
        pool.acquire.assert_not_called()
        pool.release.assert_not_called()

    def test_stage_empty_input(self):
        shared = {"validated": {}}
        stage = StageStage(shared=shared)
        context = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(context))
        self.assertEqual(result.rows_read, 0)
        self.assertEqual(result.rows_accepted, 0)
        self.assertEqual(result.rows_rejected, 0)
        self.assertNotIn("staged", shared)

    def test_stage_missing_validated_key(self):
        shared = {}
        stage = StageStage(shared=shared)
        context = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(context))
        self.assertEqual(result.rows_read, 0)
        self.assertEqual(result.rows_accepted, 0)

    def test_stage_multiple_sources(self):
        att_outcome = ValidationOutcome(
            source="daily_attendance",
            accepted=[attendance_row()],
            quarantined=[],
        )
        tt_outcome = ValidationOutcome(
            source="weekly_timetable",
            accepted=[timetable_row()],
            quarantined=[],
        )
        shared = {"validated": {
            "daily_attendance": att_outcome,
            "weekly_timetable": tt_outcome,
        }}
        stage = StageStage(shared=shared)
        context = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(context))
        self.assertEqual(result.rows_read, 2)
        self.assertEqual(result.rows_accepted, 2)
        self.assertIn("daily_attendance", shared["staged"])
        self.assertIn("weekly_timetable", shared["staged"])

    def test_stage_source_filter(self):
        att_outcome = ValidationOutcome(
            source="daily_attendance",
            accepted=[attendance_row()],
            quarantined=[],
        )
        tt_outcome = ValidationOutcome(
            source="weekly_timetable",
            accepted=[timetable_row()],
            quarantined=[],
        )
        shared = {"validated": {
            "daily_attendance": att_outcome,
            "weekly_timetable": tt_outcome,
        }}
        stage = StageStage(sources=("daily_attendance",), shared=shared)
        context = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(context))
        self.assertEqual(result.rows_read, 1)
        self.assertEqual(result.rows_accepted, 1)
        self.assertIn("daily_attendance", shared["staged"])
        self.assertNotIn("weekly_timetable", shared["staged"])

    def test_stage_result_metadata(self):
        outcome = ValidationOutcome(
            source="daily_attendance",
            accepted=[attendance_row()],
            quarantined=[],
        )
        shared = {"validated": {"daily_attendance": outcome}}
        stage = StageStage(shared=shared)
        context = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(context))
        self.assertEqual(result.metadata["run_id"], context.run_id)
        self.assertIn("daily_attendance", result.metadata["source_keys"])
        self.assertEqual(result.metadata["staged_counts"]["daily_attendance"], 1)

    def test_stage_quarantined_rows_not_included(self):
        from etl.validation import QuarantineRecord
        accepted = [attendance_row(), attendance_row(student_id="STU000002")]
        quarantined = [QuarantineRecord(
            run_id="test-run", stage="validate", source="daily_attendance",
            row_index=3, reason_code="test", reason="test quarantine",
            keys={}, offending_values={}, raw={},
        )]
        outcome = ValidationOutcome(
            source="daily_attendance",
            accepted=accepted,
            quarantined=quarantined,
        )
        shared = {"validated": {"daily_attendance": outcome}}
        stage = StageStage(shared=shared)
        context = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(context))
        self.assertEqual(result.rows_read, 3)
        self.assertEqual(result.rows_accepted, 2)
        staged = shared["staged"]["daily_attendance"]
        self.assertEqual(len(staged), 2)


class TestStageIntegration(unittest.TestCase):
    def test_extract_validate_stage_pipeline(self):
        shared = {}
        sources = ("daily_attendance", "weekly_timetable")
        runner = EtlRunner()
        runner.register(ExtractStage(sources=sources, shared=shared))
        runner.register(ValidateStage(sources=sources, shared=shared))
        runner.register(StageStage(sources=sources, shared=shared))
        summary = asyncio.run(
            runner.run(sources=sources, dry_run=True)
        )
        self.assertEqual(summary.exit_code, 0)
        self.assertEqual(len(summary.stages), 3)
        self.assertEqual(summary.stages[0].stage, "extract")
        self.assertEqual(summary.stages[1].stage, "validate")
        self.assertEqual(summary.stages[2].stage, "stage")
        self.assertIn("staged", shared)
        self.assertIn("daily_attendance", shared["staged"])
        self.assertIn("weekly_timetable", shared["staged"])
        att_count = len(shared["staged"]["daily_attendance"])
        tt_count = len(shared["staged"]["weekly_timetable"])
        self.assertEqual(att_count, 6150)
        self.assertEqual(tt_count, 15)


if __name__ == "__main__":
    unittest.main()
