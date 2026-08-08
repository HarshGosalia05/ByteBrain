"""Pipeline runner: executes registered ETL stages in order, fail-loud.

Supports normal execution and dry-run, per-stage timing, structured logging, a
final run summary, and meaningful exit codes (plan `01` §5.3). A stage failure
stops the pipeline immediately — nothing silently continues after a critical
failure (P1).
"""

from datetime import datetime, timezone
from time import monotonic
from typing import Callable, Iterable, List, Optional, Sequence

import etl.db as etl_db
from etl.config import EtlConfig, etl_config
from etl.context import RunContext
from etl.exceptions import (
    EXIT_SUCCESS,
    EtlError,
    EtlStageError,
    EtlUnexpectedError,
    to_exit_code,
)
from etl.logging import EtlLogger
from etl.result import RunSummary, StageResult
from etl.stages import Stage


class EtlRunner:
    def __init__(
        self,
        config: Optional[EtlConfig] = None,
        logger_factory: Optional[Callable[[str, str], EtlLogger]] = None,
    ) -> None:
        self.config = config or etl_config
        self._logger_factory = logger_factory
        self._stages: List[Stage] = []
        self._stage_names = set()

    def register(self, stage: Stage) -> "EtlRunner":
        """Register a stage; the runner executes stages in registration order."""
        if not isinstance(stage, Stage):
            raise TypeError(f"expected a Stage instance, got {type(stage).__name__}")
        if stage.name in self._stage_names:
            raise ValueError(f"a stage named '{stage.name}' is already registered")
        self._stage_names.add(stage.name)
        self._stages.append(stage)
        return self

    def register_many(self, stages: Iterable[Stage]) -> "EtlRunner":
        for stage in stages:
            self.register(stage)
        return self

    @property
    def stages(self) -> Sequence[str]:
        return tuple(stage.name for stage in self._stages)

    def _make_logger(self, run_id: str, log_level: Optional[str] = None) -> EtlLogger:
        level = log_level or self.config.ETL_LOG_LEVEL
        if self._logger_factory:
            return self._logger_factory(run_id, level)
        return EtlLogger(run_id, level)

    async def _invoke_stage(
        self,
        stage: Stage,
        context: RunContext,
        pool,
    ) -> StageResult:
        started = monotonic()
        try:
            result = await stage.run(context, pool=pool)
            result.duration = monotonic() - started
            return result
        except EtlError as exc:
            result = StageResult.failure(stage.name, exc)
            result.exit_code = to_exit_code(exc)
            result.duration = monotonic() - started
            return result
        except Exception as exc:  # noqa: BLE001 - unexpected failures must fail loud
            wrapped = EtlUnexpectedError(f"{stage.name} failed unexpectedly: {exc!r}")
            result = StageResult.failure(stage.name, wrapped)
            result.exit_code = to_exit_code(wrapped)
            result.duration = monotonic() - started
            return result

    async def run(
        self,
        *,
        sources: Sequence[str] = (),
        dry_run: bool = False,
        run_id: Optional[str] = None,
        pipeline_version: Optional[str] = None,
        environment: Optional[str] = None,
        log_level: Optional[str] = None,
    ) -> RunSummary:
        context = RunContext.create(
            pipeline_name=self.config.ETL_PIPELINE_NAME,
            pipeline_version=pipeline_version or self.config.ETL_PIPELINE_VERSION,
            environment=environment or self.config.ETL_ENVIRONMENT,
            sources=tuple(sources),
            dry_run=dry_run,
            run_id=run_id,
        )
        logger = self._make_logger(context.run_id, log_level)

        summary = RunSummary(
            run_id=context.run_id,
            pipeline_name=context.pipeline_name,
            pipeline_version=context.pipeline_version,
            environment=context.environment,
            started_at=context.started_at,
            dry_run=dry_run,
            exit_code=EXIT_SUCCESS,
        )

        logger.run_started(context)
        run_error: Optional[BaseException] = None
        pool = None
        try:
            if not dry_run:
                pool = await etl_db.create_pool()

            for stage in self._stages:
                context.current_stage = stage.name
                logger.stage_started(context)
                result = await self._invoke_stage(stage, context, pool)
                summary.stages.append(result)
                if result.failed:
                    summary.exit_code = result.exit_code or to_exit_code(EtlStageError())
                    logger.stage_failed(context, stage.name, result.errors)
                    run_error = EtlStageError(
                        f"pipeline failed at stage '{stage.name}': {result.errors}"
                    )
                    break
                logger.stage_completed(context, result)
        except EtlError as exc:
            run_error = exc
            summary.exit_code = to_exit_code(exc)
        except Exception as exc:  # noqa: BLE001 - fail loud on anything unexpected
            run_error = exc
            summary.exit_code = to_exit_code(EtlUnexpectedError(str(exc)))
        finally:
            if pool is not None:
                await pool.close()
            summary.finished_at = datetime.now(timezone.utc)

        if run_error is not None:
            logger.run_failed(context, run_error)
        else:
            logger.run_completed(context, summary)
        return summary
