"""Extract stage: read raw CSV sources into validated-ready artifacts.

Plan `01` §3.1 Extract. Read-only: never touches the database, so it neither
creates a pool nor asserts writability. Extracted sources are published into a
shared in-memory state dict so the Validate stage (the next registered stage)
can consume them without re-reading the files.
"""

from typing import Any, Dict, Optional, Sequence

from etl.config import EtlConfig, etl_config
from etl.result import StageResult
from etl.sources import CsvSource, DATASET_SOURCES, extract_csv
from etl.stages import STAGE_EXTRACT, Stage


class ExtractStage(Stage):
    """Extract the locked V1 CSV sources with source identity preserved."""

    name = STAGE_EXTRACT
    description = "Read raw CSV sources with source identity preserved (plan 01 §3.1)."

    def __init__(
        self,
        sources: Optional[Sequence[str]] = None,
        shared: Optional[Dict[str, Any]] = None,
        datasets_dir: Optional[Any] = None,
        config: Optional[EtlConfig] = None,
    ) -> None:
        self._sources = tuple(sources) if sources is not None else tuple(DATASET_SOURCES)
        self._shared = shared if shared is not None else {}
        self._datasets_dir = datasets_dir
        self._config = config or etl_config

    async def run(self, context, pool=None) -> StageResult:
        extracted: Dict[str, CsvSource] = {}
        total = 0
        for key in self._sources:
            source = extract_csv(key, datasets_dir=self._datasets_dir, config=self._config)
            extracted[key] = source
            total += source.row_count
        self._shared["sources"] = extracted

        result = StageResult(stage=self.name, rows_read=total, rows_accepted=total)
        result.metadata["sources"] = {key: src.to_metadata() for key, src in extracted.items()}
        result.metadata["source_keys"] = list(self._sources)
        return result
