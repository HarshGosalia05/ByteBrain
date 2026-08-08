"""ETL run context.

Carries the execution metadata for a single pipeline run. The ``run_id`` is
unique per execution and deliberately non-deterministic (plan `01` §6.1),
while business results (``etl.keys``) remain deterministic — run metadata is
never part of a business result.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from etl.exceptions import EtlDryRunError


def _new_run_id() -> str:
    """UTC timestamp + short nonce, per plan `01` §6.1."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    return f"{ts}-{uuid.uuid4().hex[:8]}"


@dataclass
class RunContext:
    run_id: str
    pipeline_name: str
    pipeline_version: str
    started_at: datetime
    environment: str
    sources: Tuple[str, ...] = ()
    dry_run: bool = False
    current_stage: Optional[str] = None
    counters: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        pipeline_name: str = "kenexai_etl",
        pipeline_version: str = "1.0.0",
        environment: str = "development",
        sources: Tuple[str, ...] = (),
        dry_run: bool = False,
        run_id: Optional[str] = None,
        started_at: Optional[datetime] = None,
    ) -> "RunContext":
        return cls(
            run_id=run_id or _new_run_id(),
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            started_at=started_at or datetime.now(timezone.utc),
            environment=environment,
            sources=tuple(sources),
            dry_run=dry_run,
        )

    def assert_writable(self, detail: str = "Database writes are not permitted in dry-run mode") -> None:
        """Raise when a stage attempts to write during a dry run."""
        if self.dry_run:
            raise EtlDryRunError(detail)

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "pipeline_name": self.pipeline_name,
            "pipeline_version": self.pipeline_version,
            "started_at": self.started_at,
            "environment": self.environment,
            "sources": list(self.sources),
            "dry_run": self.dry_run,
            "current_stage": self.current_stage,
            "counters": dict(self.counters),
        }
