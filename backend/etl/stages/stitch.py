"""Stitch: resolve staged records against canonical master data in PostgreSQL.

Plan `01` §3.1 Stitch. Read-only: reads master/bridge tables to verify FK
references and resolve identity relationships. Never writes to the database.

Consumes ``shared["staged"]`` (produced by Stage) and publishes
``shared["stitched"]`` with resolved identity information for downstream
Transform/Load stages.

For V1 sources:
- daily_attendance: resolve student_id, subject_id, faculty_id, enrollment_record_id
- weekly_timetable: resolve subject_id, faculty_id

Unresolvable records are quarantined with a clear reason — never silently
dropped (P6, plan `02` §5.1). No fuzzy matching — V1 sources carry canonical
identifiers directly (plan `02` §5.3).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

import asyncpg

from etl.result import StageResult
from etl.stages import STAGE_STITCH, Stage
from etl.stages.stage import StagedRecord
from etl.validation import QuarantineRecord

REASON_STUDENT_NOT_FOUND = "student_not_found"
REASON_SUBJECT_NOT_FOUND = "subject_not_found"
REASON_FACULTY_NOT_FOUND = "faculty_not_found"
REASON_ENROLLMENT_NOT_FOUND = "enrollment_not_found"
REASON_MULTIPLE_ENROLLMENTS = "multiple_enrollments"


@dataclass(frozen=True)
class ResolvedIdentities:
    """Which canonical entities were successfully resolved for a stitched record."""

    student: bool = False
    subject: bool = False
    faculty: bool = False
    enrollment: bool = False

    @property
    def all_resolved(self) -> bool:
        return self.student and self.subject and self.faculty and self.enrollment

    def to_dict(self) -> Dict[str, bool]:
        return {
            "student": self.student,
            "subject": self.subject,
            "faculty": self.faculty,
            "enrollment": self.enrollment,
        }


@dataclass(frozen=True)
class StitchedRecord:
    """A staged record with resolved canonical identity information.

    Attributes:
        source: The source key (e.g. ``daily_attendance``, ``weekly_timetable``).
        run_id: The pipeline run identifier this record belongs to.
        row_index: Original 1-based line number from the source file.
        row: The staged row data (dict), preserved unchanged.
        enrollment_record_id: Resolved enrollment ID (attendance only, ``None``
            for timetable or when resolution failed).
        resolved: Which canonical identities were successfully resolved.
    """

    source: str
    run_id: str
    row_index: int
    row: Dict[str, str]
    enrollment_record_id: Optional[str] = None
    resolved: ResolvedIdentities = field(default_factory=ResolvedIdentities)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "run_id": self.run_id,
            "row_index": self.row_index,
            "row": dict(self.row),
            "enrollment_record_id": self.enrollment_record_id,
            "resolved": self.resolved.to_dict(),
        }


class StitchStage(Stage):
    """Resolve staged records against canonical master data in PostgreSQL.

    Reads from ``shared["staged"]`` (produced by Stage) and publishes into
    ``shared["stitched"]``.  Read-only — never touches the database for writes.
    """

    name = STAGE_STITCH
    description = (
        "Resolve staged records against canonical master data "
        "(plan 02 §3.3, read-only)."
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
        staged: Dict[str, List[StagedRecord]] = dict(
            self._shared.get("staged") or {}
        )
        if not staged:
            return StageResult(stage=self.name, rows_read=0, rows_accepted=0)

        sources_to_stitch = (
            self._sources if self._sources else tuple(staged.keys())
        )

        students, subjects, faculty, enrollments = await self._load_master_data(pool)
        semester_no = str(context.counters.get("semester_no", "7"))

        stitched: Dict[str, List[StitchedRecord]] = {}
        quarantined: Dict[str, List[QuarantineRecord]] = {}
        rows_read = 0
        rows_accepted = 0
        rows_rejected = 0

        for source_key in sources_to_stitch:
            records = staged.get(source_key)
            if records is None:
                continue

            stitched_records: List[StitchedRecord] = []
            quarantine_records: List[QuarantineRecord] = []

            for record in records:
                row = record.row
                if source_key == "daily_attendance":
                    result = self._stitch_attendance(
                        record, context.run_id, students, subjects, faculty,
                        enrollments, semester_no,
                    )
                else:
                    result = self._stitch_timetable(
                        record, context.run_id, students, subjects, faculty,
                    )

                if isinstance(result, StitchedRecord):
                    stitched_records.append(result)
                else:
                    quarantine_records.append(result)

            stitched[source_key] = stitched_records
            quarantined[source_key] = quarantine_records
            rows_read += len(records)
            rows_accepted += len(stitched_records)
            rows_rejected += len(quarantine_records)

        self._shared["stitched"] = stitched
        self._shared["stitch_quarantine"] = quarantined

        result = StageResult(
            stage=self.name,
            rows_read=rows_read,
            rows_accepted=rows_accepted,
            rows_rejected=rows_rejected,
        )
        result.metadata["source_keys"] = list(sources_to_stitch)
        result.metadata["stitched_counts"] = {
            key: len(records) for key, records in stitched.items()
        }
        result.metadata["quarantine_counts"] = {
            key: len(records) for key, records in quarantined.items()
        }
        result.metadata["run_id"] = context.run_id
        return result

    async def _load_master_data(
        self, pool: Optional[asyncpg.Pool]
    ) -> tuple:
        """Load master/bridge data for identity resolution."""
        students: Set[str] = set()
        subjects: Set[str] = set()
        faculty: Set[str] = set()
        enrollments: List[asyncpg.Record] = []

        if pool is None:
            return students, subjects, faculty, enrollments

        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT student_id FROM students")
            students = {row["student_id"] for row in rows}

            rows = await conn.fetch("SELECT subject_id FROM subjects")
            subjects = {row["subject_id"] for row in rows}

            rows = await conn.fetch("SELECT faculty_id FROM faculty")
            faculty = {row["faculty_id"] for row in rows}

            rows = await conn.fetch(
                "SELECT enrollment_record_id, student_id, subject_id, semester_no "
                "FROM student_subject_enrollment"
            )
            enrollments = list(rows)

        return students, subjects, faculty, enrollments

    def _stitch_attendance(
        self,
        record: StagedRecord,
        run_id: str,
        students: Set[str],
        subjects: Set[str],
        faculty: Set[str],
        enrollments: List[asyncpg.Record],
        semester_no: str,
    ) -> Any:
        """Resolve a single attendance record against master data."""
        row = record.row
        student_id = row.get("student_id", "")
        subject_id = row.get("subject_id", "")
        faculty_id = row.get("faculty_id", "")

        if student_id not in students:
            return self._quarantine(
                run_id, record, REASON_STUDENT_NOT_FOUND,
                f"student_id '{student_id}' not found in students",
                {"student_id": student_id},
            )

        if subject_id not in subjects:
            return self._quarantine(
                run_id, record, REASON_SUBJECT_NOT_FOUND,
                f"subject_id '{subject_id}' not found in subjects",
                {"subject_id": subject_id},
            )

        if faculty_id not in faculty:
            return self._quarantine(
                run_id, record, REASON_FACULTY_NOT_FOUND,
                f"faculty_id '{faculty_id}' not found in faculty",
                {"faculty_id": faculty_id},
            )

        matching = [
            e for e in enrollments
            if e["student_id"] == student_id
            and e["subject_id"] == subject_id
            and str(e["semester_no"]) == semester_no
        ]

        if not matching:
            return self._quarantine(
                run_id, record, REASON_ENROLLMENT_NOT_FOUND,
                f"no enrollment found for student={student_id} subject={subject_id} "
                f"semester={semester_no}",
                {"student_id": student_id, "subject_id": subject_id,
                 "semester_no": semester_no},
            )

        if len(matching) > 1:
            return self._quarantine(
                run_id, record, REASON_MULTIPLE_ENROLLMENTS,
                f"multiple enrollments for student={student_id} subject={subject_id} "
                f"semester={semester_no}: {[e['enrollment_record_id'] for e in matching]}",
                {"student_id": student_id, "subject_id": subject_id,
                 "semester_no": semester_no,
                 "enrollment_record_ids": [e["enrollment_record_id"] for e in matching]},
            )

        enrollment_id = matching[0]["enrollment_record_id"]

        return StitchedRecord(
            source=record.source,
            run_id=run_id,
            row_index=record.row_index,
            row=record.row,
            enrollment_record_id=enrollment_id,
            resolved=ResolvedIdentities(
                student=True, subject=True, faculty=True, enrollment=True,
            ),
        )

    def _stitch_timetable(
        self,
        record: StagedRecord,
        run_id: str,
        students: Set[str],
        subjects: Set[str],
        faculty: Set[str],
    ) -> Any:
        """Resolve a single timetable record against master data."""
        row = record.row
        subject_id = row.get("subject_id", "")
        faculty_id = row.get("faculty_id", "")

        if subject_id not in subjects:
            return self._quarantine(
                run_id, record, REASON_SUBJECT_NOT_FOUND,
                f"subject_id '{subject_id}' not found in subjects",
                {"subject_id": subject_id},
            )

        if faculty_id not in faculty:
            return self._quarantine(
                run_id, record, REASON_FACULTY_NOT_FOUND,
                f"faculty_id '{faculty_id}' not found in faculty",
                {"faculty_id": faculty_id},
            )

        return StitchedRecord(
            source=record.source,
            run_id=run_id,
            row_index=record.row_index,
            row=record.row,
            resolved=ResolvedIdentities(
                student=False, subject=True, faculty=True, enrollment=False,
            ),
        )

    @staticmethod
    def _quarantine(
        run_id: str,
        record: StagedRecord,
        reason_code: str,
        reason: str,
        keys: Dict[str, str],
    ) -> QuarantineRecord:
        """Build a quarantine record for an unresolvable staged row."""
        return QuarantineRecord(
            run_id=run_id,
            stage=STAGE_STITCH,
            source=record.source,
            row_index=record.row_index,
            reason_code=reason_code,
            reason=reason,
            keys=keys,
            offending_values={k: v for k, v in record.row.items() if k in keys},
            raw=record.row,
        )
