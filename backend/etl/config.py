"""ETL configuration.

Composes the existing application ``Settings`` (database connection + Threshold
Engine) with ETL-specific execution knobs. No credentials or developer-machine
paths are hardcoded: values come from the repository's environment/``.env.local``
convention — the same file ``app.core.config`` reads — resolved by an absolute
path so the pipeline works from any working directory, including the repository
root (plan `01` §5.1).

The database connection is declared here (same env names the app uses) so the
ETL CLI does not depend on the process working directory; the DSN format mirrors
``app.core.config.Settings.database_url`` exactly.
"""

from pathlib import Path
from typing import List
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import settings as app_settings

REPO_ROOT = Path(__file__).resolve().parents[2]


class EtlConfig(BaseSettings):
    ETL_PIPELINE_NAME: str = "kenexai_etl"
    ETL_PIPELINE_VERSION: str = "1.0.0"
    ETL_ENVIRONMENT: str = "development"
    ETL_LOG_LEVEL: str = "INFO"
    ETL_MAX_QUARANTINE_RATIO: float = 0.05
    ETL_DATASETS_DIR: str = str(REPO_ROOT / "backend" / "datasets")

    # V1 locked scope (plan `01` §8, `02` §1.2). Tenant/semester scoping comes
    # from configuration and the data itself, never hardcoded in stage code:
    # a new department/semester is a configuration exercise, not a code change.
    ETL_DEPARTMENT_CODE: int = 1
    ETL_SEMESTER_NO: int = 7
    ETL_ACADEMIC_YEAR: str = "2026-2027"
    # Academic-year format, cohort-aware. Default accepts both the locked V1
    # "YYYY-YYYY" form ("2026-2027") and the "YYYY-YY" form used by earlier
    # admission cohorts ("2021-22".."2025-26"). The pattern is configuration,
    # never a regex hardcoded in stage/transform code.
    ETL_ACADEMIC_YEAR_PATTERN: str = r"^\d{4}-(\d{2}|\d{4})$"
    ETL_STUDENT_ID_PATTERN: str = r"^STU\d{6}$"
    ETL_SUBJECT_ID_PATTERN: str = r"^SUB\d{4}$"
    ETL_FACULTY_ID_PATTERN: str = r"^FAC\d{3}$"
    ETL_ENROLLMENT_NO_PATTERN: str = r"^2023\d{6}$"
    ETL_STUDENT_ID_MIN: str = "STU000001"
    ETL_STUDENT_ID_MAX: str = "STU000050"

    # Cohort-aware identity validation (Task 2). The locked scope above remains
    # the single default namespace. Extra namespaces let the SAME ETL validate a
    # second cohort (e.g. the 6A-1200 dataset with student STU6A0001..STU6A1200
    # and enrollment 2021...) without editing validation code: patterns and
    # ranges stay config-derived, never hardcoded. Defaults are empty, so V1
    # behavior is unchanged unless a cohort explicitly registers itself.
    # Each student-id namespace entry is "pattern|min|max" (min/max optional;
    # empty = unbounded on that side). Each enrollment-no entry is a plain
    # anchored fullmatch pattern.
    ETL_STUDENT_ID_NAMESPACES_EXTRA: List[str] = []
    ETL_ENROLLMENT_NO_PATTERNS_EXTRA: List[str] = []

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "postgres"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """Same DSN shape as ``app.core.config.Settings.database_url``."""
        encoded_password = quote_plus(self.DB_PASSWORD)
        return (
            f"postgresql://{self.DB_USER}:{encoded_password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def thresholds(self):
        """Reuse the application Threshold Engine constants (plan `03` §2)."""
        return app_settings

    @property
    def datasets_dir(self) -> Path:
        return Path(self.ETL_DATASETS_DIR)


etl_config = EtlConfig()
