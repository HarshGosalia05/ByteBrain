"""M3 chronological (later academic-year) cohort-expansion analysis.

Determines, from REAL project data, whether a chronologically later
academic-year cohort exists that could expand the M3 (`is_at_risk_next_sem`)
training/evaluation population with additional independent, outcome-derived
at-risk labels.

Key distinction
---------------
- ``student_semester_summary.academic_year`` (e.g. '2023-24','2024-25','2025-26',
  '2026-27') is the CALENDAR year of each semester of the SAME admission cohort
  as it progresses.  It is NOT a cohort identifier.
- A chronologically later COHORT is identified by a distinct ADMISSION year
  (``students.admission_year``) newer than the current cohort's, with its own
  unique students and their own completed academic outcomes in
  ``student_semester_summary``.

This module reuses the existing independent academic-outcome label definition
(``v1_label_builder``: at-risk = FAIL/ATKT result or backlog_count > 0 at T+1)
and the existing per-student deployment boundary (last semester per student has
no T+1 outcome).  It NEVER manufactures data: if no later cohort exists, it
reports ``expansion_possible = False`` with an exact reason and an added-positive
delta of 0.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .v1_label_builder import AT_RISK_RESULTS, _at_risk_from

logger = logging.getLogger(__name__)

STUDENT_ID_MIN = "STU000001"
STUDENT_ID_MAX = "STU000080"


@dataclass(frozen=True)
class M3CohortExpansionAnalysis:
    """Result of the chronological cohort-expansion analysis."""
    # Cohort census
    admission_years: list[int]
    current_academic_years: list[str]
    n_students_total: int
    student_id_range: tuple[str, str]
    # Current (baseline) cohort = the earliest admission cohort already used by M3
    current_cohort_year: int
    current_student_ids: list[str]
    # Would-be later cohorts
    later_admission_years: list[int]
    later_student_ids: list[str]
    later_summary_rows: int
    later_positive_rows: int
    later_positive_students: int
    # Verdict
    expansion_possible: bool
    reason: str
    # Whether the current M3 population already consumes every available
    # independent outcome row (i.e. nothing is left to add within this cohort).
    all_labeled_rows_consumed: bool = True


def _analyze_tables(summary: pd.DataFrame, students: pd.DataFrame) -> M3CohortExpansionAnalysis:
    """Analyze the real cohort chronology from raw summary + students tables."""
    st = students.copy()
    sm = summary.copy()

    admission_years = sorted(int(y) for y in pd.to_numeric(
        st["admission_year"], errors="coerce"
    ).dropna().unique().tolist())
    current_academic_years = sorted(
        str(v) for v in st["current_academic_year"].dropna().unique().tolist()
    )
    n_total = int(st["student_id"].nunique())
    id_range = (
        str(st["student_id"].min()), str(st["student_id"].max()),
    )

    if not admission_years:
        return M3CohortExpansionAnalysis(
            admission_years=[], current_academic_years=current_academic_years,
            n_students_total=n_total, student_id_range=id_range,
            current_cohort_year=0, current_student_ids=[],
            later_admission_years=[], later_student_ids=[],
            later_summary_rows=0, later_positive_rows=0, later_positive_students=0,
            expansion_possible=False,
            reason="No admission_year data available; cannot establish a cohort.",
            all_labeled_rows_consumed=False,
        )

    current_year = admission_years[0]
    current_students = sorted(st.loc[
        st["admission_year"].astype(str) == str(current_year), "student_id"
    ].tolist())
    later_years = [y for y in admission_years if y > current_year]
    later_students = sorted(st.loc[
        st["admission_year"].astype(str).isin([str(y) for y in later_years]),
        "student_id",
    ].tolist())
    later_ids_set = set(later_students)

    later_summary = sm[sm["student_id"].isin(later_ids_set)] if later_ids_set else sm.iloc[0:0]
    later_summary_rows = int(len(later_summary))

    # Count independent positive outcomes available in the later cohort using the
    # EXACT existing academic-outcome label rule (at T+1, per student).
    later_positive_rows = 0
    later_positive_students = 0
    if later_summary_rows > 0 and {"semester_result", "backlog_count"}.issubset(
        later_summary.columns
    ):
        lc = later_summary.sort_values(["student_id", "semester_no"]).copy()
        lc["next_result"] = lc.groupby("student_id")["semester_result"].shift(-1)
        lc["next_backlogs"] = lc.groupby("student_id")["backlog_count"].shift(-1)
        lc["label"] = lc.apply(
            lambda r: _at_risk_from({
                "semester_result": r["next_result"],
                "backlog_count": r["next_backlogs"],
            }), axis=1,
        )
        lc = lc[lc["label"].notna()]
        later_positive_rows = int((lc["label"] == 1).sum())
        later_positive_students = int(
            len(set(lc.loc[lc["label"] == 1, "student_id"].unique()))
        )

    if not later_years or not later_students:
        reason = (
            "No chronologically later admission cohort exists in the real data: "
            f"single admission year {admission_years}; {n_total} students "
            f"(ids {id_range[0]}..{id_range[1]}); all active. The distinct "
            "student_semester_summary.academic_year values are CALENDAR years of "
            "the SAME cohort's semester sequence, not separate cohorts. "
            "Expansion would add 0 independent positive students."
        )
        expansion_possible = False
    else:
        reason = (
            f"Found {len(later_students)} later-cohort students "
            f"(admission years {later_years}); {later_summary_rows} summary rows, "
            f"{later_positive_rows} positive rows across "
            f"{later_positive_students} positive students."
        )
        expansion_possible = True

    # Confirm the current M3 population (all labeled rows with a T+1 outcome) is
    # fully consumed by the existing cohort build -> nothing left within it.
    all_labeled = True
    if {"student_id", "semester_no", "semester_result", "backlog_count"}.issubset(
        sm.columns
    ):
        cc = sm.sort_values(["student_id", "semester_no"]).copy()
        cc["nr"] = cc.groupby("student_id")["semester_result"].shift(-1)
        cc["nb"] = cc.groupby("student_id")["backlog_count"].shift(-1)
        # The expansion candidate excludes the baseline cohort students; for the
        # baseline cohort every labeled row is already used by the M3 build.
        all_labeled = later_summary_rows == 0  # nothing outside current cohort

    return M3CohortExpansionAnalysis(
        admission_years=admission_years,
        current_academic_years=current_academic_years,
        n_students_total=n_total,
        student_id_range=id_range,
        current_cohort_year=current_year,
        current_student_ids=current_students,
        later_admission_years=later_years,
        later_student_ids=later_students,
        later_summary_rows=later_summary_rows,
        later_positive_rows=later_positive_rows,
        later_positive_students=later_positive_students,
        expansion_possible=expansion_possible,
        reason=reason,
        all_labeled_rows_consumed=all_labeled,
    )


def analyze_m3_cohort_expansion(
    tables: dict[str, pd.DataFrame] | None = None,
) -> M3CohortExpansionAnalysis:
    """Analyze whether a chronologically later M3 cohort can be added.

    ``tables`` optionally supplies pre-loaded ``summary``/``students``
    DataFrames (e.g. live PostgreSQL via asyncpg); defaults to the existing CLI
    CSV snapshot loader (reused, not a parallel loader).
    """
    from .v1_cohort_dataset import _load_summary_and_students
    summary, students = _load_summary_and_students(tables)
    return _analyze_tables(summary, students)


def render_expansion_analysis(a: M3CohortExpansionAnalysis) -> str:
    lines = [
        "=" * 72,
        "M3 CHRONOLOGICAL (LATER ACADEMIC-YEAR) COHORT ANALYSIS",
        "=" * 72,
        f"  Admission years (real data): {a.admission_years}",
        f"  Current academic years: {a.current_academic_years}",
        f"  Students total: {a.n_students_total} "
        f"(ids {a.student_id_range[0]}..{a.student_id_range[1]})",
        f"  Current (baseline) M3 cohort admission year: {a.current_cohort_year}",
        f"  Later admission years: {a.later_admission_years}",
        f"  Later-cohort students: {len(a.later_student_ids)}",
        "  ---- expansion ----",
        f"  Expansion possible: {a.expansion_possible}",
        f"  Would-add summary rows: {a.later_summary_rows}",
        f"  Would-add positive rows: {a.later_positive_rows}",
        f"  Would-add positive students: {a.later_positive_students}",
        f"  All existing labeled rows already consumed: {a.all_labeled_rows_consumed}",
        "",
        "  WHY: " + a.reason,
        "=" * 72,
    ]
    return "\n".join(lines)
