"""KenexAI KDAC-3 reusable ETL pipeline.

Infrastructure (Phase 1): config, run context, structured results, the stage
contract, the runner, CLI, logging, exceptions, and the idempotency / lineage /
transaction-safety hooks. Business stages so far (Extract + Validate slice):
raw CSV extraction with source identity, and plan `03` §3.3 validation with
quarantine. Downstream stages (Stage/Stitch/Transform/Load/Derive) are later
slices (plan `data_engineering/01` §3.1).
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
from etl.validation import (
    QuarantineRecord,
    Scope,
    TimetableReference,
    ValidationOutcome,
    assert_within_quarantine_ratio,
    validate_attendance,
    validate_timetable,
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
]
