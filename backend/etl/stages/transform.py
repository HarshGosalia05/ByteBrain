"""Transform: deterministic mappings and derivations at the fact grain.

Plan `01` §3.1 Transform. Stateless, in-memory, pure-function stage. Reads
from ``shared["stitched"]`` (produced by Stitch) and publishes
``shared["transformed"]``.

Six responsibilities (plan `03` §3.3):
1. Parse dates — ``lecture_date`` string → ``datetime.date``
2. Parse times — ``start_time``/``end_time`` strings → ``datetime.time``
3. Normalize strings — strip whitespace, case normalization
4. Enrich subject_name — canonical name from stitched row data
5. Derive lecture_session_key — ``(subject_id, lecture_date, lecture_number)``
6. Threshold Engine integration — individual attendance fields prepared for
   Derive-stage aggregate classification

No summarization (deferred to Derive). No database writes.
"""

import datetime
from typing import Any, Dict, List, Optional, Sequence

import asyncpg

from etl.config import etl_config
from etl.exceptions import EtlTransformError
from etl.keys import LECTURE_SESSION_KEY_FIELDS
from etl.result import StageResult
from etl.stages import STAGE_TRANSFORM, Stage
from etl.stages.stitch import StitchedRecord
from etl.validation import parse_attendance_status

VALID_DAYS = frozenset({"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"})
VALID_ATTENDANCE_STATUS_TEXT = frozenset({"Present", "Absent"})


class TransformStage(Stage):
    """Deterministic mappings and derivations at fact grain.

    Consumes ``shared["stitched"]`` and publishes ``shared["transformed"]``.
    No database writes — entirely in-memory (plan `01` §3.1).
    """

    name = STAGE_TRANSFORM
    description = (
        "Deterministic mappings and derivations at fact grain "
        "(plan 01 §3.1, in-memory only)."
    )

    def __init__(
        self,
        sources: Optional[Sequence[str]] = None,
        shared: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._sources = tuple(sources) if sources is not None else ()
        self._shared = shared if shared is not None else {}

    async def run(
        self, context, pool: Optional[asyncpg.Pool] = None
    ) -> StageResult:
        stitched: Dict[str, List[StitchedRecord]] = dict(
            self._shared.get("stitched") or {}
        )
        if not stitched:
            return StageResult(stage=self.name, rows_read=0, rows_accepted=0)

        sources_to_transform = (
            self._sources if self._sources else tuple(stitched.keys())
        )

        subject_map = self._build_subject_map(stitched)

        transformed: Dict[str, List[Dict[str, Any]]] = {}
        rows_read = 0
        rows_transformed = 0

        for source_key in sources_to_transform:
            records = stitched.get(source_key)
            if records is None:
                continue

            rows_read += len(records)
            out: List[Dict[str, Any]] = []

            for record in records:
                if source_key == "daily_attendance":
                    transformed_row = self._transform_attendance(
                        record, subject_map
                    )
                elif source_key == "weekly_timetable":
                    transformed_row = self._transform_timetable(
                        record, subject_map
                    )
                else:
                    transformed_row = self._transform_passthrough(record)

                out.append(transformed_row)
                rows_transformed += 1

            transformed[source_key] = out

        self._shared["transformed"] = transformed

        result = StageResult(
            stage=self.name,
            rows_read=rows_read,
            rows_accepted=rows_transformed,
        )
        result.metadata["source_keys"] = list(sources_to_transform)
        result.metadata["transformed_counts"] = {
            key: len(records) for key, records in transformed.items()
        }
        result.metadata["run_id"] = context.run_id
        return result

    def _build_subject_map(
        self, stitched: Dict[str, List[StitchedRecord]]
    ) -> Dict[str, str]:
        """Build subject_id → canonical subject_name from stitched row data."""
        subject_map: Dict[str, str] = {}
        for records in stitched.values():
            for record in records:
                row = record.row
                sid = row.get("subject_id", "")
                sname = row.get("subject_name", "")
                if sid and sname and sid not in subject_map:
                    subject_map[sid] = sname.strip()
        return subject_map

    def _transform_attendance(
        self,
        record: StitchedRecord,
        subject_map: Dict[str, str],
    ) -> Dict[str, Any]:
        """Transform a single stitched attendance record."""
        row = record.row

        raw_date = row.get("lecture_date", "")
        raw_status = row.get("attendance_status", "")
        raw_day = row.get("day_name", "")
        raw_subject_name = row.get("subject_name", "")
        subject_id = row.get("subject_id", "")
        lecture_number = row.get("lecture_number", "")

        lecture_date = self._parse_date(raw_date)
        try:
            parsed_status = parse_attendance_status(raw_status)
        except ValueError as exc:
            raise EtlTransformError(
                f"Invalid attendance status '{raw_status}' at row {record.row_index}: {exc}"
            ) from exc
        is_present = parsed_status == "P"
        attendance_status_text = "Present" if is_present else "Absent"
        day_name = self._normalize_day_name(raw_day)
        subject_name = subject_map.get(
            subject_id, raw_subject_name.strip()
        )

        lecture_session_key = "|".join(
            str(v) for v in (
                subject_id, lecture_date.isoformat(), lecture_number
            )
        )

        return {
            "source": record.source,
            "run_id": record.run_id,
            "row_index": record.row_index,
            "enrollment_record_id": record.enrollment_record_id,
            "attendance_id": row.get("attendance_id", ""),
            "student_id": row.get("student_id", ""),
            "enrollment_no": row.get("enrollment_no", ""),
            "subject_id": subject_id,
            "subject_name": subject_name,
            "faculty_id": row.get("faculty_id", ""),
            "lecture_date": lecture_date,
            "lecture_number": lecture_number,
            "day_name": day_name,
            "department_code": row.get("department_code", ""),
            "semester_no": row.get("semester_no", ""),
            "academic_year": row.get("academic_year", ""),
            "attendance_status": parsed_status,
            "attendance_status_text": attendance_status_text,
            "is_present": is_present,
            "lecture_session_key": lecture_session_key,
        }

    def _transform_timetable(
        self,
        record: StitchedRecord,
        subject_map: Dict[str, str],
    ) -> Dict[str, Any]:
        """Transform a single stitched timetable record."""
        row = record.row

        raw_subject_name = row.get("subject_name", "")
        subject_id = row.get("subject_id", "")
        subject_name = subject_map.get(
            subject_id, raw_subject_name.strip()
        )

        start_time = self._parse_time(row.get("start_time", ""))
        end_time = self._parse_time(row.get("end_time", ""))
        lecture_type = row.get("lecture_type", "").strip().capitalize()

        day_name = self._normalize_day_name(row.get("day_name", ""))
        slot_no = row.get("slot_no", "")

        lecture_session_key = "|".join(
            str(v) for v in (subject_id, day_name, slot_no)
        )

        return {
            "source": record.source,
            "run_id": record.run_id,
            "row_index": record.row_index,
            "timetable_id": row.get("timttable_id", ""),
            "department_code": row.get("department_code", ""),
            "semester_no": row.get("semester_no", ""),
            "academic_year": row.get("academic_year", ""),
            "day_name": day_name,
            "slot_no": slot_no,
            "start_time": start_time,
            "end_time": end_time,
            "subject_id": subject_id,
            "subject_name": subject_name,
            "faculty_id": row.get("faculty_id", ""),
            "lecture_type": lecture_type,
            "lecture_session_key": lecture_session_key,
        }

    def _transform_passthrough(
        self, record: StitchedRecord
    ) -> Dict[str, Any]:
        """Passthrough for unknown sources — preserve original row."""
        return {
            "source": record.source,
            "run_id": record.run_id,
            "row_index": record.row_index,
            "row": dict(record.row),
        }

    @staticmethod
    def _parse_date(raw: str) -> datetime.date:
        """Parse a date string (YYYY-MM-DD) to datetime.date."""
        cleaned = raw.strip()
        parts = cleaned.split("-")
        if len(parts) == 3:
            return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        raise ValueError(f"unparseable date: {raw!r}")

    @staticmethod
    def _parse_time(raw: str) -> datetime.time:
        """Parse a time string (HH:MM:SS) to datetime.time."""
        cleaned = raw.strip()
        parts = cleaned.split(":")
        if len(parts) == 3:
            return datetime.time(int(parts[0]), int(parts[1]), int(parts[2]))
        raise ValueError(f"unparseable time: {raw!r}")

    @staticmethod
    def _normalize_day_name(raw: str) -> str:
        """Normalize day name to title case if within valid set."""
        cleaned = raw.strip()
        if cleaned in VALID_DAYS:
            return cleaned
        title = cleaned.title()
        if title in VALID_DAYS:
            return title
        return cleaned

    @staticmethod
    def attendance_band(percentage: Optional[float]) -> Dict[str, str]:
        """Threshold Engine bands at the aggregate level (reused by Derive).

        Reads thresholds from ``etl_config.thresholds`` (the application's
        ``Settings`` singleton — plan `03` §4.3, plan `10` §2).

        Returns a dict with ``attendance_status``, ``eligibility_status``,
        and ``shortage_flag`` suitable for canonical table columns.
        """
        thresholds = etl_config.thresholds
        critical = thresholds.FACULTY_ATTENDANCE_CRITICAL_THRESHOLD
        compliance = thresholds.FACULTY_ATTENDANCE_THRESHOLD
        good_split = thresholds.ATTENDANCE_STATUS_GOOD_SPLIT
        excellent = thresholds.FACULTY_ATTENDANCE_EXCELLENT_THRESHOLD

        if percentage is None:
            return {
                "attendance_status": None,
                "eligibility_status": "Not Eligible",
                "shortage_flag": "Yes",
            }

        if percentage < critical:
            status = "Critical"
        elif percentage < compliance:
            status = "Low"
        elif percentage < good_split:
            status = "Average"
        elif percentage < excellent:
            status = "Good"
        else:
            status = "Excellent"

        eligible = percentage >= compliance
        return {
            "attendance_status": status,
            "eligibility_status": "Eligible" if eligible else "Not Eligible",
            "shortage_flag": "No" if eligible else "Yes",
        }
