"""Extract: read raw CSV source rows with their source identity preserved.

Plan `01` §3.1: Extract pulls raw source bytes/rows with source identity
preserved and no transformation. Plan `01` §4.2: V1 needs only the Python
standard library (``csv``) + ``asyncpg`` — no pandas.

A missing, unreadable, empty, or structurally malformed source fails loud with
``EtlSourceError`` (exit 1, plan `01` §6.2) rather than silently producing an
empty extraction. Raw values are preserved as strings; the SHA-256 checksum and
extraction timestamp are the source-fingerprint metadata the lineage ledger
uses (plan `03` §5.1).
"""

import csv
import hashlib
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from etl.config import EtlConfig, etl_config
from etl.exceptions import EtlConfigurationError, EtlSourceError

DATASET_SOURCES: Dict[str, str] = {
    "daily_attendance": "daily_attendance_cse_sem7.csv",
    "weekly_timetable": "weekly_timetable_cse_sem7.csv",
}


@dataclass
class CsvSource:
    """A raw extracted source: rows + source identity metadata."""

    key: str
    filename: str
    path: Path
    checksum_sha256: str
    row_count: int
    columns: Tuple[str, ...]
    rows: List[Dict[str, str]]
    line_numbers: Tuple[int, ...]
    extracted_at: datetime

    def to_metadata(self) -> Dict[str, object]:
        return {
            "source": self.key,
            "filename": self.filename,
            "path": str(self.path),
            "checksum_sha256": self.checksum_sha256,
            "row_count": self.row_count,
            "columns": list(self.columns),
            "extracted_at": self.extracted_at.isoformat(),
        }


def extract_csv(
    source_key: str,
    *,
    path: Optional[Path] = None,
    datasets_dir: Optional[Path] = None,
    extracted_at: Optional[datetime] = None,
    config: Optional[EtlConfig] = None,
) -> CsvSource:
    """Read one configured CSV source into a ``CsvSource``.

    Deterministic record set: rows keep file order and raw string values. The
    only non-deterministic fields are ``extracted_at`` and the path — run
    metadata, never part of a business result (plan `01` §P2).
    """
    cfg = config or etl_config
    if source_key not in DATASET_SOURCES:
        raise EtlConfigurationError(f"unknown source '{source_key}'")
    filename = DATASET_SOURCES[source_key]
    directory = Path(datasets_dir) if datasets_dir is not None else cfg.datasets_dir
    file_path = Path(path) if path is not None else directory / filename

    if not file_path.exists():
        raise EtlSourceError(f"source '{source_key}' missing: {file_path}")
    if not file_path.is_file():
        raise EtlSourceError(f"source '{source_key}' is not a file: {file_path}")

    try:
        raw = file_path.read_bytes()
    except OSError as exc:
        raise EtlSourceError(
            f"source '{source_key}' unreadable: {file_path}: {exc}"
        ) from exc
    checksum = hashlib.sha256(raw).hexdigest()

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise EtlSourceError(
            f"source '{source_key}' is not valid UTF-8: {exc}"
        ) from exc

    try:
        raw_rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise EtlSourceError(
            f"source '{source_key}' is malformed CSV: {exc}"
        ) from exc

    if not raw_rows:
        raise EtlSourceError(f"source '{source_key}' is empty: {file_path}")

    header = [column.strip() for column in raw_rows[0]]
    if not header or any(not column for column in header):
        raise EtlSourceError(f"source '{source_key}' has no usable header: {file_path}")

    rows: List[Dict[str, str]] = []
    line_numbers: List[int] = []
    for index, values in enumerate(raw_rows[1:], start=2):
        if not values or all(value == "" for value in values):
            continue
        if len(values) != len(header):
            raise EtlSourceError(
                f"source '{source_key}' malformed at line {index}: "
                f"expected {len(header)} fields, found {len(values)}"
            )
        rows.append(dict(zip(header, values)))
        line_numbers.append(index)

    if not rows:
        raise EtlSourceError(f"source '{source_key}' has no data rows: {file_path}")

    return CsvSource(
        key=source_key,
        filename=file_path.name,
        path=file_path,
        checksum_sha256=checksum,
        row_count=len(rows),
        columns=tuple(header),
        rows=rows,
        line_numbers=tuple(line_numbers),
        extracted_at=extracted_at or datetime.now(timezone.utc),
    )
