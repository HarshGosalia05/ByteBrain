"""Validate: schema / integrity / domain / uniqueness checks with quarantine.

Implements the plan `03` §3.3 validation checklist for the two locked V1
sources (``daily_attendance_cse_sem7.csv``, ``weekly_timetable_cse_sem7.csv``)
plus the cross-dataset relationship checks of plan `02` §8 (subject_name
agreement, timetable coherence). Every check is a deterministic function of the
record + scope configuration — never of run metadata or row order (P2).

Failure discipline (plan `03` §4.2):
- Rows failing a check are quarantined with ``run_id, stage, reason_code, row
  identity, offending values, raw row`` — never silently dropped.
- Whole-source schema failures (missing required columns) fail loud with
  ``EtlValidationError`` (plan `03` §3.3: "fail if whole-source").
- The quarantined ratio per source is compared against
  ``ETL_MAX_QUARANTINE_RATIO``; exceeding it fails the run (exit 1).

Referential checks against the live masters (``students``/``subjects``/
``faculty``) are the Stitch stage's concern (plan `02` §3.3) and are not part
of this slice — membership here is checked against the locked scope
configuration and the timetable dataset graph, both deterministic and DB-free.
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from etl.config import EtlConfig, etl_config
from etl.exceptions import EtlValidationError
from etl.keys import (
    ATTENDANCE_ROW_KEY_FIELDS,
    LECTURE_SESSION_KEY_FIELDS,
    business_key,
    business_key_str,
)

REASON_MISSING_COLUMN = "missing_column"
REASON_NULL_REQUIRED = "null_required"
REASON_INVALID_STUDENT_ID = "invalid_student_id"
REASON_INVALID_SUBJECT_ID = "invalid_subject_id"
REASON_INVALID_FACULTY_ID = "invalid_faculty_id"
REASON_INVALID_ENROLLMENT_NO = "invalid_enrollment_no"
REASON_INVALID_ACADEMIC_YEAR = "invalid_academic_year"
REASON_INVALID_DATE = "invalid_date"
REASON_INVALID_LECTURE_NUMBER = "invalid_lecture_number"
REASON_INVALID_STATUS = "invalid_status"
REASON_INVALID_TIMETABLE_ID = "invalid_timetable_id"
REASON_INVALID_SLOT = "invalid_slot"
REASON_INVALID_TIME = "invalid_time"
REASON_INVALID_LECTURE_TYPE = "invalid_lecture_type"
REASON_WRONG_SCOPE = "wrong_scope"
REASON_DAY_MISMATCH = "day_mismatch"
REASON_TIMETABLE_MISMATCH = "timetable_mismatch"
REASON_SUBJECT_NAME_MISMATCH = "subject_name_mismatch"
REASON_DUPLICATE_SESSION = "duplicate_session"
REASON_DUPLICATE_ROW = "duplicate_row"
REASON_DUPLICATE_SLOT = "duplicate_slot"
REASON_DUPLICATE_TIMETABLE_ID = "duplicate_timetable_id"

ATTENDANCE_REQUIRED_COLUMNS = (
    "attendance_id",
    "student_id",
    "enrollment_no",
    "subject_id",
    "subject_name",
    "faculty_id",
    "lecture_date",
    "lecture_number",
    "day_name",
    "department_code",
    "semester_no",
    "academic_year",
    "attendance_status",
)

TIMETABLE_REQUIRED_COLUMNS = (
    "timttable_id",
    "department_code",
    "semester_no",
    "academic_year",
    "day_name",
    "slot_no",
    "start_time",
    "end_time",
    "subject_id",
    "subject_name",
    "faculty_id",
    "lecture_type",
)

VALID_ATTENDANCE_STATUSES = frozenset({"P", "A"})
VALID_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
VALID_SLOTS = frozenset({"1", "2", "3"})
VALID_LECTURE_TYPES = frozenset({"Theory", "Lab"})
_INTEGER_PATTERN = re.compile(r"^\d+$")

# Reconciliation expectations verified in plan `03` §3.1. Violations are
# completeness warnings (flag -> reconcile, plan `03` §3.3), never quarantines.
EXPECTED_ATTENDANCE_STUDENTS = 50
EXPECTED_ATTENDANCE_SUBJECT_PAIRS = 350
EXPECTED_ATTENDANCE_LECTURES = 123
EXPECTED_STUDENTS_PER_LECTURE = 50
EXPECTED_TIMETABLE_ROWS = 15


@dataclass(frozen=True)
class Scope:
    """Run scope from configuration (plan `01` §8, `02` §1.2).

    The base identity fields (student_id_pattern / enrollment_no_pattern /
    student_id_min..max) are the V1 locked scope and remain the ONLY accepted
    namespace when the extra namespace fields are empty (Task 2 cohort-aware
    defaults — V1 unchanged). Each extra enrolment/student namespace tuple is
    ``(pattern, min, max)`` where ``min``/``max`` may be ``""`` (unbounded on
    that side). An id is accepted when it matches ANY registered namespace and
    lies within that namespace's range.
    """

    department_code: str
    semester_no: str
    academic_year: str
    student_id_pattern: str
    subject_id_pattern: str
    faculty_id_pattern: str
    enrollment_no_pattern: str
    student_id_min: str
    student_id_max: str
    # Academic-year format pattern, cohort-aware (configuration, never a regex
    # hardcoded in stage code). Default accepts both the locked V1 "YYYY-YYYY"
    # form and earlier-cohort "YYYY-YY" forms, so direct construction (tests)
    # remains backward-compatible; from_config always supplies an explicit value.
    academic_year_pattern: str = r"^\d{4}-(\d{2}|\d{4})$"
    student_id_namespaces_extra: Tuple[Tuple[str, str, str], ...] = ()
    enrollment_no_namespaces_extra: Tuple[Tuple[str, str, str], ...] = ()

    @classmethod
    def from_config(cls, config: Optional[EtlConfig] = None) -> "Scope":
        cfg = config or etl_config
        return cls(
            department_code=str(cfg.ETL_DEPARTMENT_CODE),
            semester_no=str(cfg.ETL_SEMESTER_NO),
            academic_year=cfg.ETL_ACADEMIC_YEAR,
            academic_year_pattern=cfg.ETL_ACADEMIC_YEAR_PATTERN,
            student_id_pattern=cfg.ETL_STUDENT_ID_PATTERN,
            subject_id_pattern=cfg.ETL_SUBJECT_ID_PATTERN,
            faculty_id_pattern=cfg.ETL_FACULTY_ID_PATTERN,
            enrollment_no_pattern=cfg.ETL_ENROLLMENT_NO_PATTERN,
            student_id_min=cfg.ETL_STUDENT_ID_MIN,
            student_id_max=cfg.ETL_STUDENT_ID_MAX,
            student_id_namespaces_extra=_parse_id_namespaces(
                cfg.ETL_STUDENT_ID_NAMESPACES_EXTRA
            ),
            enrollment_no_namespaces_extra=_parse_enrollment_namespaces(
                cfg.ETL_ENROLLMENT_NO_PATTERNS_EXTRA
            ),
        )


def _parse_id_namespaces(
    specs: Sequence[str],
) -> Tuple[Tuple[str, str, str], ...]:
    """Parse "pattern|min|max" config entries into (pattern, min, max) tuples.

    min/max are optional; missing parts become "" (unbounded). Kept read-only
    and deterministic (Task 2: cohort-aware namespaces are configuration, not
    hardcoded regexes).
    """
    namespaces: List[Tuple[str, str, str]] = []
    for spec in specs or ():
        parts = spec.split("|")
        pattern = parts[0].strip()
        if not pattern:
            raise ValueError(f"empty pattern in ETL_STUDENT_ID_NAMESPACES_EXTRA: {spec!r}")
        lo = parts[1].strip() if len(parts) > 1 else ""
        hi = parts[2].strip() if len(parts) > 2 else ""
        namespaces.append((pattern, lo, hi))
    return tuple(namespaces)


def _parse_enrollment_namespaces(
    specs: Sequence[str],
) -> Tuple[Tuple[str, str, str], ...]:
    """Parse plain anchored enrollment patterns into (pattern, "", "") tuples."""
    return tuple((spec.strip(), "", "") for spec in (specs or ()) if spec.strip())


def _student_id_in_scope(sid: str, scope: Scope) -> bool:
    """True when ``sid`` matches the base namespace or any extra namespace."""
    if re.fullmatch(scope.student_id_pattern, sid) and (
        scope.student_id_min <= sid <= scope.student_id_max
    ):
        return True
    for pattern, lo, hi in scope.student_id_namespaces_extra:
        if not re.fullmatch(pattern, sid):
            continue
        if lo and sid < lo:
            continue
        if hi and sid > hi:
            continue
        return True
    return False


def _enrollment_no_in_scope(enr: str, scope: Scope) -> bool:
    """True when ``enr`` matches the base namespace or any extra namespace."""
    if re.fullmatch(scope.enrollment_no_pattern, enr):
        return True
    for pattern, lo, hi in scope.enrollment_no_namespaces_extra:
        if re.fullmatch(pattern, enr):
            if lo and enr < lo:
                continue
            if hi and enr > hi:
                continue
            return True
    return False


def valid_academic_year(value: str, scope: Scope) -> bool:
    """True when ``value`` matches the configured academic-year format.

    Cohort-aware: derives the accepted format from ``scope.academic_year_pattern``
    (configuration, never a hardcoded regex in stage code). Accepts the locked V1
    "YYYY-YYYY" form and earlier-cohort "YYYY-YY" forms per the default pattern.
    """
    if value is None:
        return False
    return re.fullmatch(scope.academic_year_pattern, str(value).strip()) is not None


@dataclass(frozen=True)
class TimetableReference:
    """Cross-dataset relationship graph derived from the timetable rows.

    The plan `02` §4.2 "relationship contract": the subjects / faculties in
    scope, their canonical subject names, and the (day -> {subject, faculty})
    session map used for timetable-coherence checks.
    """

    subjects: frozenset
    faculties: frozenset
    subject_names: Dict[str, str]
    day_sessions: Dict[str, frozenset]
    day_subjects: Dict[str, frozenset]

    @classmethod
    def from_rows(cls, rows: Sequence[Dict[str, str]]) -> "TimetableReference":
        subjects: set = set()
        faculties: set = set()
        subject_names: Dict[str, str] = {}
        day_sessions: Dict[str, set] = defaultdict(set)
        day_subjects: Dict[str, set] = defaultdict(set)
        for row in rows:
            subjects.add(row["subject_id"])
            faculties.add(row["faculty_id"])
            subject_names[row["subject_id"]] = row["subject_name"]
            day_sessions[row["day_name"]].add((row["subject_id"], row["faculty_id"]))
            day_subjects[row["day_name"]].add(row["subject_id"])
        return cls(
            subjects=frozenset(subjects),
            faculties=frozenset(faculties),
            subject_names=dict(subject_names),
            day_sessions={day: frozenset(sessions) for day, sessions in day_sessions.items()},
            day_subjects={day: frozenset(subjects_) for day, subjects_ in day_subjects.items()},
        )


@dataclass(frozen=True)
class QuarantineRecord:
    """One quarantined row with its full audit context (plan `03` §4.2)."""

    run_id: str
    stage: str
    source: str
    row_index: int
    reason_code: str
    reason: str
    keys: Dict[str, str]
    offending_values: Dict[str, str]
    raw: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "stage": self.stage,
            "source": self.source,
            "row_index": self.row_index,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "keys": dict(self.keys),
            "offending_values": dict(self.offending_values),
            "raw": dict(self.raw),
        }


@dataclass
class ValidationOutcome:
    """Result of validating one source: accepted rows + quarantine records."""

    source: str
    accepted: List[Dict[str, str]]
    quarantined: List[QuarantineRecord]
    warnings: List[str] = field(default_factory=list)
    rule_counts: Dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.accepted) + len(self.quarantined)

    @property
    def quarantine_ratio(self) -> float:
        if self.total == 0:
            return 0.0
        return len(self.quarantined) / self.total


def _check_schema(
    rows: Sequence[Dict[str, str]],
    required_columns: Sequence[str],
    source: str,
    stage: str,
) -> None:
    if not rows:
        raise EtlValidationError(f"source '{source}' has no data rows to validate")
    present = set(rows[0].keys())
    missing = [column for column in required_columns if column not in present]
    if missing:
        raise EtlValidationError(
            f"source '{source}' failed schema validation (stage '{stage}'): "
            f"missing required columns: {', '.join(missing)}"
        )


def _parse_iso_date(value: str) -> Optional[datetime.date]:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _parse_time(value: str) -> Optional[datetime.time]:
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value, fmt).time()
        except (ValueError, TypeError):
            continue
    return None


def _make_record(
    run_id: str,
    stage: str,
    source: str,
    row_index: int,
    reason_code: str,
    reason: str,
    keys: Dict[str, str],
    offending: Dict[str, str],
    raw: Dict[str, str],
) -> QuarantineRecord:
    return QuarantineRecord(
        run_id=run_id,
        stage=stage,
        source=source,
        row_index=row_index,
        reason_code=reason_code,
        reason=reason,
        keys=keys,
        offending_values=offending,
        raw=raw,
    )


def assert_within_quarantine_ratio(
    ratio: float,
    max_ratio: float,
    source: str = "source",
) -> None:
    """Fail loud when a source's quarantined ratio exceeds the configured gate."""
    if ratio > max_ratio:
        raise EtlValidationError(
            f"source '{source}' quarantine ratio {ratio:.4f} exceeds "
            f"ETL_MAX_QUARANTINE_RATIO {max_ratio:.4f}"
        )


def _check_attendance_row(
    row: Dict[str, str],
    line_no: int,
    scope: Scope,
    ref: Optional[TimetableReference],
    stage: str,
    run_id: str,
) -> Optional[QuarantineRecord]:
    failures: List[Tuple[str, str, Dict[str, str]]] = []

    def fail(code: str, message: str, offending: Dict[str, str]) -> None:
        failures.append((code, message, offending))

    sid = (row.get("student_id") or "").strip()
    subj = (row.get("subject_id") or "").strip()
    fac = (row.get("faculty_id") or "").strip()
    date_s = (row.get("lecture_date") or "").strip()
    lec = (row.get("lecture_number") or "").strip()
    day = (row.get("day_name") or "").strip()
    status = (row.get("attendance_status") or "").strip()
    enr = (row.get("enrollment_no") or "").strip()

    for name, value in (
        ("student_id", sid),
        ("subject_id", subj),
        ("faculty_id", fac),
        ("lecture_date", date_s),
        ("lecture_number", lec),
        ("day_name", day),
    ):
        if value == "":
            fail(REASON_NULL_REQUIRED, f"required key {name} is null", {name: row.get(name)})

    if sid:
        if not _student_id_in_scope(sid, scope):
            fail(
                REASON_INVALID_STUDENT_ID,
                f"student_id '{sid}' outside locked cohort-aware scope "
                f"{scope.student_id_pattern} {scope.student_id_min}..{scope.student_id_max} "
                f"(incl. {len(scope.student_id_namespaces_extra)} extra namespace(s))",
                {"student_id": row.get("student_id")},
            )
    if enr and not _enrollment_no_in_scope(enr, scope):
        fail(
            REASON_INVALID_ENROLLMENT_NO,
            f"enrollment_no '{enr}' does not match {scope.enrollment_no_pattern} "
            f"(incl. {len(scope.enrollment_no_namespaces_extra)} extra namespace(s))",
            {"enrollment_no": row.get("enrollment_no")},
        )
    if subj:
        if not re.fullmatch(scope.subject_id_pattern, subj):
            fail(
                REASON_INVALID_SUBJECT_ID,
                f"subject_id '{subj}' does not match {scope.subject_id_pattern}",
                {"subject_id": row.get("subject_id")},
            )
        elif ref is not None and subj not in ref.subjects:
            fail(
                REASON_INVALID_SUBJECT_ID,
                f"subject_id '{subj}' not present in weekly_timetable reference",
                {"subject_id": row.get("subject_id")},
            )
    if fac:
        if not re.fullmatch(scope.faculty_id_pattern, fac):
            fail(
                REASON_INVALID_FACULTY_ID,
                f"faculty_id '{fac}' does not match {scope.faculty_id_pattern}",
                {"faculty_id": row.get("faculty_id")},
            )
        elif ref is not None and fac not in ref.faculties:
            fail(
                REASON_INVALID_FACULTY_ID,
                f"faculty_id '{fac}' not present in weekly_timetable reference",
                {"faculty_id": row.get("faculty_id")},
            )
    parsed_date = None
    if date_s:
        parsed_date = _parse_iso_date(date_s)
        if parsed_date is None:
            fail(
                REASON_INVALID_DATE,
                f"lecture_date '{date_s}' is not a valid ISO date (YYYY-MM-DD)",
                {"lecture_date": row.get("lecture_date")},
            )
    if lec:
        if not _INTEGER_PATTERN.fullmatch(lec) or int(lec) < 1:
            fail(
                REASON_INVALID_LECTURE_NUMBER,
                f"lecture_number '{lec}' must be a positive integer",
                {"lecture_number": row.get("lecture_number")},
            )
    if status and status not in VALID_ATTENDANCE_STATUSES:
        fail(
            REASON_INVALID_STATUS,
            f"attendance_status '{status}' must be one of P, A",
            {"attendance_status": row.get("attendance_status")},
        )
    if day:
        if day not in VALID_DAYS:
            fail(
                REASON_DAY_MISMATCH,
                f"day_name '{day}' is not a valid teaching day",
                {"day_name": row.get("day_name")},
            )
        elif parsed_date is not None:
            actual = parsed_date.strftime("%A")
            if actual != day:
                fail(
                    REASON_DAY_MISMATCH,
                    f"day_name '{day}' does not match {date_s} ({actual})",
                    {"day_name": row.get("day_name"), "lecture_date": row.get("lecture_date")},
                )
    dept_ok = str(row.get("department_code")) == scope.department_code
    sem_ok = str(row.get("semester_no")) == scope.semester_no
    ay_ok = str(row.get("academic_year")) == scope.academic_year
    if not (dept_ok and sem_ok and ay_ok):
        fail(
            REASON_WRONG_SCOPE,
            f"row scope ({row.get('department_code')},{row.get('semester_no')},"
            f"{row.get('academic_year')}) does not match run scope "
            f"({scope.department_code},{scope.semester_no},{scope.academic_year})",
            {
                "department_code": row.get("department_code"),
                "semester_no": row.get("semester_no"),
                "academic_year": row.get("academic_year"),
            },
        )
    if ref is not None and day in VALID_DAYS:
        sessions = ref.day_sessions.get(day, frozenset())
        if (subj, fac) not in sessions:
            fail(
                REASON_TIMETABLE_MISMATCH,
                f"subject {subj} / faculty {fac} has no lecture session on {day} "
                "per weekly_timetable",
                {"subject_id": row.get("subject_id"), "faculty_id": row.get("faculty_id"),
                 "day_name": row.get("day_name")},
            )
    if ref is not None and subj in ref.subject_names and row.get("subject_name") != ref.subject_names[subj]:
        fail(
            REASON_SUBJECT_NAME_MISMATCH,
            f"subject_name '{row.get('subject_name')}' disagrees with weekly_timetable "
            f"'{ref.subject_names[subj]}' for {subj}",
            {"subject_name": row.get("subject_name")},
        )

    if not failures:
        return None
    code, message, offending = failures[0]
    keys = {k: row.get(k) for k in ATTENDANCE_ROW_KEY_FIELDS}
    return _make_record(run_id, stage, "daily_attendance", line_no, code, message, keys, offending, row)


def _apply_attendance_uniqueness(
    indexed: List[Tuple[int, Dict[str, str]]],
    rule_counts: Counter,
    run_id: str,
    stage: str,
) -> Tuple[List[Tuple[int, Dict[str, str]]], List[QuarantineRecord]]:
    """Deterministic duplicate detection (plan `02` §4.3).

    A lecture session legitimately has one row per student, so the two locked
    uniqueness checks are:

    1. **Attendance-row key** ``(student_id, subject_id, lecture_date,
       lecture_number)`` — a specific student recorded twice for the same
       lecture is a duplicate row (plan `02` §2.1).
    2. **Lecture session key** ``(subject_id, lecture_date, lecture_number)``
       — a session recorded with more than the expected one row per student
       means the same lecture was recorded twice (plan `02` §4.3, §8 rule 4),
       which would silently inflate ``total_classes``.

    Both passes order by business key with the source line number as tie-break,
    so kept-vs-duplicate is a pure function of the source file, never of row
    order (P2).
    """
    ordered_rows = sorted(
        indexed,
        key=lambda ln_row: (business_key_str(ln_row[1], ATTENDANCE_ROW_KEY_FIELDS), ln_row[0]),
    )
    seen_rows: set = set()
    row_kept: List[Tuple[int, Dict[str, str]]] = []
    duplicate_rows: List[Tuple[int, Dict[str, str]]] = []
    for line_no, row in ordered_rows:
        key = business_key(row, ATTENDANCE_ROW_KEY_FIELDS)
        if key in seen_rows:
            duplicate_rows.append((line_no, row))
        else:
            seen_rows.add(key)
            row_kept.append((line_no, row))

    sessions: Dict[Tuple[Any, ...], List[Tuple[int, Dict[str, str]]]] = defaultdict(list)
    for line_no, row in row_kept:
        sessions[business_key(row, LECTURE_SESSION_KEY_FIELDS)].append((line_no, row))

    kept: List[Tuple[int, Dict[str, str]]] = []
    duplicate_sessions: List[Tuple[int, Dict[str, str]]] = []
    for members in sessions.values():
        members.sort(key=lambda ln_row: ln_row[0])
        if len(members) > EXPECTED_STUDENTS_PER_LECTURE:
            kept.extend(members[:EXPECTED_STUDENTS_PER_LECTURE])
            duplicate_sessions.extend(members[EXPECTED_STUDENTS_PER_LECTURE:])
        else:
            kept.extend(members)
    kept.sort(key=lambda ln_row: ln_row[0])

    records: List[QuarantineRecord] = []
    for line_no, row in duplicate_rows:
        rule_counts[REASON_DUPLICATE_ROW] += 1
        keys = {k: row.get(k) for k in ATTENDANCE_ROW_KEY_FIELDS}
        offending = {k: row.get(k) for k in ATTENDANCE_ROW_KEY_FIELDS}
        records.append(_make_record(
            run_id, stage, "daily_attendance", line_no, REASON_DUPLICATE_ROW,
            "duplicate attendance row (student_id, subject_id, lecture_date, lecture_number)",
            keys, offending, row,
        ))
    for line_no, row in duplicate_sessions:
        rule_counts[REASON_DUPLICATE_SESSION] += 1
        keys = {k: row.get(k) for k in ATTENDANCE_ROW_KEY_FIELDS}
        offending = {k: row.get(k) for k in LECTURE_SESSION_KEY_FIELDS}
        records.append(_make_record(
            run_id, stage, "daily_attendance", line_no, REASON_DUPLICATE_SESSION,
            f"lecture session recorded more than once (more than "
            f"{EXPECTED_STUDENTS_PER_LECTURE} students for the same session key)",
            keys, offending, row,
        ))
    return kept, records


def validate_attendance(
    rows: Sequence[Dict[str, str]],
    *,
    line_numbers: Optional[Sequence[int]] = None,
    run_id: str,
    scope: Optional[Scope] = None,
    stage: str = "validate",
    timetable_ref: Optional[TimetableReference] = None,
) -> ValidationOutcome:
    """Validate daily-attendance rows; return accepted rows + quarantine."""
    scope = scope or Scope.from_config()
    _check_schema(rows, ATTENDANCE_REQUIRED_COLUMNS, "daily_attendance", stage)
    if line_numbers is None:
        line_numbers = list(range(1, len(rows) + 1))

    accepted: List[Tuple[int, Dict[str, str]]] = []
    quarantined: List[QuarantineRecord] = []
    rule_counts: Counter = Counter()

    for line_no, row in zip(line_numbers, rows):
        record = _check_attendance_row(row, line_no, scope, timetable_ref, stage, run_id)
        if record is not None:
            quarantined.append(record)
            rule_counts[record.reason_code] += 1
        else:
            accepted.append((line_no, row))

    kept, duplicate_records = _apply_attendance_uniqueness(accepted, rule_counts, run_id, stage)
    quarantined.extend(duplicate_records)

    warnings: List[str] = []
    cleaned = [row for _, row in kept]
    if cleaned:
        distinct_students = {r["student_id"] for r in cleaned}
        if len(distinct_students) != EXPECTED_ATTENDANCE_STUDENTS:
            warnings.append(
                f"completeness: distinct students {len(distinct_students)} != "
                f"expected {EXPECTED_ATTENDANCE_STUDENTS}"
            )
        pairs = {(r["student_id"], r["subject_id"]) for r in cleaned}
        if len(pairs) != EXPECTED_ATTENDANCE_SUBJECT_PAIRS:
            warnings.append(
                f"completeness: distinct (student, subject) pairs {len(pairs)} != "
                f"expected {EXPECTED_ATTENDANCE_SUBJECT_PAIRS}"
            )
        sessions = {(r["subject_id"], r["lecture_date"], r["lecture_number"]) for r in cleaned}
        if len(sessions) != EXPECTED_ATTENDANCE_LECTURES:
            warnings.append(
                f"completeness: distinct lectures {len(sessions)} != "
                f"expected {EXPECTED_ATTENDANCE_LECTURES}"
            )
        per_session: Counter = Counter(
            (r["subject_id"], r["lecture_date"], r["lecture_number"]) for r in cleaned
        )
        uneven = {k: v for k, v in per_session.items() if v != EXPECTED_STUDENTS_PER_LECTURE}
        if uneven:
            warnings.append(
                f"completeness: {len(uneven)} lecture session(s) do not have "
                f"{EXPECTED_STUDENTS_PER_LECTURE} students (plan `03` §3.3 flag -> reconcile)"
            )

    quarantined.sort(key=lambda q: (q.row_index, q.reason_code))
    return ValidationOutcome(
        source="daily_attendance",
        accepted=cleaned,
        quarantined=quarantined,
        warnings=warnings,
        rule_counts=dict(rule_counts),
    )


def _check_timetable_row(
    row: Dict[str, str],
    line_no: int,
    scope: Scope,
    stage: str,
    run_id: str,
    subjects: frozenset,
    faculties: frozenset,
) -> Optional[QuarantineRecord]:
    failures: List[Tuple[str, str, Dict[str, str]]] = []

    def fail(code: str, message: str, offending: Dict[str, str]) -> None:
        failures.append((code, message, offending))

    tt_id = (row.get("timttable_id") or "").strip()
    subj = (row.get("subject_id") or "").strip()
    fac = (row.get("faculty_id") or "").strip()
    slot = (row.get("slot_no") or "").strip()
    day = (row.get("day_name") or "").strip()
    start = (row.get("start_time") or "").strip()
    end = (row.get("end_time") or "").strip()
    name = (row.get("subject_name") or "").strip()
    ltype = (row.get("lecture_type") or "").strip()

    for field_name, value in (
        ("timttable_id", tt_id),
        ("subject_id", subj),
        ("faculty_id", fac),
        ("slot_no", slot),
        ("day_name", day),
        ("start_time", start),
        ("end_time", end),
        ("subject_name", name),
    ):
        if value == "":
            fail(REASON_NULL_REQUIRED, f"required value {field_name} is null", {field_name: row.get(field_name)})

    if tt_id and (not _INTEGER_PATTERN.fullmatch(tt_id) or int(tt_id) < 1):
        fail(
            REASON_INVALID_TIMETABLE_ID,
            f"timttable_id '{tt_id}' must be a positive integer",
            {"timttable_id": row.get("timttable_id")},
        )
    dept_ok = str(row.get("department_code")) == scope.department_code
    sem_ok = str(row.get("semester_no")) == scope.semester_no
    ay_ok = str(row.get("academic_year")) == scope.academic_year
    if not (dept_ok and sem_ok and ay_ok):
        fail(
            REASON_WRONG_SCOPE,
            f"row scope ({row.get('department_code')},{row.get('semester_no')},"
            f"{row.get('academic_year')}) does not match run scope "
            f"({scope.department_code},{scope.semester_no},{scope.academic_year})",
            {
                "department_code": row.get("department_code"),
                "semester_no": row.get("semester_no"),
                "academic_year": row.get("academic_year"),
            },
        )
    if day and day not in VALID_DAYS:
        fail(
            REASON_DAY_MISMATCH,
            f"day_name '{day}' is not a valid teaching day",
            {"day_name": row.get("day_name")},
        )
    if slot and slot not in VALID_SLOTS:
        fail(
            REASON_INVALID_SLOT,
            f"slot_no '{slot}' must be one of {sorted(VALID_SLOTS)}",
            {"slot_no": row.get("slot_no")},
        )
    if start or end:
        start_t = _parse_time(start) if start else None
        end_t = _parse_time(end) if end else None
        if start and start_t is None:
            fail(REASON_INVALID_TIME, f"start_time '{start}' is not a valid HH:MM[:SS] time",
                 {"start_time": row.get("start_time")})
        if end and end_t is None:
            fail(REASON_INVALID_TIME, f"end_time '{end}' is not a valid HH:MM[:SS] time",
                 {"end_time": row.get("end_time")})
        if start_t is not None and end_t is not None and start_t >= end_t:
            fail(REASON_INVALID_TIME, f"start_time {start} is not before end_time {end}",
                 {"start_time": row.get("start_time"), "end_time": row.get("end_time")})
    if subj:
        if not re.fullmatch(scope.subject_id_pattern, subj):
            fail(REASON_INVALID_SUBJECT_ID, f"subject_id '{subj}' does not match {scope.subject_id_pattern}",
                 {"subject_id": row.get("subject_id")})
        elif subj not in subjects:
            fail(REASON_INVALID_SUBJECT_ID, f"subject_id '{subj}' is not a known subject in this timetable",
                 {"subject_id": row.get("subject_id")})
    if fac:
        if not re.fullmatch(scope.faculty_id_pattern, fac):
            fail(REASON_INVALID_FACULTY_ID, f"faculty_id '{fac}' does not match {scope.faculty_id_pattern}",
                 {"faculty_id": row.get("faculty_id")})
        elif fac not in faculties:
            fail(REASON_INVALID_FACULTY_ID, f"faculty_id '{fac}' is not a known faculty in this timetable",
                 {"faculty_id": row.get("faculty_id")})
    if ltype and ltype not in VALID_LECTURE_TYPES:
        fail(REASON_INVALID_LECTURE_TYPE, f"lecture_type '{ltype}' must be one of Theory, Lab",
             {"lecture_type": row.get("lecture_type")})

    if not failures:
        return None
    code, message, offending = failures[0]
    keys = {"timttable_id": row.get("timttable_id")}
    return _make_record(run_id, stage, "weekly_timetable", line_no, code, message, keys, offending, row)


def _apply_timetable_uniqueness(
    indexed: List[Tuple[int, Dict[str, str]]],
    rule_counts: Counter,
    run_id: str,
    stage: str,
) -> Tuple[List[Tuple[int, Dict[str, str]]], List[QuarantineRecord]]:
    slot_fields = ("department_code", "semester_no", "academic_year", "day_name", "slot_no")
    ordered = sorted(indexed, key=lambda ln_row: (business_key_str(ln_row[1], slot_fields), ln_row[0]))
    seen_slots: set = set()
    kept: List[Tuple[int, Dict[str, str]]] = []
    duplicate_slots: List[Tuple[int, Dict[str, str]]] = []
    for line_no, row in ordered:
        key = business_key(row, slot_fields)
        if key in seen_slots:
            duplicate_slots.append((line_no, row))
        else:
            seen_slots.add(key)
            kept.append((line_no, row))

    id_ordered = sorted(kept, key=lambda ln_row: (row_id(ln_row[1]), ln_row[0]))
    seen_ids: set = set()
    final_kept: List[Tuple[int, Dict[str, str]]] = []
    duplicate_ids: List[Tuple[int, Dict[str, str]]] = []
    for line_no, row in id_ordered:
        key = row_id(row)
        if key in seen_ids:
            duplicate_ids.append((line_no, row))
        else:
            seen_ids.add(key)
            final_kept.append((line_no, row))

    records: List[QuarantineRecord] = []
    for line_no, row in duplicate_slots:
        rule_counts[REASON_DUPLICATE_SLOT] += 1
        offending = {k: row.get(k) for k in slot_fields}
        records.append(_make_record(
            run_id, stage, "weekly_timetable", line_no, REASON_DUPLICATE_SLOT,
            "duplicate timetable slot (department_code, semester_no, academic_year, day_name, slot_no) "
            "violates unique_timetable_slot",
            {"timttable_id": row.get("timttable_id")}, offending, row,
        ))
    for line_no, row in duplicate_ids:
        rule_counts[REASON_DUPLICATE_TIMETABLE_ID] += 1
        records.append(_make_record(
            run_id, stage, "weekly_timetable", line_no, REASON_DUPLICATE_TIMETABLE_ID,
            "duplicate timttable_id",
            {"timttable_id": row.get("timttable_id")}, {"timttable_id": row.get("timttable_id")}, row,
        ))
    final_kept.sort(key=lambda ln_row: ln_row[0])
    return final_kept, records


def row_id(row: Dict[str, str]) -> str:
    return str(row.get("timttable_id"))


def validate_timetable(
    rows: Sequence[Dict[str, str]],
    *,
    line_numbers: Optional[Sequence[int]] = None,
    run_id: str,
    scope: Optional[Scope] = None,
    stage: str = "validate",
) -> ValidationOutcome:
    """Validate weekly-timetable rows; return accepted rows + quarantine."""
    scope = scope or Scope.from_config()
    _check_schema(rows, TIMETABLE_REQUIRED_COLUMNS, "weekly_timetable", stage)
    if line_numbers is None:
        line_numbers = list(range(1, len(rows) + 1))

    subjects = frozenset(r["subject_id"] for r in rows if (r.get("subject_id") or "").strip())
    faculties = frozenset(r["faculty_id"] for r in rows if (r.get("faculty_id") or "").strip())

    accepted: List[Tuple[int, Dict[str, str]]] = []
    quarantined: List[QuarantineRecord] = []
    rule_counts: Counter = Counter()

    for line_no, row in zip(line_numbers, rows):
        record = _check_timetable_row(row, line_no, scope, stage, run_id, subjects, faculties)
        if record is not None:
            quarantined.append(record)
            rule_counts[record.reason_code] += 1
        else:
            accepted.append((line_no, row))

    kept, duplicate_records = _apply_timetable_uniqueness(accepted, rule_counts, run_id, stage)
    quarantined.extend(duplicate_records)

    warnings: List[str] = []
    if len(rows) != EXPECTED_TIMETABLE_ROWS:
        warnings.append(
            f"completeness: timetable rows {len(rows)} != expected {EXPECTED_TIMETABLE_ROWS}"
        )

    quarantined.sort(key=lambda q: (q.row_index, q.reason_code))
    return ValidationOutcome(
        source="weekly_timetable",
        accepted=[row for _, row in kept],
        quarantined=quarantined,
        warnings=warnings,
        rule_counts=dict(rule_counts),
    )
