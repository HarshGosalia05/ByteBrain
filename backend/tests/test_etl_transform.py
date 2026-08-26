"""Unit tests for the ETL Transform slice.

Covers: date parsing, time parsing, string normalization, subject_name
enrichment, lecture_session_key derivation, attendance status normalization,
Threshold Engine bands, no database writes, input mutation prevention, empty
input handling, and pipeline integration through Transform.
"""

import asyncio
import datetime
import unittest

from etl import EtlRunner
from etl.config import etl_config
from etl.context import RunContext
from etl.stages import STAGE_TRANSFORM
from etl.stages.extract import ExtractStage
from etl.stages.stage import StageStage
from etl.stages.stitch import ResolvedIdentities, StitchStage, StitchedRecord
from etl.stages.transform import VALID_DAYS, TransformStage
from etl.stages.validate import ValidateStage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def attendance_row(**overrides):
    base = {
        "attendance_id": "1", "student_id": "STU000001",
        "enrollment_no": "2023010001", "subject_id": "SUB0050",
        "subject_name": "Software Engineering", "faculty_id": "FAC005",
        "lecture_date": "2026-06-22", "lecture_number": "1",
        "day_name": "Monday", "department_code": "1", "semester_no": "7",
        "academic_year": "2026-2027", "attendance_status": "P",
    }
    base.update(overrides)
    return base


def timetable_row(**overrides):
    base = {
        "timttable_id": "1", "department_code": "1", "semester_no": "7",
        "academic_year": "2026-2027", "day_name": "Monday", "slot_no": "1",
        "start_time": "13:00:00", "end_time": "14:00:00",
        "subject_id": "SUB0050", "subject_name": "Software Engineering",
        "faculty_id": "FAC005", "lecture_type": "Theory",
    }
    base.update(overrides)
    return base


def make_stitched(source, row, enrollment_record_id=None, resolved=None):
    if resolved is None:
        resolved = ResolvedIdentities(
            student=True, subject=True, faculty=True,
            enrollment=enrollment_record_id is not None,
        )
    return StitchedRecord(
        source=source,
        run_id="test-run-001",
        row_index=1,
        row=row,
        enrollment_record_id=enrollment_record_id,
        resolved=resolved,
    )


# ---------------------------------------------------------------------------
# Date Parsing
# ---------------------------------------------------------------------------

class TestDateParsing(unittest.TestCase):
    def test_parse_valid_date(self):
        result = TransformStage._parse_date("2026-06-22")
        self.assertEqual(result, datetime.date(2026, 6, 22))

    def test_parse_date_with_whitespace(self):
        result = TransformStage._parse_date("  2026-01-15  ")
        self.assertEqual(result, datetime.date(2026, 1, 15))

    def test_parse_date_first_day_of_year(self):
        result = TransformStage._parse_date("2026-01-01")
        self.assertEqual(result, datetime.date(2026, 1, 1))

    def test_parse_date_last_day_of_year(self):
        result = TransformStage._parse_date("2026-12-31")
        self.assertEqual(result, datetime.date(2026, 12, 31))

    def test_parse_date_invalid_format_raises(self):
        with self.assertRaises(ValueError):
            TransformStage._parse_date("22-06-2026")

    def test_parse_date_empty_raises(self):
        with self.assertRaises(ValueError):
            TransformStage._parse_date("")

    def test_parse_date_non_numeric_raises(self):
        with self.assertRaises(ValueError):
            TransformStage._parse_date("abcd-ef-gh")


# ---------------------------------------------------------------------------
# Time Parsing
# ---------------------------------------------------------------------------

class TestTimeParsing(unittest.TestCase):
    def test_parse_valid_time(self):
        result = TransformStage._parse_time("13:00:00")
        self.assertEqual(result, datetime.time(13, 0, 0))

    def test_parse_time_with_whitespace(self):
        result = TransformStage._parse_time("  09:30:00  ")
        self.assertEqual(result, datetime.time(9, 30, 0))

    def test_parse_time_midnight(self):
        result = TransformStage._parse_time("00:00:00")
        self.assertEqual(result, datetime.time(0, 0, 0))

    def test_parse_time_end_of_day(self):
        result = TransformStage._parse_time("23:59:59")
        self.assertEqual(result, datetime.time(23, 59, 59))

    def test_parse_time_invalid_format_raises(self):
        with self.assertRaises(ValueError):
            TransformStage._parse_time("13:00")

    def test_parse_time_empty_raises(self):
        with self.assertRaises(ValueError):
            TransformStage._parse_time("")


# ---------------------------------------------------------------------------
# String Normalization
# ---------------------------------------------------------------------------

class TestStringNormalization(unittest.TestCase):
    def test_normalize_day_name_exact(self):
        self.assertEqual(TransformStage._normalize_day_name("Monday"), "Monday")

    def test_normalize_day_name_lowercase(self):
        self.assertEqual(TransformStage._normalize_day_name("monday"), "Monday")

    def test_normalize_day_name_uppercase(self):
        self.assertEqual(TransformStage._normalize_day_name("TUESDAY"), "Tuesday")

    def test_normalize_day_name_with_whitespace(self):
        self.assertEqual(TransformStage._normalize_day_name("  Wednesday  "), "Wednesday")

    def test_normalize_day_name_invalid(self):
        self.assertEqual(TransformStage._normalize_day_name("Funday"), "Funday")

    def test_valid_days_set(self):
        self.assertEqual(
            VALID_DAYS,
            frozenset({"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}),
        )


# ---------------------------------------------------------------------------
# Threshold Engine Bands
# ---------------------------------------------------------------------------

class TestAttendanceBands(unittest.TestCase):
    def test_critical_below_60(self):
        result = TransformStage.attendance_band(50.0)
        self.assertEqual(result["attendance_status"], "Critical")
        self.assertEqual(result["eligibility_status"], "Not Eligible")
        self.assertEqual(result["shortage_flag"], "Yes")

    def test_low_between_60_and_75(self):
        result = TransformStage.attendance_band(68.0)
        self.assertEqual(result["attendance_status"], "Low")
        self.assertEqual(result["eligibility_status"], "Not Eligible")
        self.assertEqual(result["shortage_flag"], "Yes")

    def test_average_between_75_and_80(self):
        result = TransformStage.attendance_band(77.0)
        self.assertEqual(result["attendance_status"], "Average")
        self.assertEqual(result["eligibility_status"], "Eligible")
        self.assertEqual(result["shortage_flag"], "No")

    def test_good_between_80_and_90(self):
        result = TransformStage.attendance_band(85.0)
        self.assertEqual(result["attendance_status"], "Good")
        self.assertEqual(result["eligibility_status"], "Eligible")
        self.assertEqual(result["shortage_flag"], "No")

    def test_excellent_at_90(self):
        result = TransformStage.attendance_band(90.0)
        self.assertEqual(result["attendance_status"], "Excellent")
        self.assertEqual(result["eligibility_status"], "Eligible")
        self.assertEqual(result["shortage_flag"], "No")

    def test_excellent_above_90(self):
        result = TransformStage.attendance_band(95.0)
        self.assertEqual(result["attendance_status"], "Excellent")
        self.assertEqual(result["eligibility_status"], "Eligible")
        self.assertEqual(result["shortage_flag"], "No")

    def test_none_percentage(self):
        result = TransformStage.attendance_band(None)
        self.assertIsNone(result["attendance_status"])
        self.assertEqual(result["eligibility_status"], "Not Eligible")
        self.assertEqual(result["shortage_flag"], "Yes")

    def test_boundary_60(self):
        result = TransformStage.attendance_band(60.0)
        self.assertEqual(result["attendance_status"], "Low")

    def test_boundary_75(self):
        result = TransformStage.attendance_band(75.0)
        self.assertEqual(result["attendance_status"], "Average")
        self.assertEqual(result["eligibility_status"], "Eligible")

    def test_boundary_80(self):
        result = TransformStage.attendance_band(80.0)
        self.assertEqual(result["attendance_status"], "Good")

    def test_thresholds_match_config(self):
        thresholds = etl_config.thresholds
        self.assertEqual(thresholds.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD, 60.0)
        self.assertEqual(thresholds.FACULTY_ATTENDANCE_THRESHOLD, 75.0)
        self.assertEqual(thresholds.ATTENDANCE_STATUS_GOOD_SPLIT, 80.0)
        self.assertEqual(thresholds.FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD, 90.0)


# ---------------------------------------------------------------------------
# Attendance Record Transformation
# ---------------------------------------------------------------------------

class TestTransformAttendance(unittest.TestCase):
    def setUp(self):
        self.stage = TransformStage()

    def test_basic_attendance_transform(self):
        stitched = make_stitched(
            "daily_attendance",
            attendance_row(),
            enrollment_record_id="ENR000001",
        )
        result = self.stage._transform_attendance(stitched, {})
        self.assertEqual(result["lecture_date"], datetime.date(2026, 6, 22))
        self.assertTrue(result["is_present"])
        self.assertEqual(result["attendance_status_text"], "Present")
        self.assertEqual(result["day_name"], "Monday")
        self.assertEqual(result["subject_name"], "Software Engineering")

    def test_absent_record(self):
        stitched = make_stitched(
            "daily_attendance",
            attendance_row(attendance_status="A"),
            enrollment_record_id="ENR000001",
        )
        result = self.stage._transform_attendance(stitched, {})
        self.assertFalse(result["is_present"])
        self.assertEqual(result["attendance_status_text"], "Absent")
        self.assertEqual(result["attendance_status"], "A")

    def test_lecture_session_key(self):
        stitched = make_stitched(
            "daily_attendance",
            attendance_row(),
            enrollment_record_id="ENR000001",
        )
        result = self.stage._transform_attendance(stitched, {})
        self.assertEqual(
            result["lecture_session_key"],
            "SUB0050|2026-06-22|1",
        )

    def test_subject_name_enrichment_from_map(self):
        stitched = make_stitched(
            "daily_attendance",
            attendance_row(subject_name="Old Name"),
            enrollment_record_id="ENR000001",
        )
        subject_map = {"SUB0050": "Software Engineering"}
        result = self.stage._transform_attendance(stitched, subject_map)
        self.assertEqual(result["subject_name"], "Software Engineering")

    def test_subject_name_fallback_to_row(self):
        stitched = make_stitched(
            "daily_attendance",
            attendance_row(subject_name="Row Name"),
            enrollment_record_id="ENR000001",
        )
        result = self.stage._transform_attendance(stitched, {})
        self.assertEqual(result["subject_name"], "Row Name")

    def test_source_and_run_id_preserved(self):
        stitched = make_stitched(
            "daily_attendance",
            attendance_row(),
            enrollment_record_id="ENR000001",
        )
        result = self.stage._transform_attendance(stitched, {})
        self.assertEqual(result["source"], "daily_attendance")
        self.assertEqual(result["run_id"], "test-run-001")

    def test_enrollment_record_id_preserved(self):
        stitched = make_stitched(
            "daily_attendance",
            attendance_row(),
            enrollment_record_id="ENR000042",
        )
        result = self.stage._transform_attendance(stitched, {})
        self.assertEqual(result["enrollment_record_id"], "ENR000042")

    def test_all_original_fields_preserved(self):
        stitched = make_stitched(
            "daily_attendance",
            attendance_row(),
            enrollment_record_id="ENR000001",
        )
        result = self.stage._transform_attendance(stitched, {})
        self.assertEqual(result["attendance_id"], "1")
        self.assertEqual(result["student_id"], "STU000001")
        self.assertEqual(result["enrollment_no"], "2023010001")
        self.assertEqual(result["subject_id"], "SUB0050")
        self.assertEqual(result["faculty_id"], "FAC005")
        self.assertEqual(result["department_code"], "1")
        self.assertEqual(result["semester_no"], "7")
        self.assertEqual(result["academic_year"], "2026-2027")

    def test_day_name_normalized_from_lowercase(self):
        stitched = make_stitched(
            "daily_attendance",
            attendance_row(day_name="tuesday"),
            enrollment_record_id="ENR000001",
        )
        result = self.stage._transform_attendance(stitched, {})
        self.assertEqual(result["day_name"], "Tuesday")


# ---------------------------------------------------------------------------
# Timetable Record Transformation
# ---------------------------------------------------------------------------

class TestTransformTimetable(unittest.TestCase):
    def setUp(self):
        self.stage = TransformStage()

    def test_basic_timetable_transform(self):
        stitched = make_stitched("weekly_timetable", timetable_row())
        result = self.stage._transform_timetable(stitched, {})
        self.assertEqual(result["start_time"], datetime.time(13, 0, 0))
        self.assertEqual(result["end_time"], datetime.time(14, 0, 0))
        self.assertEqual(result["lecture_type"], "Theory")
        self.assertEqual(result["subject_name"], "Software Engineering")

    def test_lecture_session_key_timetable(self):
        stitched = make_stitched("weekly_timetable", timetable_row())
        result = self.stage._transform_timetable(stitched, {})
        self.assertEqual(
            result["lecture_session_key"],
            "SUB0050|Monday|1",
        )

    def test_lecture_type_capitalized(self):
        stitched = make_stitched(
            "weekly_timetable",
            timetable_row(lecture_type="lab"),
        )
        result = self.stage._transform_timetable(stitched, {})
        self.assertEqual(result["lecture_type"], "Lab")

    def test_subject_name_enrichment(self):
        stitched = make_stitched(
            "weekly_timetable",
            timetable_row(subject_name="Old"),
        )
        subject_map = {"SUB0050": "Software Engineering"}
        result = self.stage._transform_timetable(stitched, subject_map)
        self.assertEqual(result["subject_name"], "Software Engineering")

    def test_all_original_fields_preserved(self):
        stitched = make_stitched("weekly_timetable", timetable_row())
        result = self.stage._transform_timetable(stitched, {})
        self.assertEqual(result["timetable_id"], "1")
        self.assertEqual(result["department_code"], "1")
        self.assertEqual(result["semester_no"], "7")
        self.assertEqual(result["academic_year"], "2026-2027")
        self.assertEqual(result["day_name"], "Monday")
        self.assertEqual(result["slot_no"], "1")
        self.assertEqual(result["subject_id"], "SUB0050")
        self.assertEqual(result["faculty_id"], "FAC005")

    def test_day_name_normalized(self):
        stitched = make_stitched(
            "weekly_timetable",
            timetable_row(day_name="friday"),
        )
        result = self.stage._transform_timetable(stitched, {})
        self.assertEqual(result["day_name"], "Friday")


# ---------------------------------------------------------------------------
# Subject Map Building
# ---------------------------------------------------------------------------

class TestBuildSubjectMap(unittest.TestCase):
    def test_builds_map_from_stitched(self):
        stage = TransformStage()
        records = [
            make_stitched("daily_attendance", attendance_row()),
            make_stitched(
                "daily_attendance",
                attendance_row(subject_id="SUB0051", subject_name="HCI"),
            ),
        ]
        stitched = {"daily_attendance": records}
        subject_map = stage._build_subject_map(stitched)
        self.assertEqual(subject_map["SUB0050"], "Software Engineering")
        self.assertEqual(subject_map["SUB0051"], "HCI")

    def test_first_seen_wins(self):
        stage = TransformStage()
        records = [
            make_stitched("daily_attendance", attendance_row(subject_name="First")),
            make_stitched(
                "daily_attendance",
                attendance_row(subject_name="Second"),
            ),
        ]
        stitched = {"daily_attendance": records}
        subject_map = stage._build_subject_map(stitched)
        self.assertEqual(subject_map["SUB0050"], "First")

    def test_empty_stitched(self):
        stage = TransformStage()
        self.assertEqual(stage._build_subject_map({}), {})


# ---------------------------------------------------------------------------
# Passthrough
# ---------------------------------------------------------------------------

class TestTransformPassthrough(unittest.TestCase):
    def test_unknown_source_passthrough(self):
        stage = TransformStage()
        stitched = make_stitched("unknown_source", {"foo": "bar"})
        result = stage._transform_passthrough(stitched)
        self.assertEqual(result["source"], "unknown_source")
        self.assertEqual(result["row"]["foo"], "bar")


# ---------------------------------------------------------------------------
# Stage Contract (no DB writes)
# ---------------------------------------------------------------------------

class TestTransformStageContract(unittest.TestCase):
    def test_name(self):
        self.assertEqual(TransformStage.name, STAGE_TRANSFORM)

    def test_empty_stitched_returns_zero(self):
        stage = TransformStage(shared={})
        ctx = RunContext.create(run_id="test-run-001")
        result = asyncio.run(
            stage.run(ctx, pool=None)
        )
        self.assertEqual(result.rows_read, 0)
        self.assertEqual(result.rows_accepted, 0)

    def test_transform_writes_to_shared(self):
        shared = {
            "stitched": {
                "daily_attendance": [
                    make_stitched(
                        "daily_attendance",
                        attendance_row(),
                        enrollment_record_id="ENR000001",
                    ),
                ],
            },
        }
        stage = TransformStage(shared=shared)
        ctx = RunContext.create(run_id="test-run-001")
        result = asyncio.run(
            stage.run(ctx, pool=None)
        )
        self.assertEqual(result.rows_read, 1)
        self.assertEqual(result.rows_accepted, 1)
        self.assertIn("transformed", shared)
        self.assertEqual(len(shared["transformed"]["daily_attendance"]), 1)

    def test_transform_preserves_input_stitched(self):
        stitched_record = make_stitched(
            "daily_attendance",
            attendance_row(),
            enrollment_record_id="ENR000001",
        )
        shared = {"stitched": {"daily_attendance": [stitched_record]}}
        stage = TransformStage(shared=shared)
        ctx = RunContext.create(run_id="test-run-001")
        asyncio.run(
            stage.run(ctx, pool=None)
        )
        self.assertEqual(stitched_record.row["attendance_status"], "P")

    def test_transform_multiple_sources(self):
        shared = {
            "stitched": {
                "daily_attendance": [
                    make_stitched(
                        "daily_attendance",
                        attendance_row(),
                        enrollment_record_id="ENR000001",
                    ),
                ],
                "weekly_timetable": [
                    make_stitched("weekly_timetable", timetable_row()),
                ],
            },
        }
        stage = TransformStage(shared=shared)
        ctx = RunContext.create(run_id="test-run-001")
        result = asyncio.run(
            stage.run(ctx, pool=None)
        )
        self.assertEqual(result.rows_read, 2)
        self.assertEqual(result.rows_accepted, 2)
        self.assertEqual(len(shared["transformed"]["daily_attendance"]), 1)
        self.assertEqual(len(shared["transformed"]["weekly_timetable"]), 1)

    def test_no_database_write_with_pool(self):
        stage = TransformStage(
            shared={
                "stitched": {
                    "daily_attendance": [
                        make_stitched(
                            "daily_attendance",
                            attendance_row(),
                            enrollment_record_id="ENR000001",
                        ),
                    ],
                },
            }
        )
        ctx = RunContext.create(run_id="test-run-001")
        result = asyncio.run(
            stage.run(ctx, pool="fake-pool")
        )
        self.assertEqual(result.rows_accepted, 1)

    def test_sources_filter(self):
        shared = {
            "stitched": {
                "daily_attendance": [
                    make_stitched(
                        "daily_attendance",
                        attendance_row(),
                        enrollment_record_id="ENR000001",
                    ),
                ],
                "weekly_timetable": [
                    make_stitched("weekly_timetable", timetable_row()),
                ],
            },
        }
        stage = TransformStage(
            sources=["daily_attendance"], shared=shared
        )
        ctx = RunContext.create(run_id="test-run-001")
        result = asyncio.run(
            stage.run(ctx, pool=None)
        )
        self.assertEqual(result.rows_read, 1)
        self.assertEqual(len(shared["transformed"]), 1)
        self.assertIn("daily_attendance", shared["transformed"])

    def test_metadata_populated(self):
        shared = {
            "stitched": {
                "daily_attendance": [
                    make_stitched(
                        "daily_attendance",
                        attendance_row(),
                        enrollment_record_id="ENR000001",
                    ),
                ],
            },
        }
        stage = TransformStage(shared=shared)
        ctx = RunContext.create(run_id="test-run-001")
        result = asyncio.run(
            stage.run(ctx, pool=None)
        )
        self.assertIn("source_keys", result.metadata)
        self.assertIn("transformed_counts", result.metadata)
        self.assertIn("run_id", result.metadata)
        self.assertEqual(result.metadata["run_id"], "test-run-001")


# ---------------------------------------------------------------------------
# Pipeline Integration
# ---------------------------------------------------------------------------

class TestTransformPipelineIntegration(unittest.TestCase):
    def test_transform_after_stitch_prepopulated(self):
        shared: dict = {
            "stitched": {
                "daily_attendance": [
                    make_stitched(
                        "daily_attendance",
                        attendance_row(),
                        enrollment_record_id="ENR000001",
                    ),
                    make_stitched(
                        "daily_attendance",
                        attendance_row(
                            attendance_id="2", student_id="STU000002",
                            enrollment_no="2023010002", attendance_status="A",
                        ),
                        enrollment_record_id="ENR000002",
                    ),
                ],
                "weekly_timetable": [
                    make_stitched("weekly_timetable", timetable_row()),
                ],
            },
        }
        stage = TransformStage(shared=shared)
        ctx = RunContext.create(run_id="integration-test-001")
        result = asyncio.run(
            stage.run(ctx, pool=None)
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(result.rows_read, 3)
        self.assertEqual(result.rows_accepted, 3)
        self.assertIn("transformed", shared)
        self.assertEqual(len(shared["transformed"]["daily_attendance"]), 2)
        self.assertEqual(len(shared["transformed"]["weekly_timetable"]), 1)

    def test_transformed_attendance_row_shape(self):
        shared: dict = {
            "stitched": {
                "daily_attendance": [
                    make_stitched(
                        "daily_attendance",
                        attendance_row(),
                        enrollment_record_id="ENR000001",
                    ),
                ],
            },
        }
        stage = TransformStage(shared=shared)
        ctx = RunContext.create(run_id="shape-test-001")
        asyncio.run(
            stage.run(ctx, pool=None)
        )
        transformed = shared["transformed"]["daily_attendance"]
        self.assertEqual(len(transformed), 1)
        row = transformed[0]
        self.assertIn("lecture_date", row)
        self.assertIn("is_present", row)
        self.assertIn("attendance_status_text", row)
        self.assertIn("lecture_session_key", row)
        self.assertIn("subject_name", row)
        self.assertIsInstance(row["lecture_date"], datetime.date)

    def test_transformed_timetable_row_shape(self):
        timetable_records = []
        for i in range(1, 16):
            timetable_records.append(
                make_stitched(
                    "weekly_timetable",
                    timetable_row(timttable_id=str(i), slot_no=str((i - 1) % 3 + 1)),
                )
            )
        shared: dict = {
            "stitched": {
                "weekly_timetable": timetable_records,
            },
        }
        stage = TransformStage(shared=shared)
        ctx = RunContext.create(run_id="shape-test-002")
        asyncio.run(
            stage.run(ctx, pool=None)
        )
        transformed = shared["transformed"]["weekly_timetable"]
        self.assertEqual(len(transformed), 15)
        row = transformed[0]
        self.assertIn("start_time", row)
        self.assertIn("end_time", row)
        self.assertIn("lecture_type", row)
        self.assertIn("lecture_session_key", row)
        self.assertIsInstance(row["start_time"], datetime.time)
        self.assertIsInstance(row["end_time"], datetime.time)


if __name__ == "__main__":
    unittest.main()
