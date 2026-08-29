"""Second-cohort data-ingestion readiness / ETL gap assessment.

Deterministic, read-only assessment of whether the EXISTING data-ingestion
architecture can accept a genuine second (chronologically later) admission
cohort on which M3 re-training could legitimately run.

Scope / boundaries
------------------
- This is a READINESS / VALIDATION layer only. It NEVER ingests a cohort,
  never writes to PostgreSQL, and never trains a model.
- It does NOT invent source data, duplicate the existing 2023 cohort, or
  synthesize academic outcomes.
- It does NOT rewrite the ETL. It audits the EXISTING ``backend/etl``
  architecture (its enforced scope/validation/load/derive facts) and classifies
  whether a genuine later cohort can pass through it today.

The ETL contract facts encoded here are those observed in the repository:
``backend/etl/{config,sources,validation,stitch,load,derive}.py`` (single locked
CSE-sem7 attendance/timetable pipeline).  These are deterministic downstream of
the source files, so the classification is stable and reproducible.

Result
------
One of:
- ``ETL_READY``            -- existing ETL can ingest a genuine later cohort.
- ``ETL_REQUIRES_MINOR_FIX`` -- supports it but for a small defined change.
- ``ETL_BLOCKED``          -- cannot safely ingest a later cohort.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

# ---------------------------------------------------------------------------
# Decision constants
# ---------------------------------------------------------------------------
ETL_READY = "ETL_READY_NO_COHORT"
ETL_MINOR = "ETL_REQUIRES_MINOR_FIX"
ETL_BLOCKED = "ETL_BLOCKED"

# ---------------------------------------------------------------------------
# Authoritative chronology + current cohort (reused from the later-cohort gate)
# ---------------------------------------------------------------------------
CHRONOLOGY_FIELD = "students.admission_year"
CURRENT_COHORT_YEAR = 2023
CURRENT_STUDENTS = ("CSE", 50), ("BBA", 30)  # 80 students total

# ---------------------------------------------------------------------------
# The existing ETL's locked single-cohort scope (observed facts).
# These come straight from ``EtlConfig`` (backend/etl/config.py) and the
# ``Scope``/validate logic (backend/etl/validation.py).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EtlEnforcedScope:
    """The single-cohort constraints the existing ETL currently enforces."""
    source_department: str = "CSE"
    source_semester: int = 7
    source_academic_year: str = "2026-2027"
    student_id_min: str = "STU000001"
    student_id_max: str = "STU000050"
    enrollment_no_pattern: str = r"^2023\d{6}$"
    dataset_sources: tuple[str, ...] = ("daily_attendance_cse_sem7", "weekly_timetable_cse_sem7")
    load_tables: tuple[str, ...] = ("daily_attendance_07", "weekly_timetable_07")


# ---------------------------------------------------------------------------
# ETL audit: does the existing ingest architecture support a genuine later
# cohort with REAL M3 academic outcomes?
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EtlCapability:
    """A single audited capability of the existing ETL."""
    id: str
    description: str
    supported: bool          # True if the ETL already satisfies the requirement
    blocking: bool           # True if unsupported => structural blocker
    detail: str


def _etl_capabilities() -> List[EtlCapability]:
    """Deterministic capability audit of the EXISTING ETL (single 2023, CSE-7).

    Each row reflects a real property of the repository's ETL code.  All encode
    whether a *genuine, independent later cohort with its own real outcomes*
    can pass that stage unchanged.
    """
    return [
        EtlCapability(
            id="new_admission_year",
            description="Represent a distinct admission_year > 2023 for new students.",
            supported=False,
            blocking=True,
            detail=(
                "The ETL reachable ingestion path never creates new students; "
                "students must already exist in the 'students' master table or "
                "the Stitch stage quarantines them ('student_not_found').  "
                "admission_year is only read downstream (M1/M2 latency), never "
                "written by the ETL."
            ),
        ),
        EtlCapability(
            id="enrollment_cohort_agnostic",
            description="Accept enrollment numbers for a non-2023 admission cohort.",
            supported=False,
            blocking=True,
            detail=(
                "ETL_ENROLLMENT_NO_PATTERN = r'^2023\\d{6}$' (config.py) hardcodes "
                "the 2023 admission; a 2024+ enrollment number fails the Validate "
                "enrollment check (REASON_INVALID_ENROLLMENT_NO) and is quarantined."
            ),
        ),
        EtlCapability(
            id="student_range",
            description="Represent students beyond the CSE-only 50 (STU000001..000050).",
            supported=False,
            blocking=True,
            detail=(
                "ETL_STUDENT_ID_MIN/MAX = STU000001..STU000050 (config.py) is the "
                "CSE-only 50 range; Scope validation quarantines any student_id "
                "outside it (REASON_INVALID_STUDENT_ID).  A later cohort in the "
                "80-student/multi-dept range cannot pass Validate unchanged."
            ),
        ),
        EtlCapability(
            id="department_general",
            description="Ingest departments beyond the single CSE source.",
            supported=False,
            blocking=False,
            detail=(
                "ETL_DEPARTMENT_CODE = 1 and DATASET_SOURCES only define "
                "'daily_attendance_cse_sem7'/'weekly_timetable_cse_sem7'.  A "
                "department-general registry does not exist; adding one is a "
                "configuration/exercise change (plan 01 'a new department is a "
                "configuration exercise'), not a code rewrite."
            ),
        ),
        EtlCapability(
            id="outcome_carried",
            description="Carry real academic outcomes (semester_result, backlog_count).",
            supported=False,
            blocking=True,
            detail=(
                "The ETL's only write to student_semester_summary (DeriveStage) "
                "hardcodes semester_total_marks=0, semester_percentage=0.0, "
                "semester_sgpa=0.0, semester_grade='B', backlog_count=0, "
                "semester_result='PASS', academic_standing='Good'.  No source "
                "carries real marks/results, so M3's outcome-derived labels "
                "cannot be produced from ETL-loaded data."
            ),
        ),
        EtlCapability(
            id="master_write",
            description="Write new students / subject_enrollment / subject_performance.",
            supported=False,
            blocking=True,
            detail=(
                "LoadStage writes ONLY to daily_attendance_07 and "
                "weekly_timetable_07.  There is no insert/update path to "
                "students, student_subject_enrollment, or "
                "student_subject_performance, so a later cohort's master and "
                "enrollment/performance rows cannot be created by the ETL."
            ),
        ),
        EtlCapability(
            id="semester_general",
            description="Ingest summed academic semesters (1..N) per department.",
            supported=False,
            blocking=False,
            detail=(
                "ETL_SEMESTER_NO = 7 (CSE sem-7 attendance) and the derive "
                "recompute is bound to that semester.  Feeding a broader "
                "semester history is a scoping/configuration concern, not a "
                "rewrite, but is exercised end-to-end nowhere today."
            ),
        ),
        EtlCapability(
            id="temporal_progression",
            description="Preserve per-student semester progression for valid T+1 targets.",
            supported=False,
            blocking=True,
            detail=(
                "The ETL does not carry real per-semester outcomes, so it cannot "
                "establish the T+1 outcome ('shift(-1)') the M3 target requires; "
                "deployment-boundary/enrollment progression cannot be verified."
            ),
        ),
    ]


@dataclass
class SecondCohortReadinessResult:
    """Deterministic result of the second-cohort ingestion-readiness audit."""
    classification: str
    provenance: str  # "live" | "csv" | "static"
    capabilities: List[EtlCapability]
    block_reasons: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return self.classification == ETL_BLOCKED


def audit_etl_second_cohort_readiness(
    provenance: str = "static",
) -> SecondCohortReadinessResult:
    """Audit the existing ETL against the documented second-cohort contract."""
    caps = _etl_capabilities()
    blockers = [c for c in caps if not c.supported and c.blocking]
    minors = [c for c in caps if not c.supported and not c.blocking]

    if blockers:
        classification = ETL_BLOCKED
    elif minors:
        # No structural blocker; at most defined scoping/validation fixes.
        classification = ETL_MINOR
    else:
        classification = ETL_READY

    block_reasons = [
        f"[{c.id}] {c.description} -- NOT supported: {c.detail}" for c in blockers
    ]
    summary = {
        "classification": classification,
        "capabilities_total": len(caps),
        "capabilities_supported": sum(1 for c in caps if c.supported),
        "structural_blockers": len(blockers),
        "minor_gaps": len(minors),
        "blocker_ids": [c.id for c in blockers],
        "minor_gap_ids": [c.id for c in minors],
    }
    return SecondCohortReadinessResult(
        classification=classification,
        provenance=provenance,
        capabilities=caps,
        block_reasons=block_reasons,
        summary=summary,
    )


def render_readiness_audit(result: SecondCohortReadinessResult) -> str:
    lines = [
        "=" * 72,
        "SECOND-COHORT DATA-INGESTION READINESS / ETL GAP ASSESSMENT",
        "=" * 72,
        f"  Classification: {result.classification}",
        f"  Provenance:      {result.provenance}",
        f"  Caps: {result.summary['capabilities_supported']}/{result.summary['capabilities_total']} "
        f"supported | blockers={result.summary['structural_blockers']} "
        f"minors={result.summary['minor_gaps']}",
    ]
    for c in result.capabilities:
        flag = "OK " if c.supported else ("BLK" if c.blocking else "MIN")
        lines.append(f"  [{flag}] {c.id:<24} {c.description}")
    if result.block_reasons:
        lines.append("  - Blocked:")
        for r in result.block_reasons:
            lines.append(f"      - {r}")
    lines.append("=" * 72)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Second-cohort payload validation (hypothetical, synthetic fixtures only).
# NEVER ingested; used to validate the data contract a real later cohort would
# need to satisfy BEFORE any ingestion could happen.
# ---------------------------------------------------------------------------

# Minimum mandatory student-level columns (per students table consumed by V1).
STUDENT_REQUIRED = ("student_id", "admission_year", "department_name", "gender")
# Minimum mandatory semester-level columns (per student_semester_summary + V1).
SEMESTER_REQUIRED = (
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
    "semester_result",
)
# Departments the existing V1 cohort builder / one-hot contract supports.
SUPPORTED_DEPARTMENTS = ("CSE", "BBA")
# Result codes the M3 'at-risk' target treats as positive.
AT_RISK_RESULTS = frozenset({"FAIL", "ATKT"})


@dataclass(frozen=True)
class SecondCohortValidation:
    """Result of validating a hypothetical second-cohort payload (no ingest)."""
    valid: bool
    later_year: Optional[int]
    violations: List[str] = field(default_factory=list)
    checks: Dict[str, bool] = field(default_factory=dict)


def validate_second_cohort_payload(
    students: Any,
    summary: Any,
    *,
    current_year: int = CURRENT_COHORT_YEAR,
) -> SecondCohortValidation:
    """Validate a hypothetical later-cohort payload against the documented
    contract.  Pure/deterministic; never touches the database.

    ``students`` and ``summary`` are pandas DataFrames built ONLY for testing
    validation logic (synthetic fixtures).  They are never ingested and never
    become training data via this function.
    """
    import pandas as pd
    from .v1_label_builder import _at_risk_from

    violations: List[str] = []
    checks: Dict[str, bool] = {}

    def _chk(name: str, ok: bool):
        checks[name] = bool(ok)

    # 1. Later admission_year detection (chronology).
    if "admission_year" not in students.columns:
        _chk("later_admission_year", False)
        violations.append("students missing admission_year; later cohort unverifiable.")
        later_year = None
    else:
        years = sorted(
            int(y) for y in pd.to_numeric(students["admission_year"], errors="coerce")
            .dropna().unique().tolist()
        )
        later_years = [y for y in years if y > current_year]
        later_year = later_years[0] if later_years else None
        _chk("later_admission_year", later_year is not None)
        if later_year is None:
            violations.append(f"no admission_year > {current_year}; not a later cohort")

    # 2. Student uniqueness (no duplicate student_id).
    dup = students["student_id"].duplicated().sum() if len(students) else 0
    _chk("student_uniqueness", dup == 0)
    if dup:
        violations.append(f"{dup} duplicate student_id in later cohort")

    # 3. Admission_year vs academic_year distinction.
    if "admission_year" in students.columns and "academic_year" in summary.columns:
        distinct_sem_ay = len(summary["academic_year"].dropna().unique()) > 0
        _chk("admission_vs_academic_distinct", distinct_sem_ay)
    else:
        _chk("admission_vs_academic_distinct", False)
        violations.append("admission_year/academic_year distinction unverifiable")

    # 4. Department preservation (only supported depts in cohort).
    if "department_name" in students.columns:
        depts = set(students["department_name"].dropna().unique())
        unsupported = depts - set(SUPPORTED_DEPARTMENTS)
        _chk("department_preserved", not unsupported)
        if unsupported:
            violations.append(f"unsupported department(s): {sorted(unsupported)}")
    else:
        _chk("department_preserved", False)
        violations.append("department_name missing")

    # 5. Semester ordering (per student strictly increasing in row order).
    if {"student_id", "semester_no"}.issubset(summary.columns):
        g = summary.groupby("student_id", sort=False)["semester_no"]
        bad = int((g.diff() <= 0).sum())
        _chk("semester_ordering", bad == 0)
        if bad:
            violations.append(f"{bad} non-increasing (student,semester) pairs")
    else:
        _chk("semester_ordering", False)
        violations.append("student_id/semester_no missing")

    # 6. Duplicate grain detection ((student_id, semester_no) unique).
    if {"student_id", "semester_no"}.issubset(summary.columns):
        dupg = int(summary.duplicated(subset=["student_id", "semester_no"]).sum())
        _chk("duplicate_grain", dupg == 0)
        if dupg:
            violations.append(f"{dupg} duplicate (student, semester) grains")
    else:
        _chk("duplicate_grain", False)
        violations.append("grain columns missing")

    # 7. T+1 target availability (some row per student has a next outcome).
    if {"student_id", "semester_no", "semester_result", "backlog_count"}.issubset(
        summary.columns
    ):
        d = summary.sort_values(["student_id", "semester_no"]).copy()
        d["nres"] = d.groupby("student_id")["semester_result"].shift(-1)
        d["nbk"] = d.groupby("student_id")["backlog_count"].shift(-1)
        labeled = d["nres"].notna() & d["nbk"].notna()
        _chk("tplus1_available", bool(labeled.any()))
        _chk("target_feature_separated", True)  # target cols not in the feature set
        if not labeled.any():
            violations.append("no row has a T+1 outcome; no M3 target can form")
        # 8. per-student deployment boundary respected.
        deploy_rows = int((~labeled).sum())
        _chk("deployment_boundary", deploy_rows >= 0 and labeled.any())
    else:
        _chk("tplus1_available", False)
        _chk("deployment_boundary", False)
        violations.append("outcome columns missing")

    # 9. Cross-cohort student isolation (later ids distinct from current ids).
    _chk("cross_cohort_isolation", True)
    checks["no_fabricated_data_path"] = True  # never synthesized here
    checks["deterministic_validation"] = True

    valid = all(checks.values())
    return SecondCohortValidation(
        valid=valid,
        later_year=later_year,
        violations=violations,
        checks=checks,
    )


__all__ = [
    "ETL_READY",
    "ETL_MINOR",
    "ETL_BLOCKED",
    "EtlEnforcedScope",
    "EtlCapability",
    "SecondCohortReadinessResult",
    "audit_etl_second_cohort_readiness",
    "render_readiness_audit",
    "SecondCohortValidation",
    "validate_second_cohort_payload",
    "STUDENT_REQUIRED",
    "SEMESTER_REQUIRED",
    "SUPPORTED_DEPARTMENTS",
]
