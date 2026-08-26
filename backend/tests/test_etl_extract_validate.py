"""Unit tests for the ETL Extract + Validate slice.

Covers: extraction (success, missing/malformed/empty source, checksums, raw
preservation), the plan `03` §3.3 validation rules for both locked sources,
quarantine artifacts and the quarantine-ratio gate, determinism, dry-run/apply
DB safety, and pipeline stage registration/ordering. Uses the real dataset
files where they are the fixture and synthetic CSVs for failure cases.
"""

import asyncio
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from etl import (
    DATASET_SOURCES,
    EtlConfigurationError,
    EtlRunner,
    EtlSourceError,
    EtlValidationError,
    QuarantineRecord,
    Scope,
    TimetableReference,
    ValidationOutcome,
    assert_within_quarantine_ratio,
    extract_csv,
    validate_attendance,
    validate_timetable,
)
from etl import cli
from etl.exceptions import EXIT_LOAD_DERIVE_FAILURE, EXIT_SUCCESS
from etl.stages import STAGE_EXTRACT, STAGE_VALIDATE
from etl.stages.extract import ExtractStage
from etl.stages.validate import ValidateStage

DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"

ATTENDANCE_HEADER = [
    "attendance_id", "student_id", "enrollment_no", "subject_id", "subject_name",
    "faculty_id", "lecture_date", "lecture_number", "day_name", "department_code",
    "semester_no", "academic_year", "attendance_status",
]
TIMETABLE_HEADER = [
    "timttable_id", "department_code", "semester_no", "academic_year", "day_name",
    "slot_no", "start_time", "end_time", "subject_id", "subject_name", "faculty_id",
    "lecture_type",
]


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


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row in rows:
            writer.writerow([row[column] for column in header])


def write_attendance_csv(path, rows):
    write_csv(path, ATTENDANCE_HEADER, rows)


def write_timetable_csv(path, rows):
    write_csv(path, TIMETABLE_HEADER, rows)


def synthetic_timetable_rows():
    return [
        timetable_row(timttable_id="1", day_name="Monday", slot_no="1",
                      subject_id="SUB0050", faculty_id="FAC005"),
        timetable_row(timttable_id="2", day_name="Monday", slot_no="2",
                      start_time="14:00:00", end_time="15:00:00",
                      subject_id="SUB0053", subject_name="Deep Learning", faculty_id="FAC008"),
        timetable_row(timttable_id="3", day_name="Tuesday", slot_no="1",
                      subject_id="SUB0050", faculty_id="FAC005"),
        timetable_row(timttable_id="4", day_name="Tuesday", slot_no="2",
                      start_time="14:00:00", end_time="15:00:00",
                      subject_id="SUB0054", subject_name="Natural Language Processing",
                      faculty_id="FAC009"),
        timetable_row(timttable_id="5", day_name="Tuesday", slot_no="3",
                      start_time="15:00:00", end_time="16:00:00",
                      subject_id="SUB0052",
                      subject_name="Innovation, Start-up & Entrepreneurship",
                      faculty_id="FAC007"),
    ]


def synthetic_timetable_ref():
    return TimetableReference.from_rows(synthetic_timetable_rows())


def validate_att(rows, ref=None, scope=None, line_numbers=None):
    return validate_attendance(
        rows,
        line_numbers=line_numbers,
        run_id="test-run",
        scope=scope,
        timetable_ref=ref,
    )


class TestExtract(unittest.TestCase):
    def test_extract_attendance_success(self):
        source = extract_csv("daily_attendance", datasets_dir=DATASETS_DIR)
        self.assertEqual(source.row_count, 6150)
        self.assertEqual(source.columns, tuple(ATTENDANCE_HEADER))
        self.assertEqual(len(source.checksum_sha256), 64)
        self.assertEqual(source.rows[0]["attendance_id"], "1")
        self.assertEqual(source.rows[0]["student_id"], "STU000001")
        self.assertEqual(source.rows[0]["attendance_status"], "P")
        self.assertEqual(source.line_numbers[0], 2)
        self.assertEqual(source.filename, "daily_attendance_cse_sem7.csv")

    def test_extract_timetable_success(self):
        source = extract_csv("weekly_timetable", datasets_dir=DATASETS_DIR)
        self.assertEqual(source.row_count, 15)
        self.assertEqual(source.columns, tuple(TIMETABLE_HEADER))
        self.assertEqual(source.filename, "weekly_timetable_cse_sem7.csv")

    def test_extract_checksum_is_deterministic(self):
        first = extract_csv("weekly_timetable", datasets_dir=DATASETS_DIR)
        second = extract_csv("weekly_timetable", datasets_dir=DATASETS_DIR)
        self.assertEqual(first.checksum_sha256, second.checksum_sha256)

    def test_extract_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(EtlSourceError):
                extract_csv("daily_attendance", datasets_dir=Path(tmp))

    def test_extract_unknown_source_key(self):
        with self.assertRaises(EtlConfigurationError):
            extract_csv("bogus_source")

    def test_extract_malformed_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            with open(path, "w", newline="", encoding="utf-8") as handle:
                handle.write("a,b,c\n1,2\n3,4,5\n")
            with self.assertRaises(EtlSourceError):
                extract_csv("weekly_timetable", path=path)

    def test_extract_empty_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.csv"
            with open(path, "w", newline="", encoding="utf-8") as handle:
                handle.write("a,b,c\n")
            with self.assertRaises(EtlSourceError):
                extract_csv("weekly_timetable", path=path)

    def test_extract_preserves_quoted_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quoted.csv"
            with open(path, "w", newline="", encoding="utf-8") as handle:
                handle.write('timttable_id,subject_name\n1,"Innovation, Start-up & Entrepreneurship"\n')
            source = extract_csv("weekly_timetable", path=path)
            self.assertEqual(source.rows[0]["subject_name"], "Innovation, Start-up & Entrepreneurship")


class TestAttendanceValidation(unittest.TestCase):
    def test_valid_row_accepted(self):
        outcome = validate_att([attendance_row()], ref=synthetic_timetable_ref())
        self.assertEqual(outcome.total, 1)
        self.assertEqual(len(outcome.quarantined), 0)
        self.assertEqual(len(outcome.accepted), 1)

    def test_invalid_student_id_pattern(self):
        outcome = validate_att([attendance_row(student_id="STU001")], ref=synthetic_timetable_ref())
        self.assertEqual(outcome.rule_counts.get("invalid_student_id"), 1)

    def test_student_out_of_scope(self):
        outcome = validate_att([attendance_row(student_id="STU000051")], ref=synthetic_timetable_ref())
        self.assertEqual(outcome.rule_counts.get("invalid_student_id"), 1)

    def test_invalid_subject_id(self):
        outcome = validate_att([attendance_row(subject_id="SUB0099")], ref=synthetic_timetable_ref())
        self.assertEqual(outcome.rule_counts.get("invalid_subject_id"), 1)

    def test_invalid_subject_pattern(self):
        outcome = validate_att([attendance_row(subject_id="XYZ")], ref=synthetic_timetable_ref())
        self.assertEqual(outcome.rule_counts.get("invalid_subject_id"), 1)

    def test_invalid_faculty_id(self):
        outcome = validate_att([attendance_row(faculty_id="FAC999")], ref=synthetic_timetable_ref())
        self.assertEqual(outcome.rule_counts.get("invalid_faculty_id"), 1)

    def test_invalid_status(self):
        outcome = validate_att([attendance_row(attendance_status="X")], ref=synthetic_timetable_ref())
        self.assertEqual(outcome.rule_counts.get("invalid_status"), 1)

    def test_invalid_date(self):
        outcome = validate_att([attendance_row(lecture_date="2026-13-40")], ref=synthetic_timetable_ref())
        self.assertEqual(outcome.rule_counts.get("invalid_date"), 1)

    def test_invalid_lecture_number_zero(self):
        outcome = validate_att([attendance_row(lecture_number="0")], ref=synthetic_timetable_ref())
        self.assertEqual(outcome.rule_counts.get("invalid_lecture_number"), 1)

    def test_invalid_lecture_number_non_numeric(self):
        outcome = validate_att([attendance_row(lecture_number="abc")], ref=synthetic_timetable_ref())
        self.assertEqual(outcome.rule_counts.get("invalid_lecture_number"), 1)

    def test_day_name_mismatch(self):
        outcome = validate_att([attendance_row(day_name="Tuesday")], ref=synthetic_timetable_ref())
        self.assertEqual(outcome.rule_counts.get("day_mismatch"), 1)

    def test_weekend_date_rejected(self):
        outcome = validate_att(
            [attendance_row(lecture_date="2026-06-27", day_name="Saturday")],
            ref=synthetic_timetable_ref(),
        )
        self.assertEqual(outcome.rule_counts.get("day_mismatch"), 1)

    def test_wrong_scope(self):
        outcome = validate_att([attendance_row(semester_no="8")], ref=synthetic_timetable_ref())
        self.assertEqual(outcome.rule_counts.get("wrong_scope"), 1)

    def test_timetable_mismatch(self):
        outcome = validate_att(
            [attendance_row(subject_id="SUB0052", subject_name="Innovation, Start-up & Entrepreneurship",
                            faculty_id="FAC007", day_name="Monday")],
            ref=synthetic_timetable_ref(),
        )
        self.assertEqual(outcome.rule_counts.get("timetable_mismatch"), 1)

    def test_subject_name_mismatch(self):
        outcome = validate_att(
            [attendance_row(subject_name="Wrong Name")],
            ref=synthetic_timetable_ref(),
        )
        self.assertEqual(outcome.rule_counts.get("subject_name_mismatch"), 1)

    def test_null_required(self):
        outcome = validate_att([attendance_row(student_id="")], ref=synthetic_timetable_ref())
        self.assertEqual(outcome.rule_counts.get("null_required"), 1)

    def test_missing_column_fails_whole_source(self):
        rows = [dict(attendance_row())]
        del rows[0]["faculty_id"]
        with self.assertRaises(EtlValidationError):
            validate_att(rows, ref=synthetic_timetable_ref())

    def test_empty_rows_fail_whole_source(self):
        with self.assertRaises(EtlValidationError):
            validate_att([], ref=synthetic_timetable_ref())

    def test_duplicate_row_quarantined(self):
        rows = [attendance_row(attendance_id="1"), attendance_row(attendance_id="2")]
        outcome = validate_att(rows, ref=synthetic_timetable_ref())
        self.assertEqual(outcome.rule_counts.get("duplicate_row"), 1)
        self.assertEqual(len(outcome.accepted), 1)

    def test_duplicate_session_quarantined(self):
        scope = Scope(
            department_code="1", semester_no="7", academic_year="2026-2027",
            student_id_pattern=r"^STU\d{6}$", subject_id_pattern=r"^SUB\d{4}$",
            faculty_id_pattern=r"^FAC\d{3}$", enrollment_no_pattern=r"^2023\d{6}$",
            student_id_min="STU000001", student_id_max="STU000060",
        )
        rows = []
        for i in range(1, 61):
            rows.append(attendance_row(
                attendance_id=str(i), student_id=f"STU{i:06d}",
                enrollment_no=f"2023{i:06d}",
            ))
        outcome = validate_att(rows, ref=synthetic_timetable_ref(), scope=scope)
        self.assertEqual(outcome.rule_counts.get("duplicate_session"), 10)
        self.assertEqual(len(outcome.accepted), 50)
        for record in outcome.quarantined:
            self.assertEqual(record.reason_code, "duplicate_session")

    def test_quarantine_artifact_shape(self):
        outcome = validate_att(
            [attendance_row(attendance_status="X")],
            ref=synthetic_timetable_ref(),
            line_numbers=[7],
        )
        record = outcome.quarantined[0]
        self.assertIsInstance(record, QuarantineRecord)
        data = record.to_dict()
        for key in ("run_id", "stage", "source", "row_index", "reason_code",
                    "reason", "keys", "offending_values", "raw"):
            self.assertIn(key, data)
        self.assertEqual(data["row_index"], 7)
        self.assertEqual(data["source"], "daily_attendance")
        self.assertEqual(data["reason_code"], "invalid_status")
        self.assertEqual(data["keys"]["student_id"], "STU000001")
        self.assertEqual(data["raw"]["attendance_status"], "X")

    def test_deterministic_validation(self):
        rows = [
            attendance_row(attendance_id="1"),
            attendance_row(attendance_id="2", student_id="STU000002", enrollment_no="2023010002",
                           attendance_status="X"),
            attendance_row(attendance_id="3", student_id="STU000003", enrollment_no="2023010003",
                           lecture_number="0"),
            attendance_row(attendance_id="4", student_id="STU000002", enrollment_no="2023010002"),
        ]
        ref = synthetic_timetable_ref()
        first = validate_att(rows, ref=ref)
        second = validate_att(rows, ref=ref)
        self.assertEqual(first.rule_counts, second.rule_counts)
        self.assertEqual(
            [(q.row_index, q.reason_code) for q in first.quarantined],
            [(q.row_index, q.reason_code) for q in second.quarantined],
        )

    def test_order_independent_rule_counts(self):
        rows = [
            attendance_row(attendance_id="1"),
            attendance_row(attendance_id="2", attendance_status="X"),
            attendance_row(attendance_id="3", lecture_number="0"),
            attendance_row(attendance_id="4", student_id="STU000002", enrollment_no="2023010002"),
        ]
        ref = synthetic_timetable_ref()
        forward = validate_att(rows, ref=ref, line_numbers=list(range(2, 6)))
        pairs = list(zip(range(2, 6), rows))
        pairs.reverse()
        reversed_rows = [r for _, r in pairs]
        reversed_lines = [l for l, _ in pairs]
        backward = validate_att(reversed_rows, ref=ref, line_numbers=reversed_lines)
        self.assertEqual(forward.rule_counts, backward.rule_counts)

    def test_validation_without_reference_is_lenient(self):
        outcome = validate_att([attendance_row()], ref=None)
        self.assertEqual(len(outcome.quarantined), 0)
        self.assertEqual(len(outcome.accepted), 1)

    def test_real_dataset_validates_clean(self):
        source = extract_csv("daily_attendance", datasets_dir=DATASETS_DIR)
        tt = extract_csv("weekly_timetable", datasets_dir=DATASETS_DIR)
        ref = TimetableReference.from_rows(tt.rows)
        outcome = validate_attendance(
            source.rows,
            line_numbers=source.line_numbers,
            run_id="test-run",
            timetable_ref=ref,
        )
        self.assertEqual(outcome.total, 6150)
        self.assertEqual(len(outcome.quarantined), 0)
        self.assertEqual(outcome.quarantine_ratio, 0.0)
        self.assertEqual(outcome.rule_counts, {})


class TestTimetableValidation(unittest.TestCase):
    def test_valid_timetable_row_accepted(self):
        outcome = validate_timetable(synthetic_timetable_rows(), run_id="test-run")
        self.assertEqual(len(outcome.quarantined), 0)
        self.assertEqual(len(outcome.accepted), 5)

    def test_duplicate_slot_quarantined(self):
        rows = [timetable_row(timttable_id="1"), timetable_row(timttable_id="2")]
        outcome = validate_timetable(rows, run_id="test-run")
        self.assertEqual(outcome.rule_counts.get("duplicate_slot"), 1)

    def test_duplicate_timetable_id_quarantined(self):
        rows = [
            timetable_row(timttable_id="1", slot_no="1"),
            timetable_row(timttable_id="1", slot_no="2", start_time="14:00:00",
                          end_time="15:00:00", subject_id="SUB0053",
                          subject_name="Deep Learning", faculty_id="FAC008"),
        ]
        outcome = validate_timetable(rows, run_id="test-run")
        self.assertEqual(outcome.rule_counts.get("duplicate_timetable_id"), 1)

    def test_invalid_slot(self):
        outcome = validate_timetable([timetable_row(slot_no="0")], run_id="test-run")
        self.assertEqual(outcome.rule_counts.get("invalid_slot"), 1)

    def test_invalid_time(self):
        outcome = validate_timetable([timetable_row(start_time="25:00:00")], run_id="test-run")
        self.assertEqual(outcome.rule_counts.get("invalid_time"), 1)

    def test_start_not_before_end(self):
        outcome = validate_timetable([timetable_row(start_time="15:00:00", end_time="14:00:00")],
                                     run_id="test-run")
        self.assertEqual(outcome.rule_counts.get("invalid_time"), 1)

    def test_invalid_faculty(self):
        outcome = validate_timetable([timetable_row(faculty_id="FAC99")], run_id="test-run")
        self.assertEqual(outcome.rule_counts.get("invalid_faculty_id"), 1)

    def test_invalid_lecture_type(self):
        outcome = validate_timetable([timetable_row(lecture_type="Online")], run_id="test-run")
        self.assertEqual(outcome.rule_counts.get("invalid_lecture_type"), 1)

    def test_wrong_scope(self):
        outcome = validate_timetable([timetable_row(academic_year="2025-2026")], run_id="test-run")
        self.assertEqual(outcome.rule_counts.get("wrong_scope"), 1)

    def test_missing_column_fails_whole_source(self):
        rows = [dict(timetable_row())]
        del rows[0]["slot_no"]
        with self.assertRaises(EtlValidationError):
            validate_timetable(rows, run_id="test-run")

    def test_real_timetable_validates_clean(self):
        source = extract_csv("weekly_timetable", datasets_dir=DATASETS_DIR)
        outcome = validate_timetable(source.rows, line_numbers=source.line_numbers, run_id="test-run")
        self.assertEqual(outcome.total, 15)
        self.assertEqual(len(outcome.quarantined), 0)
        self.assertEqual(outcome.rule_counts, {})


class TestQuarantineRatio(unittest.TestCase):
    def test_ratio_below_threshold_passes(self):
        assert_within_quarantine_ratio(0.01, 0.05, "daily_attendance")

    def test_ratio_above_threshold_raises(self):
        with self.assertRaises(EtlValidationError):
            assert_within_quarantine_ratio(0.10, 0.05, "daily_attendance")

    def test_zero_max_ratio_any_quarantine_fails(self):
        with self.assertRaises(EtlValidationError):
            assert_within_quarantine_ratio(0.001, 0.0, "weekly_timetable")

    def test_zero_rows_ratio_is_zero(self):
        with self.assertRaises(EtlValidationError):
            validate_timetable([], run_id="test-run")


class PipelineTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.datasets = Path(self.tmp.name)
        write_timetable_csv(self.datasets / "weekly_timetable_cse_sem7.csv", synthetic_timetable_rows())
        rows = [attendance_row(attendance_id=str(i), student_id=f"STU{i:06d}",
                               enrollment_no=f"2023{i:06d}")
                for i in range(1, 51)]
        write_attendance_csv(self.datasets / "daily_attendance_cse_sem7.csv", rows)

    def build_runner(self, shared=None):
        shared = {} if shared is None else shared
        runner = EtlRunner()
        runner.register(ExtractStage(sources=("daily_attendance", "weekly_timetable"),
                                     shared=shared, datasets_dir=self.datasets))
        runner.register(ValidateStage(sources=("daily_attendance", "weekly_timetable"),
                                      shared=shared, datasets_dir=self.datasets))
        return runner

    async def test_pipeline_registers_extract_then_validate(self):
        runner = self.build_runner()
        self.assertEqual(runner.stages, (STAGE_EXTRACT, STAGE_VALIDATE))
        summary = await runner.run(dry_run=True)
        self.assertTrue(summary.success)
        self.assertEqual([s.stage for s in summary.stages], [STAGE_EXTRACT, STAGE_VALIDATE])
        self.assertEqual(summary.stages[0].rows_read, 55)
        self.assertEqual(summary.stages[1].rows_read, 55)
        self.assertEqual(summary.stages[1].rows_rejected, 0)

    async def test_dry_run_never_creates_pool(self):
        with mock.patch("etl.runner.etl_db.create_pool",
                        side_effect=AssertionError("pool created in dry run")) as create:
            summary = await self.build_runner().run(dry_run=True)
            create.assert_not_called()
            self.assertTrue(summary.success)

    async def test_apply_run_does_not_write(self):
        fake_pool = mock.MagicMock()
        fake_pool.close = mock.AsyncMock()
        fake_pool.fetch = mock.AsyncMock()
        fake_pool.execute = mock.AsyncMock()
        with mock.patch("etl.runner.etl_db.create_pool", return_value=fake_pool):
            summary = await self.build_runner().run(dry_run=False)
        self.assertTrue(summary.success)
        fake_pool.fetch.assert_not_called()
        fake_pool.execute.assert_not_called()
        fake_pool.close.assert_awaited_once()

    async def test_missing_source_stops_pipeline(self):
        for name in ("daily_attendance_cse_sem7.csv",):
            (self.datasets / name).unlink()
        summary = await self.build_runner().run(dry_run=True)
        self.assertFalse(summary.success)
        self.assertEqual(summary.exit_code, 1)
        self.assertEqual([s.stage for s in summary.stages], [STAGE_EXTRACT])

    async def test_quarantine_exceeded_stops_pipeline(self):
        bad = [attendance_row(attendance_id=str(i), student_id=f"STU{i:06d}",
                              enrollment_no=f"2023{i:06d}", attendance_status="X")
               for i in range(1, 11)]
        bad.append(attendance_row(attendance_id="99"))
        write_attendance_csv(self.datasets / "daily_attendance_cse_sem7.csv", bad)
        summary = await self.build_runner().run(dry_run=True)
        self.assertFalse(summary.success)
        self.assertEqual(summary.exit_code, 1)
        stages = [s.stage for s in summary.stages]
        self.assertEqual(stages, [STAGE_EXTRACT, STAGE_VALIDATE])
        self.assertEqual(summary.stages[1].status, "failed")

    async def test_validate_stage_self_extracts(self):
        runner = EtlRunner().register(
            ValidateStage(sources=("daily_attendance", "weekly_timetable"), datasets_dir=self.datasets)
        )
        summary = await runner.run(dry_run=True)
        self.assertTrue(summary.success)
        self.assertEqual(summary.stages[0].rows_read, 55)

    async def test_validate_failure_stops_downstream(self):
        bad = [attendance_row(attendance_id=str(i), student_id=f"STU{i:06d}",
                              enrollment_no=f"2023{i:06d}", attendance_status="X")
               for i in range(1, 11)]
        write_attendance_csv(self.datasets / "daily_attendance_cse_sem7.csv", bad)
        summary = await self.build_runner().run(dry_run=True)
        self.assertFalse(summary.success)
        self.assertEqual(summary.stages[-1].stage, STAGE_VALIDATE)


class TestCliStageSelection(unittest.TestCase):
    def capture(self, func):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = func()
        return code, out.getvalue(), err.getvalue()

    def test_cli_default_run_includes_both_sources(self):
        code, out, _ = self.capture(lambda: cli.main(["run", "--dry-run"]))
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("stages_run=7", out)
        self.assertIn("extract", out)
        self.assertIn("validate", out)
        self.assertIn("stage", out)
        self.assertIn("stitch", out)
        self.assertIn("transform", out)
        self.assertIn("load", out)

    def test_cli_single_extract_stage(self):
        code, out, _ = self.capture(lambda: cli.main(["run", "--stage", "extract"]))
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("extract: status=success", out)

    def test_cli_single_validate_stage(self):
        code, out, _ = self.capture(lambda: cli.main(["run", "--stage", "validate"]))
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("validate: status=success", out)

    def test_cli_downstream_stage_now_implemented(self):
        code, out, _ = self.capture(lambda: cli.main(["run", "--stage", "derive"]))
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("derive: status=success", out)

    def test_cli_sources_flag_scopes_run(self):
        code, out, _ = self.capture(
            lambda: cli.main(["run", "--dry-run", "--sources", "weekly_timetable"])
        )
        self.assertEqual(code, EXIT_SUCCESS)
        self.assertIn("stages_run=7", out)


if __name__ == "__main__":
    unittest.main()
