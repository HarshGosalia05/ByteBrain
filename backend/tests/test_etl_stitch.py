"""Unit tests for the ETL Stitch slice.

Covers: canonical identity resolution (student, subject, faculty, enrollment),
quarantine for unresolvable records, no silent drops, input mutation prevention,
lineage preservation, database write prevention, empty input handling, and
pipeline integration. Uses mocks for database reads.
"""

import asyncio
import unittest
from unittest import mock

from etl import EtlRunner, RunContext, StageResult, ValidationOutcome
from etl.stages import STAGE_STITCH
from etl.stages.extract import ExtractStage
from etl.stages.stage import StageStage, StagedRecord
from etl.stages.stitch import (
    REASON_ENROLLMENT_NOT_FOUND,
    REASON_FACULTY_NOT_FOUND,
    REASON_STUDENT_NOT_FOUND,
    REASON_SUBJECT_NOT_FOUND,
    ResolvedIdentities,
    StitchStage,
    StitchedRecord,
)
from etl.stages.validate import ValidateStage
from etl.validation import QuarantineRecord


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


def make_master_records(students=None, subjects=None, faculty=None, enrollments=None):
    students = students or ["STU000001", "STU000002", "STU000003"]
    subjects = subjects or ["SUB0050", "SUB0051", "SUB0052"]
    faculty = faculty or ["FAC005", "FAC006", "FAC007"]
    enrollments = enrollments or [
        {"enrollment_record_id": "ENR000001", "student_id": "STU000001",
         "subject_id": "SUB0050", "semester_no": "7"},
        {"enrollment_record_id": "ENR000002", "student_id": "STU000002",
         "subject_id": "SUB0050", "semester_no": "7"},
        {"enrollment_record_id": "ENR000003", "student_id": "STU000001",
         "subject_id": "SUB0051", "semester_no": "7"},
    ]
    return students, subjects, faculty, enrollments


def build_mock_pool(master_data=None):
    """Build a mock asyncpg pool that returns master data for stitch queries."""
    if master_data is None:
        master_data = make_master_records()

    students, subjects, faculty_list, enrollments = master_data

    pool = mock.MagicMock()
    pool.close = mock.AsyncMock()
    conn = mock.AsyncMock()
    pool.acquire.return_value.__aenter__ = mock.AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = mock.AsyncMock(return_value=False)

    student_records = [{"student_id": s} for s in students]
    subject_records = [{"subject_id": s} for s in subjects]
    faculty_records = [{"faculty_id": f} for f in faculty_list]
    enrollment_records = [dict(e) for e in enrollments]

    async def fetch_side_effect(query):
        if "FROM students" in query:
            return student_records
        elif "FROM subjects" in query:
            return subject_records
        elif "FROM faculty" in query:
            return faculty_records
        elif "FROM student_subject_enrollment" in query:
            return enrollment_records
        return []

    conn.fetch = mock.AsyncMock(side_effect=fetch_side_effect)
    return pool


class TestResolvedIdentities(unittest.TestCase):
    def test_resolved_identities_fields(self):
        r = ResolvedIdentities(student=True, subject=True, faculty=True, enrollment=True)
        self.assertTrue(r.all_resolved)
        self.assertEqual(r.to_dict(), {
            "student": True, "subject": True, "faculty": True, "enrollment": True,
        })

    def test_resolved_identities_partial(self):
        r = ResolvedIdentities(student=True, subject=True, faculty=False, enrollment=False)
        self.assertFalse(r.all_resolved)

    def test_resolved_identities_none_resolved(self):
        r = ResolvedIdentities()
        self.assertFalse(r.all_resolved)
        self.assertFalse(r.student)
        self.assertFalse(r.enrollment)


class TestStitchedRecord(unittest.TestCase):
    def test_stitched_record_fields(self):
        row = attendance_row()
        record = StitchedRecord(
            source="daily_attendance", run_id="run-123", row_index=1,
            row=row, enrollment_record_id="ENR000001",
            resolved=ResolvedIdentities(student=True, subject=True,
                                        faculty=True, enrollment=True),
        )
        self.assertEqual(record.source, "daily_attendance")
        self.assertEqual(record.run_id, "run-123")
        self.assertEqual(record.row_index, 1)
        self.assertEqual(record.row, row)
        self.assertEqual(record.enrollment_record_id, "ENR000001")
        self.assertTrue(record.resolved.all_resolved)

    def test_stitched_record_is_frozen(self):
        record = StitchedRecord(source="daily_attendance", run_id="run-123",
                                row_index=1, row=attendance_row())
        with self.assertRaises(AttributeError):
            record.source = "changed"

    def test_stitched_record_to_dict(self):
        row = attendance_row()
        record = StitchedRecord(
            source="daily_attendance", run_id="run-123", row_index=1,
            row=row, enrollment_record_id="ENR000001",
        )
        d = record.to_dict()
        self.assertEqual(d["source"], "daily_attendance")
        self.assertEqual(d["enrollment_record_id"], "ENR000001")
        self.assertEqual(d["row"], row)


class TestStitchStage(unittest.TestCase):
    def test_stitch_name(self):
        stage = StitchStage()
        self.assertEqual(stage.name, STAGE_STITCH)

    def test_stitch_valid_attendance_resolves(self):
        row = attendance_row()
        staged = {"daily_attendance": [
            StagedRecord(source="daily_attendance", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        result = asyncio.run(stage.run(context, pool=pool))
        self.assertEqual(result.rows_read, 1)
        self.assertEqual(result.rows_accepted, 1)
        self.assertEqual(result.rows_rejected, 0)
        stitched = shared["stitched"]["daily_attendance"]
        self.assertEqual(len(stitched), 1)
        self.assertEqual(stitched[0].enrollment_record_id, "ENR000001")
        self.assertTrue(stitched[0].resolved.all_resolved)

    def test_stitch_valid_subject_resolves(self):
        row = attendance_row(subject_id="SUB0051")
        staged = {"daily_attendance": [
            StagedRecord(source="daily_attendance", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        result = asyncio.run(stage.run(context, pool=pool))
        self.assertEqual(result.rows_accepted, 1)
        stitched = shared["stitched"]["daily_attendance"]
        self.assertEqual(stitched[0].enrollment_record_id, "ENR000003")

    def test_stitch_valid_faculty_resolves(self):
        row = attendance_row(faculty_id="FAC006")
        staged = {"daily_attendance": [
            StagedRecord(source="daily_attendance", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        result = asyncio.run(stage.run(context, pool=pool))
        self.assertEqual(result.rows_accepted, 1)
        stitched = shared["stitched"]["daily_attendance"]
        self.assertTrue(stitched[0].resolved.faculty)

    def test_stitch_valid_enrollment_resolves(self):
        row = attendance_row()
        staged = {"daily_attendance": [
            StagedRecord(source="daily_attendance", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        result = asyncio.run(stage.run(context, pool=pool))
        self.assertEqual(result.rows_accepted, 1)
        stitched = shared["stitched"]["daily_attendance"]
        self.assertEqual(stitched[0].enrollment_record_id, "ENR000001")
        self.assertTrue(stitched[0].resolved.enrollment)

    def test_stitch_valid_timetable_resolves(self):
        row = timetable_row()
        staged = {"weekly_timetable": [
            StagedRecord(source="weekly_timetable", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        result = asyncio.run(stage.run(context, pool=pool))
        self.assertEqual(result.rows_accepted, 1)
        self.assertEqual(result.rows_rejected, 0)
        stitched = shared["stitched"]["weekly_timetable"]
        self.assertEqual(len(stitched), 1)
        self.assertTrue(stitched[0].resolved.subject)
        self.assertTrue(stitched[0].resolved.faculty)
        self.assertFalse(stitched[0].resolved.student)
        self.assertFalse(stitched[0].resolved.enrollment)

    def test_stitch_missing_student_quarantined(self):
        row = attendance_row(student_id="STU999999")
        staged = {"daily_attendance": [
            StagedRecord(source="daily_attendance", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        result = asyncio.run(stage.run(context, pool=pool))
        self.assertEqual(result.rows_accepted, 0)
        self.assertEqual(result.rows_rejected, 1)
        quarantine = shared["stitch_quarantine"]["daily_attendance"]
        self.assertEqual(len(quarantine), 1)
        self.assertEqual(quarantine[0].reason_code, REASON_STUDENT_NOT_FOUND)

    def test_stitch_missing_subject_quarantined(self):
        row = attendance_row(subject_id="SUB9999")
        staged = {"daily_attendance": [
            StagedRecord(source="daily_attendance", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        result = asyncio.run(stage.run(context, pool=pool))
        self.assertEqual(result.rows_rejected, 1)
        quarantine = shared["stitch_quarantine"]["daily_attendance"]
        self.assertEqual(quarantine[0].reason_code, REASON_SUBJECT_NOT_FOUND)

    def test_stitch_missing_faculty_quarantined(self):
        row = attendance_row(faculty_id="FAC999")
        staged = {"daily_attendance": [
            StagedRecord(source="daily_attendance", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        result = asyncio.run(stage.run(context, pool=pool))
        self.assertEqual(result.rows_rejected, 1)
        quarantine = shared["stitch_quarantine"]["daily_attendance"]
        self.assertEqual(quarantine[0].reason_code, REASON_FACULTY_NOT_FOUND)

    def test_stitch_missing_enrollment_quarantined(self):
        row = attendance_row(subject_id="SUB0052")
        staged = {"daily_attendance": [
            StagedRecord(source="daily_attendance", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        result = asyncio.run(stage.run(context, pool=pool))
        self.assertEqual(result.rows_rejected, 1)
        quarantine = shared["stitch_quarantine"]["daily_attendance"]
        self.assertEqual(quarantine[0].reason_code, REASON_ENROLLMENT_NOT_FOUND)

    def test_stitch_no_records_silently_dropped(self):
        row = attendance_row()
        staged = {"daily_attendance": [
            StagedRecord(source="daily_attendance", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        result = asyncio.run(stage.run(context, pool=pool))
        total = result.rows_accepted + result.rows_rejected
        self.assertEqual(total, result.rows_read)

    def test_stitch_does_not_mutate_input(self):
        row = attendance_row()
        original = dict(row)
        staged = {"daily_attendance": [
            StagedRecord(source="daily_attendance", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        asyncio.run(stage.run(context, pool=pool))
        self.assertEqual(row, original)

    def test_stitch_preserves_run_id(self):
        row = attendance_row()
        staged = {"daily_attendance": [
            StagedRecord(source="daily_attendance", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        asyncio.run(stage.run(context, pool=pool))
        stitched = shared["stitched"]["daily_attendance"]
        self.assertEqual(stitched[0].run_id, context.run_id)

    def test_stitch_performs_no_database_writes(self):
        row = attendance_row()
        staged = {"daily_attendance": [
            StagedRecord(source="daily_attendance", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        asyncio.run(stage.run(context, pool=pool))
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.execute.assert_not_called()
        conn.fetchrow.assert_not_called()
        conn.fetchval.assert_not_called()

    def test_stitch_empty_input(self):
        shared = {"staged": {}}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(context))
        self.assertEqual(result.rows_read, 0)
        self.assertEqual(result.rows_accepted, 0)
        self.assertEqual(result.rows_rejected, 0)
        self.assertNotIn("stitched", shared)

    def test_stitch_missing_staged_key(self):
        shared = {}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        result = asyncio.run(stage.run(context))
        self.assertEqual(result.rows_read, 0)
        self.assertEqual(result.rows_accepted, 0)

    def test_stitch_multiple_sources(self):
        att_row = attendance_row()
        tt_row = timetable_row()
        staged = {
            "daily_attendance": [
                StagedRecord(source="daily_attendance", run_id="test-run",
                             row_index=1, row=att_row),
            ],
            "weekly_timetable": [
                StagedRecord(source="weekly_timetable", run_id="test-run",
                             row_index=1, row=tt_row),
            ],
        }
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        result = asyncio.run(stage.run(context, pool=pool))
        self.assertEqual(result.rows_read, 2)
        self.assertEqual(result.rows_accepted, 2)
        self.assertEqual(result.rows_rejected, 0)
        self.assertIn("daily_attendance", shared["stitched"])
        self.assertIn("weekly_timetable", shared["stitched"])

    def test_stitch_result_metadata(self):
        row = attendance_row()
        staged = {"daily_attendance": [
            StagedRecord(source="daily_attendance", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        pool = build_mock_pool()
        result = asyncio.run(stage.run(context, pool=pool))
        self.assertEqual(result.metadata["run_id"], context.run_id)
        self.assertIn("daily_attendance", result.metadata["source_keys"])
        self.assertEqual(result.metadata["stitched_counts"]["daily_attendance"], 1)
        self.assertEqual(result.metadata["quarantine_counts"]["daily_attendance"], 0)

    def test_stitch_no_pool_quarantines_all(self):
        row = attendance_row()
        staged = {"daily_attendance": [
            StagedRecord(source="daily_attendance", run_id="test-run",
                         row_index=1, row=row),
        ]}
        shared = {"staged": staged}
        stage = StitchStage(shared=shared)
        context = RunContext.create(dry_run=True)
        context.counters["semester_no"] = "7"
        result = asyncio.run(stage.run(context, pool=None))
        self.assertEqual(result.rows_read, 1)
        self.assertEqual(result.rows_rejected, 1)
        quarantine = shared["stitch_quarantine"]["daily_attendance"]
        self.assertEqual(quarantine[0].reason_code, REASON_STUDENT_NOT_FOUND)


class TestStitchIntegration(unittest.TestCase):
    def test_extract_validate_stage_stitch_pipeline(self):
        shared = {}
        sources = ("daily_attendance", "weekly_timetable")

        students = [f"STU{i:06d}" for i in range(1, 51)]
        subjects = [f"SUB{i:04d}" for i in range(50, 57)]
        faculty_list = [f"FAC{i:03d}" for i in range(5, 12)]
        enrollments = []
        for s in students:
            for sub in subjects:
                enrollments.append({
                    "enrollment_record_id": f"ENR{len(enrollments)+1:06d}",
                    "student_id": s, "subject_id": sub, "semester_no": "7",
                })

        pool = build_mock_pool(
            master_data=(students, subjects, faculty_list, enrollments)
        )

        runner = EtlRunner()
        runner.register(ExtractStage(sources=sources, shared=shared))
        runner.register(ValidateStage(sources=sources, shared=shared))
        runner.register(StageStage(sources=sources, shared=shared))
        stitch_stage = StitchStage(sources=sources, shared=shared)
        runner.register(stitch_stage)

        with mock.patch("etl.runner.etl_db.create_pool", new_callable=mock.AsyncMock, return_value=pool):
            summary = asyncio.run(
                runner.run(sources=sources, dry_run=False)
            )

        self.assertEqual(summary.exit_code, 0)
        self.assertEqual(len(summary.stages), 4)
        self.assertEqual(summary.stages[0].stage, "extract")
        self.assertEqual(summary.stages[1].stage, "validate")
        self.assertEqual(summary.stages[2].stage, "stage")
        self.assertEqual(summary.stages[3].stage, "stitch")
        self.assertIn("stitched", shared)
        self.assertIn("daily_attendance", shared["stitched"])
        self.assertIn("weekly_timetable", shared["stitched"])
        att_count = len(shared["stitched"]["daily_attendance"])
        tt_count = len(shared["stitched"]["weekly_timetable"])
        self.assertEqual(att_count, 6150)
        self.assertEqual(tt_count, 15)
        for record in shared["stitched"]["daily_attendance"]:
            self.assertIsInstance(record, StitchedRecord)
            self.assertTrue(record.resolved.all_resolved)
        for record in shared["stitched"]["weekly_timetable"]:
            self.assertIsInstance(record, StitchedRecord)
            self.assertTrue(record.resolved.subject)
            self.assertTrue(record.resolved.faculty)


if __name__ == "__main__":
    unittest.main()
