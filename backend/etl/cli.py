"""ETL command-line interface.

Run from the ``backend/`` directory (the repo convention used by
``uvicorn app.main:app``):

    python -m etl --help
    python -m etl stages
    python -m etl run --dry-run
    python -m etl run --apply --sources daily_attendance,weekly_timetable
    python -m etl run --dry-run --stage validate

``--dry-run`` is the default mode and never touches the database; ``--apply``
is the only mode that may write (plan `01` §5.3). No scheduling, workers, or
API endpoints exist in V1.

Implemented stages: Extract + Validate + Stage + Stitch. Downstream stages
(Transform/Load/Derive) are later slices; requesting one fails
 cleanly rather than faking success.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from etl.exceptions import EXIT_LOAD_DERIVE_FAILURE, EXIT_SUCCESS
from etl.runner import EtlRunner
from etl.sources import DATASET_SOURCES
from etl.stages import STAGE_DERIVE, STAGE_EXTRACT, STAGE_LOAD, STAGE_NAMES, STAGE_STAGE, STAGE_STITCH, STAGE_TRANSFORM, STAGE_VALIDATE
from etl.stages.derive import DeriveStage
from etl.stages.extract import ExtractStage
from etl.stages.load import LoadStage
from etl.stages.stage import StageStage
from etl.stages.stitch import StitchStage
from etl.stages.transform import TransformStage
from etl.stages.validate import ValidateStage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m etl",
        description="CampusX KDAC-3 reusable ETL pipeline (implemented: extract, validate, stage, stitch, transform, load, derive).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the ETL pipeline (implemented: extract, validate, stage, stitch, transform, load, derive).")
    run.add_argument(
        "--sources",
        default="",
        help="Comma-separated source keys to scope the run (e.g. daily_attendance,weekly_timetable).",
    )
    mode = run.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute without any database writes (default).",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Execute against the database; the only mode that may write.",
    )
    run.add_argument("--run-id", default=None, help="Explicit run_id (otherwise generated per run).")
    run.add_argument("--pipeline-version", default=None, help="Override the pipeline version.")
    run.add_argument("--environment", default=None, help="Override the environment label.")
    run.add_argument("--log-level", default=None, help="Logging level (DEBUG/INFO/WARNING/ERROR).")
    run.add_argument(
        "--stage",
        default=None,
        choices=STAGE_NAMES,
        help="Run a single named stage (implemented: extract, validate, stage, stitch, transform, load, derive).",
    )
    run.add_argument(
        "--json",
        action="store_true",
        help="Also print the run summary as JSON (run manifest shape).",
    )

    stages = sub.add_parser("stages", help="List the canonical ETL stage contract.")
    stages.add_argument("--json", action="store_true", help="Print as JSON.")

    load1200 = sub.add_parser(
        "load_1200",
        help="CSE 6A 1,200-cohort ordered data-load runner (dry-run default; zero DB writes).",
    )
    mode = load1200.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Plan + verify; zero DB writes (default).",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Execute the ordered inserts (per-step transactions).",
    )
    mode.add_argument(
        "--reconcile",
        action="store_true",
        help="Re-run the read-only post-load reconciliation against live (needs a prior --apply).",
    )
    load1200.add_argument("--datasets", type=Path, default=None,
                          help="Path to the New_1200_data_scale directory.")
    load1200.add_argument("--preflight", type=Path, default=None,
                          help="Path to preflight_1200_live.json.")
    load1200.add_argument("--baseline", type=Path, default=None,
                          help="Path to phase2_ddl_apply_live.json.")
    load1200.add_argument("--out", type=Path, default=None,
                          help="Report output path (default plan_1200_6a/phase5_load_*.json).")
    return parser


def _run_command(args: argparse.Namespace) -> int:
    dry_run = not args.apply
    sources = tuple(s for s in args.sources.split(",") if s.strip())
    if not sources:
        sources = tuple(DATASET_SOURCES)
    shared: dict = {}

    runner = EtlRunner()
    if args.stage is not None:
        if args.stage == STAGE_EXTRACT:
            runner.register(ExtractStage(sources=sources, shared=shared))
        elif args.stage == STAGE_VALIDATE:
            runner.register(ValidateStage(sources=sources, shared=shared))
        elif args.stage == STAGE_STAGE:
            runner.register(ExtractStage(sources=sources, shared=shared))
            runner.register(ValidateStage(sources=sources, shared=shared))
            runner.register(StageStage(sources=sources, shared=shared))
        elif args.stage == STAGE_STITCH:
            runner.register(ExtractStage(sources=sources, shared=shared))
            runner.register(ValidateStage(sources=sources, shared=shared))
            runner.register(StageStage(sources=sources, shared=shared))
            runner.register(StitchStage(sources=sources, shared=shared))
        elif args.stage == STAGE_TRANSFORM:
            runner.register(ExtractStage(sources=sources, shared=shared))
            runner.register(ValidateStage(sources=sources, shared=shared))
            runner.register(StageStage(sources=sources, shared=shared))
            runner.register(StitchStage(sources=sources, shared=shared))
            runner.register(TransformStage(sources=sources, shared=shared))
        elif args.stage == STAGE_LOAD:
            runner.register(ExtractStage(sources=sources, shared=shared))
            runner.register(ValidateStage(sources=sources, shared=shared))
            runner.register(StageStage(sources=sources, shared=shared))
            runner.register(StitchStage(sources=sources, shared=shared))
            runner.register(TransformStage(sources=sources, shared=shared))
            runner.register(LoadStage(sources=sources, shared=shared))
        elif args.stage == STAGE_DERIVE:
            runner.register(ExtractStage(sources=sources, shared=shared))
            runner.register(ValidateStage(sources=sources, shared=shared))
            runner.register(StageStage(sources=sources, shared=shared))
            runner.register(StitchStage(sources=sources, shared=shared))
            runner.register(TransformStage(sources=sources, shared=shared))
            runner.register(LoadStage(sources=sources, shared=shared))
            runner.register(DeriveStage(sources=sources, shared=shared))
        else:
            print(
                f"error: stage '{args.stage}' is part of the canonical contract but is not "
                "implemented in this slice",
                file=sys.stderr,
            )
            return EXIT_LOAD_DERIVE_FAILURE
    else:
        runner.register(ExtractStage(sources=sources, shared=shared))
        runner.register(ValidateStage(sources=sources, shared=shared))
        runner.register(StageStage(sources=sources, shared=shared))
        runner.register(StitchStage(sources=sources, shared=shared))
        runner.register(TransformStage(sources=sources, shared=shared))
        runner.register(LoadStage(sources=sources, shared=shared))
        runner.register(DeriveStage(sources=sources, shared=shared))

    summary = asyncio.run(
        runner.run(
            sources=sources,
            dry_run=dry_run,
            run_id=args.run_id,
            pipeline_version=args.pipeline_version,
            environment=args.environment,
            log_level=args.log_level,
        )
    )

    print(f"run_id={summary.run_id}")
    print(
        f"pipeline={summary.pipeline_name} v{summary.pipeline_version} "
        f"environment={summary.environment}"
    )
    print(f"mode={'dry-run' if summary.dry_run else 'apply'}")
    print(f"stages_run={len(summary.stages)} exit_code={summary.exit_code}")
    for result in summary.stages:
        print(
            f"  - {result.stage}: status={result.status} "
            f"rows_read={result.rows_read} accepted={result.rows_accepted} "
            f"rejected={result.rows_rejected} written={result.rows_written} "
            f"duration={result.duration:.3f}s"
        )
    if args.json:
        print(json.dumps(summary.to_dict(), default=str, indent=2))
    return summary.exit_code


def _stages_command(args: argparse.Namespace) -> int:
    if args.json:
        print(json.dumps(list(STAGE_NAMES)))
    else:
        for name in STAGE_NAMES:
            print(name)
    return EXIT_SUCCESS


def _load_1200_command(args: argparse.Namespace) -> int:
    from etl import load_1200

    return load_1200.main(argv=load_1200_cli_args(args))


def load_1200_cli_args(args: argparse.Namespace) -> List[str]:
    argv: List[str] = []
    if args.apply:
        argv.append("--apply")
    elif args.reconcile:
        argv.append("--reconcile")
    if args.datasets is not None:
        argv += ["--datasets", str(args.datasets)]
    if args.preflight is not None:
        argv += ["--preflight", str(args.preflight)]
    if args.baseline is not None:
        argv += ["--baseline", str(args.baseline)]
    if args.out is not None:
        argv += ["--out", str(args.out)]
    return argv


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "stages":
        return _stages_command(args)
    if args.command == "load_1200":
        return _load_1200_command(args)
    return _run_command(args)


def cli() -> None:
    sys.exit(main())


if __name__ == "__main__":
    sys.exit(main())
