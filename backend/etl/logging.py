"""Structured ETL logging.

One line per lifecycle event (``RUN_STARTED``, ``STAGE_STARTED``,
``STAGE_COMPLETED``, ``STAGE_FAILED``, ``RUN_COMPLETED``, ``RUN_FAILED``) with
``run_id``, stage, and timing where useful. Built on the standard library —
no new dependency. Credential-like values are redacted defensively; nothing in
the ETL logs should ever contain secrets.
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TextIO

_SENSITIVE_KEY_MARKERS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "dsn",
    "connection_string",
)


def _redact(value: Any, key: str) -> Any:
    lowered = key.lower()
    if any(marker in lowered for marker in _SENSITIVE_KEY_MARKERS):
        return "***"
    return value


def _format_value(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class EtlLogger:
    def __init__(
        self,
        run_id: str,
        log_level: str = "INFO",
        stream: Optional[TextIO] = None,
        name: str = "kenexai.etl",
    ) -> None:
        self.run_id = run_id
        self._logger = logging.getLogger(f"{name}.{run_id}")
        self._logger.setLevel(log_level.upper())
        self._logger.propagate = False
        if not self._logger.handlers:
            handler = logging.StreamHandler(stream or sys.stderr)
            handler.setFormatter(
                logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
            )
            self._logger.addHandler(handler)

    def _emit(
        self,
        level: int,
        event: str,
        message: str,
        **fields: Any,
    ) -> None:
        base = {"run_id": self.run_id}
        base.update(fields)
        rendered = " ".join(
            f"{key}={_format_value(_redact(value, key))}"
            for key, value in base.items()
        )
        self._logger.log(level, f"{event} | {message} | {rendered}")

    def debug(self, event: str, message: str, **fields: Any) -> None:
        self._emit(logging.DEBUG, event, message, **fields)

    def info(self, event: str, message: str, **fields: Any) -> None:
        self._emit(logging.INFO, event, message, **fields)

    def warning(self, event: str, message: str, **fields: Any) -> None:
        self._emit(logging.WARNING, event, message, **fields)

    def error(self, event: str, message: str, **fields: Any) -> None:
        self._emit(logging.ERROR, event, message, **fields)

    def run_started(self, context) -> None:
        self.info(
            "RUN_STARTED",
            "pipeline run started",
            pipeline=context.pipeline_name,
            version=context.pipeline_version,
            environment=context.environment,
            dry_run=context.dry_run,
            sources=",".join(context.sources) or "none",
        )

    def stage_started(self, context) -> None:
        self.info(
            "STAGE_STARTED",
            "stage started",
            stage=context.current_stage,
        )

    def stage_completed(self, context, result) -> None:
        self.info(
            "STAGE_COMPLETED",
            "stage completed",
            stage=result.stage,
            status=result.status,
            rows_read=result.rows_read,
            rows_accepted=result.rows_accepted,
            rows_rejected=result.rows_rejected,
            rows_written=result.rows_written,
            warnings=len(result.warnings),
            elapsed=round(result.duration, 4),
        )

    def stage_failed(self, context, stage: str, errors) -> None:
        self.error(
            "STAGE_FAILED",
            "stage failed",
            stage=stage,
            error="; ".join(errors),
        )

    def run_completed(self, context, summary) -> None:
        self.info(
            "RUN_COMPLETED",
            "pipeline run completed",
            stages=len(summary.stages),
            exit_code=summary.exit_code,
        )

    def run_failed(self, context, error: BaseException) -> None:
        self.error(
            "RUN_FAILED",
            "pipeline run failed",
            stage=context.current_stage,
            error=f"{type(error).__name__}: {error}",
        )
