"""ETL-specific exception hierarchy and process exit-code mapping.

Exit codes align with ``plan/data_engineering/01_reusable_etl_architecture.md``
§5.3 (0 success; 1 validation/quarantine-threshold; 2 stitch ambiguity;
3 load/derive failure) and extend them with configuration and unexpected
failure codes so every failure is distinct and machine-readable.
"""


class EtlError(Exception):
    """Base class for all ETL-specific failures."""


class EtlConfigurationError(EtlError):
    """Configuration is missing, invalid, or inconsistent."""


class EtlSourceError(EtlError):
    """A source (dataset, file, external source) is missing or unreadable."""


class EtlValidationError(EtlError):
    """Rows failed validation or the quarantine threshold was exceeded."""


class EtlStitchAmbiguityError(EtlError):
    """Identity could not be resolved unambiguously; review required."""


class EtlDatabaseError(EtlError):
    """A database operation failed (connect, query, or write)."""


class EtlLoadDeriveError(EtlError):
    """A load or derive stage failed; no partial canonical state is left."""


class EtlStageError(EtlError):
    """A generic pipeline/stage failure."""


class EtlDryRunError(EtlError):
    """A stage attempted a write while the run was in dry-run mode."""


class EtlTransformError(EtlError):
    """A transform stage failure (data type or mapping error)."""


class EtlUnexpectedError(EtlError):
    """An unexpected, internal failure."""


EXIT_SUCCESS = 0
EXIT_VALIDATION_FAILURE = 1
EXIT_STITCH_AMBIGUITY = 2
EXIT_LOAD_DERIVE_FAILURE = 3
EXIT_CONFIGURATION_ERROR = 4
EXIT_UNEXPECTED_ERROR = 5


def to_exit_code(error: BaseException) -> int:
    """Map an ETL exception to the process exit code it represents."""
    if isinstance(error, EtlConfigurationError):
        return EXIT_CONFIGURATION_ERROR
    if isinstance(error, (EtlSourceError, EtlValidationError)):
        return EXIT_VALIDATION_FAILURE
    if isinstance(error, EtlStitchAmbiguityError):
        return EXIT_STITCH_AMBIGUITY
    if isinstance(
        error,
        (EtlDatabaseError, EtlLoadDeriveError, EtlStageError, EtlDryRunError, EtlTransformError),
    ):
        return EXIT_LOAD_DERIVE_FAILURE
    return EXIT_UNEXPECTED_ERROR
