"""Data lineage foundation.

The shape future lineage records follow. In V1 there are no lineage database
tables (plan `03` §5.1 is planned DDL, not part of the 16-table schema) — this
is the in-memory metadata contract so run_id / source / source_record_id /
pipeline_version / stage / loaded_at flow through every stage and into a
future ledger unchanged.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

OP_INSERT = "insert"
OP_UPDATE = "update"
OP_NOOP = "noop"


@dataclass(frozen=True)
class LineageRecord:
    run_id: str
    source: str
    stage: str
    pipeline_version: str
    loaded_at: datetime
    entity_type: Optional[str] = None
    natural_key: Optional[Tuple[Any, ...]] = None
    source_record_id: Optional[str] = None
    op: str = OP_NOOP
    metadata: Any = None

    @classmethod
    def now(cls, **kwargs: Any) -> "LineageRecord":
        kwargs.setdefault("loaded_at", datetime.now(timezone.utc))
        return cls(**kwargs)
