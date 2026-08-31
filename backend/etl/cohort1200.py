"""CSE 6A 1,200-cohort ETL transformation and ID validation (dry-run/loader prep).

This module prepares the ``KenexAI_1200_final_v3`` cohort for loading against the
live KenexAI database contract WITHOUT executing anything: every function is a
pure, deterministic, DB-free transformation. It is deliberately NOT wired into
the locked V1 ETL stages (``steps extract..derive`` stay scoped to
``daily_attendance`` / ``weekly_timetable`` for the 50-student CSE sem-7 cohort)
— it is the loader-preparation counterpart consumed by the read-only dry-run.

Scope of this module:

A. IDENTITY / ACADEMIC-YEAR VALIDATION (cohort-aware)
   Student ids ``STU6A0001..STU6A1200`` and enrollment numbers are validated
   through the SAME cohort-aware ``Scope`` machinery the ETL already implements
   (``etl.validation``), using the ``ETL_STUDENT_ID_NAMESPACES_EXTRA`` /
   ``ETL_ENROLLMENT_NO_PATTERNS_EXTRA`` configuration. No regex is hardcoded in
   transform code; the caller supplies an ``EtlConfig``/``Scope`` (configuration).
   ``academic_year`` is validated in "YYYY-YY" (or V1 "YYYY-YYYY") format via the
   configured ``ETL_ACADEMIC_YEAR_PATTERN``.

B. FACULTY_STUDENT_MAP TRANSFORM (1:1 with target ``faculty_student_map``)
   Source rows carry only ``mapping_id, faculty_id, student_id, semester_no,
   mapping_type, is_active``. The live table (verified) requires NOT-NULL
   ``faculty_id, student_id, enrollment_no, department, mentor_role, mentor_since,
   status`` (``allocation_reason`` is nullable) plus the four proposed columns
   ``mapping_id, semester_no, mapping_type, is_active``. The transform derives the
   maintenance fields authoritatively from ``students`` and maps ``MENTOR`` to a
   CHECK-legal ``mentor_role``:
     * ``enrollment_no``       <- students.enrollment_no
     * ``department``          <- students.department_name (live column stores names,
                                  e.g. 'CSE'; NOT students.department_code which is
                                  an integer and would corrupt the VARCHAR contract)
     * ``mentor_since``        <- students.admission_date (authoritative, always set)
     * ``status``              <- 'Active' when is_active else 'Inactive'
     * ``mentor_role``         <- mapping_type looked up in MENTOR_ROLE_BY_MAPPING_TYPE
                                  (only CHECK-legal values are ever produced)
     * ``faculty_student_map_id`` <- mapping_id (unique PK carrier, VARCHAR 6A form)
   Rows that cannot be derived (unknown student, unknown mapping_type) are returned
   as quarantine records with a deterministic reason — never fabricated, never
   silently dropped.

C. MARKS TRANSFORMATION (source 0-100 frame -> DB 0-140 frame)
   Source frame (verified over all 68,400 performance rows):
     ``total_marks = internal_marks + mid_sem_marks + end_sem_marks``,
     ``percentage = clip(total_marks, 0, 100)`` — components carry the DB maxima
     (internal<=20, mid<=50, end<=70) but the aggregate stays on a 0-100 scale.
   DB contract frame (verified live):
     ``percentage = ROUND((internal+mid_sem+end_sem)/140.0*100, 2)`` with INTEGER
     components bounded by CHECK (0-20 / 0-50 / 0-70, total 0-140).
   Transform: PERCENTAGE-PRESERVING RE-PROJECTION. Integer components are chosen
   within the DB maxima whose sum yields ``target_total = round(src_pct/100*140)``
   so ``percentage = total/140*100`` equals the source percentage (rounding-only).
   Uniform ``*1.4`` scaling is FORBIDDEN (e.g. internal 18*1.4=25.2 > 20). All
   derived labels (grade/grade_point/result_status/performance_category/remarks)
   are re-derived with the authoritative ``derive_marks_fields`` (app/services/
   faculty_service.py) — identical to the live trigger, so the load is idempotent.

No database access, no file writes, no ML target/artifact changes, no CT1/CT2
re-mapping, no M1 feature engineering. Deterministic by construction: pure
functions of their inputs (P2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from app.core.config import settings as app_settings
from app.services.faculty_service import derive_marks_fields

from etl.config import EtlConfig, etl_config
from etl.validation import (
    Scope,
    _enrollment_no_in_scope,
    _student_id_in_scope,
    valid_academic_year,
)

# ---------------------------------------------------------------------------
# Cohort configuration (input to the existing cohort-aware Scope machinery).
# The regex specifications are CONFIGURATION for validate_1200_identity — they
# are fed through EtlConfig/Scope exactly like test_etl_extract_validate does —
# never regexes hardcoded inside a stage. Callers may supply their own.
# ---------------------------------------------------------------------------
ETL_STUDENT_ID_NAMESPACES_EXTRA_1200 = [r"^STU6A\d{4}$|STU6A0001|STU6A1200"]
ETL_ENROLLMENT_NO_PATTERNS_EXTRA_1200 = [r"^20(21|22)\d{6}$"]
ETL_ACADEMIC_YEAR_PATTERN_1200 = r"^\d{4}-\d{2}$"

# ---------------------------------------------------------------------------
# faculty_student_map live contract (verified against information_schema).
# ---------------------------------------------------------------------------
FSM_TABLE = "faculty_student_map"
FSM_MENTOR_ROLE_VALUES = frozenset(
    {"Academic Mentor", "Faculty Advisor", "Placement Mentor"}
)
FSM_STATUS_VALUES = frozenset({"Active", "Inactive"})
# mapping_type -> mentor_role: only CHECK-legal values are ever produced.
MENTOR_ROLE_BY_MAPPING_TYPE: Dict[str, str] = {"MENTOR": "Academic Mentor"}

# Canonical faculty_student_map columns the loader writes. allocation_reason is
# nullable in live and is NOT fabricated here.
FSM_CANONICAL_COLUMNS = (
    "faculty_student_map_id",
    "mapping_id",
    "faculty_id",
    "student_id",
    "enrollment_no",
    "department",
    "mentor_role",
    "mentor_since",
    "status",
    "semester_no",
    "mapping_type",
    "is_active",
)
FSM_NOT_NULL_COLUMNS = (
    "faculty_student_map_id",
    "faculty_id",
    "student_id",
    "enrollment_no",
    "department",
    "mentor_role",
    "mentor_since",
    "status",
)

# ---------------------------------------------------------------------------
# Marks contract (mirrors app/core/config.py MARKS_* and live CHECKs).
# ---------------------------------------------------------------------------
MARKS_INTERNAL_MAX = app_settings.MARKS_INTERNAL_MAX
MARKS_MID_SEM_MAX = app_settings.MARKS_MID_SEM_MAX
MARKS_END_SEM_MAX = app_settings.MARKS_END_SEM_MAX
MARKS_TOTAL_MAX = app_settings.MARKS_TOTAL_MAX
MARKS_CAPS = (MARKS_INTERNAL_MAX, MARKS_MID_SEM_MAX, MARKS_END_SEM_MAX)

# Pre-end-semester assessed columns the live performance table carries (M1
# permitted signals). Passed through unchanged — never derived, never used as
# the marks ground truth.
PERF_PASSTHROUGH_COLUMNS = (
    "division",
    "assignment_score",
    "quiz_avg_marks",
    "submission_delay_days",
    "pre_endsem_assessment_pct",
    "subject_domain",
    "subject_skill",
)


@dataclass(frozen=True)
class QuarantineRow:
    """One row the transform could not produce, with a deterministic reason."""

    source: str
    mapping_id: str
    row_index: int
    reason_code: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "mapping_id": self.mapping_id,
            "row_index": self.row_index,
            "reason_code": self.reason_code,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class IdentityViolation:
    """A deterministic identity/academic-year validation finding."""

    reason_code: str
    sample: Sequence[str]
    count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reason_code": self.reason_code,
            "count": self.count,
            "sample": list(self.sample[:10]),
        }


@dataclass
class IdentityValidation:
    """Cohort-aware identity + academic-year validation result (DB-free)."""

    valid: bool = True
    violations: List[IdentityViolation] = field(default_factory=list)
    checks: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "checks": dict(self.checks),
            "violations": [v.to_dict() for v in self.violations],
        }


@dataclass(frozen=True)
class TransformOutcome:
    """Pure output of a transform: canonical rows + quarantined rows."""

    rows: Sequence[Dict[str, Any]]
    quarantined: Sequence[QuarantineRow] = ()

    @property
    def accepted(self) -> int:
        return len(self.rows)

    @property
    def rejected(self) -> int:
        return len(self.quarantined)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted": self.accepted,
            "rejected": self.rejected,
            "quarantined": [q.to_dict() for q in self.quarantined],
        }


# ---------------------------------------------------------------------------
# A. Identity / academic-year validation (cohort-aware Scope)
# ---------------------------------------------------------------------------
def build_1200_scope(config: Optional[EtlConfig] = None) -> Scope:
    """Build a cohort-aware ``Scope`` for the CSE 6A 1,200 cohort.

    The 6A namespaces are supplied as EtlConfig values (configuration), exactly
    like ``test_etl_extract_validate`` exercises the extra-namespace machinery.
    Existing base patterns (``^STU\\d{6}$`` etc.) are replaced for this cohort by
    the 6A namespace registered in ``ETL_STUDENT_ID_NAMESPACES_EXTRA``.
    """
    cfg = config or etl_config.model_copy(
        update={
            "ETL_STUDENT_ID_NAMESPACES_EXTRA": ETL_STUDENT_ID_NAMESPACES_EXTRA_1200,
            "ETL_ENROLLMENT_NO_PATTERNS_EXTRA": ETL_ENROLLMENT_NO_PATTERNS_EXTRA_1200,
            "ETL_ACADEMIC_YEAR_PATTERN": ETL_ACADEMIC_YEAR_PATTERN_1200,
        }
    )
    return Scope.from_config(cfg)


def validate_1200_identity(
    students: Sequence[Dict[str, Any]],
    *,
    scope: Optional[Scope] = None,
) -> IdentityValidation:
    """Validate the 6A cohort's identity + academic-year fields, DB-free.

    Checks are deterministic functions of the rows + scope (P2). Enrollment
    numbers and student ids pass through the SAME cohort-aware membership
    functions the ETL uses; academic year follows the configured pattern.
    """
    scope = scope or build_1200_scope()
    result = IdentityValidation()

    if not students:
        result.valid = False
        result.checks["students_present"] = False
        return result
    result.checks["students_present"] = True

    check_id, check_eno, check_ay = [], [], []
    for row in students:
        sid = str(row.get("student_id") or "")
        eno = str(row.get("enrollment_no") or "")
        ay = str(row.get("current_academic_year") or "")
        if not _student_id_in_scope(sid, scope):
            check_id.append(sid)
        if eno and not _enrollment_no_in_scope(eno, scope):
            check_eno.append(eno)
        if ay and not valid_academic_year(ay, scope):
            check_ay.append(ay)

    if check_id:
        result.valid = False
        result.violations.append(
            IdentityViolation("invalid_student_id", check_id, len(check_id))
        )
    if check_eno:
        result.valid = False
        result.violations.append(
            IdentityViolation("invalid_enrollment_no", check_eno, len(check_eno))
        )
    if check_ay:
        result.valid = False
        result.violations.append(
            IdentityViolation("invalid_academic_year", check_ay, len(check_ay))
        )

    result.checks["student_ids_in_scope"] = not check_id
    result.checks["enrollment_nos_in_scope"] = not check_eno
    result.checks["academic_years_valid"] = not check_ay
    result.valid = result.valid and not result.violations
    return result


# ---------------------------------------------------------------------------
# B. faculty_student_map transform
# ---------------------------------------------------------------------------
def transform_faculty_student_map(
    rows: Sequence[Dict[str, Any]],
    students_by_id: Dict[str, Dict[str, Any]],
    *,
    mentor_role_by_mapping_type: Optional[Dict[str, str]] = None,
) -> TransformOutcome:
    """Derive the canonical ``faculty_student_map`` rows (dry-run, DB-free).

    ``students_by_id`` maps ``student_id`` to the authoritative student fields
    (``enrollment_no``, ``department_name``, ``admission_date``). A row whose
    student_id is unknown, or whose mapping_type has no CHECK-legal mentor_role,
    is quarantined with a deterministic reason — never fabricated.
    """
    role_map = mentor_role_by_mapping_type or MENTOR_ROLE_BY_MAPPING_TYPE
    rows_out: List[Dict[str, Any]] = []
    quarantined: List[QuarantineRow] = []

    for index, row in enumerate(rows, start=2):
        mapping_id = str(row.get("mapping_id") or "")
        student_id = str(row.get("student_id") or "")
        faculty_id = str(row.get("faculty_id") or "")
        mapping_type = str(row.get("mapping_type") or "").strip()
        is_active_val = row.get("is_active")
        is_active = (
            str(is_active_val).strip().lower() in {"true", "1", "yes", "y"}
            if is_active_val is not None
            else False
        )
        semester_no = row.get("semester_no")

        student = students_by_id.get(student_id)
        if student is None:
            quarantined.append(
                QuarantineRow(
                    source="faculty_student_map",
                    mapping_id=mapping_id,
                    row_index=index,
                    reason_code="student_not_found",
                    reason=f"student_id '{student_id}' not found in students source",
                )
            )
            continue

        mentor_role = role_map.get(mapping_type)
        if mentor_role not in FSM_MENTOR_ROLE_VALUES:
            quarantined.append(
                QuarantineRow(
                    source="faculty_student_map",
                    mapping_id=mapping_id,
                    row_index=index,
                    reason_code="mentor_role_not_check_legal",
                    reason=(
                        f"mapping_type '{mapping_type}' has no CHECK-legal "
                        "mentor_role (allowed: "
                        + ", ".join(sorted(FSM_MENTOR_ROLE_VALUES)) + ")"
                    ),
                )
            )
            continue

        rows_out.append(
            {
                "faculty_student_map_id": mapping_id,
                "mapping_id": mapping_id,
                "faculty_id": faculty_id,
                "student_id": student_id,
                "enrollment_no": int(student["enrollment_no"]),
                "department": str(student["department_name"]),
                "mentor_role": mentor_role,
                "mentor_since": str(student["admission_date"]),
                "status": "Active" if is_active else "Inactive",
                "semester_no": (
                    int(semester_no) if str(semester_no).strip().isdigit() else None
                ),
                "mapping_type": mapping_type,
                "is_active": is_active,
            }
        )

    return TransformOutcome(rows_out, quarantined)


def summarize_faculty_student_map(
    outcome: TransformOutcome,
) -> Dict[str, Any]:
    """Deterministic summary of a faculty_student_map transform (report gate)."""
    from collections import Counter

    rows = list(outcome.rows)
    pairs = Counter((r["faculty_id"], r["student_id"]) for r in rows)
    dup_pairs = [k for k, v in pairs.items() if v > 1]
    dup_pairs_sorted = sorted(dup_pairs)
    return {
        "accepted": len(rows),
        "rejected": outcome.rejected,
        "mentor_role": dict(Counter(r["mentor_role"] for r in rows)),
        "status": dict(Counter(r["status"] for r in rows)),
        "department": dict(Counter(r["department"] for r in rows)),
        "mapping_type": dict(Counter(r["mapping_type"] for r in rows)),
        "semester_no": dict(Counter(r["semester_no"] for r in rows)),
        "is_active": dict(Counter(r["is_active"] for r in rows)),
        "distinct_faculty": len({r["faculty_id"] for r in rows}),
        "distinct_students": len({r["student_id"] for r in rows}),
        "unique_pairs": len(rows) - len(dup_pairs),
        "duplicate_pairs": len(dup_pairs_sorted),
        "duplicate_pair_samples": dup_pairs_sorted[:10],
        "null_in_not_null_columns": sorted(
            {
                col
                for col in FSM_NOT_NULL_COLUMNS
                if any(not r.get(col) for r in rows)
            }
        ),
        "not_null_columns_ok": all(
            all(r.get(col) not in (None, "") for r in rows)
            for col in FSM_NOT_NULL_COLUMNS
        ),
    }


# ---------------------------------------------------------------------------
# C. Marks transformation (source 0-100 frame -> DB 0-140 frame)
# ---------------------------------------------------------------------------
def _largest_remainder(
    components: Sequence[float], caps: Sequence[int], target_total: int
) -> List[int]:
    """Allocate ``target_total`` across components proportionally, bounded ints.

    Largest-remainder method: each component gets a floor of its proportional
    share of ``target_total``, then the residual points are assigned to the
    components with the largest fractional remainders — still never exceeding a
    component's cap. Deterministic (ties broken by stable index order).
    """
    caps = list(caps)
    n = len(caps)
    total_in = sum(components)
    if total_in <= 0:
        return [0] * n
    raw = [float(ci) / total_in * target_total for ci in components]
    for k in range(n):
        raw[k] = min(raw[k], float(caps[k]))
    floor = [int(v) for v in raw]
    remainder = target_total - sum(floor)
    fracs = sorted(range(n), key=lambda k: raw[k] - floor[k], reverse=True)
    alloc = list(floor)
    for k in fracs:
        if remainder <= 0:
            break
        if alloc[k] < caps[k]:
            alloc[k] += 1
            remainder -= 1
    return alloc


def reproject_marks(
    internal: float,
    mid_sem: float,
    end_sem: float,
    source_percentage: float,
    *,
    caps: Sequence[int] = MARKS_CAPS,
) -> tuple:
    """Project source components into DB-bounded INTEGER components.

    Percentage-preserving re-projection: the source components carry the DB
    per-component maxima (internal 0-20, mid 0-50, end 0-70) but the source
    ``total_marks``/``percentage`` are reported on a 0-100 scale. To satisfy the
    DB contract ``percentage = total/140*100`` (with INTEGER components) we
    choose integer components ``<=`` each cap whose sum equals
    ``target_total = round(src_pct/100*140)`` so the DB percentage equals the
    source percentage up to rounding. Uniform ``*1.4`` scaling is forbidden
    (18*1.4=25.2 > 20). Pure/deterministic.
    """
    caps = list(caps)
    if len(caps) != 3:
        raise ValueError(f"expected 3 component caps, got {len(caps)}")
    total_cap = sum(caps)
    target_total = int(round(float(source_percentage) / 100.0 * total_cap))
    target_total = min(max(target_total, 0), total_cap)

    alloc = _largest_remainder([internal, mid_sem, end_sem], caps, target_total)

    delta = target_total - sum(alloc)
    while delta != 0:
        if delta > 0:
            idx = [k for k in range(3) if alloc[k] < caps[k]]
            if not idx:
                break
            k = max(idx, key=lambda kk: (alloc[kk] / caps[kk]) if caps[kk] else 1)
            alloc[k] += 1
            delta -= 1
        else:
            idx = [k for k in range(3) if alloc[k] > 0]
            if not idx:
                break
            k = min(idx, key=lambda kk: (alloc[kk] / caps[kk]) if caps[kk] else 1)
            alloc[k] -= 1
            delta += 1

    return (alloc[0], alloc[1], alloc[2])


def source_percentage_from_components(
    internal: Any, mid_sem: Any, end_sem: Any
) -> float:
    """Source-frame percentage: ``clip(internal+mid+end, 0, 100)``."""
    total = float(internal) + float(mid_sem) + float(end_sem)
    return min(max(total, 0.0), 100.0)


def transform_performance_row(
    row: Dict[str, Any],
    *,
    caps: Sequence[int] = MARKS_CAPS,
) -> Dict[str, Any]:
    """Transform ONE performance row to the DB 0-140 contract (dry-run).

    The three components are re-projected (percentage-preserving) and every
    derived label (total/percentage/grade/grade_point/result_status/
    performance_category/remarks) is re-derived with the authoritative
    ``derive_marks_fields`` — matching the live trigger so the load is
    idempotent. M1-permitted pre-end-sem columns pass through unchanged; CT1/CT2
    are not re-mapped (left absent, loader sets NULL).
    """
    internal = float(row["internal_marks"])
    mid_sem = float(row["mid_sem_marks"])
    end_sem = float(row["end_sem_marks"])
    src_pct = float(row.get("percentage") or 0.0)

    i, m, e = reproject_marks(internal, mid_sem, end_sem, src_pct, caps=caps)
    derived = derive_marks_fields(i, m, e)

    out: Dict[str, Any] = {
        "performance_id": row.get("performance_id"),
        "enrollment_record_id": row.get("enrollment_record_id"),
        "enrollment_no": int(row["enrollment_no"]),
        "student_id": row.get("student_id"),
        "subject_id": row.get("subject_id"),
        "semester_no": int(row.get("semester_no") or 0),
        "attempt_number": int(row.get("attempt_number") or 1),
        "internal_marks": i,
        "mid_sem_marks": m,
        "end_sem_marks": e,
        "total_marks": derived["total_marks"],
        "percentage": derived["percentage"],
        "grade": derived["grade"],
        "grade_point": derived["grade_point"],
        "result_status": derived["result_status"],
        "performance_category": derived["performance_category"],
        "remarks": derived["remarks"],
    }
    for col in PERF_PASSTHROUGH_COLUMNS:
        if col in row:
            out[col] = row.get(col)
    return out


def transform_performance_rows(
    rows: Sequence[Dict[str, Any]],
    *,
    caps: Sequence[int] = MARKS_CAPS,
) -> List[Dict[str, Any]]:
    """Transform every performance row deterministically (order preserved)."""
    return [transform_performance_row(r, caps=caps) for r in rows]


# ---------------------------------------------------------------------------
# D. Blocker-resolution transforms (B1-B5: vocabulary / architecture gates)
#    All pure, deterministic, DB-free. Every output value is proven to satisfy
#    the corresponding live CHECK constraint by the focused tests.
# ---------------------------------------------------------------------------

# ---- B1. admission_quota (students) ---------------------------------------
# Live CHECK: {'ACPC', 'Management', 'TFW'}  (verified from the live snapshot)
# Source vocabulary: {Merit: 960, Management: 240}
#
# Semantic decision (NOT a blind 'Merit -> Management' collapse):
# In Gujarat higher-education admission, 'ACPC' is the merit-based admission
# committee channel (merit counselling), 'Management' is the paid/quota seat,
# and 'TFW' is the tuition-fee-waiver seat. 'Merit' denotes merit-based
# admission, which is the same semantic category as 'ACPC'. Mapping 'Merit'
# onto 'ACPC' preserves the distinguished meaning of merit-based admission and
# keeps it separate from the paid 'Management' quota. A blind 'Merit ->
# Management' mapping would wrongly reclassify 960 merit-admitted students as
# paid-quota and is therefore rejected.
ADMISSION_QUOTA_ALLOWED = frozenset({"ACPC", "Management", "TFW"})
ADMISSION_QUOTA_MAP: Dict[str, str] = {
    "Merit": "ACPC",
    "Management": "Management",
}


def map_admission_quota(value: Any) -> Optional[str]:
    """Map a source admission_quota to a live CHECK-legal value (deterministic).

    ``None``/empty maps to ``None`` (never fabricated). A value with no mapping
    (i.e. not already live-Check-legal and not in the known map) returns ``None``
    so the caller can quarantine it — the transform never guesses a value.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text in ADMISSION_QUOTA_ALLOWED:
        return text
    return ADMISSION_QUOTA_MAP.get(text)


# ---- B2/B3. academic_standing (students + semester_summary) ---------------
# Live CHECK: {'Outstanding', 'Excellent', 'Good', 'Average', 'Needs Improvement'}
# Source vocabulary (identical in both tables): {Good Standing, Satisfactory,
# Needs Attention} — a clear 3-level ordinal scale, verified by the source data
# (Good Standing students avg overall percentage ~76% with 0 backlogs;
# Satisfactory ~65% with 0-1 backlogs; Needs Attention ~64% with 2-3 backlogs).
#
# ONE centralized, deterministic, order-preserving, injective mapping shared by
# BOTH tables. The source's 3-level ordinal scale maps onto the live 5-level
# scale's middle-to-low region — the two top live tiers (Outstanding/Excellent)
# are deliberately NOT claimed because the source data never asserts the very
# top tier, and no two source levels collapse to the same live level (no
# information loss):
#   Good Standing  -> Good             (upper-mid tier)
#   Satisfactory   -> Average          (mid tier)
#   Needs Attention-> Needs Improvement(low tier / near-synonym)
ACADEMIC_STANDING_ALLOWED = frozenset(
    {"Outstanding", "Excellent", "Good", "Average", "Needs Improvement"}
)
ACADEMIC_STANDING_MAP: Dict[str, str] = {
    "Good Standing": "Good",
    "Satisfactory": "Average",
    "Needs Attention": "Needs Improvement",
}


def map_academic_standing(value: Any) -> Optional[str]:
    """Map a source academic_standing to a live CHECK-legal value (deterministic).

    Shared by the ``students`` (B2) and ``student_semester_summary`` (B3)
    transforms. ``None``/empty maps to ``None``; unknown values (neither a live
    level nor a mapped source level) map to ``None`` so the caller can
    quarantine deterministically — the transform never invents a value.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text in ACADEMIC_STANDING_ALLOWED:
        return text
    return ACADEMIC_STANDING_MAP.get(text)


# ---- mental_stress_level (student_lifestyle_survey, per-semester grain) -----
# Source vocabulary (lifestyle_survey_6A_1200_final.csv): {Low, Medium, High} —
# a 3-level ordinal self-report scale (source distribution High=2863,
# Medium=4556, Low=2181). These are the ONLY legal values.
#
# ARCHITECTURE DECISION: stress is CATEGORICAL TEXT, never a numeric column.
#   * The existing 80-student `lifestyle_survey.stress_level` is `character
#     varying` with values {Low, Medium, High, Very High}.
#   * M4 (ml/src/m4/engine.py) reads that categorical string and maps it
#     internally (STRESS_LEVEL_MAP = {"Very High":0, "High":1, "Medium":3,
#     "Low":5}); M4 has NO numeric stress dependency.
# Phase 2 mistakenly created the NEW per-semester table's
# `mental_stress_level` as NUMERIC; the (non-applied) corrective migration
# alters it to VARCHAR and this transform performs the deterministic
# categorical validation + identity mapping. A derived numeric feature
# (e.g. stress_level_encoded Low->0, Medium->1, High->2) may ONLY live at the
# ML feature-engineering layer if ever needed — never stored in the warehouse.
STRESS_LEVEL_ALLOWED = frozenset({"Low", "Medium", "High"})


def map_stress_level(value: Any) -> Optional[str]:
    """Return the categorical stress level if legal, else ``None`` (deterministic).

    ``None``/empty maps to ``None`` (survey dimension not reported — never
    fabricated). An unknown value returns ``None`` so the calling step can
    reject the row — the transform never invents or re-encodes a value.
    """
    if value is None:
        return None
    text = str(value).strip()
    if text in STRESS_LEVEL_ALLOWED:
        return text
    return None


# Students canonical output columns touched by B1/B2.
STUDENTS_VOCAB_COLUMNS = ("admission_quota", "academic_standing")


def transform_student_vocabulary(
    rows: Sequence[Dict[str, Any]],
) -> TransformOutcome:
    """B1+B2: produce CHECK-legal ``admission_quota`` and ``academic_standing``.

    Returns the original row with the two vocabulary fields mapped to live
    CHECK-legal values. A row with an unmappable value is quarantined with a
    deterministic reason (never fabricated, never silently dropped).
    """
    rows_out: List[Dict[str, Any]] = []
    quarantined: List[QuarantineRow] = []

    for index, row in enumerate(rows, start=2):
        sid = str(row.get("student_id") or "")
        quota = map_admission_quota(row.get("admission_quota"))
        standing = map_academic_standing(row.get("academic_standing"))

        if quota is None and row.get("admission_quota") is not None:
            quarantined.append(
                QuarantineRow(
                    source="students",
                    mapping_id=sid,
                    row_index=index,
                    reason_code="admission_quota_unmappable",
                    reason=(
                        f"admission_quota '{row.get('admission_quota')}' has no "
                        "CHECK-legal mapping (allowed: "
                        + ", ".join(sorted(ADMISSION_QUOTA_ALLOWED)) + ")"
                    ),
                )
            )
            continue

        if standing is None and row.get("academic_standing") is not None:
            quarantined.append(
                QuarantineRow(
                    source="students",
                    mapping_id=sid,
                    row_index=index,
                    reason_code="academic_standing_unmappable",
                    reason=(
                        f"academic_standing '{row.get('academic_standing')}' has "
                        "no CHECK-legal mapping (allowed: "
                        + ", ".join(sorted(ACADEMIC_STANDING_ALLOWED)) + ")"
                    ),
                )
            )
            continue

        mapped = dict(row)
        if quota is not None:
            mapped["admission_quota"] = quota
        if standing is not None:
            mapped["academic_standing"] = standing
        rows_out.append(mapped)

    return TransformOutcome(rows_out, quarantined)


def summarize_student_vocabulary(
    source_rows: Sequence[Dict[str, Any]],
    outcome: TransformOutcome,
) -> Dict[str, Any]:
    """Deterministic B1/B2 summary: counts + live-Check coverage proof."""
    from collections import Counter

    rows = list(outcome.rows)
    quota = Counter(r.get("admission_quota") for r in rows)
    standing = Counter(r.get("academic_standing") for r in rows)
    return {
        "accepted": len(rows),
        "rejected": outcome.rejected,
        "source_admission_quota": dict(
            Counter(r.get("admission_quota") for r in source_rows)
        ),
        "mapped_admission_quota": dict(quota),
        "admission_quota_all_check_legal": all(
            v in ADMISSION_QUOTA_ALLOWED for v in quota
        ),
        "source_academic_standing": dict(
            Counter(r.get("academic_standing") for r in source_rows)
        ),
        "mapped_academic_standing": dict(standing),
        "academic_standing_all_check_legal": all(
            v in ACADEMIC_STANDING_ALLOWED for v in standing
        ),
    }


def transform_semester_summary_standing(
    rows: Sequence[Dict[str, Any]],
) -> TransformOutcome:
    """B3: map ``student_semester_summary.academic_standing`` to CHECK-legal.

    Reuses the SAME centralized ``map_academic_standing`` as the students
    (B2) transform. A row with an unmappable value is quarantined.
    """
    rows_out: List[Dict[str, Any]] = []
    quarantined: List[QuarantineRow] = []

    for index, row in enumerate(rows, start=2):
        sid = str(row.get("student_id") or "")
        standing = map_academic_standing(row.get("academic_standing"))
        if standing is None and row.get("academic_standing") is not None:
            quarantined.append(
                QuarantineRow(
                    source="student_semester_summary",
                    mapping_id=sid,
                    row_index=index,
                    reason_code="academic_standing_unmappable",
                    reason=(
                        f"academic_standing '{row.get('academic_standing')}' has "
                        "no CHECK-legal mapping (allowed: "
                        + ", ".join(sorted(ACADEMIC_STANDING_ALLOWED)) + ")"
                    ),
                )
            )
            continue
        mapped = dict(row)
        if standing is not None:
            mapped["academic_standing"] = standing
        rows_out.append(mapped)

    return TransformOutcome(rows_out, quarantined)


def summarize_semester_summary_standing(
    source_rows: Sequence[Dict[str, Any]],
    outcome: TransformOutcome,
) -> Dict[str, Any]:
    """Deterministic B3 summary: counts + live-Check coverage proof."""
    from collections import Counter

    rows = list(outcome.rows)
    standing = Counter(r.get("academic_standing") for r in rows)
    return {
        "accepted": len(rows),
        "rejected": outcome.rejected,
        "source_academic_standing": dict(
            Counter(r.get("academic_standing") for r in source_rows)
        ),
        "mapped_academic_standing": dict(standing),
        "academic_standing_all_check_legal": all(
            v in ACADEMIC_STANDING_ALLOWED for v in standing
        ),
        "mapping_engine": "map_academic_standing (shared B2/B3)",
    }


# ---- B4. career_preferences v2 (architecture: separate table) --------------
# Decision: create a DEDICATED ``career_preferences_v2`` table for the new
# 1,200-cohort career schema and LEAVE the existing ``career_preferences``
# (80-cohort, M4-read) table completely untouched.
#
# Rationale:
#  * M4's contract (student_repo.get_career_preferences) SELECTs the OLD schema
#    columns (preferred_domain, dream_job_role, preferred_industry,
#    preferred_work_mode, target_package_lpa, higher_studies_interest,
#    entrepreneurship_interest, certification_interest, internship_completed,
#    placement_readiness_level, survey_date). The new 1,200 CSV has NONE of
#    those — it is a different, richer schema.
#  * The old NOT-NULL + CHECK constraints on career_preferences would reject
#    (or force fake values for) the new rows; the task forbids fabricating
#    entrepreneurship_interest/certification_interest/internship_completed/
#    placement_readiness_level/target_package_lpa/survey_date/preferred_industry/
#    preferred_domain.
#  * M4 is rule-based/deterministic today and its persisted output must be
#    preserved — re-basing M4 onto the new career schema is a SEPARATE future
#    task. Architecture B isolates the new schema, preserves the 80-cohort data,
#    retains ALL new career information, and keeps M4's existing contract intact.
CAREER_PREFERENCES_V2_TABLE = "career_preferences_v2"
CAREER_PREFERENCES_V2_COLUMNS = (
    "career_preference_id",
    "student_id",
    "primary_interest_domain",
    "secondary_interest_domain",
    "preferred_role",
    "higher_studies_intent",
    "preferred_work_mode",
    "desired_salary_lpa",
    "career_role_category",
    "career_preference_version",
    "required_skills_for_preferred_role",
    "role_skill_profile_version",
    "career_preference_source",
)


def transform_career_preferences_v2(
    rows: Sequence[Dict[str, Any]],
    students_by_id: Dict[str, Dict[str, Any]],
) -> TransformOutcome:
    """B4: project the new career CSV onto the dedicated ``career_preferences_v2``.

    The new schema is stored verbatim with NO fabricated values. Only the
    canonical v2 columns are kept (in canonical order). A row whose student_id
    is not in the 1,200 students master is quarantined (FK safety) — never
    invented.
    """
    rows_out: List[Dict[str, Any]] = []
    quarantined: List[QuarantineRow] = []

    for index, row in enumerate(rows, start=2):
        cp_id = str(row.get("career_preference_id") or "")
        student_id = str(row.get("student_id") or "")

        if student_id not in students_by_id:
            quarantined.append(
                QuarantineRow(
                    source=CAREER_PREFERENCES_V2_TABLE,
                    mapping_id=cp_id,
                    row_index=index,
                    reason_code="student_not_found",
                    reason=(
                        f"student_id '{student_id}' not found in the 1,200 "
                        "cohort students master"
                    ),
                )
            )
            continue

        out: Dict[str, Any] = {}
        for col in CAREER_PREFERENCES_V2_COLUMNS:
            out[col] = row.get(col)
        rows_out.append(out)

    return TransformOutcome(rows_out, quarantined)


def summarize_career_preferences_v2(
    outcome: TransformOutcome,
) -> Dict[str, Any]:
    """Deterministic B4 summary: row count, column coverage, FK integrity."""
    from collections import Counter

    rows = list(outcome.rows)
    return {
        "table": CAREER_PREFERENCES_V2_TABLE,
        "accepted": len(rows),
        "rejected": outcome.rejected,
        "distinct_students": len({r["student_id"] for r in rows}),
        "unique_student_ids": len(rows) == len({r["student_id"] for r in rows}),
        "columns_written": list(CAREER_PREFERENCES_V2_COLUMNS),
        "fabricated_fields": [],  # none — the v2 schema stores only declared data
    }


# ---- B5. hard safety gate: raw performance CSV must NEVER be inserted -------
# The raw CSV stores `performance_category` in a vocab {Good, Developing,
# Excellent, At Risk} that is NOT the live CHECK set {Top, Above Average,
# Average, Below Average, Low Performer}, and stores marks on a 0-100 weighted
# aggregate frame (decimal components) instead of the live 0-140 INTEGER frame.
# Inserting raw rows verbatim would (a) fail the performance_category CHECK and
# (b) be overwritten by the sem-7 trigger, silently corrupting data. Therefore
# the loader MUST always consume ``transform_performance_rows`` output.
PERF_LIVE_CATEGORY_VALUES = frozenset(
    {"Top", "Above Average", "Average", "Below Average", "Low Performer"}
)
PERF_LIVE_GRADE_VALUES = frozenset({"O", "A+", "A", "B+", "B", "C", "F"})
PERF_LIVE_STATUS_VALUES = frozenset({"Pass", "Fail"})
PERF_SOURCE_CATEGORY_VALUES = frozenset(
    {"Good", "Developing", "Excellent", "At Risk"}
)


def guard_raw_performance_not_insertable(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    """Return all reasons a RAW performance row must NOT be inserted directly.

    This is the hard safety gate for B5: it inspects rows and returns a list of
    human-readable reasons why the raw CSV is not loadable as-is. The loader
    must assert this is empty for any row it attempts to write; instead it must
    pass rows through ``transform_performance_rows``. Deterministic/DB-free.
    """
    reasons: List[str] = []
    for index, row in enumerate(rows, start=2):
        row_reasons: List[str] = []
        for col, cap in (
            ("internal_marks", MARKS_INTERNAL_MAX),
            ("mid_sem_marks", MARKS_MID_SEM_MAX),
            ("end_sem_marks", MARKS_END_SEM_MAX),
        ):
            if col in row and row[col] not in (None, ""):
                try:
                    v = float(row[col])
                except (TypeError, ValueError):
                    row_reasons.append(f"{col} not numeric")
                    continue
                if not v.is_integer():
                    row_reasons.append(f"{col} not an integer for DB INTEGER column")
                if not (0 <= v <= cap):
                    row_reasons.append(f"{col} out of DB range 0-{cap}")
        src_pct = row.get("percentage")
        if src_pct not in (None, ""):
            try:
                v = float(src_pct)
                if not (0 <= v <= 100):
                    row_reasons.append("percentage out of 0-100")
            except (TypeError, ValueError):
                row_reasons.append("percentage not numeric")
        if row.get("performance_category") in PERF_SOURCE_CATEGORY_VALUES:
            row_reasons.append(
                "performance_category is the source vocab (not a live CHECK value)"
            )
        if row.get("grade") not in (None, "") and str(
            row.get("grade")
        ) not in PERF_LIVE_GRADE_VALUES:
            row_reasons.append("grade not a live CHECK value")
        if row.get("result_status") not in (None, "") and str(
            row.get("result_status")
        ) not in PERF_LIVE_STATUS_VALUES:
            row_reasons.append("result_status not a live CHECK value")
        if row_reasons:
            reasons.append(
                f"row {index} ({row.get('performance_id')}): "
                + "; ".join(row_reasons)
            )
    return reasons


def assert_raw_performance_not_loaded(
    rows: Sequence[Dict[str, Any]],
) -> None:
    """Raise if ANY raw performance row would be directly insertable/illegal.

    Hard guard: if the raw CSV's category/grade/status vocab is not already the
    live CHECK set, this raises (the loader must pass rows through
    ``transform_performance_rows`` instead). If the raw set were already live
    compatible, the loader still must NOT bypass the transform (see
    transform_required_note). Deterministic/DB-free.
    """
    reasons = guard_raw_performance_not_insertable(rows)
    if reasons:
        raise ValueError(
            "RAW performance CSV must never be inserted into student_subject_"
            "performance. Run transform_performance_rows first. Issues:\n  "
            + "\n  ".join(reasons[:50])
            + (f"\n  ... and {len(reasons)-50} more" if len(reasons) > 50 else "")
        )


def summarize_marks_transform(
    source_rows: Sequence[Dict[str, Any]],
    transformed_rows: Sequence[Dict[str, Any]],
    *,
    example_count: int = 12,
) -> Dict[str, Any]:
    """Deterministic marks-transform summary + >=10 real before/after examples."""
    from collections import Counter

    totals = []
    grade_pairs = Counter()
    pct_dirs = Counter()
    bad = []
    examples: List[Dict[str, Any]] = []

    n = min(len(source_rows), len(transformed_rows))
    for src, txn in zip(source_rows, transformed_rows):
        src_pct = float(src.get("percentage") or 0.0)
        t_pct = float(txn["percentage"] or 0.0)
        totals.append(t_pct - src_pct)
        grade_pairs[f"{src.get('grade')}->{txn['grade']}"] += 1
        pct_dirs["rounding_drift"] += abs(t_pct - src_pct) > 1.0
        if not (
            0 <= txn["internal_marks"] <= MARKS_INTERNAL_MAX
            and 0 <= txn["mid_sem_marks"] <= MARKS_MID_SEM_MAX
            and 0 <= txn["end_sem_marks"] <= MARKS_END_SEM_MAX
            and txn["total_marks"] == (
                txn["internal_marks"] + txn["mid_sem_marks"] + txn["end_sem_marks"]
            )
            and txn["total_marks"] <= MARKS_TOTAL_MAX
        ):
            bad.append(src.get("performance_id"))

    for idx in range(min(example_count, n)):
        src = source_rows[idx]
        txn = transformed_rows[idx]
        examples.append(
            {
                "performance_id": src.get("performance_id"),
                "source_internal_0_20": src.get("internal_marks"),
                "source_mid_0_50": src.get("mid_sem_marks"),
                "source_end_0_70": src.get("end_sem_marks"),
                "source_total_0_100": src.get("total_marks"),
                "source_pct": src.get("percentage"),
                "source_grade": src.get("grade"),
                "source_grade_point": src.get("grade_point"),
                "transformed_internal": txn["internal_marks"],
                "transformed_mid_sem": txn["mid_sem_marks"],
                "transformed_end_sem": txn["end_sem_marks"],
                "transformed_total_0_140": txn["total_marks"],
                "transformed_pct": txn["percentage"],
                "transformed_grade": txn["grade"],
                "transformed_grade_point": txn["grade_point"],
            }
        )

    return {
        "rows_transformed": n,
        "source_formula": "total_marks = internal+mid+end; percentage = clip(total,0,100)  [0-100 weighted aggregate frame]",
        "db_contract_formula": "percentage = ROUND((internal+mid_sem+end_sem)/140*100, 2); grade/grade_point/result_status/performance_category/remarks via derive_marks_fields  [0-140 frame, INTEGER components]",
        "decision": "Percentage-preserving re-projection (target_total = round(src_pct/100*140); bounded integer components sum to target_total). Uniform *1.4 FORBIDDEN (18*1.4=25.2>20). Re-derived labels == live trigger -> idempotent load.",
        "out_of_db_bounds_rows": len(bad),
        "pct_drift_exceeding_1pt": pct_dirs["rounding_drift"],
        "pct_diff_min": round(min(totals), 2) if totals else 0.0,
        "pct_diff_max": round(max(totals), 2) if totals else 0.0,
        "grade_pairs": dict(grade_pairs.most_common(20)),
        "examples": examples,
    }


__all__ = [
    "ETL_STUDENT_ID_NAMESPACES_EXTRA_1200",
    "ETL_ENROLLMENT_NO_PATTERNS_EXTRA_1200",
    "ETL_ACADEMIC_YEAR_PATTERN_1200",
    "FSM_TABLE",
    "FSM_MENTOR_ROLE_VALUES",
    "FSM_STATUS_VALUES",
    "MENTOR_ROLE_BY_MAPPING_TYPE",
    "FSM_CANONICAL_COLUMNS",
    "FSM_NOT_NULL_COLUMNS",
    "MARKS_INTERNAL_MAX",
    "MARKS_MID_SEM_MAX",
    "MARKS_END_SEM_MAX",
    "MARKS_TOTAL_MAX",
    "MARKS_CAPS",
    "PERF_PASSTHROUGH_COLUMNS",
    "QuarantineRow",
    "IdentityViolation",
    "IdentityValidation",
    "TransformOutcome",
    "build_1200_scope",
    "validate_1200_identity",
    "transform_faculty_student_map",
    "summarize_faculty_student_map",
    "reproject_marks",
    "source_percentage_from_components",
    "transform_performance_row",
    "transform_performance_rows",
    "summarize_marks_transform",
    "ADMISSION_QUOTA_ALLOWED",
    "ADMISSION_QUOTA_MAP",
    "map_admission_quota",
    "transform_student_vocabulary",
    "summarize_student_vocabulary",
    "ACADEMIC_STANDING_ALLOWED",
    "ACADEMIC_STANDING_MAP",
    "map_academic_standing",
    "STRESS_LEVEL_ALLOWED",
    "map_stress_level",
    "transform_semester_summary_standing",
    "summarize_semester_summary_standing",
    "STUDENTS_VOCAB_COLUMNS",
    "CAREER_PREFERENCES_V2_TABLE",
    "CAREER_PREFERENCES_V2_COLUMNS",
    "transform_career_preferences_v2",
    "summarize_career_preferences_v2",
    "PERF_LIVE_CATEGORY_VALUES",
    "PERF_LIVE_GRADE_VALUES",
    "PERF_LIVE_STATUS_VALUES",
    "PERF_SOURCE_CATEGORY_VALUES",
    "guard_raw_performance_not_insertable",
    "assert_raw_performance_not_loaded",
]