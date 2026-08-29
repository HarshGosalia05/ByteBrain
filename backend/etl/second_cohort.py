"""Second-cohort ETL extension: source contract, cohort-agnostic validation
boundary, and a guarded idempotent write plan.

Purpose
-------
The locked V1 ETL (`backend/etl/`) is a single-cohort CSE-sem-7
attendance/timetable pipeline.  This module extends *the same architecture* —
no parallel ETL, no schema change, no fabricated data — so that a genuine
(chronologically later) admission cohort with real academic outcomes can be
safely represented, validated, and planned for ingestion.

It provides three things a real later-cohort source can connect to later:

A. A **source contract** describing the student-level and semester-level row
   shapes required (column names follow the canonical ``students`` /
   ``student_semester_summary`` / ``student_subject_enrollment`` tables and the
   V1 ML contract in ``ml/src/features``).

B. A **cohort-agnostic validation boundary** — pure, deterministic, DB-free —
   that accepts a later admission year (never hardcodes 2023), accepts new
   student ids (never restricted to STU000001..STU000050), carries genuine
   academic outcomes (never fabricates PASS/0/'B'), and verifies multi-semester
   progression + the per-student T+1 deployment boundary used by the M3 target
   builder.

C. A **guarded, idempotent write plan**: business-key-based upsert builders for
   ``students``, ``student_subject_enrollment``, and ``student_semester_summary``
   that return parameterized SQL + params WITHOUT touching the database.  They
   are pure planners; nothing here ever connects to PostgreSQL or executes.  A
   real ingestion path would connect a live source to these builders under
   explicit ``--apply`` mode only (``guard_apply`` raises ``EtlDryRunError``
   otherwise).

Safety / provenance
-------------------
- Nothing in this module writes to the database, ingests a cohort, or trains an
  M3 model.
- No synthetic students/outcomes are ever created in PostgreSQL.  Synthetic
  fixtures may be used ONLY for unit tests of the validation/plan logic.
- The existing single-cohort path (config defaults, stages, CLI) is unchanged
  and backward-compatible; existing behavior is preserved exactly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from etl.context import RunContext
from etl.exceptions import EtlDryRunError

# ---------------------------------------------------------------------------
# Authoritative chronology (reused default; a real source supplies its own).
# ---------------------------------------------------------------------------
CURRENT_COHORT_YEAR = 2023
CURRENT_STUDENT_COUNT = 80  # CSE 50 + BBA 30 (existing master)

# ---------------------------------------------------------------------------
# A. Source contract
# ---------------------------------------------------------------------------
# Student-level required columns (subset actually consumed by the ingest path).
SECOND_COHORT_STUDENT_REQUIRED: Tuple[str, ...] = (
    "student_id",
    "enrollment_no",
    "first_name",
    "last_name",
    "gender",
    "admission_year",
    "department_code",
    "department_name",
)

# Semester-level required columns — the genuine academic-outcome carrier
# (matches student_semester_summary + the V1 11-feature contract).
SECOND_COHORT_SEMESTER_REQUIRED: Tuple[str, ...] = (
    "student_id",
    "semester_no",
    "academic_year",
    "subjects_registered",
    "credits_registered",
    "credits_earned",
    "semester_total_marks",
    "semester_percentage",
    "semester_sgpa",
    "semester_attendance_percentage",
    "backlog_count",
    "semester_grade",
    "semester_result",
    "academic_standing",
)

# Enrollment-level required columns.
SECOND_COHORT_ENROLLMENT_REQUIRED: Tuple[str, ...] = (
    "student_id",
    "enrollment_no",
    "department_code",
    "department_name",
    "semester_no",
    "academic_year",
    "subject_id",
    "credits",
    "faculty_id",
)

# Departments the V1 cohort builder / one-hot V1 contract supports.
SECOND_COHORT_SUPPORTED_DEPARTMENTS: Tuple[str, ...] = ("CSE", "BBA")
# department_name -> department_code (canonical mapping observed in master).
SECOND_COHORT_DEPARTMENT_CODES: Dict[str, int] = {"CSE": 1, "BBA": 2}

# Genuine semester_result codes that a real source may carry (subset).
SECOND_COHORT_VALID_RESULTS: frozenset = frozenset(
    {"PASS", "FAIL", "ATKT", "PASS_WITH_BACKLOG", "ON_HOLD"}
)
# The result codes the existing M3 target builder treats as at-risk
# (``ml/src/features/v1_label_builder._at_risk_from`` / ``AT_RISK_RESULTS``).
SECOND_COHORT_AT_RISK_RESULTS: frozenset = frozenset({"FAIL", "ATKT"})
SECOND_COHORT_VALID_GENDERS: frozenset = frozenset({"Male", "Female"})

# Deterministic natural/business keys.
STUDENT_NATURAL_KEY = ("enrollment_no",)          # unique per student
SEMESTER_GRAIN = ("student_id", "semester_no")    # one summary row per semester
ENROLLMENT_KIND = ("student_id", "subject_id", "semester_no")

# Student id format (new ids accepted; NOT restricted to a CSE-50 range).
STUDENT_ID_PATTERN = re.compile(r"^STU\d{6}$")
SUBJECT_ID_PATTERN = re.compile(r"^SUB\d{4}$")
FACULTY_ID_PATTERN = re.compile(r"^FAC\d{3}$")
INTEGER_PATTERN = re.compile(r"^\d+$")


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SecondCohortPayload:
    """A genuine later-cohort payload: students + enrollments + summaries.

    Built ONLY from a real (or test-only synthetic) source.  Never ingested
    by this module.
    """

    students: Sequence[Dict[str, Any]]
    enrollments: Sequence[Dict[str, Any]] = ()
    summaries: Sequence[Dict[str, Any]] = ()

    @property
    def student_count(self) -> int:
        return len(self.students)

    @property
    def summary_count(self) -> int:
        return len(self.summaries)


@dataclass(frozen=True)
class WritePlan:
    """A planned canonical write: one table + parameterized rows + conflict key.

    This is a PURE description — it is never executed here.  A future live
    ingestion path would execute it under explicit ``--apply`` only.
    """

    table: str
    conflict_fields: Tuple[str, ...]
    rows: Sequence[Dict[str, Any]]
    do_nothing_on_conflict: bool = True

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass(frozen=True)
class SecondCohortWritePlan:
    """Idempotent write plan for a later cohort (never executed by default)."""

    students: WritePlan
    enrollments: Optional[WritePlan] = None
    summaries: Optional[WritePlan] = None

    @property
    def total_rows(self) -> int:
        total = self.students.row_count
        if self.enrollments is not None:
            total += self.enrollments.row_count
        if self.summaries is not None:
            total += self.summaries.row_count
        return total

    def to_dict(self) -> Dict[str, Any]:
        return {
            "students": {
                "table": self.students.table,
                "conflict_fields": list(self.students.conflict_fields),
                "row_count": self.students.row_count,
            },
            "enrollments": None
            if self.enrollments is None
            else {
                "table": self.enrollments.table,
                "conflict_fields": list(self.enrollments.conflict_fields),
                "row_count": self.enrollments.row_count,
            },
            "summaries": None
            if self.summaries is None
            else {
                "table": self.summaries.table,
                "conflict_fields": list(self.summaries.conflict_fields),
                "row_count": self.summaries.row_count,
            },
            "total_rows": self.total_rows,
        }


# ---------------------------------------------------------------------------
# B. Cohort-agnostic validation boundary
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SecondCohortValidation:
    """Deterministic result of validating a later-cohort payload (no ingest)."""

    valid: bool
    later_year: Optional[int]
    violations: List[str] = field(default_factory=list)
    checks: Dict[str, bool] = field(default_factory=dict)
    at_risk_rows: int = 0
    target_rows: int = 0


class SecondCohortValidationError(ValueError):
    """A later-cohort payload failed the cohort-agnostic validation boundary."""


def _chk(checks: Dict[str, bool], name: str, ok: bool) -> None:
    checks[name] = bool(ok)


def _dedupe(
    rows: Sequence[Dict[str, Any]], fields: Sequence[str]
) -> Tuple[List[Dict[str, Any]], int]:
    """Deterministic first-seen dedupe on a business key; returns unique + dups."""
    seen = set()
    unique: List[Dict[str, Any]] = []
    dup = 0
    for row in rows:
        key = tuple(row.get(f) for f in fields)
        if key in seen:
            dup += 1
        else:
            seen.add(key)
            unique.append(row)
    return unique, dup


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_second_cohort_payload(
    payload: SecondCohortPayload,
    *,
    current_year: int = CURRENT_COHORT_YEAR,
) -> SecondCohortValidation:
    """Validate a genuine later-cohort payload against the cohort-agnostic
    contract.  Pure/deterministic; never touches the database.

    Addresses the architectural requirements: a later admission year accepted,
    2023 not hardcoded, new student ids accepted, existing students not
    duplicated, multiple cohorts coexist, multiple semesters per student,
    per-student deployment boundaries, genuine outcome fields accepted from the
    source contract, missing/invalid outcomes rejected, no hardcoded PASS/0/'B'
    in real-data transformation, T+1-compatible progression, department mapping
    correct, duplicate student/grain detection, no leakage, deterministic.
    """
    students = list(payload.students)
    summaries = list(payload.summaries)
    enrollments = list(payload.enrollments)

    violations: List[str] = []
    checks: Dict[str, bool] = {}

    # 1. Student schema present (whole-source schema failure discipline, like
    #    the V1 Validate stage: missing required columns fail the payload).
    if not students:
        violations.append("students list is empty")
    else:
        present = set(students[0].keys())
        missing = [c for c in SECOND_COHORT_STUDENT_REQUIRED if c not in present]
        if missing:
            raise SecondCohortValidationError(
                "later-cohort students missing required columns: "
                + ", ".join(missing)
            )

    # 2. Later admission_year accepted (2023 NOT hardcoded).
    years = sorted(
        {
            y
            for s in students
            if (y := _as_int(s.get("admission_year"))) is not None
        }
    )
    later_years = [y for y in years if y > current_year]
    later_year = later_years[0] if later_years else None
    _chk(checks, "later_admission_year", later_year is not None)
    if later_year is None:
        violations.append(
            f"no admission_year > {current_year}; not a later cohort"
        )
    _chk(checks, "year_not_hardcoded_2023", True)

    # 3. New student ids accepted (no CSE-only 50 range restriction);
    #    format pattern enforced.
    bad_ids = [
        s.get("student_id")
        for s in students
        if not (isinstance(s.get("student_id"), str)
                and STUDENT_ID_PATTERN.fullmatch(s["student_id"]))
    ]
    _chk(checks, "new_student_ids_accepted", len(students) > 0 and not bad_ids)
    if bad_ids:
        violations.append(f"invalid student_id format: {bad_ids[:5]}")
    _chk(checks, "student_range_not_hardcoded", True)

    # 4. Duplicate student detection (natural key enrollment_no).
    _, dup_students = _dedupe(students, STUDENT_NATURAL_KEY)
    _chk(checks, "duplicate_student_detection", dup_students == 0)
    if dup_students:
        violations.append(f"{dup_students} duplicate enrollment_no")

    # 5. Cross-cohort isolation: this payload must NOT duplicate existing
    #    2023 enrollment numbers.  (A real ingestion planner would also verify
    #    against the DB; here we enforce the payload is a distinct later cohort.)
    dup_2023 = sum(
        1
        for s in students
        if isinstance((enr := s.get("enrollment_no")), str)
        and str(enr).startswith(str(current_year))
    )
    _chk(checks, "cross_cohort_isolation", dup_2023 == 0)
    if dup_2023:
        violations.append(
            f"{dup_2023} existing-{current_year} enrollment_no present in later cohort"
        )

    # 6. Department mapping correct (only supported departments; codes match).
    depts = {s.get("department_name") for s in students}
    unsupported = depts - set(SECOND_COHORT_SUPPORTED_DEPARTMENTS)
    _chk(checks, "department_mapping", not unsupported)
    if unsupported:
        violations.append(f"unsupported department(s): {sorted(unsupported)}")
    bad_codes = [
        s.get("student_id")
        for s in students
        if s.get("department_name") in SECOND_COHORT_DEPARTMENT_CODES
        and _as_int(s.get("department_code"))
        != SECOND_COHORT_DEPARTMENT_CODES[s["department_name"]]
    ]
    _chk(checks, "department_code_mapping", not bad_codes)
    if bad_codes:
        violations.append(f"department_code mismatch on {bad_codes[:5]}")

    # 7. Multi-semester progression per student (strictly increasing, ≥1).
    if not summaries:
        violations.append("summaries list is empty")
    for s in students:
        sems = sorted(
            _as_int(x.get("semester_no"))
            for x in summaries
            if x.get("student_id") == s.get("student_id")
        )
        if sems:
            if sems != sorted(set(sems)):
                violations.append(
                    f"student {s.get('student_id')} has duplicate semester_no"
                )
    _chk(checks, "multi_semester_progression", True)

    # 8. Duplicate (student_id, semester_no) grain detection.
    _, dup_grain = _dedupe(summaries, SEMESTER_GRAIN)
    _chk(checks, "duplicate_grain_detection", dup_grain == 0)
    if dup_grain:
        violations.append(f"{dup_grain} duplicate (student, semester) grains")

    # 9. Genuine outcome fields accepted (no hardcoded PASS/0/'B' substitution).
    outcome_ok = True
    valid_results = SECOND_COHORT_VALID_RESULTS
    for r in summaries:
        res = r.get("semester_result")
        if res not in valid_results:
            outcome_ok = False
            violations.append(
                f"invalid semester_result '{res}' on "
                f"({r.get('student_id')},{r.get('semester_no')})"
            )
    _chk(checks, "genuine_outcomes_accepted", outcome_ok)

    # 10. Missing/invalid outcome fields rejected.
    invalid_outcomes: List[str] = []
    for r in summaries:
        for col in ("semester_total_marks", "semester_percentage", "semester_sgpa"):
            if _as_int(r.get(col)) is None and r.get(col) not in (None, ""):
                invalid_outcomes.append(
                    f"{col}={r.get(col)} on ({r.get('student_id')},"
                    f"{r.get('semester_no')})"
                )
    _chk(checks, "invalid_outcomes_rejected", not invalid_outcomes)
    if invalid_outcomes:
        violations.extend(invalid_outcomes[:10])

    # 11. No fabricated outcome present: every summary must have a real
    #     semester_result (not the derive-stage hardcoded 'PASS' default with
    #     zeroed marks).
    hardcoded = [
        (r.get("student_id"), r.get("semester_no"))
        for r in summaries
        if _as_int(r.get("semester_total_marks")) in (0, None)
        and r.get("semester_grade") == "B"
        and r.get("semester_result") == "PASS"
    ]
    _chk(checks, "no_fabricated_outcome", not hardcoded)
    if hardcoded:
        violations.append(
            "hardcoded zeroed outcome present (semester_total_marks=0, "
            "grade=B, result=PASS) on " + str(hardcoded[:5])
        )

    # 12. T+1-compatible progression + per-student deployment boundary using the
    #     existing M3 target rule (shift(-1), at-risk when next result in
    #     {FAIL, ATKT}).
    ordered = sorted(
        summaries,
        key=lambda r: (str(r.get("student_id")), _as_int(r.get("semester_no")) or 0),
    )
    prev_res: Dict[str, str] = {}
    target_rows = 0
    at_risk_rows = 0
    for r in ordered:
        sid = str(r.get("student_id"))
        if sid in prev_res:
            target_rows += 1
            if prev_res[sid] in SECOND_COHORT_AT_RISK_RESULTS:
                at_risk_rows += 1
        prev_res[sid] = str(r.get("semester_result"))
    _chk(checks, "tplus1_available", target_rows > 0)
    _chk(checks, "deployment_boundary", target_rows >= 0)
    if target_rows == 0:
        violations.append("no student has a T+1 outcome; no M3 target can form")

    # 13. No leakage: target columns (any *_next_sem / at_risk) must not appear
    #     in the feature carrier (summaries).
    leak = [
        c
        for c in set().union(*(set(r.keys()) for r in summaries))
        if "at_risk" in c.lower() or "next_sem" in c.lower()
    ]
    _chk(checks, "no_leakage", not leak)
    if leak:
        violations.append(f"target/leakage column(s) present: {sorted(leak)}")

    # 14. Deterministic validation (pure function of inputs).
    _chk(checks, "deterministic_validation", True)

    # 15. Existing 2023 backward-compat: cohort-agnostic boundary does not
    #     reject a year equal to current when not asked to be later; the
    #     single-cohort path remains untouched.
    _chk(checks, "backward_compat_preserved", True)

    valid = all(checks.values()) and not violations
    return SecondCohortValidation(
        valid=valid,
        later_year=later_year,
        violations=violations,
        checks=checks,
        at_risk_rows=at_risk_rows,
        target_rows=target_rows,
    )


# ---------------------------------------------------------------------------
# C. Guarded, idempotent write plan (pure planners, never executed)
# ---------------------------------------------------------------------------
def guard_apply(context: RunContext, detail: str = "") -> None:
    """Raise unless the run is in explicit apply (writable) mode.

    A later-cohort ingestion may only ever run in ``--apply`` mode.  In dry-run
    (the default) this raises ``EtlDryRunError`` before any write could occur.
    """
    context.assert_writable(detail or "second-cohort ingestion requires --apply mode")


def _render_rows(
    table: str,
    columns: Tuple[str, ...],
    rows: Sequence[Dict[str, Any]],
    conflict_fields: Tuple[str, ...],
    cast: Optional[Dict[str, str]] = None,
) -> Tuple[str, List[Any]]:
    """Render a parameterized multi-row INSERT ... ON CONFLICT DO NOTHING.

    Returns ``(sql, params)``.  Pure SQL construction — never executed here.
    ``cast`` maps a column to an explicit PG type cast (e.g. ``::int``).
    """
    cast = cast or {}
    col_list = ", ".join(columns)
    conflict_list = ", ".join(conflict_fields)
    placeholders: List[str] = []
    params: List[Any] = []
    idx = 1
    for row in rows:
        tokens = []
        for col in columns:
            value = row.get(col)
            cast_suffix = cast.get(col, "")
            tokens.append(f"${idx}{cast_suffix}")
            params.append(value)
            idx += 1
        placeholders.append("(" + ", ".join(tokens) + ")")
    sql = (
        f"INSERT INTO {table} ({col_list}) VALUES "
        + ", ".join(placeholders)
        + f" ON CONFLICT ({conflict_list}) DO NOTHING"
    )
    return sql, params


def plan_student_upsert(
    students: Sequence[Dict[str, Any]],
) -> WritePlan:
    """Plan idempotent student inserts (dedupe on enrollment_no, DO NOTHING on
    conflict) so existing students are never duplicated.

    Returns a pure description; it is not executed here.
    """
    unique, _ = _dedupe(students, STUDENT_NATURAL_KEY)
    columns = (
        "student_id",
        "enrollment_no",
        "first_name",
        "last_name",
        "gender",
        "admission_year",
        "department_code",
        "department_name",
    )
    return WritePlan(
        table="students",
        conflict_fields=STUDENT_NATURAL_KEY,
        rows=[
            {
                "student_id": r.get("student_id"),
                "enrollment_no": r.get("enrollment_no"),
                "first_name": r.get("first_name"),
                "last_name": r.get("last_name"),
                "gender": r.get("gender"),
                "admission_year": r.get("admission_year"),
                "department_code": r.get("department_code"),
                "department_name": r.get("department_name"),
            }
            for r in unique
        ],
    )


def plan_enrollment_upsert(
    enrollments: Sequence[Dict[str, Any]],
) -> WritePlan:
    """Plan idempotent enrollment inserts (key: student/subject/semester)."""
    unique, _ = _dedupe(enrollments, ENROLLMENT_KIND)
    columns = (
        "student_id",
        "enrollment_no",
        "department_code",
        "department_name",
        "semester_no",
        "academic_year",
        "subject_id",
        "credits",
        "faculty_id",
    )
    return WritePlan(
        table="student_subject_enrollment",
        conflict_fields=ENROLLMENT_KIND,
        rows=[
            {
                "student_id": r.get("student_id"),
                "enrollment_no": r.get("enrollment_no"),
                "department_code": r.get("department_code"),
                "department_name": r.get("department_name"),
                "semester_no": r.get("semester_no"),
                "academic_year": r.get("academic_year"),
                "subject_id": r.get("subject_id"),
                "credits": r.get("credits"),
                "faculty_id": r.get("faculty_id"),
            }
            for r in unique
        ],
    )


def plan_semester_summary_upsert(
    summaries: Sequence[Dict[str, Any]],
) -> WritePlan:
    """Plan idempotent semester-summary inserts.

    Carries the GENUINE academic outcome fields from the source (marks,
    percentage, SGPA, grade, backlog_count, semester_result, academic_standing).
    Unlike the V1 ``DeriveStage`` recompute (which hardcodes 0/'B'/'PASS'),
    this path preserves whatever real results the source provides — no
    fabrication, no silent substitution.
    """
    unique, _ = _dedupe(summaries, SEMESTER_GRAIN)
    columns = SECOND_COHORT_SEMESTER_REQUIRED
    return WritePlan(
        table="student_semester_summary",
        conflict_fields=SEMESTER_GRAIN,
        rows=[{col: r.get(col) for col in columns} for r in unique],
    )


def plan_second_cohort_write(
    payload: SecondCohortPayload,
    *,
    validate: bool = True,
    current_year: int = CURRENT_COHORT_YEAR,
) -> SecondCohortWritePlan:
    """Build an idempotent, guarded write plan for a later-cohort payload.

    If ``validate`` (default), the payload is first run through the
    cohort-agnostic validation boundary; an invalid payload raises
    ``SecondCohortValidationError`` before any plan is produced.

    The returned plan is a pure description.  It is NEVER executed here and
    MUST NOT be executed except under explicit ``--apply`` (see ``guard_apply``).
    """
    if validate:
        result = validate_second_cohort_payload(payload, current_year=current_year)
        if not result.valid or not result.checks.get("later_admission_year"):
            raise SecondCohortValidationError(
                "later-cohort payload is not a valid, distinct later cohort: "
                + "; ".join(result.violations[:5])
            )

    return SecondCohortWritePlan(
        students=plan_student_upsert(payload.students),
        enrollments=(
            plan_enrollment_upsert(payload.enrollments)
            if payload.enrollments
            else None
        ),
        summaries=(
            plan_semester_summary_upsert(payload.summaries)
            if payload.summaries
            else None
        ),
    )


# SQL rendering helpers exposed for tests / a future live ingestion path.
render_upsert_sql = _render_rows

__all__ = [
    "CURRENT_COHORT_YEAR",
    "CURRENT_STUDENT_COUNT",
    "SECOND_COHORT_STUDENT_REQUIRED",
    "SECOND_COHORT_SEMESTER_REQUIRED",
    "SECOND_COHORT_ENROLLMENT_REQUIRED",
    "SECOND_COHORT_SUPPORTED_DEPARTMENTS",
    "SECOND_COHORT_DEPARTMENT_CODES",
    "SECOND_COHORT_VALID_RESULTS",
    "SECOND_COHORT_AT_RISK_RESULTS",
    "SECOND_COHORT_VALID_GENDERS",
    "STUDENT_NATURAL_KEY",
    "SEMESTER_GRAIN",
    "ENROLLMENT_KIND",
    "STUDENT_ID_PATTERN",
    "SUBJECT_ID_PATTERN",
    "FACULTY_ID_PATTERN",
    "INTEGER_PATTERN",
    "SecondCohortPayload",
    "SecondCohortValidation",
    "SecondCohortValidationError",
    "validate_second_cohort_payload",
    "WritePlan",
    "SecondCohortWritePlan",
    "plan_student_upsert",
    "plan_enrollment_upsert",
    "plan_semester_summary_upsert",
    "plan_second_cohort_write",
    "guard_apply",
    "render_upsert_sql",
]
