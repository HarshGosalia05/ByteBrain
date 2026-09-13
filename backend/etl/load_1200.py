"""PHASE 5 — CSE 6A 1,200-cohort data load runner (ordered, batched, transform-aware).

Consumes the ``New_1200_data_scale`` CSVs through the approved 11-step ordered
load (``MDs/reports/migration/DATA_LOAD_PLAN.md``), applying the B1-B5 transforms from
``etl.cohort1200`` and the ``student_semester_summary`` (B3) standing map, then
emits a deterministic reconciliation report.

Two modes (mirroring the V1 ETL CLI contract):

* ``--dry-run`` (default): zero database writes. All live checks run through a
  read-only session (``default_transaction_read_only = on``) so even a stray
  write would be rejected by Postgres. Loader writes are structurally
  impossible: the insert path is a separate function gated behind ``--apply``.
* ``--apply``: runs the SAME read-only prechecks (guard_preliminary) plus a
  full per-step prepare validation against the source CSVs, and only then
  executes the ordered inserts inside ONE transaction PER STEP with
  ``INSERT ... ON CONFLICT ... DO NOTHING`` (idempotent; conflict targets from
  ``STEPS_CONF`` verified against live unique indexes). Every step is reconciled
  (final 6A-prefix count == accepted) inside its own transaction, so a failed
  step rolls back cleanly and aborts the run. After the last step a read-only
  post-load reconciliation (same 80-cohort fingerprint guard, per-table counts,
  FK/duplicate/leakage/RLS checks) is emitted. ``--apply`` writes only the
  configured 11 target tables; it never touches the 80-cohort, subjects,
  faculty, M1-M4, or analytics code.
* ``--reconcile``: re-runs ONLY the read-only post-load reconciliation against
  the live database (reads the apply-time master/RLS snapshot from the prior
  ``phase5_load_live.json``) and patches that report + canonical artifacts in
  place; performs zero writes.

Dry-run twice must be byte-identical in the canonical body: the ``runtime``
(elapsed/peak-memory) and ``determinism`` sections are excluded from the
canonical body, so the business content + ``determinism_sha256`` are stable
across runs; a ``.canonical.json`` artifact is also emitted.

Nothing here trains M1-M4, writes ML artifacts, touches the V1 ETL stages, or
modifies the existing 80-student cohort.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import re
import sys
import tracemalloc
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import asyncpg

from app.services.faculty_service import derive_marks_fields
from db_env import db_config

from etl.cohort1200 import (
    CAREER_PREFERENCES_V2_COLUMNS,
    FSM_CANONICAL_COLUMNS,
    STRESS_LEVEL_ALLOWED,
    TransformOutcome,
    guard_raw_performance_not_insertable,
    map_academic_standing,
    map_admission_quota,
    map_stress_level,
    transform_career_preferences_v2,
    transform_faculty_student_map,
    transform_performance_row,
    validate_1200_identity,
)
from etl.exceptions import (
    EXIT_SUCCESS,
    EXIT_UNEXPECTED_ERROR,
    EXIT_VALIDATION_FAILURE,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_DIR = REPO_ROOT / "plan_1200_6a"
DEFAULT_DATASETS = REPO_ROOT / "backend" / "datasets" / "New_1200_data_scale"
PREFLIGHT_REPORT = PLAN_DIR / "preflight_1200_live.json"
BASELINE_REPORT = PLAN_DIR / "phase2_ddl_apply_live.json"

LOADER_VERSION = "v1"

# Phase-2 ADD COLUMN list (must stay in sync with the DDL report). Used to
# rebuild the pre-DDL column projection for the 80-cohort hash guard.
ADDED_COLUMNS: Dict[str, Tuple[str, ...]] = {
    "students": (
        "division", "cohort_id", "source_dataset", "generation_version",
        "dataset_version",
    ),
    "student_subject_enrollment": ("division", "subject_domain", "subject_skill"),
    "student_subject_performance": (
        "division", "assignment_score", "quiz_avg_marks", "submission_delay_days",
        "pre_endsem_assessment_pct", "subject_domain", "subject_skill",
    ),
    "student_semester_summary": (
        "division", "previous_sem_sgpa", "sgpa_drift", "sgpa_rolling_mean_3",
        "previous_sem_backlog_count", "backlog_change", "cumulative_backlog_events",
        "backlog_trajectory", "attendance_aggregate_pct",
        "is_m1_deployment_boundary", "target_available_if_completed",
    ),
    "faculty_student_map": ("mapping_id", "semester_no", "mapping_type", "is_active"),
}

# Ordered loader steps per plan section 1.
STEP_ORDER: List[str] = [
    "students",
    "student_subject_enrollment",
    "student_subject_performance",
    "student_semester_summary",
    "attendance_weekly",
    "student_learning_activity",
    "faculty_student_map",
    "student_skill_profile",
    "student_lifestyle_survey",
    "placement",
    "career_preferences_v2",
]

# table -> (csv filename, expected rows, conflict target, batch size)
STEPS_CONF: Dict[str, Tuple[str, int, Tuple[str, ...], int]] = {
    "students": ("students_6A_1200_final.csv", 1200, ("student_id",), 500),
    "student_subject_enrollment": (
        "student_subject_enrollment_6A_1200_final.csv", 68400,
        ("student_id", "subject_id", "academic_year"), 500,
    ),
    "student_subject_performance": (
        "student_subject_performance_6A_1200_final.csv", 68400,
        ("performance_id",), 500,
    ),
    "student_semester_summary": (
        "student_semester_summary_6A_1200_final.csv", 9600,
        ("semester_summary_id",), 500,
    ),
    "attendance_weekly": (
        "attendance_6A_1200_final.csv", 547200, ("enrollment_record_id", "week_number"), 1000,
    ),
    "student_learning_activity": (
        "student_learning_activity_6A_1200_final.csv", 547200,
        ("enrollment_record_id", "week_number"), 1000,
    ),
    "faculty_student_map": (
        "faculty_student_map_6A_1200_final.csv", 1200, ("faculty_student_map_id",), 500,
    ),
    "student_skill_profile": (
        "student_skill_profile_6A_1200_final.csv", 19200, ("student_skill_id",), 500,
    ),
    "student_lifestyle_survey": (
        "lifestyle_survey_6A_1200_final.csv", 9600, ("student_id", "semester_no"), 500,
    ),
    "placement": ("placement_6A_1200_final.csv", 1200, ("student_id",), 500),
    "career_preferences_v2": (
        "career_preferences_6A_1200_final.csv", 1200, ("student_id",), 500,
    ),
}

# id-prefix conflict scan per table (must be zero before load).
ID_PREFIX: Dict[str, str] = {
    "students": "STU6A%",
    "student_subject_enrollment": "ENR6A%",
    "student_subject_performance": "PER6A%",
    "student_semester_summary": "SEM6A%",
    "attendance_weekly": "ATT6A%",
    "student_learning_activity": "LRN6A%",
    "faculty_student_map": "FSM6A%",
    "student_skill_profile": "SKP6A%",
    "student_lifestyle_survey": "LIFE6A%",
    "placement": "PLC6A%",
    "career_preferences_v2": "CAR6A%",
}

PRIMARY_ID_COL: Dict[str, str] = {
    "students": "student_id",
    "student_subject_enrollment": "enrollment_record_id",
    "student_subject_performance": "performance_id",
    "student_semester_summary": "semester_summary_id",
    "attendance_weekly": "attendance_id",
    "student_learning_activity": "learning_activity_id",
    "faculty_student_map": "faculty_student_map_id",
    "student_skill_profile": "student_skill_id",
    "student_lifestyle_survey": "survey_id",
    "placement": "placement_id",
    "career_preferences_v2": "career_preference_id",
}

# Column type contract (mirrors the live schema probe): (pg_type, not-null-non-default).
LIVE_COLUMNS: Dict[str, Dict[str, Tuple[str, bool]]] = {
    "students": {
        "student_id": ("varchar", True), "enrollment_no": ("bigint", True),
        "university_roll_no": ("varchar", True), "first_name": ("varchar", True),
        "last_name": ("varchar", True), "gender": ("varchar", True),
        "date_of_birth": ("date", True), "blood_group": ("varchar", False),
        "category": ("varchar", True), "admission_year": ("integer", True),
        "admission_date": ("date", True), "admission_type": ("varchar", True),
        "admission_quota": ("varchar", True), "department_code": ("integer", True),
        "department_name": ("varchar", True), "current_semester": ("integer", True),
        "current_academic_year": ("varchar", True), "domicile_state": ("varchar", True),
        "city": ("varchar", True), "guardian_name": ("varchar", False),
        "guardian_phone": ("bigint", False), "email": ("varchar", True),
        "student_phone_number": ("bigint", True), "student_status": ("varchar", True),
        "created_at": ("timestamp", True), "updated_at": ("timestamp", True),
        "full_name": ("varchar", True), "latest_sgpa": ("numeric", True),
        "overall_cgpa": ("numeric", True), "overall_percentage": ("numeric", True),
        "overall_attendance_percentage": ("numeric", True),
        "total_credits_registered": ("integer", True),
        "total_credits_earned": ("integer", True), "total_backlogs": ("integer", True),
        "academic_standing": ("varchar", True), "division": ("varchar", False),
        "cohort_id": ("varchar", False), "source_dataset": ("varchar", False),
        "generation_version": ("varchar", False), "dataset_version": ("varchar", False),
    },
    "student_subject_enrollment": {
        "enrollment_record_id": ("varchar", True), "student_id": ("varchar", True),
        "enrollment_no": ("bigint", True), "department_code": ("integer", True),
        "department_name": ("varchar", True), "semester_no": ("integer", True),
        "academic_year": ("varchar", True), "subject_id": ("varchar", True),
        "subject_code": ("varchar", True), "subject_name": ("varchar", True),
        "credits": ("integer", True), "subject_type": ("varchar", True),
        "faculty_id": ("varchar", False), "enrollment_date": ("date", True),
        "enrollment_status": ("varchar", True), "division": ("varchar", False),
        "subject_domain": ("varchar", False), "subject_skill": ("varchar", False),
    },
    "student_subject_performance": {
        "performance_id": ("varchar", True), "enrollment_record_id": ("varchar", True),
        "enrollment_no": ("bigint", True), "student_id": ("varchar", True),
        "subject_id": ("varchar", True), "semester_no": ("integer", True),
        "internal_marks": ("integer", True), "mid_sem_marks": ("integer", True),
        "end_sem_marks": ("integer", False), "total_marks": ("integer", False),
        "percentage": ("numeric", False), "grade": ("varchar", False),
        "grade_point": ("integer", False), "result_status": ("varchar", False),
        "attempt_number": ("integer", True), "performance_category": ("varchar", False),
        "remarks": ("text", False), "ct1_marks": ("integer", False),
        "ct2_marks": ("integer", False), "updated_at": ("timestamptz", False),
        "updated_by": ("varchar", False), "division": ("varchar", False),
        "assignment_score": ("numeric", False), "quiz_avg_marks": ("numeric", False),
        "submission_delay_days": ("numeric", False),
        "pre_endsem_assessment_pct": ("numeric", False),
        "subject_domain": ("varchar", False), "subject_skill": ("varchar", False),
    },
    "student_semester_summary": {
        "semester_summary_id": ("varchar", True), "student_id": ("varchar", True),
        "enrollment_no": ("bigint", True), "semester_no": ("integer", True),
        "academic_year": ("varchar", True), "subjects_registered": ("integer", True),
        "credits_registered": ("integer", True), "credits_earned": ("integer", True),
        "semester_total_marks": ("integer", True), "semester_percentage": ("numeric", True),
        "semester_sgpa": ("numeric", True), "semester_grade": ("varchar", True),
        "semester_attendance_percentage": ("numeric", True),
        "backlog_count": ("integer", True), "semester_result": ("varchar", True),
        "academic_standing": ("varchar", True), "division": ("varchar", False),
        "previous_sem_sgpa": ("numeric", False), "sgpa_drift": ("numeric", False),
        "sgpa_rolling_mean_3": ("numeric", False),
        "previous_sem_backlog_count": ("integer", False),
        "backlog_change": ("integer", False), "cumulative_backlog_events": ("integer", False),
        "backlog_trajectory": ("varchar", False), "attendance_aggregate_pct": ("numeric", False),
        "is_m1_deployment_boundary": ("boolean", False),
        "target_available_if_completed": ("boolean", False),
    },
    "attendance_weekly": {
        "attendance_id": ("varchar", True), "student_id": ("varchar", True),
        "enrollment_record_id": ("varchar", True), "subject_id": ("varchar", True),
        "semester_no": ("integer", True), "week_number": ("integer", True),
        "classes_held": ("integer", True), "classes_attended": ("integer", True),
        "attendance_percentage": ("numeric", True), "attendance_velocity": ("numeric", False),
        "attendance_rolling_2w": ("numeric", False), "attendance_rolling_4w": ("numeric", False),
        "attendance_baseline": ("numeric", False),
        "attendance_change_from_baseline": ("numeric", False),
        "low_attendance_flag": ("boolean", False),
    },
    "student_learning_activity": {
        "learning_activity_id": ("varchar", True), "student_id": ("varchar", True),
        "enrollment_record_id": ("varchar", True), "subject_id": ("varchar", True),
        "semester_no": ("integer", True), "week_number": ("integer", True),
        "active_days": ("integer", False), "learning_sessions": ("integer", False),
        "resource_views": ("integer", False), "assessment_attempts": ("integer", False),
        "submission_count": ("integer", False), "late_submission_count": ("integer", False),
        "avg_submission_delay_days": ("numeric", False), "activity_trend": ("varchar", False),
        "activity_volume": ("integer", False), "activity_velocity": ("numeric", False),
        "activity_change_pct": ("numeric", False), "inactive_week_flag": ("boolean", False),
        "engagement_consistency": ("numeric", False),
        "late_submission_rate": ("numeric", False),
        "assessment_completion_rate": ("numeric", False),
        "activity_mapping_note": ("text", False),
    },
    "faculty_student_map": {
        "faculty_student_map_id": ("varchar", True), "faculty_id": ("varchar", True),
        "student_id": ("varchar", True), "enrollment_no": ("bigint", True),
        "department": ("varchar", True), "mentor_role": ("varchar", True),
        "allocation_reason": ("varchar", False), "mentor_since": ("date", True),
        "status": ("varchar", True), "mapping_id": ("varchar", False),
        "semester_no": ("integer", False), "mapping_type": ("varchar", False),
        "is_active": ("boolean", False),
    },
    "student_skill_profile": {
        "student_skill_id": ("varchar", True), "student_id": ("varchar", True),
        "skill_id": ("varchar", True), "skill_name": ("varchar", True),
        "proficiency_level": ("numeric", False), "evidence_type": ("varchar", False),
        "evidence_score": ("numeric", False), "semester_no": ("integer", False),
        "skill_domain": ("varchar", False), "normalized_proficiency_pct": ("numeric", False),
        "skill_evidence_quality": ("varchar", False),
    },
    "student_lifestyle_survey": {
        "survey_id": ("varchar", True), "student_id": ("varchar", True),
        "semester_no": ("integer", True), "sleep_hours_per_day": ("numeric", False),
        "commute_time_mins": ("numeric", False), "study_hours_per_week": ("numeric", False),
        # VARCHAR after the corrective migration: categorical {Low, Medium, High}.
        "mental_stress_level": ("varchar", False),
        "extracurricular_hours_per_week": ("numeric", False),
    },
    "placement": {
        "placement_id": ("varchar", True), "student_id": ("varchar", True),
        "placement_status": ("varchar", True), "package_lpa": ("numeric", False),
        "package_tier": ("varchar", False), "placement_domain": ("varchar", False),
        "placement_date": ("date", False),
    },
    "career_preferences_v2": {
        "career_preference_id": ("varchar", True), "student_id": ("varchar", True),
        "primary_interest_domain": ("varchar", False),
        "secondary_interest_domain": ("varchar", False),
        "preferred_role": ("varchar", False), "higher_studies_intent": ("varchar", False),
        "preferred_work_mode": ("varchar", False), "desired_salary_lpa": ("numeric", False),
        "career_role_category": ("varchar", False),
        "career_preference_version": ("varchar", False),
        "required_skills_for_preferred_role": ("text", False),
        "role_skill_profile_version": ("varchar", False),
        "career_preference_source": ("varchar", False),
    },
}

# explicitly-emitted DB columns per step (in live order). created_at/updated_at
# and ct1/ct2/updated_at/updated_by/ct labels are deliberately NOT emitted.
EMITTED: Dict[str, Tuple[str, ...]] = {
    "students": (
        "student_id", "enrollment_no", "university_roll_no", "first_name", "last_name",
        "gender", "date_of_birth", "blood_group", "category", "admission_year",
        "admission_date", "admission_type", "admission_quota", "department_code",
        "department_name", "division", "current_semester", "current_academic_year",
        "domicile_state", "city", "guardian_name", "guardian_phone", "email",
        "student_phone_number", "student_status", "full_name", "overall_percentage",
        "academic_standing", "cohort_id", "source_dataset", "generation_version",
        "latest_sgpa", "overall_cgpa", "total_credits_registered",
        "total_credits_earned", "total_backlogs", "overall_attendance_percentage",
        "dataset_version",
    ),
    "student_subject_enrollment": (
        "enrollment_record_id", "student_id", "enrollment_no", "department_code",
        "department_name", "division", "semester_no", "academic_year", "subject_id",
        "subject_code", "subject_name", "credits", "subject_type", "faculty_id",
        "enrollment_date", "enrollment_status", "subject_domain", "subject_skill",
    ),
    "student_subject_performance": (
        "performance_id", "enrollment_record_id", "enrollment_no", "student_id",
        "subject_id", "semester_no", "internal_marks", "mid_sem_marks", "end_sem_marks",
        "total_marks", "percentage", "grade", "grade_point", "result_status",
        "attempt_number", "performance_category", "remarks", "division",
        "assignment_score", "quiz_avg_marks", "submission_delay_days",
        "pre_endsem_assessment_pct", "subject_domain", "subject_skill",
    ),
    "student_semester_summary": (
        "semester_summary_id", "student_id", "enrollment_no", "division", "semester_no",
        "academic_year", "subjects_registered", "credits_registered", "credits_earned",
        "semester_total_marks", "semester_percentage", "semester_sgpa",
        "semester_grade", "semester_attendance_percentage", "backlog_count",
        "semester_result", "academic_standing", "previous_sem_sgpa", "sgpa_drift",
        "sgpa_rolling_mean_3", "previous_sem_backlog_count", "backlog_change",
        "cumulative_backlog_events", "backlog_trajectory", "attendance_aggregate_pct",
        "is_m1_deployment_boundary", "target_available_if_completed",
    ),
    "attendance_weekly": (
        "attendance_id", "student_id", "enrollment_record_id", "subject_id",
        "semester_no", "week_number", "classes_held", "classes_attended",
        "attendance_percentage", "attendance_velocity", "attendance_rolling_2w",
        "attendance_rolling_4w", "attendance_baseline", "attendance_change_from_baseline",
        "low_attendance_flag",
    ),
    "student_learning_activity": (
        "learning_activity_id", "student_id", "enrollment_record_id", "subject_id",
        "semester_no", "week_number", "active_days", "learning_sessions",
        "resource_views", "assessment_attempts", "submission_count",
        "late_submission_count", "avg_submission_delay_days", "activity_trend",
        "activity_volume", "activity_velocity", "activity_change_pct",
        "inactive_week_flag", "engagement_consistency", "late_submission_rate",
        "assessment_completion_rate", "activity_mapping_note",
    ),
    "faculty_student_map": (
        "faculty_student_map_id", "mapping_id", "faculty_id", "student_id",
        "enrollment_no", "department", "mentor_role", "mentor_since", "status",
        "semester_no", "mapping_type", "is_active",
    ),
    "student_skill_profile": (
        "student_skill_id", "student_id", "skill_id", "skill_name", "proficiency_level",
        "evidence_type", "evidence_score", "semester_no", "skill_domain",
        "normalized_proficiency_pct", "skill_evidence_quality",
    ),
    "student_lifestyle_survey": (
        "survey_id", "student_id", "semester_no", "sleep_hours_per_day",
        "commute_time_mins", "study_hours_per_week", "mental_stress_level",
        "extracurricular_hours_per_week",
    ),
    "placement": (
        "placement_id", "student_id", "placement_status", "package_lpa", "package_tier",
        "placement_domain", "placement_date",
    ),
    "career_preferences_v2": (
        "career_preference_id", "student_id", "primary_interest_domain",
        "secondary_interest_domain", "preferred_role", "higher_studies_intent",
        "preferred_work_mode", "desired_salary_lpa", "career_role_category",
        "career_preference_version", "required_skills_for_preferred_role",
        "role_skill_profile_version", "career_preference_source",
    ),
}

# emitted `date` columns per table (used by _encode_for_insert).
EMITTED_DATE_COLUMNS: Dict[str, Tuple[str, ...]] = {
    t: tuple(c for c in EMITTED[t] if LIVE_COLUMNS[t].get(c, ("", False))[0] == "date")
    for t in STEP_ORDER
}

# NOT-NULL columns the DDL gives a default for a new row (loader omits them).
NOT_NULL_EXEMPT: Dict[str, Tuple[str, ...]] = {
    "students": ("created_at", "updated_at"),
    "student_subject_enrollment": (), "student_subject_performance": (),
    "student_semester_summary": (), "attendance_weekly": (),
    "student_learning_activity": (), "faculty_student_map": (),
    "student_skill_profile": (), "student_lifestyle_survey": (),
    "placement": (), "career_preferences_v2": (),
}


# ---------------------------------------------------------------------------
# value coercion helpers (deterministic)
# ---------------------------------------------------------------------------
def _text(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _int(v: Any) -> Optional[int]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    return int(Decimal(s))


def _dec(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    return Decimal(s)


def _date(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        return s


def _bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"1", "t", "true", "y", "yes"}:
        return True
    if s in {"0", "f", "false", "n", "no"}:
        return False
    return None


def _int_coerce(value: Any) -> Tuple[Optional[int], bool]:
    """INTEGER cast. A non-integer source is rounded half-even and flagged."""
    if value is None:
        return None, False
    s = str(value).strip()
    if not s:
        return None, False
    d = Decimal(s)
    if d == d.to_integral_value():
        return int(d), False
    return int(d.quantize(Decimal(1), rounding=ROUND_HALF_EVEN)), True


# ---------------------------------------------------------------------------
# row builders (raw CSV row -> typed row for insert)
# ---------------------------------------------------------------------------
def build_students(row: Dict[str, Any]) -> Dict[str, Any]:
    """B1 (admission_quota) + B2 (academic_standing) + cast; omitted created_at/updated_at."""
    return {
        "student_id": _text(row.get("student_id")),
        "enrollment_no": _int(row.get("enrollment_no")),
        "university_roll_no": _text(row.get("university_roll_no")),
        "first_name": _text(row.get("first_name")),
        "last_name": _text(row.get("last_name")),
        "gender": _text(row.get("gender")),
        "date_of_birth": _date(row.get("date_of_birth")),
        "blood_group": _text(row.get("blood_group")),
        "category": _text(row.get("category")),
        "admission_year": _int(row.get("admission_year")),
        "admission_date": _date(row.get("admission_date")),
        "admission_type": _text(row.get("admission_type")),
        "admission_quota": map_admission_quota(row.get("admission_quota")),
        "department_code": _int(row.get("department_code")),
        "department_name": _text(row.get("department_name")),
        "division": _text(row.get("division")),
        "current_semester": _int(row.get("current_semester")),
        "current_academic_year": _text(row.get("current_academic_year")),
        "domicile_state": _text(row.get("domicile_state")),
        "city": _text(row.get("city")),
        "guardian_name": _text(row.get("guardian_name")),
        "guardian_phone": _int(row.get("guardian_phone")),
        "email": _text(row.get("email")),
        "student_phone_number": _int(row.get("student_phone_number")),
        "student_status": _text(row.get("student_status")),
        "full_name": _text(row.get("full_name")),
        "overall_percentage": _dec(row.get("overall_percentage")),
        "academic_standing": map_academic_standing(row.get("academic_standing")),
        "cohort_id": _text(row.get("cohort_id")),
        "source_dataset": _text(row.get("source_dataset")),
        "generation_version": _text(row.get("generation_version")),
        "latest_sgpa": _dec(row.get("latest_sgpa")),
        "overall_cgpa": _dec(row.get("overall_cgpa")),
        "total_credits_registered": _int(row.get("total_credits_registered")),
        "total_credits_earned": _int(row.get("total_credits_earned")),
        "total_backlogs": _int(row.get("total_backlogs")),
        "overall_attendance_percentage": _dec(row.get("overall_attendance_percentage")),
        "dataset_version": _text(row.get("dataset_version")),
    }


def build_enrollment(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "enrollment_record_id": _text(row.get("enrollment_record_id")),
        "student_id": _text(row.get("student_id")),
        "enrollment_no": _int(row.get("enrollment_no")),
        "department_code": _int(row.get("department_code")),
        "department_name": _text(row.get("department_name")),
        "division": _text(row.get("division")),
        "semester_no": _int(row.get("semester_no")),
        "academic_year": _text(row.get("academic_year")),
        "subject_id": _text(row.get("subject_id")),
        "subject_code": _text(row.get("subject_code")),
        "subject_name": _text(row.get("subject_name")),
        "credits": _int(row.get("credits")),
        "subject_type": _text(row.get("subject_type")),
        "faculty_id": _text(row.get("faculty_id")),
        "enrollment_date": _date(row.get("enrollment_date")),
        "enrollment_status": _text(row.get("enrollment_status")),
        "subject_domain": _text(row.get("subject_domain")),
        "subject_skill": _text(row.get("subject_skill")),
    }


def build_performance(row: Dict[str, Any], coercions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """B5: consume transform_performance_row; cast passthrough/derived types.

    The hard ``guard_raw_performance_not_insertable`` gate is asserted against
    the pipeline in ``prepare_step`` (proves the raw CSV cannot be loaded
    verbatim); per-row, the loader never inserts raw rows by construction.
    """
    t = transform_performance_row(row)
    return {
        "performance_id": t.get("performance_id"),
        "enrollment_record_id": t.get("enrollment_record_id"),
        "enrollment_no": t["enrollment_no"],
        "student_id": t.get("student_id"),
        "subject_id": t.get("subject_id"),
        "semester_no": t["semester_no"],
        "internal_marks": int(t["internal_marks"]),
        "mid_sem_marks": int(t["mid_sem_marks"]),
        "end_sem_marks": int(t["end_sem_marks"]),
        "total_marks": int(t["total_marks"]),
        "percentage": _dec(t["percentage"]),
        "grade": _text(t.get("grade")),
        "grade_point": int(t["grade_point"]) if t.get("grade_point") is not None else None,
        "result_status": _text(t.get("result_status")),
        "attempt_number": t.get("attempt_number", 1),
        "performance_category": _text(t.get("performance_category")),
        "remarks": _text(t.get("remarks")),
        "division": _text(t.get("division")),
        "assignment_score": _dec(t.get("assignment_score")),
        "quiz_avg_marks": _dec(t.get("quiz_avg_marks")),
        "submission_delay_days": _dec(t.get("submission_delay_days")),
        "pre_endsem_assessment_pct": _dec(t.get("pre_endsem_assessment_pct")),
        "subject_domain": _text(t.get("subject_domain")),
        "subject_skill": _text(t.get("subject_skill")),
    }


def build_semester_summary(row: Dict[str, Any], coercions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """B3: map academic_standing; semester_total_marks decimal->int (half-even)."""
    standing = map_academic_standing(row.get("academic_standing"))
    total_marks, flagged = _int_coerce(row.get("semester_total_marks"))
    if flagged:
        coercions.append({
            "column": "semester_total_marks", "kind": "decimal_to_integer_half_even",
            "source": row.get("semester_total_marks"),
            "note": "live column is INTEGER NOT NULL; 0-100 aggregate carries decimals",
        })
    return {
        "semester_summary_id": _text(row.get("semester_summary_id")),
        "student_id": _text(row.get("student_id")),
        "enrollment_no": _int(row.get("enrollment_no")),
        "division": _text(row.get("division")),
        "semester_no": _int(row.get("semester_no")),
        "academic_year": _text(row.get("academic_year")),
        "subjects_registered": _int(row.get("subjects_registered")),
        "credits_registered": _int(row.get("credits_registered")),
        "credits_earned": _int(row.get("credits_earned")),
        "semester_total_marks": total_marks,
        "semester_percentage": _dec(row.get("semester_percentage")),
        "semester_sgpa": _dec(row.get("semester_sgpa")),
        "semester_grade": _text(row.get("semester_grade")),
        "semester_attendance_percentage": _dec(row.get("semester_attendance_percentage")),
        "backlog_count": _int(row.get("backlog_count")),
        "semester_result": _text(row.get("semester_result")),
        "academic_standing": standing,
        "previous_sem_sgpa": _dec(row.get("previous_sem_sgpa")),
        "sgpa_drift": _dec(row.get("sgpa_drift")),
        "sgpa_rolling_mean_3": _dec(row.get("sgpa_rolling_mean_3")),
        "previous_sem_backlog_count": _int(row.get("previous_sem_backlog_count")),
        "backlog_change": _int(row.get("backlog_change")),
        "cumulative_backlog_events": _int(row.get("cumulative_backlog_events")),
        "backlog_trajectory": _text(row.get("backlog_trajectory")),
        "attendance_aggregate_pct": _dec(row.get("attendance_aggregate_pct")),
        "is_m1_deployment_boundary": _bool(row.get("is_m1_deployment_boundary")),
        "target_available_if_completed": _bool(row.get("target_available_if_completed")),
    }


def build_attendance(row: Dict[str, Any], coercions: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "attendance_id": _text(row.get("attendance_id")),
        "student_id": _text(row.get("student_id")),
        "enrollment_record_id": _text(row.get("enrollment_record_id")),
        "subject_id": _text(row.get("subject_id")),
        "semester_no": _int(row.get("semester_no")),
        "week_number": _int(row.get("week_number")),
        "classes_held": _int(row.get("classes_held")),
        "classes_attended": _int(row.get("classes_attended")),
        "attendance_percentage": _dec(row.get("attendance_percentage")),
        "attendance_velocity": _dec(row.get("attendance_velocity")),
        "attendance_rolling_2w": _dec(row.get("attendance_rolling_2w")),
        "attendance_rolling_4w": _dec(row.get("attendance_rolling_4w")),
        "attendance_baseline": _dec(row.get("attendance_baseline")),
        "attendance_change_from_baseline": _dec(row.get("attendance_change_from_baseline")),
        "low_attendance_flag": _bool(row.get("low_attendance_flag")),
    }


def build_learning_activity(row: Dict[str, Any], coercions: List[Dict[str, Any]]) -> Dict[str, Any]:
    volume, flagged = _int_coerce(row.get("activity_volume"))
    if flagged:
        coercions.append({
            "column": "activity_volume", "kind": "decimal_to_integer_half_even",
            "source": row.get("activity_volume"),
            "note": "live column is INTEGER; source carries whole-number decimals",
        })
    return {
        "learning_activity_id": _text(row.get("learning_activity_id")),
        "student_id": _text(row.get("student_id")),
        "enrollment_record_id": _text(row.get("enrollment_record_id")),
        "subject_id": _text(row.get("subject_id")),
        "semester_no": _int(row.get("semester_no")),
        "week_number": _int(row.get("week_number")),
        "active_days": _int(row.get("active_days")),
        "learning_sessions": _int(row.get("learning_sessions")),
        "resource_views": _int(row.get("resource_views")),
        "assessment_attempts": _int(row.get("assessment_attempts")),
        "submission_count": _int(row.get("submission_count")),
        "late_submission_count": _int(row.get("late_submission_count")),
        "avg_submission_delay_days": _dec(row.get("avg_submission_delay_days")),
        "activity_trend": _text(row.get("activity_trend")),
        "activity_volume": volume,
        "activity_velocity": _dec(row.get("activity_velocity")),
        "activity_change_pct": _dec(row.get("activity_change_pct")),
        "inactive_week_flag": _bool(row.get("inactive_week_flag")),
        "engagement_consistency": _dec(row.get("engagement_consistency")),
        "late_submission_rate": _dec(row.get("late_submission_rate")),
        "assessment_completion_rate": _dec(row.get("assessment_completion_rate")),
        "activity_mapping_note": _text(row.get("activity_mapping_note")),
    }


def build_fsm(outcome: TransformOutcome) -> List[Dict[str, Any]]:
    rows = []
    for r in outcome.rows:
        rows.append({
            "faculty_student_map_id": r["faculty_student_map_id"],
            "mapping_id": r.get("mapping_id"),
            "faculty_id": r["faculty_id"],
            "student_id": r["student_id"],
            "enrollment_no": int(r["enrollment_no"]),
            "department": r["department"],
            "mentor_role": r["mentor_role"],
            "mentor_since": _date(r["mentor_since"]),
            "status": r["status"],
            "semester_no": r.get("semester_no"),
            "mapping_type": r.get("mapping_type"),
            "is_active": bool(r["is_active"]),
        })
    return rows


def build_skill_profile(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "student_skill_id": _text(row.get("student_skill_id")),
        "student_id": _text(row.get("student_id")),
        "skill_id": _text(row.get("skill_id")),
        "skill_name": _text(row.get("skill_name")),
        "proficiency_level": _dec(row.get("proficiency_level")),
        "evidence_type": _text(row.get("evidence_type")),
        "evidence_score": _dec(row.get("evidence_score")),
        "semester_no": _int(row.get("semester_no")),
        "skill_domain": _text(row.get("skill_domain")),
        "normalized_proficiency_pct": _dec(row.get("normalized_proficiency_pct")),
        "skill_evidence_quality": _text(row.get("skill_evidence_quality")),
    }


def build_lifestyle(row: Dict[str, Any]) -> Dict[str, Any]:
    # mental_stress_level is a VARCHAR categorical contract ({Low, Medium, High});
    # the prepare_step lifestyle branch rejects invalid values (never NULLed,
    # never fabricated). Empty -> None = dimension not reported.
    return {
        "survey_id": _text(row.get("survey_id")),
        "student_id": _text(row.get("student_id")),
        "semester_no": _int(row.get("semester_no")),
        "sleep_hours_per_day": _dec(row.get("sleep_hours_per_day")),
        "commute_time_mins": _dec(row.get("commute_time_mins")),
        "study_hours_per_week": _dec(row.get("study_hours_per_week")),
        "mental_stress_level": map_stress_level(row.get("mental_stress_level")),
        "extracurricular_hours_per_week": _dec(row.get("extracurricular_hours_per_week")),
    }


def build_placement(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "placement_id": _text(row.get("placement_id")),
        "student_id": _text(row.get("student_id")),
        "placement_status": _text(row.get("placement_status")),
        "package_lpa": _dec(row.get("package_lpa")),
        "package_tier": _text(row.get("package_tier")),
        "placement_domain": _text(row.get("placement_domain")),
        "placement_date": _date(row.get("placement_date")),
    }


def build_career_v2(outcome: TransformOutcome) -> List[Dict[str, Any]]:
    rows = []
    for r in outcome.rows:
        rows.append({
            "career_preference_id": _text(r.get("career_preference_id")),
            "student_id": _text(r.get("student_id")),
            "primary_interest_domain": _text(r.get("primary_interest_domain")),
            "secondary_interest_domain": _text(r.get("secondary_interest_domain")),
            "preferred_role": _text(r.get("preferred_role")),
            "higher_studies_intent": _text(r.get("higher_studies_intent")),
            "preferred_work_mode": _text(r.get("preferred_work_mode")),
            "desired_salary_lpa": _dec(r.get("desired_salary_lpa")),
            "career_role_category": _text(r.get("career_role_category")),
            "career_preference_version": _text(r.get("career_preference_version")),
            "required_skills_for_preferred_role": _text(r.get("required_skills_for_preferred_role")),
            "role_skill_profile_version": _text(r.get("role_skill_profile_version")),
            "career_preference_source": _text(r.get("career_preference_source")),
        })
    return rows


# ---------------------------------------------------------------------------
# dataset readers
# ---------------------------------------------------------------------------
def read_csv_rows(source: Path) -> Iterable[Dict[str, str]]:
    with source.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            yield row


def csv_header(source: Path) -> List[str]:
    with source.open(newline="", encoding="utf-8") as fh:
        r = csv.DictReader(fh)
        return list(r.fieldnames or [])


def dataset_sha(source: Path) -> str:
    h = hashlib.sha256()
    with source.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# per-step FK definition
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _RefCheck:
    label: str
    col: str
    ctx_attr: str  # name of a PipelineCtx attribute holding the reference set


STEP_FK: Dict[str, List[_RefCheck]] = {
    "students": [_RefCheck("department_code -> departments(live)", "department_code", "live_departments")],
    "student_subject_enrollment": [
        _RefCheck("student_id -> students(in-run)", "student_id", "students_ids"),
        _RefCheck("subject_id -> subjects(live)", "subject_id", "live_subjects"),
        _RefCheck("faculty_id -> faculty(live)", "faculty_id", "live_faculty"),
        _RefCheck("department_code -> departments(live)", "department_code", "live_departments"),
    ],
    "student_subject_performance": [
        _RefCheck("enrollment_record_id -> enrollment(in-run)", "enrollment_record_id", "enrollment_ids"),
        _RefCheck("student_id -> students(in-run)", "student_id", "students_ids"),
        _RefCheck("subject_id -> subjects(live)", "subject_id", "live_subjects"),
    ],
    "student_semester_summary": [
        _RefCheck("student_id -> students(in-run)", "student_id", "students_ids"),
        _RefCheck("enrollment_no -> students.enrollment_no(in-run)", "enrollment_no", "students_eno"),
    ],
    "attendance_weekly": [
        _RefCheck("student_id -> students(in-run)", "student_id", "students_ids"),
        _RefCheck("enrollment_record_id -> enrollment(in-run)", "enrollment_record_id", "enrollment_ids"),
        _RefCheck("subject_id -> subjects(live)", "subject_id", "live_subjects"),
    ],
    "student_learning_activity": [
        _RefCheck("student_id -> students(in-run)", "student_id", "students_ids"),
        _RefCheck("enrollment_record_id -> enrollment(in-run)", "enrollment_record_id", "enrollment_ids"),
        _RefCheck("subject_id -> subjects(live)", "subject_id", "live_subjects"),
    ],
    "faculty_student_map": [
        _RefCheck("faculty_id -> faculty(live)", "faculty_id", "live_faculty"),
        _RefCheck("student_id -> students(in-run)", "student_id", "students_ids"),
    ],
    "student_skill_profile": [_RefCheck("student_id -> students(in-run)", "student_id", "students_ids")],
    "student_lifestyle_survey": [_RefCheck("student_id -> students(in-run)", "student_id", "students_ids")],
    "placement": [_RefCheck("student_id -> students(in-run)", "student_id", "students_ids")],
    "career_preferences_v2": [_RefCheck("student_id -> students(in-run)", "student_id", "students_ids")],
}


# ---------------------------------------------------------------------------
# step preparation
# ---------------------------------------------------------------------------
@dataclass
class StepStats:
    step: int
    table: str
    transform: str
    expected_rows: int
    source_rows: int = 0
    accepted: int = 0
    quarantined: int = 0
    quarantine_reasons: List[Dict[str, Any]] = field(default_factory=list)
    insert_columns: List[str] = field(default_factory=list)
    dropped_columns: List[str] = field(default_factory=list)
    conflict_target: Tuple[str, ...] = ()
    batch_size: int = 500
    batch_count: int = 0
    batch_sizes: List[int] = field(default_factory=list)
    duplicates: int = 0
    fk_checks: List[Dict[str, Any]] = field(default_factory=list)
    not_null_missing: List[str] = field(default_factory=list)
    schema_compat_issues: List[str] = field(default_factory=list)
    coercions: List[Dict[str, Any]] = field(default_factory=list)
    existing_conflicts: int = 0
    planned_writes: int = 0
    writes: int = 0
    elapsed_s: float = 0.0
    peak_mb: float = 0.0
    stress_unexpected: int = 0
    stress_missing: int = 0
    stress_distribution: Dict[str, int] = field(default_factory=dict)

    def to_dict(self, include_runtime: bool = True) -> Dict[str, Any]:
        d = {
            "step": self.step, "table": self.table, "transform": self.transform,
            "expected_rows": self.expected_rows, "source_rows": self.source_rows,
            "accepted": self.accepted, "quarantined": self.quarantined,
            "quarantined_reasons": self.quarantine_reasons,
            "insert_columns": self.insert_columns, "dropped_columns": self.dropped_columns,
            "conflict_target": list(self.conflict_target), "batch_size": self.batch_size,
            "batch_count": self.batch_count, "batch_sizes": self.batch_sizes,
            "duplicates": self.duplicates,
            "fk_checks": self.fk_checks, "not_null_missing": self.not_null_missing,
            "schema_compat_issues": self.schema_compat_issues,
            "schema_coercions": self.coercions,
            "existing_6a_conflicts": self.existing_conflicts,
            "planned_writes": self.planned_writes, "writes": self.writes,
            "stress_validation": {
                "unexpected": self.stress_unexpected,
                "missing": self.stress_missing,
                "distribution": {
                    k: self.stress_distribution[k]
                    for k in sorted(self.stress_distribution)
                },
            },
        }
        if include_runtime:
            d["elapsed_s"] = round(self.elapsed_s, 3)
            d["peak_mb"] = round(self.peak_mb, 1)
        return d


def _transform_label(table: str) -> str:
    labels = {
        "students": "B1 admission_quota (Merit->ACPC, Management->Management) + B2 academic_standing map",
        "student_subject_enrollment": "column projection + cast (no vocab transform required)",
        "student_subject_performance": "B5 transform_performance_rows (0-140 reprojection + derive_marks_fields)",
        "student_semester_summary": "B3 academic_standing map (shared map_academic_standing)",
        "attendance_weekly": "column projection + cast (grain (enrollment_record_id, week_number))",
        "student_learning_activity": "column projection + cast (grain (enrollment_record_id, week_number))",
        "faculty_student_map": "transform_faculty_student_map (NOT-NULL maintenance derived from students)",
        "student_skill_profile": "column projection + cast",
        "student_lifestyle_survey": "categorical mental_stress_level validated against {Low, Medium, High}; invalid rows rejected (never NULLed)",
        "placement": "column projection + cast (student_id UNIQUE)",
        "career_preferences_v2": "B4 transform_career_preferences_v2 (ARCHITECTURE B; old table untouched)",
    }
    return labels[table]


def _type_ok(value: Any, pg_type: str) -> bool:
    if value is None:
        return True
    if pg_type == "numeric":
        return isinstance(value, (Decimal, int, float))
    if pg_type in ("integer", "bigint", "smallint"):
        return isinstance(value, int) and not isinstance(value, bool)
    if pg_type == "boolean":
        return isinstance(value, bool)
    if pg_type == "date":
        return isinstance(value, str)
    if pg_type in ("varchar", "text", "timestamp", "timestamptz"):
        return isinstance(value, str)
    return True


def prepare_step(ctx: "PipelineCtx", step_no: int, table: str) -> StepStats:
    """Deterministic, DB-free row preparation + validation for ONE step."""
    csv_name, expected, conflict, batch_size = STEPS_CONF[table]
    source = ctx.datasets_dir / csv_name
    stats = StepStats(step=step_no, table=table, transform=_transform_label(table),
                      expected_rows=expected, conflict_target=conflict, batch_size=batch_size)
    stats.insert_columns = list(EMITTED[table])
    stats.dropped_columns = sorted({c for c in csv_header(source) if c not in set(EMITTED[table])})

    required_not_null = [
        c for c, (pg, nn) in LIVE_COLUMNS[table].items()
        if nn and c not in NOT_NULL_EXEMPT.get(table, ())
    ]
    coercions: List[Dict[str, Any]] = []
    grain_seen: set = set()
    dup = 0
    fk_missing: Dict[str, Dict[str, Any]] = {}
    fk_checked: Dict[str, int] = {}
    nn_missing: set = set()
    type_bad: set = set()

    if table == "students":
        for raw in read_csv_rows(source):
            t = build_students(raw)
            _accumulate(t, table, stats, conflict, grain_seen, required_not_null,
                        nn_missing, type_bad, ctx, fk_missing, fk_checked, dup, coercions)
            ctx.students_ids.add(t["student_id"])
            ctx.students_eno.add(t["enrollment_no"])
            ctx.students_by_id[t["student_id"]] = {
                "enrollment_no": t["enrollment_no"], "department_name": t["department_name"],
                "admission_date": t["admission_date"],
            }
        return _finalize(stats, expected, grain_seen, fk_checked, fk_missing, type_bad)

    if table == "student_subject_enrollment":
        for raw in read_csv_rows(source):
            t = build_enrollment(raw)
            _accumulate(t, table, stats, conflict, grain_seen, required_not_null,
                        nn_missing, type_bad, ctx, fk_missing, fk_checked, dup, coercions)
            ctx.enrollment_ids.add(t["enrollment_record_id"])
            ctx.enrollment_pairs.add((t["student_id"], t["subject_id"]))
        return _finalize(stats, expected, grain_seen, fk_checked, fk_missing, type_bad)

    if table == "student_subject_performance":
        raw_rows = list(read_csv_rows(source))
        guard = guard_raw_performance_not_insertable(raw_rows)
        if guard:
            stats.quarantined = len(raw_rows)
            stats.quarantine_reasons = [{
                "reason_code": "raw_csv_not_insertable",
                "note": "raw CSV is provably not loadable; loader consumes transform_performance_rows",
                "sample": guard[:10],
            }]
        for raw in raw_rows:
            t = build_performance(raw, coercions)
            _accumulate(t, table, stats, conflict, grain_seen, required_not_null,
                        nn_missing, type_bad, ctx, fk_missing, fk_checked, dup, coercions)
        stats.quarantined = 0  # B5 transform consumed; quarantine is informational
        return _finalize(stats, expected, grain_seen, fk_checked, fk_missing, type_bad)

    if table == "student_semester_summary":
        for raw in read_csv_rows(source):
            t = build_semester_summary(raw, coercions)
            _accumulate(t, table, stats, conflict, grain_seen, required_not_null,
                        nn_missing, type_bad, ctx, fk_missing, fk_checked, dup, coercions)
        return _finalize(stats, expected, grain_seen, fk_checked, fk_missing, type_bad)

    if table == "attendance_weekly":
        builder = build_attendance
        return _prepare_stream(builder, table, ctx, stats, expected, conflict, grain_seen,
                               required_not_null, nn_missing, type_bad, coercions,
                               fk_missing, fk_checked)

    if table == "student_learning_activity":
        builder = build_learning_activity
        return _prepare_stream(builder, table, ctx, stats, expected, conflict, grain_seen,
                               required_not_null, nn_missing, type_bad, coercions,
                               fk_missing, fk_checked)

    if table == "faculty_student_map":
        raw_rows = list(read_csv_rows(source))
        outcome = transform_faculty_student_map(raw_rows, ctx.students_by_id)
        stats.quarantined = outcome.rejected
        stats.quarantine_reasons = [q.to_dict() for q in outcome.quarantined]
        for t in build_fsm(outcome):
            _accumulate(t, table, stats, conflict, grain_seen, required_not_null,
                        nn_missing, type_bad, ctx, fk_missing, fk_checked, dup, coercions)
        return _finalize(stats, expected, grain_seen, fk_checked, fk_missing, type_bad, outcome)

    if table == "student_skill_profile":
        return _prepare_simple(build_skill_profile, table, ctx, stats, expected, conflict,
                               grain_seen, required_not_null, nn_missing, type_bad,
                               coercions, fk_missing, fk_checked)

    if table == "student_lifestyle_survey":
        bad_samples: List[str] = []
        for raw in read_csv_rows(source):
            raw_stress = _text(raw.get("mental_stress_level"))
            if raw_stress is None:
                stats.stress_missing += 1
            elif raw_stress in STRESS_LEVEL_ALLOWED:
                stats.stress_distribution[raw_stress] = (
                    stats.stress_distribution.get(raw_stress, 0) + 1)
            else:
                if len(bad_samples) < 10:
                    bad_samples.append(raw_stress)
                stats.stress_unexpected += 1
                stats.quarantined += 1
                continue  # invalid value: reject the row, never NULL it
            t = build_lifestyle(raw)
            _accumulate(t, table, stats, conflict, grain_seen, required_not_null,
                        nn_missing, type_bad, ctx, fk_missing, fk_checked, dup, coercions)
        if stats.stress_unexpected:
            stats.quarantine_reasons.append({
                "reason_code": "invalid_stress_level",
                "note": "mental_stress_level must be one of "
                        + ", ".join(sorted(STRESS_LEVEL_ALLOWED))
                        + "; violating rows are rejected (never NULLed, never fabricated)",
                "sample": bad_samples,
            })
        stats.coercions.append({
            "column": "mental_stress_level", "kind": "varchar_categorical_contract",
            "count": sum(stats.stress_distribution.values()) if stats.stress_distribution else 0,
            "note": "column is VARCHAR (corrective migration, not applied); categorical "
                    "values (Low/Medium/High) preserved verbatim; no coercion applied",
        })
        return _finalize(stats, expected, grain_seen, fk_checked, fk_missing, type_bad)

    if table == "placement":
        return _prepare_simple(build_placement, table, ctx, stats, expected, conflict,
                               grain_seen, required_not_null, nn_missing, type_bad,
                               coercions, fk_missing, fk_checked)

    if table == "career_preferences_v2":
        raw_rows = list(read_csv_rows(source))
        outcome = transform_career_preferences_v2(raw_rows, ctx.students_by_id)
        stats.quarantined = outcome.rejected
        stats.quarantine_reasons = [q.to_dict() for q in outcome.quarantined]
        for t in build_career_v2(outcome):
            _accumulate(t, table, stats, conflict, grain_seen, required_not_null,
                        nn_missing, type_bad, ctx, fk_missing, fk_checked, dup, coercions)
        return _finalize(stats, expected, grain_seen, fk_checked, fk_missing, type_bad, outcome)

    raise ValueError(f"unhandled step table: {table}")


def _prepare_stream(builder, table, ctx, stats, expected, conflict, grain_seen,
                    required_not_null, nn_missing, type_bad, coercions,
                    fk_missing, fk_checked):
    one = {k: None for k in EMITTED[table]}
    dup = 0
    for raw in read_csv_rows(ctx.datasets_dir / STEPS_CONF[table][0]):
        t = builder(raw, coercions)
        _accumulate(t, table, stats, conflict, grain_seen, required_not_null,
                    nn_missing, type_bad, ctx, fk_missing, fk_checked, dup, coercions)
    return _finalize(stats, expected, grain_seen, fk_checked, fk_missing, type_bad)


def _prepare_simple(builder, table, ctx, stats, expected, conflict, grain_seen,
                    required_not_null, nn_missing, type_bad, coercions,
                    fk_missing, fk_checked):
    dup = 0
    for raw in read_csv_rows(ctx.datasets_dir / STEPS_CONF[table][0]):
        t = builder(raw)
        _accumulate(t, table, stats, conflict, grain_seen, required_not_null,
                    nn_missing, type_bad, ctx, fk_missing, fk_checked, dup, coercions)
    return _finalize(stats, expected, grain_seen, fk_checked, fk_missing, type_bad)


def _accumulate(t, table, stats, conflict, grain_seen, required_not_null, nn_missing,
                type_bad, ctx, fk_missing, fk_checked, dup, coercions):
    g = _grain_key(t, conflict)
    if g in grain_seen:
        stats.duplicates += 1
    grain_seen.add(g)
    for c in required_not_null:
        if t.get(c) in (None, ""):
            nn_missing.add(c)
    for c, (pg, _nn) in LIVE_COLUMNS[table].items():
        if c in t and not _type_ok(t.get(c), pg):
            type_bad.add(f"{c}({pg})")
    for ref in STEP_FK.get(table, []):
        v = t.get(ref.col)
        if v is None:
            continue
        key = ref.label
        fk_checked[key] = fk_checked.get(key, 0) + 1
        entry = fk_missing.setdefault(key, {"missing": 0, "samples": []})
        if v not in getattr(ctx, ref.ctx_attr):
            entry["missing"] += 1
            if len(entry["samples"]) < 10:
                entry["samples"].append(v)
    stats.accepted += 1
    stats.source_rows += 1


def _grain_key(t: Dict[str, Any], conflict: Sequence[str]) -> Tuple[Any, ...]:
    return tuple(t.get(c) for c in conflict)


def _finalize(
    stats: StepStats,
    expected: int,
    grain_seen: set,
    fk_checked: Dict[str, int],
    fk_missing: Dict[str, Dict[str, Any]],
    type_bad: set,
    outcome: Optional[TransformOutcome] = None,
) -> StepStats:
    stats.planned_writes = stats.accepted
    stats.writes = 0
    stats.batch_count = (stats.accepted + stats.batch_size - 1) // stats.batch_size
    stats.batch_sizes = [min(stats.batch_size, stats.accepted - i * stats.batch_size)
                         for i in range(stats.batch_count)]
    stats.fk_checks = [{
        "check": label, "checked": n,
        "missing": fk_missing.get(label, {"missing": 0, "samples": []})["missing"],
        "sample": fk_missing.get(label, {"missing": 0, "samples": []})["samples"],
    } for label, n in dict_sorted(fk_checked)]
    stats.not_null_missing = sorted(stats.not_null_missing)
    issues = set(stats.schema_compat_issues)
    issues.update(f"bad_type:{t}" for t in type_bad)
    stats.schema_compat_issues = sorted(issues)
    return stats


def dict_sorted(d: Dict[str, Any]) -> List[Tuple[str, Any]]:
    return sorted(d.items())


# ---------------------------------------------------------------------------
# pipeline context
# ---------------------------------------------------------------------------
@dataclass
class PipelineCtx:
    datasets_dir: Path
    plan_dir: Path
    preflight_path: Path
    baseline_path: Path
    mode: str  # "dry-run" | "apply"
    live_subjects: set = field(default_factory=set)
    live_faculty: set = field(default_factory=set)
    live_departments: set = field(default_factory=set)
    students_ids: set = field(default_factory=set)
    students_eno: set = field(default_factory=set)
    students_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    enrollment_ids: set = field(default_factory=set)
    enrollment_pairs: set = field(default_factory=set)


# ---------------------------------------------------------------------------
# live guards (read-only)
# ---------------------------------------------------------------------------
async def guard_preliminary(conn, ctx: PipelineCtx) -> Dict[str, Any]:
    def hdr(p: Path) -> Optional[str]:
        return None

    g: Dict[str, Any] = {}

    g["source_sha256"] = {
        STEPS_CONF[t][0]: dataset_sha(ctx.datasets_dir / STEPS_CONF[t][0])
        for t in STEP_ORDER
    }

    # cohort-aware identity + academic-year validation (DB-free)
    students_raw = list(read_csv_rows(ctx.datasets_dir / STEPS_CONF["students"][0]))
    g["identity"] = validate_1200_identity(students_raw).to_dict()

    # live master sets for FK resolution
    ctx.live_subjects = {r["subject_id"] for r in await conn.fetch("SELECT subject_id FROM subjects")}
    ctx.live_faculty = {r["faculty_id"] for r in await conn.fetch("SELECT faculty_id FROM faculty")}
    ctx.live_departments = {r["dept_code"] for r in await conn.fetch("SELECT dept_code FROM departments")}
    g["live_masters"] = {
        "subjects": len(ctx.live_subjects), "faculty": len(ctx.live_faculty),
        "departments": len(ctx.live_departments),
    }

    conflicts = {}
    for table in STEP_ORDER:
        id_col = PRIMARY_ID_COL[table]
        prefix = ID_PREFIX[table]
        conflicts[table] = await conn.fetchval(
            f'SELECT count(*) FROM "{table}" WHERE {id_col} LIKE $1', prefix)
    g["existing_6a_prefix_rows"] = conflicts
    g["any_existing_6a_rows"] = any(v > 0 for v in conflicts.values())

    new_counts = {}
    for t in ("attendance_weekly", "student_learning_activity", "student_skill_profile",
              "placement", "student_lifestyle_survey", "career_preferences_v2"):
        new_counts[t] = await conn.fetchval(f'SELECT count(*) FROM "{t}"')
    g["new_table_row_counts"] = new_counts
    g["new_tables_empty"] = all(v == 0 for v in new_counts.values())

    g.update(await _check_fingerprint(conn, ctx))
    if ctx.mode == "apply":
        g["master_hashes"] = {
            t: await _table_hash(conn, t) for t in ("subjects", "faculty", "departments")
        }

    pol = await conn.fetchval(
        "SELECT count(*) FROM pg_policies p WHERE p.schemaname='public' AND p.tablename='placement'")
    helpers = await conn.fetchval(
        "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='public' AND p.proname = ANY($1::text[])",
        ["app_role", "app_user_id", "app_student_id", "app_faculty_id"],
    )
    g["rls_facts"] = {"placement_policies": pol, "helper_functions": helpers}
    return g


async def _check_fingerprint(conn, ctx: PipelineCtx) -> Dict[str, Any]:
    """80-cohort fingerprint guard vs the phase-2 baseline (read-only)."""
    pre = json.loads(ctx.preflight_path.read_text(encoding="utf-8"))
    baseline = json.loads(ctx.baseline_path.read_text(encoding="utf-8"))
    pre_ddl_cols: Dict[str, List[str]] = {}
    for t, info in pre.get("constraint_summary", {}).items():
        cols = [c["column_name"] for c in info.get("columns", [])]
        if cols:
            pre_ddl_cols[t] = cols

    base_fp = (baseline.get("post_ddl_verification", {}) or {}).get("post_ddl_fingerprint", {})
    now_fp, match = {}, {}
    all_match = bool(base_fp)  # fail closed when the phase-2 baseline is absent
    for t, b in base_fp.items():  # type: ignore[assignment]
        bcount = b.get("count")
        live_cols = await _live_columns(conn, t)
        if "hash_projected_to_pre_ddl_columns" in b:
            cols = pre_ddl_cols.get(t) or [c for c in live_cols if c not in ADDED_COLUMNS.get(t, ())]
            h = await _projected_hash(conn, t, cols)
            now_fp[t] = {"count": await _row_count(conn, t),
                         "hash_projected_to_pre_ddl_columns": h}
            ok = now_fp[t]["count"] == bcount and h == b["hash_projected_to_pre_ddl_columns"]
        else:
            h = await _table_hash(conn, t)
            now_fp[t] = {"count": await _row_count(conn, t), "hash": h}
            ok = now_fp[t]["count"] == bcount and h == b["hash"]
        match[t] = ok
        all_match = all_match and ok

    return {
        "fingerprint_target_tables": sorted(base_fp),
        "fingerprint_baseline": {
            k: {"count": v.get("count"),
                "hash": v.get("hash") or v.get("hash_projected_to_pre_ddl_columns")}
            for k, v in base_fp.items()
        },
        "fingerprint_now": now_fp,
        "fingerprint_match": match,
        "fingerprint_all_match": all_match,
        "fingerprint_baseline_missing": not base_fp,
    }


async def _row_count(conn, table: str) -> int:
    return await conn.fetchval(f'SELECT count(*) FROM "{table}"')


async def _table_hash(conn, table: str) -> Optional[str]:
    row = await conn.fetchrow(
        f'SELECT md5(string_agg(rh, \'\' ORDER BY rh)) AS th FROM '
        f'(SELECT md5(ROW(d.*)::text) AS rh FROM "{table}" d) sub')
    return row["th"] if row and row["th"] else None


async def _live_columns(conn, table: str) -> List[str]:
    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=$1 ORDER BY ordinal_position", table)
    return [r["column_name"] for r in rows]


async def _projected_hash(conn, table: str, cols: List[str]) -> Optional[str]:
    if not cols:
        return None
    colsql = ", ".join(f'"{c}"' for c in cols)
    row = await conn.fetchrow(
        f'SELECT md5(string_agg(rh, \'\' ORDER BY rh)) AS th FROM '
        f'(SELECT md5(ROW({colsql})::text) AS rh FROM "{table}" d) sub')
    return row["th"] if row and row["th"] else None


async def _subset_projected_hash(conn, table: str, cols: List[str],
                                 where_sql: str, where_arg: str) -> Optional[str]:
    """Projected hash over a row subset (e.g. legacy rows excluding the 6A prefix)."""
    if not cols:
        return None
    colsql = ", ".join(f'"{c}"' for c in cols)
    row = await conn.fetchrow(
        f'SELECT md5(string_agg(rh, \'\' ORDER BY rh)) AS th FROM '
        f'(SELECT md5(ROW({colsql})::text) AS rh FROM "{table}" '
        f'WHERE {where_sql}) sub', where_arg)
    return row["th"] if row and row["th"] else None


async def _legacy_80cohort_fingerprint(conn, ctx: "PipelineCtx") -> Dict[str, Any]:
    """Post-load 80-cohort guard: shared tables projected over the NON-6A subset.

    The loader appends 6A rows to the shared tables (students, enrollment,
    performance, summary, faculty_student_map) that the phase-2 baseline
    fingerprinted when they held ONLY the 80-cohort rows. Checking full-table
    hashes would be a false negative, so the 80-cohort subset (same pre-DDL
    projection, md5-ordered like the baseline) must reproduce the baseline hash;
    untouched tables must match exactly (count + hash).
    """
    pre = json.loads(ctx.preflight_path.read_text(encoding="utf-8"))
    baseline = json.loads(ctx.baseline_path.read_text(encoding="utf-8"))
    pre_ddl_cols: Dict[str, List[str]] = {}
    for t, info in pre.get("constraint_summary", {}).items():
        cols = [c["column_name"] for c in info.get("columns", [])]
        if cols:
            pre_ddl_cols[t] = cols

    base_fp = (baseline.get("post_ddl_verification", {}) or {}).get("post_ddl_fingerprint", {})
    written = set(STEP_ORDER)
    now_fp, match = {}, {}
    all_match = bool(base_fp)
    for t, b in base_fp.items():  # type: ignore[assignment]
        bcount = b.get("count")
        live_cols = await _live_columns(conn, t)
        if "hash_projected_to_pre_ddl_columns" in b:
            cols = pre_ddl_cols.get(t) or [c for c in live_cols if c not in ADDED_COLUMNS.get(t, ())]
            if t in written:
                where = f"{PRIMARY_ID_COL[t]} NOT LIKE $1"
                h = await _subset_projected_hash(conn, t, cols, where, ID_PREFIX[t])
                cnt = int(await conn.fetchval(
                    f'SELECT count(*) FROM "{t}" WHERE {where}', ID_PREFIX[t]))
                now_fp[t] = {
                    "legacy_count": cnt, "baseline_count": bcount,
                    "hash_projected_to_pre_ddl_columns_legacy": h,
                    "scope": "legacy_rows_excluding_6a",
                }
                ok = cnt == bcount and h == b["hash_projected_to_pre_ddl_columns"]
            else:
                h = await _projected_hash(conn, t, cols)
                cnt = await _row_count(conn, t)
                now_fp[t] = {"count": cnt,
                             "hash_projected_to_pre_ddl_columns": h}
                ok = cnt == bcount and h == b["hash_projected_to_pre_ddl_columns"]
        else:
            h = await _table_hash(conn, t)
            cnt = await _row_count(conn, t)
            now_fp[t] = {"count": cnt, "hash": h}
            ok = cnt == bcount and h == b["hash"]
        match[t] = ok
        all_match = all_match and ok

    return {
        "baseline": {
            k: {"count": v.get("count"),
                "hash": v.get("hash") or v.get("hash_projected_to_pre_ddl_columns")}
            for k, v in base_fp.items()
        },
        "now": now_fp,
        "match": match,
        "all_match": all_match,
    }


# ---------------------------------------------------------------------------
# pipeline orchestration
# ---------------------------------------------------------------------------
def _step_pass(stats: "StepStats") -> bool:
    """Per-step prepare gate (same predicate _build_summary uses on the dicts)."""
    return (
        stats.source_rows == stats.expected_rows
        and stats.quarantined == 0
        and stats.duplicates == 0
        and not stats.not_null_missing
        and not stats.schema_compat_issues
        and all(c["missing"] == 0 for c in stats.fk_checks)
        and stats.existing_conflicts == 0
        and stats.stress_unexpected == 0
        and stats.stress_missing == 0
    )


async def load_1200_pipeline(ctx: PipelineCtx, conn) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    body: Dict[str, Any] = {
        "task": "cse6a_1200_data_load",
        "phase": "PHASE_5_LOAD_DRYRUN" if ctx.mode == "dry-run" else "PHASE_5_LOAD_LIVE",
        "mode": ctx.mode,
        "loader_version": LOADER_VERSION,
        "plan": "MDs/reports/migration/DATA_LOAD_PLAN.md",
        "datasets_dir": str(ctx.datasets_dir.relative_to(REPO_ROOT)),
    }

    body["prechecks"] = await guard_preliminary(conn, ctx)

    runtime: Dict[str, Any] = {"steps": {}}
    steps: List[Dict[str, Any]] = []
    stats_by_table: Dict[str, StepStats] = {}
    for step_no, table in enumerate(STEP_ORDER, 1):
        tracemalloc.start()
        t0 = datetime.now()
        stats = prepare_step(ctx, step_no, table)
        stats.elapsed_s = (datetime.now() - t0).total_seconds()
        stats.peak_mb = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
        tracemalloc.stop()
        runtime["steps"][table] = {"elapsed_s": round(stats.elapsed_s, 3),
                                   "peak_mb": round(stats.peak_mb, 1)}
        steps.append(stats.to_dict(include_runtime=False))
        stats_by_table[table] = stats
    body["steps"] = steps

    load: Optional[Dict[str, Any]] = None
    reconcile: Optional[Dict[str, Any]] = None
    if ctx.mode == "apply":
        if not all(_step_pass(stats) for stats in stats_by_table.values()):
            failed = [t for t in STEP_ORDER if not _step_pass(stats_by_table[t])]
            raise RuntimeError("apply blocked: steps failed preparation "
                               f"({failed}) — aborting BEFORE any insert "
                               "(nothing written)")
        load = await apply_load(ctx, conn, stats_by_table)
        reconcile = await reconcile_live(conn, ctx, body["prechecks"])
        body["load"] = load
        body["reconcile"] = reconcile
        runtime["load"] = {"writes_total": load["writes_total"]}
        applied_writes = {p["table"]: p["inserted"] for p in load["per_step"]}
        for s in body["steps"]:
            s["writes"] = applied_writes.get(s["table"], 0)

    summary = _build_summary(body, ctx.mode)
    body["summary"] = summary

    canonical = {
        k: v for k, v in body.items()
        if k not in ("runtime", "determinism")
    }
    canonical_text = json.dumps(canonical, sort_keys=True, indent=2, default=str)
    body["runtime"] = runtime
    body["determinism"] = {
        "canonical_sha256": hashlib.sha256(canonical_text.encode("utf-8")).hexdigest(),
        "excluded_from_canonical": ["runtime", "determinism", "elapsed_s", "peak_mb"],
    }
    return body, canonical


# ---------------------------------------------------------------------------
# apply-mode insert path (idempotent; one transaction per step; dry-run-independent)
# ---------------------------------------------------------------------------
def _insert_sql(table: str) -> str:
    """INSERT ... ON CONFLICT (<live unique target>) DO NOTHING for one table."""
    cols = list(EMITTED[table])
    col_list = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(f"${i}" for i in range(1, len(cols) + 1))
    conflict = ", ".join(f'"{c}"' for c in STEPS_CONF[table][2])
    return (f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
            f'ON CONFLICT ({conflict}) DO NOTHING')


def _prefix_count_sql(table: str) -> str:
    return (f'SELECT count(*) FROM "{table}" WHERE {PRIMARY_ID_COL[table]} LIKE $1')


def _encode_for_insert(table: str, row: Dict[str, Any]) -> Tuple[Any, ...]:
    """Project a builder row onto EMITTED[table] and coerce date str -> date."""
    cols: List[str] = list(EMITTED[table])
    vals: List[Any] = []
    for c in cols:
        v = row.get(c)
        if v is None:
            vals.append(None)
        elif isinstance(v, str) and c in EMITTED_DATE_COLUMNS.get(table, ()):
            vals.append(date.fromisoformat(v))
        else:
            vals.append(v)
    return tuple(vals)


def iter_insert_rows(table: str, ctx: "PipelineCtx") -> Iterable[Dict[str, Any]]:
    """Yield the exact Builder rows the load step will insert.

    Mirrors prepare_step row-for-row (same source CSVs, same builders/transforms),
    so the per-step accepted count is the number of rows INSERT must match.
    """
    source = ctx.datasets_dir / STEPS_CONF[table][0]
    if table == "students":
        for raw in read_csv_rows(source):
            yield build_students(raw)
    elif table == "student_subject_enrollment":
        for raw in read_csv_rows(source):
            yield build_enrollment(raw)
    elif table == "student_subject_performance":
        # The raw CSV is provably not insertable (guard_raw_performance_not_insertable);
        # the loader consumes transform_performance_rows (B5), exactly as prepare_step.
        for raw in read_csv_rows(source):
            yield build_performance(raw, [])
    elif table == "student_semester_summary":
        for raw in read_csv_rows(source):
            yield build_semester_summary(raw, [])
    elif table == "attendance_weekly":
        for raw in read_csv_rows(source):
            yield build_attendance(raw, [])
    elif table == "student_learning_activity":
        for raw in read_csv_rows(source):
            yield build_learning_activity(raw, [])
    elif table == "faculty_student_map":
        outcome = transform_faculty_student_map(list(read_csv_rows(source)), ctx.students_by_id)
        for row in build_fsm(outcome):
            yield row
    elif table == "student_skill_profile":
        for raw in read_csv_rows(source):
            yield build_skill_profile(raw)
    elif table == "student_lifestyle_survey":
        for raw in read_csv_rows(source):
            raw_stress = _text(raw.get("mental_stress_level"))
            if raw_stress is not None and raw_stress not in STRESS_LEVEL_ALLOWED:
                continue  # rejected (never NULLed) — same rule as prepare_step
            yield build_lifestyle(raw)
    elif table == "placement":
        for raw in read_csv_rows(source):
            yield build_placement(raw)
    elif table == "career_preferences_v2":
        outcome = transform_career_preferences_v2(list(read_csv_rows(source)), ctx.students_by_id)
        for row in build_career_v2(outcome):
            yield row
    else:
        raise ValueError(f"unhandled step table: {table}")


async def apply_load(ctx, conn, steps: Dict[str, "StepStats"]) -> Dict[str, Any]:
    """Run the ordered inserts. ONE transaction per step (rollback on any mismatch)."""
    apply: Dict[str, Any] = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "per_step": [],
        "writes_total": 0,
    }
    for step_no, table in enumerate(STEP_ORDER, 1):
        stats = steps[table]
        prior = int(await conn.fetchval(_prefix_count_sql(table), ID_PREFIX[table]))
        if prior:
            raise RuntimeError(
                f"apply guard: {table} already holds {prior} rows matching "
                f"{ID_PREFIX[table]} — aborting before any insert")
        sql = _insert_sql(table)
        batch: List[Tuple[Any, ...]] = []
        yielded = 0
        t0 = datetime.now()
        async with conn.transaction():
            for row in iter_insert_rows(table, ctx):
                yielded += 1
                batch.append(_encode_for_insert(table, row))
                if len(batch) >= stats.batch_size:
                    await conn.executemany(sql, batch)
                    batch = []
            if batch:
                await conn.executemany(sql, batch)
            final = int(await conn.fetchval(_prefix_count_sql(table), ID_PREFIX[table]))
            inserted = final - prior
            if yielded != stats.accepted:
                raise RuntimeError(
                    f"apply step {table}: iter_insert_rows yielded {yielded} != prepare "
                    f"accepted {stats.accepted} (transaction rolled back)")
            if inserted != stats.accepted:
                raise RuntimeError(
                    f"apply step {table}: inserted {inserted} != accepted {stats.accepted} "
                    f"(transaction rolled back)")
        stats.writes = inserted
        stats.elapsed_s += (datetime.now() - t0).total_seconds()
        apply["per_step"].append({
            "step": step_no,
            "table": table,
            "prior_6a_count": prior,
            "inserted": inserted,
            "final_6a_count": final,
            "expected": stats.accepted,
        })
        apply["writes_total"] += inserted
    apply["finished_at"] = datetime.now().isoformat(timespec="seconds")
    return apply


# ---------------------------------------------------------------------------
# apply-mode post-load reconciliation (read-only; plan DATA_LOAD_PLAN.md §4)
# ---------------------------------------------------------------------------
async def reconcile_live(conn, ctx: "PipelineCtx", pre: Dict[str, Any]) -> Dict[str, Any]:
    """25 read-only post-load checks; any red flag fails reconciliation."""
    rc: Dict[str, Any] = {"checks": {}}
    problems: List[str] = []

    def _ck(name: str, ok: bool, detail: Any) -> None:
        rc["checks"][name] = {"pass": bool(ok), "detail": detail}
        if not ok:
            problems.append(name)

    prefix_counts: Dict[str, int] = {}
    for table in STEP_ORDER:
        prefix_counts[table] = int(await conn.fetchval(
            _prefix_count_sql(table), ID_PREFIX[table]))
    counts_ok = all(prefix_counts[t] == STEPS_CONF[t][1] for t in STEP_ORDER)
    _ck("counts_exact_per_table", counts_ok,
        {t: {"prefix_rows": prefix_counts[t], "expected": STEPS_CONF[t][1]}
         for t in STEP_ORDER})

    ids = await conn.fetch(
        "SELECT student_id FROM students WHERE student_id LIKE 'STU6A%' ORDER BY student_id")
    got_ids = [r["student_id"] for r in ids]
    expected_ids = [f"STU6A{n:04d}" for n in range(1, 1201)]
    _ck("students_STU6A0001_1200_all_present", got_ids == expected_ids,
        {"found": len(got_ids), "expected": len(expected_ids)})

    dup_specs = [
        ("dup_students", "students", ("student_id",)),
        ("dup_enrollment_grains", "student_subject_enrollment",
         ("student_id", "subject_id", "academic_year")),
        ("dup_performance", "student_subject_performance", ("performance_id",)),
        ("dup_summary_grains", "student_semester_summary",
         ("student_id", "semester_no", "academic_year")),
        ("dup_attendance_grains", "attendance_weekly",
         ("enrollment_record_id", "week_number")),
        ("dup_learning_grains", "student_learning_activity",
         ("enrollment_record_id", "week_number")),
        ("dup_fsm", "faculty_student_map", ("faculty_student_map_id",)),
        ("dup_skill", "student_skill_profile", ("student_skill_id",)),
        ("dup_lifestyle_grains", "student_lifestyle_survey", ("student_id", "semester_no")),
        ("dup_placement", "placement", ("student_id",)),
        ("dup_career", "career_preferences_v2", ("student_id",)),
    ]
    for name, table, cols in dup_specs:
        cols_sql = ", ".join(f'"{c}"' for c in cols)
        n = int(await conn.fetchval(
            f"SELECT count(*) FROM (SELECT 1 FROM \"{table}\" WHERE "
            f"{PRIMARY_ID_COL[table]} LIKE $1 GROUP BY {cols_sql} HAVING count(*) > 1) x",
            ID_PREFIX[table]))
        _ck(name, n == 0, n)

    async def _orphans(table: str, ref_col: str, ref_table: str, ref_target: str,
                       prefix_col: str, prefix: str) -> int:
        return int(await conn.fetchval(
            f"SELECT count(*) FROM \"{table}\" p WHERE {prefix_col} LIKE $1 "
            f"AND NOT EXISTS (SELECT 1 FROM \"{ref_table}\" r "
            f"WHERE r.{ref_target} = p.{ref_col})", prefix))

    _ck("fk_attendance_enrollment_ok", await _orphans(
        "attendance_weekly", "enrollment_record_id", "student_subject_enrollment",
        "enrollment_record_id", "attendance_id", "ATT6A%") == 0, 0)
    _ck("fk_learning_enrollment_ok", await _orphans(
        "student_learning_activity", "enrollment_record_id", "student_subject_enrollment",
        "enrollment_record_id", "learning_activity_id", "LRN6A%") == 0, 0)
    _ck("fk_performance_enrollment_ok", await _orphans(
        "student_subject_performance", "enrollment_record_id", "student_subject_enrollment",
        "enrollment_record_id", "performance_id", "PER6A%") == 0, 0)
    _ck("fk_summary_students_ok", await _orphans(
        "student_semester_summary", "student_id", "students",
        "student_id", "semester_summary_id", "SEM6A%") == 0, 0)
    _ck("fk_fsm_students_ok", await _orphans(
        "faculty_student_map", "student_id", "students",
        "student_id", "faculty_student_map_id", "FSM6A%") == 0, 0)
    _ck("fk_placement_students_ok", await _orphans(
        "placement", "student_id", "students",
        "student_id", "placement_id", "PLC6A%") == 0, 0)
    _ck("fk_career_students_ok", await _orphans(
        "career_preferences_v2", "student_id", "students",
        "student_id", "career_preference_id", "CAR6A%") == 0, 0)

    null_stress = int(await conn.fetchval(
        "SELECT count(*) FROM student_lifestyle_survey WHERE survey_id LIKE 'LIFE6A%' "
        "AND mental_stress_level IS NULL"))
    _ck("lifestyle_stress_no_nulls", null_stress == 0, null_stress)
    dist = {r["s"]: r["n"] for r in await conn.fetch(
        "SELECT mental_stress_level AS s, count(*) AS n FROM student_lifestyle_survey "
        "WHERE survey_id LIKE 'LIFE6A%' GROUP BY mental_stress_level ORDER BY 1")}
    _ck("lifestyle_stress_enum_valid", set(dist) - set(STRESS_LEVEL_ALLOWED) == set(), dist)
    expected_dist = {"High": 2863, "Medium": 4556, "Low": 2181}
    _ck("lifestyle_stress_distribution_exact", dist == expected_dist,
        {"actual": dist, "expected": expected_dist})

    bad_marks = int(await conn.fetchval(
        "SELECT count(*) FROM student_subject_performance WHERE performance_id LIKE 'PER6A%' "
        "AND NOT ("
        "  (end_sem_marks IS NULL AND total_marks IS NULL AND percentage IS NULL)"
        "  OR ("
        "    end_sem_marks IS NOT NULL"
        "    AND total_marks = internal_marks + mid_sem_marks + end_sem_marks"
        "    AND total_marks BETWEEN 0 AND 140"
        "    AND percentage = ROUND((total_marks::numeric * 100.0) / 140.0, 2)"
        "    AND internal_marks BETWEEN 0 AND 20"
        "    AND mid_sem_marks BETWEEN 0 AND 50"
        "    AND end_sem_marks BETWEEN 0 AND 70"
        "    AND grade IN ('O','A+','A','B+','B','C','F')"
        "    AND grade_point IN (0,5,6,7,8,9,10)"
        "    AND result_status IN ('Pass','Fail')"
        "    AND performance_category IN ('Top','Above Average','Average','Below Average','Low Performer')"
        "  )"
        ")"))
    _ck("performance_derived_marks_constraint", bad_marks == 0, bad_marks)

    rows = await conn.fetch(
        "SELECT internal_marks, mid_sem_marks, end_sem_marks, total_marks, "
        "percentage, grade, grade_point, result_status, performance_category, remarks "
        "FROM student_subject_performance WHERE performance_id LIKE 'PER6A%'")
    mism: Dict[str, int] = {}
    for r in rows:
        d = derive_marks_fields(r["internal_marks"], r["mid_sem_marks"], r["end_sem_marks"])
        stored = {
            "total_marks": r["total_marks"],
            "percentage": r["percentage"].quantize(Decimal("0.01"))
            if r["percentage"] is not None else None,
            "grade": r["grade"],
            "grade_point": r["grade_point"],
            "result_status": r["result_status"],
            "performance_category": r["performance_category"],
            "remarks": r["remarks"],
        }
        expected = {
            "total_marks": d["total_marks"],
            "percentage": Decimal(str(d["percentage"])).quantize(Decimal("0.01"))
            if d["percentage"] is not None else None,
            "grade": d["grade"],
            "grade_point": d["grade_point"],
            "result_status": d["result_status"],
            "performance_category": d["performance_category"],
            "remarks": d["remarks"],
        }
        for k in stored:
            if stored[k] != expected[k]:
                mism[k] = mism.get(k, 0) + 1
    _ck("performance_trigger_parity", not mism, {"mismatched_fields": mism, "rows": len(rows)})

    leak_hits = _scan_leakage_tokens()
    _ck("m1_m2_m3_no_leakage_static", not leak_hits, leak_hits)

    summary_filter = "semester_summary_id LIKE 'SEM6A%'"
    boundary_true = int(await conn.fetchval(
        "SELECT count(*) FROM student_semester_summary WHERE " + summary_filter
        + " AND is_m1_deployment_boundary"))
    boundary_wrong_sem = int(await conn.fetchval(
        "SELECT count(*) FROM student_semester_summary WHERE " + summary_filter
        + " AND is_m1_deployment_boundary AND semester_no <> 7"))
    target_ok = int(await conn.fetchval(
        "SELECT count(*) FROM student_semester_summary WHERE " + summary_filter
        + " AND NOT target_available_if_completed"))
    _ck("boundary_markers_semantics",
        boundary_true == 1200 and boundary_wrong_sem == 0 and target_ok == 0,
        {"boundary_true_rows": boundary_true, "boundary_wrong_semester": boundary_wrong_sem,
         "target_not_available_rows": target_ok})

    masters_now = {
        t: await _table_hash(conn, t) for t in ("subjects", "faculty", "departments")
    }
    masters_base = pre.get("master_hashes") or {}
    masters_ok = all(masters_now.get(t) == masters_base.get(t) for t in masters_now)
    legacy = await _legacy_80cohort_fingerprint(conn, ctx)
    _ck("masters_and_80cohort_unchanged", masters_ok and legacy["all_match"],
        {"masters_match": masters_ok, "master_hashes_now": masters_now,
         "masters_baseline": masters_base,
         "legacy_80cohort_all_match": legacy["all_match"],
         "legacy_fingerprint_now": legacy["now"],
         "legacy_fingerprint_match": legacy["match"]})

    rls_tables = ("attendance_weekly", "student_learning_activity", "student_skill_profile",
                  "student_lifestyle_survey", "placement", "career_preferences_v2")
    rls_now: Dict[str, Any] = {}
    rls_enabled = True
    for t in rls_tables:
        r = await conn.fetchrow(
            "SELECT relrowsecurity FROM pg_class WHERE oid = to_regclass('public." + t + "')")
        n = int(await conn.fetchval(
            "SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename=$1", t))
        enabled = bool(r and r["relrowsecurity"])
        rls_now[t] = {"relrowsecurity": enabled, "policies": n}
        if not enabled:
            rls_enabled = False
    placement_policies_now = rls_now["placement"]["policies"]
    placement_policies_base = pre.get("rls_facts", {}).get("placement_policies")
    helpers_now = int(await conn.fetchval(
        "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='public' AND p.proname = ANY($1::text[])",
        ["app_role", "app_user_id", "app_student_id", "app_faculty_id"]))
    helpers_base = pre.get("rls_facts", {}).get("helper_functions")
    role = await conn.fetchrow(
        "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
    _ck("rls_intact",
        rls_enabled and placement_policies_now == placement_policies_base
        and helpers_now == helpers_base,
        {"rls_enabled": rls_enabled, "rls_now": rls_now,
         "placement_policies": {"baseline": placement_policies_base,
                                "now": placement_policies_now},
         "helper_functions": {"baseline": helpers_base, "now": helpers_now},
         "role": dict(role) if role else None,
         "note": "RLS stays enabled for all six target tables; tables with zero "
                 "policies are deny-by-default by design (unchanged from pre-load). "
                 "role postgres owns the tables; rolbypassrls=true lets the loader "
                 "bypass RLS while application roles keep RLS enforcement"})

    rc["pass"] = not problems
    rc["checks_total"] = len(rc["checks"])
    rc["checks_passed"] = len(rc["checks"]) - len(problems)
    rc["failed_checks"] = problems
    return rc


# Graduated M1/M2/M3 feature surface: these paths + m1/, m2/, m3/, features/.
# m4/, m4_backup/ and ml/tests are intentionally OUT OF SCOPE (M4's target is
# package_lpa by design; tests legitimately reference it).
ML_FEATURE_SURFACE_FILES = (
    "feature_data.py", "features.py", "feature_config.py",
    "inference.py", "prediction_service.py",
)
ML_FEATURE_SURFACE_DIRS = ("features/", "m1/", "m2/", "m3/")
ML_LEAK_TOKENS = (
    r"\bplacement_status\b", r"\bpackage_lpa\b",
    r"\bis_m1_deployment_boundary\b", r"\btarget_available_if_completed\b",
    r"\bcareer_preferences_v2\b", r"\bfrom\s+placement\b",
)


def _scan_leakage_tokens() -> Dict[str, List[str]]:
    """Static no-leak gate over the graduated M1/M2/M3 feature surface."""
    hits: Dict[str, List[str]] = {}
    src = REPO_ROOT / "ml" / "src"
    for path in sorted(src.rglob("*.py")):
        rel = path.relative_to(src).as_posix()
        if rel not in ML_FEATURE_SURFACE_FILES and not rel.startswith(ML_FEATURE_SURFACE_DIRS):
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            low = line.lower()
            for tok in ML_LEAK_TOKENS:
                if re.search(tok, low):
                    hits.setdefault(tok, []).append(f"{path.relative_to(REPO_ROOT)}:{i}")
    return hits


def _build_summary(body: Dict[str, Any], mode: str) -> Dict[str, Any]:
    pre = body["prechecks"]
    steps = body["steps"]
    steps_ok = all(
        s["source_rows"] == s["expected_rows"]
        and s["quarantined"] == 0
        and s["duplicates"] == 0
        and not s["not_null_missing"]
        and not s["schema_compat_issues"]
        and all(c["missing"] == 0 for c in s["fk_checks"])
        and s["existing_6a_conflicts"] == 0
        and s["stress_validation"]["unexpected"] == 0
        and s["stress_validation"]["missing"] == 0
        for s in steps
    )
    guards_ok = (
        not pre["any_existing_6a_rows"]
        and pre["new_tables_empty"]
        and pre["fingerprint_all_match"]
    )
    cleanup_fp: Dict[str, Any] = {"fingerprint_all_match": pre["fingerprint_all_match"]}
    summary = {
        "mode": mode,
        "steps_total": len(steps),
        "row_counts_expected": [s["expected_rows"] for s in steps],
        "every_step_source_equals_expected": all(
            s["source_rows"] == s["expected_rows"] for s in steps),
        "every_step_quarantine_zero": all(s["quarantined"] == 0 for s in steps),
        "every_step_duplicates_zero": all(s["duplicates"] == 0 for s in steps),
        "every_step_fk_clean": all(
            all(c["missing"] == 0 for c in s["fk_checks"]) for s in steps),
        "every_step_not_null_ok": all(not s["not_null_missing"] for s in steps),
        "every_step_schema_compat_ok": all(not s["schema_compat_issues"] for s in steps),
        "every_step_mental_stress_valid": all(
            s["stress_validation"]["unexpected"] == 0
            and s["stress_validation"]["missing"] == 0 for s in steps),
        "every_step_zero_6a_conflicts": all(
            s["existing_6a_conflicts"] == 0 for s in steps),
        "identity_valid": bool(pre["identity"]["valid"]),
        "guards": guards_ok,
        "dry_run_zero_writes": mode == "dry-run",
        "pass": bool(pre["identity"]["valid"]) and steps_ok and guards_ok,
    }
    if mode == "apply":
        reconcile = body.get("reconcile", {})
        summary["cleanup_precheck_fingerprint"] = cleanup_fp
        summary["reconcile_pass"] = bool(reconcile.get("pass"))
        summary["reconcile_checks_total"] = reconcile.get("checks_total")
        summary["reconcile_checks_passed"] = reconcile.get("checks_passed")
        summary["reconcile_failed_checks"] = reconcile.get("failed_checks", [])
        summary["writes_total"] = body.get("load", {}).get("writes_total", 0)
        summary["pass"] = summary["pass"] and summary["reconcile_pass"]
    return summary


# ---------------------------------------------------------------------------
# entrypoints
# ---------------------------------------------------------------------------
async def _connect_retry(cfg) -> asyncpg.Connection:
    last: Any = None
    for attempt in range(6):
        try:
            return await asyncpg.connect(
                host=cfg.host, port=cfg.port, database=cfg.name, user=cfg.user,
                password=cfg.password, ssl="require", statement_cache_size=0, timeout=60)
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < 5:
                await asyncio.sleep(2 * (attempt + 1))
    raise last


def run_loader(
    *,
    mode: str,
    datasets_dir: Path = DEFAULT_DATASETS,
    preflight_path: Path = PREFLIGHT_REPORT,
    baseline_path: Path = BASELINE_REPORT,
) -> Dict[str, Any]:
    """Synchronous entry; connects read-only for dry-run, applies for --apply."""
    cfg = db_config()
    ctx = PipelineCtx(datasets_dir=datasets_dir, plan_dir=PLAN_DIR,
                      preflight_path=preflight_path, baseline_path=baseline_path,
                      mode=mode)

    async def _go() -> Tuple[Dict[str, Any], Dict[str, Any]]:
        conn = await _connect_retry(cfg)
        try:
            if mode == "dry-run":
                await conn.execute("SET default_transaction_read_only = on")
            elif mode == "apply":
                # pgbouncer transaction pooler can reuse a backend that carries a
                # leaked read-only flag from an earlier dry-run; force it off. Note:
                # this only affects THIS session, never the DDL/app role.
                await conn.execute("SET default_transaction_read_only = off")
            else:
                raise ValueError(f"unknown loader mode: {mode}")
            body, canonical = await load_1200_pipeline(ctx, conn)
            return body, canonical
        finally:
            await conn.close()

    body, _canonical = asyncio.run(_go())
    return body


def run_reconcile(
    *,
    prior_report: Path = PLAN_DIR / "phase5_load_live.json",
    datasets_dir: Path = DEFAULT_DATASETS,
    preflight_path: Path = PREFLIGHT_REPORT,
    baseline_path: Path = BASELINE_REPORT,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Re-run the read-only post-load reconciliation against the live database.

    Reads the apply-time precheck snapshot (master hashes / RLS facts) from the
    prior ``--apply`` report and returns the fresh reconciliation plus the
    patched apply body (reconcile section, summary, canonical determinism) so
    ``phase5_load_live.json`` can be corrected without re-running inserts.
    """
    cfg = db_config()
    prior = json.loads(prior_report.read_text(encoding="utf-8"))
    ctx = PipelineCtx(datasets_dir=datasets_dir, plan_dir=PLAN_DIR,
                      preflight_path=preflight_path, baseline_path=baseline_path,
                      mode="reconcile")
    pre = prior["prechecks"]

    async def _go() -> Dict[str, Any]:
        conn = await _connect_retry(cfg)
        try:
            await conn.execute("SET default_transaction_read_only = on")
            return await reconcile_live(conn, ctx, pre)
        finally:
            await conn.close()

    rc = asyncio.run(_go())
    body = dict(prior)
    body["reconcile"] = rc
    body["reconcile_mode"] = "re-read-only"
    body["summary"] = _build_summary(body, "apply")
    canonical = {
        k: v for k, v in body.items()
        if k not in ("runtime", "determinism")
    }
    canonical_text = json.dumps(canonical, sort_keys=True, indent=2, default=str)
    body["determinism"] = {
        "canonical_sha256": hashlib.sha256(canonical_text.encode("utf-8")).hexdigest(),
        "excluded_from_canonical": ["runtime", "determinism", "elapsed_s", "peak_mb"],
    }
    return body, canonical


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m etl load_1200",
        description="CSE 6A 1,200-cohort ordered data-load runner (dry-run default; zero DB writes).",
    )
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--dry-run", action="store_true", default=True,
                     help="Plan + verify; zero writes (default).")
    grp.add_argument("--apply", action="store_true",
                     help="Precheck (read-only) then execute ordered inserts "
                          "and the 25-check post-load reconciliation.")
    grp.add_argument("--reconcile", action="store_true",
                     help="Re-run the read-only post-load reconciliation "
                          "against the live database (needs a prior --apply).")
    parser.add_argument("--datasets", type=Path, default=DEFAULT_DATASETS)
    parser.add_argument("--preflight", type=Path, default=PREFLIGHT_REPORT)
    parser.add_argument("--baseline", type=Path, default=BASELINE_REPORT)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv or [])

    mode = ("apply" if args.apply else "reconcile" if args.reconcile else "dry-run")
    if mode == "reconcile":
        out = args.out or (PLAN_DIR / "phase5_load_live.json")
        try:
            body, _canonical = run_reconcile(
                datasets_dir=args.datasets, preflight_path=args.preflight,
                baseline_path=args.baseline)
        except Exception as exc:  # noqa: BLE001
            print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
            return EXIT_UNEXPECTED_ERROR
    else:
        out = args.out or (
            PLAN_DIR / ("phase5_load_live.json" if mode == "apply" else "phase5_load_dryrun.json")
        )
        try:
            body = run_loader(mode=mode, datasets_dir=args.datasets,
                              preflight_path=args.preflight, baseline_path=args.baseline)
        except Exception as exc:  # noqa: BLE001
            print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
            return EXIT_UNEXPECTED_ERROR

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=2, sort_keys=True, default=str), encoding="utf-8")
    canonical_out = out.with_name(out.stem + ".canonical.json")
    canonical_out.write_text(
        json.dumps({k: v for k, v in body.items() if k not in ("runtime", "determinism")},
                   sort_keys=True, indent=2, default=str),
        encoding="utf-8")
    print(f"wrote {out}")
    print(f"wrote {canonical_out}")
    if mode in ("apply", "reconcile"):
        rec_out = PLAN_DIR / "post_load_reconciliation_1200.json"
        rec_out.write_text(
            json.dumps(body["reconcile"], indent=2, sort_keys=True, default=str),
            encoding="utf-8")
        print(f"wrote {rec_out}")
    if body["summary"]["pass"] and (
            mode not in ("apply", "reconcile") or body.get("reconcile", {}).get("pass")):
        print("PASS: every gate green.")
        return EXIT_SUCCESS
    print("FAIL: one or more gates red — inspect the report.", file=sys.stderr)
    return EXIT_VALIDATION_FAILURE


if __name__ == "__main__":
    sys.exit(main())