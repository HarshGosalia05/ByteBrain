"""Reusable ETL stage contract.

Only the execution contract lives here. Stage business logic is implemented in
later slices; this package defines the interface every future stage must follow:

    input -> stage.run(context, pool) -> StageResult

The canonical stage names are declared so all future slices register under the
same contract (plan `01` §3.1: Extract, Validate, Stage, Stitch, Transform,
Load, Derive).

Implemented: Extract, Validate, Stage, Stitch, Transform, Load, Derive.
"""

from abc import ABC, abstractmethod
from typing import Optional

import asyncpg

from etl.result import StageResult

STAGE_EXTRACT = "extract"
STAGE_VALIDATE = "validate"
STAGE_STAGE = "stage"
STAGE_STITCH = "stitch"
STAGE_TRANSFORM = "transform"
STAGE_LOAD = "load"
STAGE_DERIVE = "derive"

STAGE_NAMES = (
    STAGE_EXTRACT,
    STAGE_VALIDATE,
    STAGE_STAGE,
    STAGE_STITCH,
    STAGE_TRANSFORM,
    STAGE_LOAD,
    STAGE_DERIVE,
)


class Stage(ABC):
    """Contract every ETL stage must implement."""

    name: str
    description: str = ""

    @abstractmethod
    async def run(
        self,
        context,
        pool: Optional[asyncpg.Pool] = None,
    ) -> StageResult:
        """Execute the stage against the run context and optional DB pool.

        ``pool`` is ``None`` during a dry run so a stage can never write to
        the database implicitly. Stages that would write must call
        ``context.assert_writable()`` and raise an ``EtlDryRunError`` if the
        run is in dry-run mode.
        """

    def __repr__(self) -> str:
        return f"<Stage {self.name}>"
