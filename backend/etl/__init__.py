"""CampusX KDAC-3 reusable ETL pipeline.

Infrastructure (Phase 1): config, run context, structured results, the stage
contract, the runner, CLI, logging, exceptions, and the idempotency / lineage /
transaction-safety hooks. Business stages (Extract + Validate + Stage + Stitch +
Transform + Load + Derive): raw CSV extraction with source identity, plan `03`
§3.3 validation with quarantine, in-memory staging with run_id tagging, canonical
identity resolution against master data, deterministic fact-level transformations,
idempotent upserts into canonical tables, and aggregate recompute into derived
tables. All seven canonical stages are now implemented.
"""

__version__ = "1.0.0"

from etl.context import RunContext
from etl.exceptions import (
    EtlConfigurationError,
    EtlDatabaseError,
    EtlDryRunError,
    EtlError,
    EtlLoadDeriveError,
    EtlSourceError,
    EtlStageError,
    EtlStitchAmbiguityError,
    EtlUnexpectedError,
    EtlValidationError,
)
from etl.keys import (
    ATTENDANCE_ROW_KEY_FIELDS,
    LECTURE_SESSION_KEY_FIELDS,
    business_key,
    business_key_str,
    dedupe_by_key,
)
from etl.logging import EtlLogger
from etl.result import RunSummary, StageResult
from etl.runner import EtlRunner
from etl.sources import DATASET_SOURCES, CsvSource, extract_csv
from etl.stages import Stage, STAGE_NAMES
from etl.stages.stage import StageStage
from etl.stages.stitch import StitchStage, StitchedRecord, ResolvedIdentities
from etl.stages.transform import TransformStage
from etl.stages.load import LoadStage
from etl.stages.derive import DeriveStage
from etl.validation import (
    QuarantineRecord,
    Scope,
    TimetableReference,
    ValidationOutcome,
    assert_within_quarantine_ratio,
    validate_attendance,
    validate_timetable,
)
from etl.second_cohort import (
    SecondCohortPayload,
    SecondCohortValidation,
    SecondCohortValidationError,
    SecondCohortWritePlan,
    WritePlan,
    guard_apply,
    plan_enrollment_upsert,
    plan_second_cohort_write,
    plan_student_upsert,
    plan_semester_summary_upsert,
    validate_second_cohort_payload,
)

__all__ = [
    "__version__",
    "EtlConfigurationError",
    "EtlDatabaseError",
    "EtlDryRunError",
    "EtlError",
    "EtlLoadDeriveError",
    "EtlSourceError",
    "EtlStageError",
    "EtlStitchAmbiguityError",
    "EtlUnexpectedError",
    "EtlValidationError",
    "EtlLogger",
    "EtlRunner",
    "RunContext",
    "RunSummary",
    "Stage",
    "StageResult",
    "StageStage",
    "StitchStage",
    "StitchedRecord",
    "ResolvedIdentities",
    "TransformStage",
    "LoadStage",
    "DeriveStage",
    "STAGE_NAMES",
    "ATTENDANCE_ROW_KEY_FIELDS",
    "LECTURE_SESSION_KEY_FIELDS",
    "business_key",
    "business_key_str",
    "dedupe_by_key",
    "DATASET_SOURCES",
    "CsvSource",
    "extract_csv",
    "QuarantineRecord",
    "Scope",
    "TimetableReference",
    "ValidationOutcome",
    "assert_within_quarantine_ratio",
    "validate_attendance",
    "validate_timetable",
    "SecondCohortPayload",
    "SecondCohortValidation",
    "SecondCohortValidationError",
    "SecondCohortWritePlan",
    "WritePlan",
    "guard_apply",
    "plan_enrollment_upsert",
    "plan_second_cohort_write",
    "plan_student_upsert",
    "plan_semester_summary_upsert",
    "validate_second_cohort_payload",
]
