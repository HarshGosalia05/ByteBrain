"""V1 Independent M3 Ground-Truth Label Builder / Audit (READ-ONLY).

Builds a trustworthy source of ``is_at_risk_next_sem`` labels for M3 from
**actual academic outcomes** in ``student_semester_summary`` only.  It is
strictly independent of ``prediction_feedback`` (human/model verdicts on a
prediction) — the labels here are the ground-truth academic reality that M3 is
trying to predict.

Reuses the project's documented M3 target semantics (V1Config /
V1Dataset):
    is_at_risk_next_sem(row @ semester T) =
        (semester_result(T+1) IN ('FAIL','ATKT')) OR (backlog_count(T+1) > 0)

label source_type = ``academic`` so it can never be confused with
``prediction_feedback`` verdicts.

Grain: one row = one student at one completed semester.
Temporal: features from semester T label risk in semester T+1 (only
information that becomes known AFTER the prediction point is used in the
label).  A student's last available semester has no observable future outcome
→ unlabeled (deployment) row, piped through as ``label=None``.

READ-ONLY: never writes to any table, never trains, never persists a model,
never generates predictions, never alters schema or ETL.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .v1_config import V1Config
from .v1_dataset import V1Dataset

logger = logging.getLogger(__name__)

AT_RISK_RESULTS = frozenset({"FAIL", "ATKT"})
LABEL_SOURCE = "academic"
LENGTH_UNIT = "semester"
FUTURE = "+1"


# ---------------------------------------------------------------------------
# Outcome normalization
# ---------------------------------------------------------------------------

def _normalize_result(value: Any) -> Optional[str]:
    """Normalize a semester_result cell; None/'nan'/empty -> None."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.lower() == "nan" or s == "None":
        return None
    return s.upper()


def _normalize_backlogs(value: Any) -> Optional[float]:
    """Normalize a backlog_count cell; missing -> None."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _at_risk_from(row_values) -> Optional[int]:
    """Compute at-risk from a dict/Series with semester_result, backlog_count.

    Returns 0/1, or None when the outcome cannot be determined.
    """
    result = _normalize_result(row_values.get("semester_result"))
    backlogs = _normalize_backlogs(row_values.get("backlog_count"))
    if result is None and backlogs is None:
        return None
    at_risk = (result in AT_RISK_RESULTS) or (backlogs is not None and backlogs > 0)
    return int(at_risk)


# ---------------------------------------------------------------------------
# Label builder
# ---------------------------------------------------------------------------

@dataclass
class OutcomeConflict:
    """A duplicate (student, semester) outcome row (possibly conflicting)."""
    student_id: str
    semester_no: int
    entries: List[Dict[str, Any]]


@dataclass
class LabelAuditReport:
    """Deterministic label-quality report of independently built labels."""
    feature_rows: int
    labeled_rows: int
    unlabeled_rows: int
    positive_rows: int
    negative_rows: int
    unique_students_total: int
    unique_positive: int
    unique_negative: int
    unique_unlabeled: int
    duplicate_grain_cases: int
    conflicting_outcome_cases: int
    ambiguous_outcome_rows: int
    label_source: str
    conflicts: List[OutcomeConflict] = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        return {
            "label_source": self.label_source,
            "feature_rows": self.feature_rows,
            "labeled_rows": self.labeled_rows,
            "positive_rows": self.positive_rows,
            "negative_rows": self.negative_rows,
            "unlabeled_rows": self.unlabeled_rows,
            "unique_students_total": self.unique_students_total,
            "unique_positive": self.unique_positive,
            "unique_negative": self.unique_negative,
            "unique_unlabeled": self.unique_unlabeled,
            "duplicate_grain_cases": self.duplicate_grain_cases,
            "conflicting_outcome_cases": self.conflicting_outcome_cases,
            "ambiguous_outcome_rows": self.ambiguous_outcome_rows,
        }


def build_academic_labels(
    outcome_df: pd.DataFrame,
    *,
    student_id_col: str = "student_id",
    semester_col: str = "semester_no",
) -> pd.DataFrame:
    """Build deterministic independent M3 labels from raw academic outcomes.

    Parameters
    ----------
    outcome_df : DataFrame with
        student_id, semester_no, semester_result, backlog_count.
        One row per (student, semester).  Must not already contain the target.

    Returns
    -------
    DataFrame with one row per (student, semester) feature snapshot:
        student_id, semester_no, semester_result (T), backlog_count (T),
        label (int 0/1 or None when no future outcome / ambiguous),
        target_semester (T+1 or None), label_source='academic',
        at_risk_result_at_T1, at_risk_backlogs_at_T1,
        duplicate (bool), conflicting (bool), ambiguous (bool).
    """
    df = outcome_df.copy()

    required = {student_id_col, semester_col, "semester_result", "backlog_count"}
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required outcome columns: {missing}")

    # Normalize id/semester
    df[student_id_col] = df[student_id_col].astype(str)
    df[semester_col] = pd.to_numeric(df[semester_col], errors="coerce")

    # Detect duplicate (student, semester) grain BEFORE shift so we can label
    # conflicts / ambiguities deterministically.
    dup_mask = df.duplicated(subset=[student_id_col, semester_col], keep=False)
    df["duplicate"] = dup_mask

    conflicts: List[OutcomeConflict] = []
    duplicate_grain_count = 0
    for (sid, sem), g in df.groupby([student_id_col, semester_col]):
        if len(g) > 1:
            duplicate_grain_count += 1
            at_risk_values = []
            entries = []
            for _, row in g.iterrows():
                entries.append(
                    {
                        "semester_result": _normalize_result(row.get("semester_result")),
                        "backlog_count": _normalize_backlogs(row.get("backlog_count")),
                    }
                )
                at_risk_values.append(_at_risk_from(row))
            # conflicting if the resulting at-risk interpretations differ
            non_none = [v for v in at_risk_values if v is not None]
            is_conflict = len(set(non_none)) > 1 if non_none else False
            if is_conflict:
                conflicts.append(
                    OutcomeConflict(student_id=sid, semester_no=int(sem), entries=entries)
                )
    # flag conflicting / ambiguous rows (only genuine conflicts are unlabeled)
    conflict_keys = {(c.student_id, c.semester_no) for c in conflicts}
    df["conflicting"] = df.apply(
        lambda r: (r[student_id_col], int(r[semester_col])) in conflict_keys
        if pd.notna(r[semester_col])
        else False,
        axis=1,
    )
    df["duplicate_grain_count"] = duplicate_grain_count

    df = df.sort_values([student_id_col, semester_col]).reset_index(drop=True)

    # Shift future outcomes within each student
    df["semester_result_next"] = df.groupby(student_id_col)["semester_result"].shift(-1)
    df["backlog_count_next"] = df.groupby(student_id_col)["backlog_count"].shift(-1)
    df["target_semester"] = df.groupby(student_id_col)[semester_col].shift(-1)

    # Future outcome of the NEXT semester = the label's ground truth
    next_vals = df.apply(
        lambda r: _at_risk_from(
            {"semester_result": r.get("semester_result_next"),
             "backlog_count": r.get("backlog_count_next")}
        ),
        axis=1,
    )
    df["label"] = next_vals

    # no observable future semester for this row -> unlabeled (deployment)
    df.loc[df["target_semester"].isna(), "label"] = None

    # conflicting duplicate outcome -> ambiguous (no trustworthy label)
    df["ambiguous"] = df["conflicting"]
    df.loc[df["conflicting"], "label"] = None

    df["label_source"] = LABEL_SOURCE
    df["at_risk_result_at_T1"] = df.apply(
        lambda r: int(
            _normalize_result(r.get("semester_result_next")) in AT_RISK_RESULTS
        )
        if pd.notna(r.get("semester_result_next")) else np.nan,
        axis=1,
    )
    df["at_risk_backlogs_at_T1"] = df.apply(
        lambda r: (
            1 if (_normalize_backlogs(r.get("backlog_count_next")) or 0) > 0 else 0
        )
        if _normalize_backlogs(r.get("backlog_count_next")) is not None else np.nan,
        axis=1,
    )

    # drop intermediate next columns except those we keep for traceability
    keep = [
        student_id_col,
        semester_col,
        "semester_result",
        "backlog_count",
        "label",
        "target_semester",
        "label_source",
        "duplicate",
        "conflicting",
        "ambiguous",
        "at_risk_result_at_T1",
        "at_risk_backlogs_at_T1",
    ]
    out = df[[c for c in keep if c in df.columns]]
    out.attrs["conflicts"] = conflicts
    out.attrs["duplicate_grain_count"] = duplicate_grain_count
    return out


def audit_labels(label_df: pd.DataFrame) -> LabelAuditReport:
    """Summarize the built label table (deterministic)."""
    labeled = label_df[label_df["label"].notna()]
    positive = labeled[labeled["label"] == 1]
    negative = labeled[labeled["label"] == 0]
    unlabeled = label_df[label_df["label"].isna()]
    pos_students = set(positive["student_id"])
    neg_students = set(negative["student_id"])

    conflicts = list(label_df.attrs.get("conflicts", []))
    duplicate_grain_count = int(label_df.attrs.get("duplicate_grain_count", 0))
    n_conflict_cases = len(conflicts) or int(label_df["conflicting"].fillna(False).sum())
    n_dup_cases = duplicate_grain_count
    n_ambiguous = int(label_df["ambiguous"].fillna(False).sum())

    return LabelAuditReport(
        feature_rows=len(label_df),
        labeled_rows=len(labeled),
        unlabeled_rows=len(unlabeled),
        positive_rows=int(len(positive)),
        negative_rows=int(len(negative)),
        unique_students_total=label_df["student_id"].nunique(),
        unique_positive=len(pos_students),
        unique_negative=len(neg_students),
        unique_unlabeled=len(set(unlabeled["student_id"])),
        duplicate_grain_cases=n_dup_cases,
        conflicting_outcome_cases=n_conflict_cases,
        ambiguous_outcome_rows=n_ambiguous,
        label_source=LABEL_SOURCE,
    )


def render_label_report(report: LabelAuditReport) -> str:
    """Render a concise human-readable quality report."""
    s = report.summary()
    return "\n".join(
        [
            "==============================================================",
            "V1 INDEPENDENT M3 GROUND-TRUTH LABEL REPORT",
            "==============================================================",
            f"  Label source:                        {report.label_source}",
            f"  Feature rows:                        {report.feature_rows}",
            f"  Labeled rows:                        {report.labeled_rows}",
            f"    Positive rows:                     {report.positive_rows}",
            f"    Negative rows:                     {report.negative_rows}",
            f"  Unlabeled rows (no future outcome):  {report.unlabeled_rows}",
            f"  Unique students (total):             {report.unique_students_total}",
            f"  Unique POSITIVE students:            {report.unique_positive}",
            f"  Unique NEGATIVE students:            {report.unique_negative}",
            f"  Unique unlabeled-only students:      {report.unique_unlabeled}",
            "",
            "--- Quality ---",
            f"  Duplicate (student, semester) cases: {report.duplicate_grain_cases}",
            f"  Conflicting outcome cases:           {report.conflicting_outcome_cases}",
            f"  Ambiguous (unlabeled) rows:          {report.ambiguous_outcome_rows}",
            "",
            "Note: labels are INDEPENDENT ACADEMIC OUTCOMES, never "
            "prediction_feedback verdicts.",
        ]
    )
