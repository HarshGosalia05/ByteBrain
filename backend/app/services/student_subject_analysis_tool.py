"""G2.3 Student Subject Analysis Tool.

Third REAL GenAI analytics tool: an adapter/orchestration layer over the
existing verified backend.

Composes:
  * ``StudentService.get_performance`` -> verified per-subject performance
    (``student_subject_performance``): semester-tagged marks, canonical
    percentage, grade, result status, attendance.
  * ``student_analytics_rules.classify_subject`` -> the approved strength-band
    classification (Strong >= 75 | Good 60-74.99 | Needs Attention 45-59.99 |
    Critical < 45). No competing classification is invented.

It does NOT:
  * generate natural language (that is G0 GenAIService's job),
  * call any LLM provider directly,
  * execute or build SQL itself,
  * accept a DB session / repository object from anywhere external.

Design notes:
  * Existing ``compute_strengths`` / ``compute_needs_attention`` rules were
    inspected but NOT reused because they aggregate the same subject_code
    across semesters; G2.3 must preserve per-semester context, so each record
    is classified individually with ``classify_subject``.
  * ``subject_filter`` is a data-selection operation INSIDE the already
    authorized student scope (matched by subject_code or subject_name). It is
    never used for authorization and never trusted as a DB identifier.

Security (self-scope):
  * Student-only. The authenticated ``student_id`` is the ONLY identity.
  * A caller-supplied ``target_student_id`` that differs is REJECTED (403),
    matching the existing ``authorize_prediction_access`` convention.

G1 integration:
  * ``TOOL_NAME`` / ``INTENT`` match the registered G1 tool definition
    ``student_subject_analysis_tool`` -> ``subject_analysis``.
  * G1 ToolRegistry remains data-only (no callable handlers by design); the
    executable implementation lives here under the same tool name.

G0 boundary:
  * ``to_verified_context`` produces a G0 ``VerifiedContext`` consumed by
    ``GenAIService``. The tool never bypasses G0.
"""
from __future__ import annotations

import difflib
import logging
import re
from collections import Counter
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.schemas.genai import VerifiedContext
from app.schemas.student_subject_analysis_tool import (
    StudentSubjectAnalysisResult,
    ToolSubjectRecord,
    ToolSubjectSignals,
    ToolSubjectSummary,
)
from app.services.student_analytics_rules import classify_subject
from app.services.student_service import StudentService

logger = logging.getLogger(__name__)

TOOL_NAME = "student_subject_analysis_tool"
INTENT = "subject_analysis"
SOURCE_LABEL = "students/student_subject_performance"

_CATEGORIES = ("Strong", "Good", "Needs Attention", "Critical")


def _fuzzy_single_word(record, query: str) -> ToolSubjectRecord | None:
    """Match a query to one significant token of a subject name (typo-safe).

    Exact token wins first; a near miss (ratio >= 0.8) is accepted only when
    there is exactly one plausible subject so we never guess on ambiguity.
    """
    name = record.subject_name
    if not name:
        return None
    tokens = re.findall(r"[A-Za-z]+", name)
    if not tokens:
        return None
    lowered = [token.lower() for token in tokens]
    if query in lowered:
        return record
    if max(difflib.SequenceMatcher(None, query, token).ratio() for token in lowered) >= 0.8:
        return record
    return None


class StudentSubjectAnalysisTool:
    """Verified subject-level performance for the authenticated student."""

    def __init__(self, pool) -> None:
        self._student_service = StudentService(pool)

    async def execute(
        self,
        *,
        student_id: str,
        target_student_id: str | None = None,
        subject_filter: str | None = None,
        semester: int | None = None,
    ) -> StudentSubjectAnalysisResult:
        """Return verified subject analysis, scoped to the authenticated student.

        ``student_id`` is ALWAYS the authenticated identity. Any differing
        ``target_student_id`` (client-supplied) is rejected before any data
        access. ``subject_filter`` only narrows the data selection inside the
        already-authorized student scope.
        """
        if not student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated student identity",
            )
        if target_student_id is not None and target_student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only access their own subject data",
            )

        response = await self._student_service.get_performance(student_id, semester)
        records = self._records(response.performance)
        data_available = bool(records)

        requested = (
            subject_filter.strip() if subject_filter and subject_filter.strip() else None
        )
        note: str | None = None
        requested_subject_found = True
        analyzed = records

        if not data_available:
            note = "No verified subject performance data available."
        elif requested is not None:
            matched = self._match(records, requested)
            if matched:
                analyzed = matched
            else:
                analyzed = []
                requested_subject_found = False
                note = (
                    "Requested subject not found in the student's verified "
                    "subject records."
                )

        summary = self._summary(analyzed) if analyzed else None
        signals = self._signals(analyzed)

        return StudentSubjectAnalysisResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            student_id=student_id,
            data_available=data_available,
            requested_subject=requested,
            requested_subject_found=requested_subject_found,
            summary=summary,
            semester_subjects=analyzed,
            subject_signals=signals,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=note,
        )

    @staticmethod
    def _records(items) -> list[ToolSubjectRecord]:
        """Map verified performance rows, classifying each with the approved rule."""
        records: list[ToolSubjectRecord] = []
        for item in items:
            classification = None
            if item.percentage is not None:
                classification = classify_subject(float(item.percentage))
            records.append(
                ToolSubjectRecord(
                    semester=item.semester,
                    academic_year=item.academic_year,
                    subject_id=item.subject_id,
                    subject_code=item.subject_code,
                    subject_name=item.subject_name,
                    credits=item.credits,
                    internal_marks=item.internal_marks,
                    mid_sem_marks=item.mid_sem_marks,
                    end_sem_marks=item.end_sem_marks,
                    total_marks=item.total_marks,
                    percentage=item.percentage,
                    grade=item.grade,
                    grade_point=item.grade_point,
                    result_status=item.result_status,
                    attempt_number=item.attempt_number,
                    classification=classification,
                    attendance_percentage=item.attendance_percentage,
                )
            )
        records.sort(key=lambda record: (record.semester, record.subject_name))
        return records

    @staticmethod
    def _match(
        records: list[ToolSubjectRecord], requested: str
    ) -> list[ToolSubjectRecord]:
        """Resolve a subject by code / name, tolerating typos and abbreviations.

        Never guesses on ambiguity: an abbreviation that matches more than one
        distinct subject resolves to ``[]`` (caller reports "not found") rather
        than a best-effort pick.
        """
        query = requested.strip().lower()
        if not query:
            return []

        by_code = [
            record
            for record in records
            if record.subject_code and record.subject_code.lower() == query
        ]
        if by_code:
            return by_code

        names = [
            record
            for record in records
            if record.subject_name and record.subject_name.lower() == query
        ]
        if names:
            return names

        substring = [
            record
            for record in records
            if record.subject_name and query in record.subject_name.lower()
        ]
        if substring:
            return substring

        # Abbreviation resolution ("DL" -> "Deep Learning"), only if unambiguous.
        abbr_matches: list[ToolSubjectRecord] = []
        for record in records:
            abbr = StudentSubjectAnalysisTool._abbrev(record.subject_name)
            if abbr and abbr == query:
                abbr_matches.append(record)
        if len(abbr_matches) == 1:
            return abbr_matches
        if len(abbr_matches) > 1:
            return []

        # Fuzzy match against the full name when query is reasonably close.
        close = [
            record
            for record in records
            if StudentSubjectAnalysisTool._fuzzy_close(record.subject_name, query)
        ]
        if close:
            return close

        # Space-agnostic concatenated-name fuzzy ("deeplearing" -> "deeplearning").
        concat_close = [
            record
            for record in records
            if StudentSubjectAnalysisTool._fuzzy_concat(record.subject_name, query)
        ]
        if len(concat_close) == 1:
            return concat_close

        # Single-word fuzzy match ("deeplearing" -> "deep learning").
        token_hits = [_fuzzy_single_word(record, query) for record in records]
        token_hits = [record for record in token_hits if record is not None]
        if len(token_hits) == 1:
            return token_hits
        return []

    @staticmethod
    def _abbrev(subject_name: str | None) -> str | None:
        if not subject_name:
            return None
        words = re.findall(r"[A-Za-z]+", subject_name)
        if not words:
            return None
        abbr = "".join(word[0] for word in words).lower()
        return abbr if len(abbr) > 1 else None

    @staticmethod
    def _fuzzy_close(subject_name: str | None, query: str) -> bool:
        if not subject_name:
            return False
        ratio = difflib.SequenceMatcher(
            None, subject_name.lower(), query
        ).ratio()
        return ratio >= 0.8

    @staticmethod
    def _fuzzy_concat(subject_name: str | None, query: str) -> bool:
        """Match a query against the subject name with spaces removed.

        Handles "deep learning" vs "deeplearing" / "deeplearning" by comparing
        concatenated forms (query stripped of spaces vs name stripped of spaces).
        """
        if not subject_name:
            return False
        name_concat = re.sub(r"\s+", "", subject_name.lower())
        query_concat = re.sub(r"\s+", "", query)
        if not name_concat or not query_concat:
            return False
        if query_concat in name_concat:
            return True
        return (
            difflib.SequenceMatcher(None, name_concat, query_concat).ratio() >= 0.85
        )

    @staticmethod
    def find_subject_names(records: list[ToolSubjectRecord]) -> list[str]:
        """Distinct verified subject names for gateway-level subject routing."""
        seen: list[str] = []
        for record in records:
            name = record.subject_name
            if name and name.lower() not in {n.lower() for n in seen}:
                seen.append(name)
        return seen

    async def discover_subject_records(
        self, *, student_id: str
    ) -> list[ToolSubjectRecord]:
        """Return the student's verified subject records (name + code) for routing."""
        response = await self._student_service.get_performance(student_id)
        return self._records(response.performance)

    @staticmethod
    def match_subject_query(
        message: str, records: list[ToolSubjectRecord]
    ) -> str | None:
        """Find a student subject (name/code/typo/unambiguous abbreviation) in ``message``.

        Returns the matched subject query string (to be used as ``subject_filter``)
        or ``None`` when no verified subject is clearly referenced.
        """
        msg = message.lower().strip()
        if not msg:
            return None

        for record in records:
            code = record.subject_code
            if code and code.lower() and code.lower() in msg:
                return code

        # Name matching: choose the MOST SPECIFIC (longest) subject name that is
        # a substring of the message. This prevents silently collapsing a more
        # specific subject ("Deep Learning Laboratory") into a prefix subject
        # ("Deep Learning") when both exist. Exact and strict substrings always
        # win over fuzzy/abbreviation resolution below.
        name_hits: set[str] = set()
        for record in records:
            name = record.subject_name
            if name and name.lower() and name.lower() in msg:
                name_hits.add(name)
        if name_hits:
            longest = max(name_hits, key=len)
            return longest

        words = re.findall(r"[A-Za-z]+", message)
        token_matches: set[str] = set()
        for token in words:
            lowered = token.lower()
            token_len = len(lowered)
            if token_len not in (2, 3):
                if token_len >= 4 and len(token_matches) < 2:
                    concat_hits = [
                        record.subject_name
                        for record in records
                        if StudentSubjectAnalysisTool._fuzzy_concat(
                            record.subject_name, lowered
                        )
                    ]
                    if len(concat_hits) == 1:
                        token_matches.add(concat_hits[0])
                continue
            abbr_hits = [
                record.subject_name
                for record in records
                if StudentSubjectAnalysisTool._abbrev(record.subject_name) == lowered
            ]
            if len(abbr_hits) == 1:
                token_matches.add(abbr_hits[0])
            elif len(abbr_hits) > 1:
                continue
            elif token_len >= 3:
                single = [
                    record.subject_name
                    for record in records
                    if _fuzzy_single_word(record, lowered) is not None
                ]
                if len(single) == 1:
                    token_matches.add(single[0])
        if len(token_matches) == 1:
            return next(iter(token_matches))
        return None

    @staticmethod
    def _summary(records: list[ToolSubjectRecord]) -> ToolSubjectSummary:
        counts = Counter(
            record.classification
            for record in records
            if record.classification in _CATEGORIES
        )
        valid = [record for record in records if record.percentage is not None]
        highest = (
            max(valid, key=lambda r: (float(r.percentage), r.subject_code))
            if valid
            else None
        )
        lowest = (
            min(valid, key=lambda r: (float(r.percentage), r.subject_code))
            if valid
            else None
        )
        average = (
            round(
                sum(float(r.percentage) for r in valid) / len(valid),
                2,
            )
            if valid
            else None
        )
        return ToolSubjectSummary(
            total_subjects=len(records),
            strong_subjects=counts.get("Strong", 0),
            good_subjects=counts.get("Good", 0),
            needs_attention_subjects=counts.get("Needs Attention", 0),
            critical_subjects=counts.get("Critical", 0),
            average_percentage=average,
            highest_percentage=highest.percentage if highest else None,
            highest_subject_code=highest.subject_code if highest else None,
            highest_subject_name=highest.subject_name if highest else None,
            lowest_percentage=lowest.percentage if lowest else None,
            lowest_subject_code=lowest.subject_code if lowest else None,
            lowest_subject_name=lowest.subject_name if lowest else None,
        )

    @staticmethod
    def _signals(records: list[ToolSubjectRecord]) -> ToolSubjectSignals:
        """Deterministic, data-traceable signals (no advice, no guesses)."""
        strong: list[str] = []
        attention: list[str] = []
        for record in records:
            if record.percentage is None or record.classification is None:
                continue
            label = record.subject_code
            if record.classification == "Strong":
                strong.append(
                    f"Strong in {label} (semester {record.semester}): "
                    f"{record.percentage:.2f}%"
                )
            elif record.classification == "Good":
                strong.append(
                    f"Good in {label} (semester {record.semester}): "
                    f"{record.percentage:.2f}%"
                )
            elif record.classification == "Needs Attention":
                attention.append(
                    f"Needs attention in {label} (semester {record.semester}): "
                    f"{record.percentage:.2f}%"
                )
            elif record.classification == "Critical":
                attention.append(
                    f"Critical in {label} (semester {record.semester}): "
                    f"{record.percentage:.2f}%"
                )
        valid = [record for record in records if record.percentage is not None]
        if valid:
            highest = max(valid, key=lambda r: (float(r.percentage), r.subject_code))
            lowest = min(valid, key=lambda r: (float(r.percentage), r.subject_code))
            strong.append(
                f"Highest subject: {highest.subject_code} "
                f"({highest.percentage:.2f}%) in semester {highest.semester}"
            )
            attention.append(
                f"Lowest subject: {lowest.subject_code} "
                f"({lowest.percentage:.2f}%) in semester {lowest.semester}"
            )
        return ToolSubjectSignals(strong_areas=strong, attention_areas=attention)

    def to_verified_context(
        self, result: StudentSubjectAnalysisResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext.

        ``data`` carries only JSON-serializable, verified values.
        """
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
        )
