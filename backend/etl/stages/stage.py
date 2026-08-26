"""Stage: place validated rows into an in-memory staging bucket.

Plan `01` §3.1 Stage. Read-only: never touches the database. Consumes the
validation outcomes produced by the Validate stage (shared in-memory state)
and publishes tagged, ordered staging records so downstream stages (Stitch,
Transform) can consume them without re-validation.

In V1 the staging bucket is purely in-memory — no staging tables, no disk
writes (§7.2). Each staged row carries its source identity, the current
``run_id``, and the original row data unchanged.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from etl.result import StageResult
from etl.stages import STAGE_STAGE, Stage
from etl.validation import ValidationOutcome


@dataclass(frozen=True)
class StagedRecord:
    """One validated row held in the staging bucket with run metadata.

    Attributes:
        source: The source key (e.g. ``daily_attendance``, ``weekly_timetable``).
        run_id: The pipeline run identifier this record belongs to.
        row_index: Original 1-based line number from the source file.
        row: The validated row data (dict), preserved unchanged.
    """

    source: str
    run_id: str
    row_index: int
    row: Dict[str, str]


class StageStage(Stage):
    """Hold validated rows in an in-memory staging bucket with run_id metadata.

    Reads from ``shared["validated"]`` (produced by Validate) and publishes
    into ``shared["staged"]``.  Deterministic ordering is preserved from the
    Validate stage output.
    """

    name = STAGE_STAGE
    description = "In-memory staging bucket with run_id tagging (plan 01 §3.1)."

    def __init__(
        self,
        sources: Optional[Sequence[str]] = None,
        shared: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._sources = tuple(sources) if sources is not None else ()
        self._shared = shared if shared is not None else {}

    async def run(self, context, pool=None) -> StageResult:
        validated: Dict[str, ValidationOutcome] = dict(
            self._shared.get("validated") or {}
        )
        if not validated:
            return StageResult(stage=self.name, rows_read=0, rows_accepted=0)

        sources_to_stage = (
            self._sources if self._sources else tuple(validated.keys())
        )

        staged: Dict[str, List[StagedRecord]] = {}
        rows_read = 0
        rows_accepted = 0

        for source_key in sources_to_stage:
            outcome = validated.get(source_key)
            if outcome is None:
                continue

            records: List[StagedRecord] = []
            for row_index, row in enumerate(outcome.accepted, start=1):
                records.append(
                    StagedRecord(
                        source=source_key,
                        run_id=context.run_id,
                        row_index=row_index,
                        row=row,
                    )
                )
            staged[source_key] = records
            rows_read += outcome.total
            rows_accepted += len(outcome.accepted)

        self._shared["staged"] = staged

        result = StageResult(
            stage=self.name,
            rows_read=rows_read,
            rows_accepted=rows_accepted,
            rows_rejected=0,
            rows_written=0,
        )
        result.metadata["source_keys"] = list(sources_to_stage)
        result.metadata["staged_counts"] = {
            key: len(records) for key, records in staged.items()
        }
        result.metadata["run_id"] = context.run_id
        return result
