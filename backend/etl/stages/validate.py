"""Validate stage: schema / integrity / domain / uniqueness checks + quarantine.

Plan `01` §3.1 Validate and plan `03` §3.3. Consumes the sources extracted by
the Extract stage (shared in-memory state); when run standalone (``--stage
validate``) it extracts the requested sources itself. Enforces the
``ETL_MAX_QUARANTINE_RATIO`` gate per source and fails loud (exit 1) when it is
exceeded. Read-only — never touches the database.
"""

from typing import Any, Dict, Optional, Sequence

from etl.config import EtlConfig, etl_config
from etl.exceptions import EtlValidationError
from etl.result import StageResult
from etl.sources import CsvSource, DATASET_SOURCES, extract_csv
from etl.stages import STAGE_VALIDATE, Stage
from etl.validation import (
    Scope,
    TimetableReference,
    assert_within_quarantine_ratio,
    validate_attendance,
    validate_timetable,
)


class ValidateStage(Stage):
    """Validate the extracted sources and quarantine failures."""

    name = STAGE_VALIDATE
    description = "Schema/integrity/domain/uniqueness validation with quarantine (plan 03 §3.3)."

    def __init__(
        self,
        sources: Optional[Sequence[str]] = None,
        shared: Optional[Dict[str, Any]] = None,
        datasets_dir: Optional[Any] = None,
        max_quarantine_ratio: Optional[float] = None,
        config: Optional[EtlConfig] = None,
    ) -> None:
        self._sources = tuple(sources) if sources is not None else tuple(DATASET_SOURCES)
        self._shared = shared if shared is not None else {}
        self._datasets_dir = datasets_dir
        self._config = config or etl_config
        self._max_ratio = (
            max_quarantine_ratio
            if max_quarantine_ratio is not None
            else float(self._config.ETL_MAX_QUARANTINE_RATIO)
        )

    async def run(self, context, pool=None) -> StageResult:
        extracted: Dict[str, CsvSource] = dict(self._shared.get("sources") or {})
        for key in self._sources:
            if key not in extracted:
                extracted[key] = extract_csv(key, datasets_dir=self._datasets_dir, config=self._config)

        scope = Scope.from_config(self._config)
        timetable_ref: Optional[TimetableReference] = None
        timetable_source = extracted.get("weekly_timetable")
        if timetable_source is not None:
            timetable_ref = TimetableReference.from_rows(timetable_source.rows)

        outcomes: Dict[str, Any] = {}
        warnings: Dict[str, list] = {}
        rows_read = 0
        rows_rejected = 0

        for key in self._sources:
            source = extracted[key]
            if key == "weekly_timetable":
                outcome = validate_timetable(
                    source.rows,
                    line_numbers=source.line_numbers,
                    run_id=context.run_id,
                    scope=scope,
                    stage=self.name,
                )
            else:
                outcome = validate_attendance(
                    source.rows,
                    line_numbers=source.line_numbers,
                    run_id=context.run_id,
                    scope=scope,
                    stage=self.name,
                    timetable_ref=timetable_ref,
                )
            outcomes[key] = outcome
            warnings[key] = list(outcome.warnings)
            if timetable_ref is None and key != "weekly_timetable":
                warnings[key].insert(
                    0,
                    "weekly_timetable reference not available; cross-dataset "
                    "timetable/subject checks skipped for this source",
                )
            rows_read += outcome.total
            rows_rejected += len(outcome.quarantined)
            assert_within_quarantine_ratio(outcome.quarantine_ratio, self._max_ratio, key)

        if timetable_ref is not None and "daily_attendance" in outcomes:
            attendance_rows = outcomes["daily_attendance"].accepted
            att_subjects = {row["subject_id"] for row in attendance_rows}
            att_faculties = {row["faculty_id"] for row in attendance_rows}
            unused_subjects = sorted(timetable_ref.subjects - att_subjects)
            if unused_subjects:
                warnings["weekly_timetable"].append(
                    f"reference: subject(s) {', '.join(unused_subjects)} in the timetable "
                    "have no attendance rows"
                )
            unused_faculties = sorted(timetable_ref.faculties - att_faculties)
            if unused_faculties:
                warnings["weekly_timetable"].append(
                    f"reference: faculty id(s) {', '.join(unused_faculties)} in the timetable "
                    "teach no attendance rows"
                )

        result = StageResult(
            stage=self.name,
            rows_read=rows_read,
            rows_accepted=rows_read - rows_rejected,
            rows_rejected=rows_rejected,
        )
        result.metadata["quarantine"] = {
            key: [record.to_dict() for record in outcome.quarantined]
            for key, outcome in outcomes.items()
        }
        result.metadata["rule_counts"] = {key: outcome.rule_counts for key, outcome in outcomes.items()}
        result.metadata["quarantine_ratio"] = {
            key: outcome.quarantine_ratio for key, outcome in outcomes.items()
        }
        result.metadata["warnings"] = warnings
        return result
