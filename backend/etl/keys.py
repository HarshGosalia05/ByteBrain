"""Idempotency foundation: deterministic business keys.

The locked attendance keys (plan `02` §2.1, §4.3):

- Lecture session key       = ``(subject_id, lecture_date, lecture_number)``
  used for duplicate-lecture detection and the ``total_classes`` derive. It is
  *not* the unique key for individual student attendance rows.
- Individual attendance-row key = ``(student_id, subject_id, lecture_date,
  lecture_number)`` used as the natural key for idempotent row loads and
  corrections.

These helpers are the architectural hooks future Load/Derive stages use for
deterministic keys, upsert scoping, and duplicate detection. They are pure
functions of their input — never of run metadata (P2).
"""

from typing import Any, Dict, List, Sequence, Tuple

LECTURE_SESSION_KEY_FIELDS = ("subject_id", "lecture_date", "lecture_number")
ATTENDANCE_ROW_KEY_FIELDS = ("student_id", "subject_id", "lecture_date", "lecture_number")


def business_key(record: Dict[str, Any], fields: Sequence[str]) -> Tuple[Any, ...]:
    """Build a deterministic, hashable business key from a record."""
    missing = [field for field in fields if record.get(field) is None]
    if missing:
        raise ValueError(f"cannot build business key, missing fields: {missing}")
    return tuple(record[field] for field in fields)


def business_key_str(record: Dict[str, Any], fields: Sequence[str]) -> str:
    """Render a business key as a stable, comparable string."""
    return "|".join(repr(part) for part in business_key(record, fields))


def dedupe_by_key(
    rows: Sequence[Dict[str, Any]],
    fields: Sequence[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Partition rows into first-seen unique rows and later duplicates.

    Deterministic on ``fields``; duplicate detection relies on the caller
    passing a canonical ordering if a specific winner is required.
    """
    seen = set()
    unique: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []
    for row in rows:
        key = business_key(row, fields)
        if key in seen:
            duplicates.append(row)
        else:
            seen.add(key)
            unique.append(row)
    return unique, duplicates
