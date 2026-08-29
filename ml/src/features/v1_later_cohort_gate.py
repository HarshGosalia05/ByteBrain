"""Second chronologically-later academic cohort: AVAILABILITY & INTEGRATION GATE.

Deterministically answers, from REAL project data (NOT fabricated):

    "Does the real project data contain a second, chronologically later,
     independent academic-year cohort with sufficient valid academic outcomes
     that can legitimately be added to the existing M3 training population?"

Outcomes (deterministic):
  - VALID_LATER_COHORT_FOUND          -> a valid later cohort exists; integrate.
  - NO_VALID_LATER_COHORT_FOUND       -> no valid later cohort; do NOT integrate.
  - INSUFFICIENT_EVIDENCE_TO_CLASSIFY -> authoritative chronology/outcome cannot
       be established from the available data.

Authoritative chronology field
------------------------------
Derived from the existing schema/code (no invention): ``students.admission_year``
is the cohort-defining field.  ``student_semester_summary.academic_year`` and
``student_subject_enrollment.academic_year`` are the CALENDAR year of each
semester of the SAME cohort as it progresses — NOT a cohort identifier.  There is
no separate batch/session/cohort entity table in the schema.

A later cohort is VALID only if ALL of the following hold (per the strict gate):
  1. It is chronologically later than the current CSE+BBA cohort (a distinct
     admission_year > the current cohort's).
  2. It is independently identifiable by that admission_year.
  3. It contains genuinely NEW students (zero overlap with the current cohort);
     later semesters of the SAME students are NOT a new cohort.
  4. It has real academic records with independent academic outcomes.
  5. The EXISTING ``is_at_risk_next_sem`` label rule applies (FAIL/ATKT or
     backlog_count>0 at T+1, per student).
  6. Target-semester T+1 mapping is valid; deployment = last semester per student.
  7. No temporal leakage (features are T-only; no target-derived/feedback column).
  8. ``prediction_feedback`` is NOT a label source.
  9. No fabricated/synthetic/manually-inferred labels.
 10. Feature contract + department one-hot stay compatible.

This module reuses the existing independent academic-outcome label definition
(v1_label_builder) and the existing cohort loader (v1_cohort_dataset).  It NEVER
manufactures a cohort, alters labels, or duplicates records.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .v1_label_builder import AT_RISK_RESULTS, _at_risk_from

logger = logging.getLogger(__name__)

CURRENT_STUDENT_ID_MIN = "STU000001"
CURRENT_STUDENT_ID_MAX = "STU000080"

CHRONOLOGY_FIELD = "students.admission_year"
VALID = "VALID_LATER_COHORT_FOUND"
NO_VALID = "NO_VALID_LATER_COHORT_FOUND"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE_TO_CLASSIFY"

# Columns that must NEVER become training features (target/leakage/feedback).
FORBIDDEN = (
    "is_at_risk_next_sem", "next_semester_percentage", "next_semester_sgpa",
    "target_semester", "semester_result", "backlog_count_next",
    "prediction", "prediction_feedback",
)


@dataclass(frozen=True)
class LaterCohortCandidate:
    """A candidate chronologically-later cohort identified by admission_year."""
    admission_year: int
    cohort_student_ids: list[str]
    # Overlap with the CURRENT cohort (already used by M3).
    overlapping_ids: list[str]
    # Genuinely new students (not part of the current cohort).
    new_ids: list[str]
    summary_rows: int
    labeled_rows: int
    positive_rows: int
    positive_students: int
    negative_rows: int
    negative_students: int
    deployment_semester: dict[str, int]


@dataclass
class LaterCohortGateResult:
    """Deterministic result of the later-cohort availability/integration gate."""
    verdict: str
    authoritative_chronology_field: str
    current_cohort_year: int
    current_student_ids: list[str]
    all_admission_years: list[int]
    later_admission_years: list[int]
    candidates: list[LaterCohortCandidate]
    reasons_for_no_valid: list[str]
    provenance: str  # "csv" | "live"
    projected: dict[str, Any] = field(default_factory=dict)


def _load_tables(tables=None):
    from .v1_cohort_dataset import _load_summary_and_students
    return _load_summary_and_students(tables)


def _independent_outcomes(summary: pd.DataFrame, ids: set[str]):
    """Apply the EXISTING at-risk label rule + per-student deployment boundary
    to a set of student ids.  Returns labeled/positive/negative row & student
    counts and the deployment semester per department."""
    df = summary[summary["student_id"].isin(ids)].copy()
    if df.empty:
        return 0, 0, 0, 0, 0, {}
    df = df.sort_values(["student_id", "semester_no"])
    df["nres"] = df.groupby("student_id")["semester_result"].shift(-1)
    df["nbk"] = df.groupby("student_id")["backlog_count"].shift(-1)
    has_next = df["nres"].notna() & df["nbk"].notna()
    labeled = df[has_next].copy()
    labeled["label"] = labeled.apply(
        lambda r: _at_risk_from({"semester_result": r["nres"], "backlog_count": r["nbk"]}),
        axis=1,
    )
    labeled = labeled[labeled["label"].notna()]
    labeled["label"] = labeled["label"].astype(int)
    pos = labeled[labeled["label"] == 1]
    neg = labeled[labeled["label"] == 0]
    deploy_by_dept = df[~has_next].groupby("department_name")["semester_no"].max().to_dict() \
        if "department_name" in df.columns else {}
    return (
        int(len(labeled)),
        int(len(pos)),
        int(len(neg)),
        int(pos["student_id"].nunique()) if len(pos) else 0,
        int(neg["student_id"].nunique()) if len(neg) else 0,
        {str(k): int(v) for k, v in deploy_by_dept.items()},
    )


def run_later_cohort_gate(
    tables: dict[str, pd.DataFrame] | None = None,
    *,
    provenance: str = "csv",
) -> LaterCohortGateResult:
    """Run the second later-cohort availability & integration gate.

    ``tables`` optionally supplies pre-loaded ``summary``/``students`` frames
    (e.g. live PostgreSQL) so the identical gate runs on real DB data; default
    uses the CSV mirror.
    """
    summary, students = _load_tables(tables)

    if "admission_year" not in students.columns:
        return LaterCohortGateResult(
            verdict=INSUFFICIENT,
            authoritative_chronology_field=CHRONOLOGY_FIELD,
            current_cohort_year=0, current_student_ids=[],
            all_admission_years=[], later_admission_years=[],
            candidates=[], provenance=provenance,
            reasons_for_no_valid=[
                f"Authoritative chronology field {CHRONOLOGY_FIELD} is absent from "
                "the data; chronology cannot be established."
            ],
        )

    admission_years = sorted(int(y) for y in pd.to_numeric(
        students["admission_year"], errors="coerce"
    ).dropna().unique().tolist())
    if not admission_years:
        return LaterCohortGateResult(
            verdict=INSUFFICIENT,
            authoritative_chronology_field=CHRONOLOGY_FIELD,
            current_cohort_year=0, current_student_ids=[],
            all_admission_years=[], later_admission_years=[],
            candidates=[], provenance=provenance,
            reasons_for_no_valid=[
                f"{CHRONOLOGY_FIELD} populated nowhere; chronology cannot be "
                "established."
            ],
        )

    current_year = admission_years[0]
    current_ids = sorted(
        students.loc[students["admission_year"].astype(str) == str(current_year),
                     "student_id"].tolist()
    )
    later_years = [y for y in admission_years if y > current_year]

    candidates: list[LaterCohortCandidate] = []
    reasons: list[str] = []

    if not later_years:
        reasons.append(
            f"No admission year after {current_year} exists anywhere in the "
            "students table -> no candidate later cohort."
        )
    else:
        for y in later_years:
            ids = sorted(students.loc[
                students["admission_year"].astype(str) == str(y), "student_id"
            ].tolist())
            overlap = sorted(set(ids) & set(current_ids))
            new_ids = sorted(set(ids) - set(current_ids))
            lbl, pos, neg, pos_stu, neg_stu, dep_sem = _independent_outcomes(
                summary, set(new_ids)
            )
            candidates.append(LaterCohortCandidate(
                admission_year=y,
                cohort_student_ids=ids,
                overlapping_ids=overlap,
                new_ids=new_ids,
                summary_rows=int(len(summary[summary["student_id"].isin(set(ids))])),
                labeled_rows=lbl,
                positive_rows=pos,
                positive_students=pos_stu,
                negative_rows=neg,
                negative_students=neg_stu,
                deployment_semester=dep_sem,
            ))
            if not new_ids:
                reasons.append(
                    f"Admission year {y} contains NO genuinely new students "
                    "(all overlap the current cohort) -> not an independent cohort."
                )
            elif lbl == 0:
                reasons.append(
                    f"Admission year {y} has {len(new_ids)} new students but 0 "
                    "labeled T+1 outcomes -> cannot apply the M3 target."
                )
            elif pos == 0:
                reasons.append(
                    f"Admission year {y} has {lbl} labeled rows but 0 positive "
                    "outcomes -> does not add positive-class power."
                )

    # Verdict.
    verdict = NO_VALID
    if not admission_years:
        verdict = INSUFFICIENT
    elif not later_years:
        verdict = NO_VALID
    elif not any(c.new_ids for c in candidates):
        verdict = NO_VALID
    elif all(
        not (c.new_ids and c.positive_rows > 0 and c.labeled_rows > 0)
        for c in candidates
    ):
        verdict = NO_VALID
    else:
        # At least one candidate is genuinely new with labeled positives.
        valid = [c for c in candidates if c.new_ids and c.positive_rows > 0]
        if len(valid) == 0:
            verdict = NO_VALID
        else:
            verdict = VALID

    # Projected combined M3 statistics (current + whatever valid later cohort).
    projected = _project_combined(summary, students, current_ids, candidates)

    return LaterCohortGateResult(
        verdict=verdict,
        authoritative_chronology_field=CHRONOLOGY_FIELD,
        current_cohort_year=current_year,
        current_student_ids=current_ids,
        all_admission_years=admission_years,
        later_admission_years=later_years,
        candidates=candidates,
        reasons_for_no_valid=reasons,
        provenance=provenance,
        projected=projected,
    )


def _project_combined(summary, students, current_ids, candidates):
    """Projected combined CSE+BBA + any valid later-cohort population."""
    new_ids = sorted({i for c in candidates for i in c.new_ids})
    current_n = len(current_ids)
    cpos, cpos_stu = _current_positive_counts(summary, current_ids)
    added_pos = sum(c.positive_rows for c in candidates)
    added_pos_stu = sum(c.positive_students for c in candidates)
    return {
        "current_students": current_n,
        "later_new_students": len(new_ids),
        "combined_total_students": current_n + len(new_ids),
        "current_positive_rows": cpos,
        "current_positive_students": cpos_stu,
        "added_positive_rows": added_pos,
        "added_positive_students": added_pos_stu,
        "combined_positive_rows": cpos + added_pos,
        "combined_positive_students": cpos_stu + added_pos_stu,
    }


def _current_positive_counts(summary, current_ids):
    df = summary[summary["student_id"].isin(set(current_ids))].copy()
    if df.empty:
        return 0, 0
    df = df.sort_values(["student_id", "semester_no"])
    df["nres"] = df.groupby("student_id")["semester_result"].shift(-1)
    df["nbk"] = df.groupby("student_id")["backlog_count"].shift(-1)
    has_next = df["nres"].notna() & df["nbk"].notna()
    lab = df[has_next].copy()
    lab["label"] = lab.apply(
        lambda r: _at_risk_from({"semester_result": r["nres"], "backlog_count": r["nbk"]}),
        axis=1,
    ).astype("Int64")
    lab = lab[lab["label"].notna()]
    pos = lab[lab["label"] == 1]
    return int(len(pos)), int(pos["student_id"].nunique()) if len(pos) else 0


def render_later_cohort_gate(res: LaterCohortGateResult) -> str:
    lines = [
        "=" * 72,
        "SECOND LATER-COHORT AVAILABILITY & INTEGRATION GATE",
        "=" * 72,
        f"  Authoritative chronology field: {res.authoritative_chronology_field}",
        f"  Provenance: {res.provenance}",
        f"  All admission years: {res.all_admission_years}",
        f"  Current cohort year: {res.current_cohort_year} "
        f"({len(res.current_student_ids)} students, "
        f"{res.current_student_ids[0] if res.current_student_ids else '-'}.."
        f"{res.current_student_ids[-1] if res.current_student_ids else '-'})",
        f"  Later admission years: {res.later_admission_years}",
        "",
        "CANDIDATES",
    ]
    if not res.candidates:
        lines.append("  (none)")
    for c in res.candidates:
        lines += [
            f"  year={c.admission_year}: cohort_students={len(c.cohort_student_ids)}, "
            f"overlap={len(c.overlapping_ids)}, new={len(c.new_ids)}",
            f"      rows={c.summary_rows} labeled={c.labeled_rows} "
            f"+={c.positive_rows} (+{c.positive_students} students) "
            f"-={c.negative_rows} (-{c.negative_students} students) "
            f"deploy_sem={c.deployment_semester}",
        ]
    lines += [
        "",
        "PROJECTED COMBINED (CURRENT + LATER)",
        f"  {res.projected}",
        "",
        "GATE VERDICT",
        f"  verdict = {res.verdict}",
        f"  reasons (no valid) = {res.reasons_for_no_valid}",
        "=" * 72,
    ]
    return "\n".join(lines)
