"""Structured result model for ETL stages and full runs.

Kept deliberately lightweight — this is the contract future Extract/Validate/
Stage/Stitch/Transform/Load/Derive stages return, not an observability
platform (plan `01` §5.3, §6.3).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


@dataclass
class StageResult:
    stage: str
    status: str = STATUS_SUCCESS
    rows_read: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    rows_written: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    exit_code: Optional[int] = None

    @property
    def failed(self) -> bool:
        return self.status == STATUS_FAILED or bool(self.errors)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.status = STATUS_FAILED

    @classmethod
    def failure(cls, stage: str, error: BaseException, **kwargs: Any) -> "StageResult":
        result = cls(stage=stage, status=STATUS_FAILED, **kwargs)
        result.errors.append(f"{type(error).__name__}: {error}")
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "rows_read": self.rows_read,
            "rows_accepted": self.rows_accepted,
            "rows_rejected": self.rows_rejected,
            "rows_written": self.rows_written,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "duration": self.duration,
            "metadata": dict(self.metadata),
        }


@dataclass
class RunSummary:
    run_id: str
    pipeline_name: str
    pipeline_version: str
    environment: str
    started_at: datetime
    dry_run: bool
    finished_at: Optional[datetime] = None
    stages: List[StageResult] = field(default_factory=list)
    exit_code: int = 0

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pipeline_name": self.pipeline_name,
            "pipeline_version": self.pipeline_version,
            "environment": self.environment,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "dry_run": self.dry_run,
            "exit_code": self.exit_code,
            "stages": [s.to_dict() for s in self.stages],
        }
