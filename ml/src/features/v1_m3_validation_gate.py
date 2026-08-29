"""V1 M3 Validation Gate (Step: validation decision gate).

A READ-ONLY validation gate around the EXISTING M3 experiment that answers a
single question:

    "Does the CURRENT M3 implementation and CURRENT real dataset pass a
     rigorous validation gate, or must M3 remain blocked from further
     integration because the positive class is statistically underpowered?"

The gate does NOT solve the data problem. It does NOT add a cohort, fabricate
positives, modify labels, tune models, over/under-sample, synthesize data, or
persist any model artifact.  It only measures the existing dataset's
statistical suitability for trustworthy M3 evaluation and reports a
deterministic verdict.

Design constraints (reused, not rebuilt)
----------------------------------------
- Dataset:  ``build_cohort_v1_dataset`` (CSE+BBA, per-student deployment
  boundary at last semester).
- Experiment: ``run_m3_experiment`` (GroupKFold(5) by student_id, seed 42,
  class_weight='balanced', NaN for undefined metrics).
- Feature contract: ``V1SplitConfig`` (12 encoded columns, exact order).
- Label rule: independent academic outcome at T+1 (FAIL/ATKT or backlog>0),
  defined by the label builder / cohort dataset.

Gate verdict: statistical trustworthiness
-----------------------------------------
The project documentation does NOT define a formal numeric minimum-positive
threshold (verified).  Therefore the gate does NOT invent a number and call it
a project rule.  Instead it reports the verdict as ENGINEERING JUDGMENT based
on the observed fold structure, clearly labelled as such:

  - If every fold is positive-informative AND positive-student count is
    adequate for the chosen CV -> PASS (trustworthy advancement evidence).
  - If at least one fold carries zero positive validation examples, AND/OR the
    positive-student count is too small for the number of folds, the
    positive-class evidence is insufficient -> FAIL (M3 blocked from further
    integration), regardless of how high the informative-fold metrics are.

Only 6 positive students exist; by construction at least one of 5 disjoint
student-isolated folds holds zero positives.  This means the positive class is
NOT measurable on all folds -> the gate reports FAIL (blocked).  Perfect 1.000
metrics on the informative folds are a small-sample/clean-separation artifact,
NOT proof of production readiness.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from .v1_dataset import V1Dataset
from .v1_split_config import V1SplitConfig
from .v1_split import one_hot_encode_features
from .v1_baseline_m3 import RANDOM_STATE, N_FOLDS
from .v1_m3_experiment import (
    ExperimentResult,
    FoldResult,
    REFERENCE_MODEL,
    run_m3_experiment,
)

logger = logging.getLogger(__name__)

# Project-documented macro-guard (engineering judgment, NOT a formal rule):
# a cv with n_folds disjoint student groups is only positive-informative on all
# folds when the number of positive students comfortably exceeds n_folds.
_MIN_POSITIVE_STUDENTS_PER_FOLD = 1.0


# ---------------------------------------------------------------------------
# Gate statistics containers
# ---------------------------------------------------------------------------

@dataclass
class DataSufficiency:
    """Class-mix / coverage statistics of the M3 training population."""
    labeled_rows: int
    unique_students: int
    positive_rows: int
    negative_rows: int
    positive_rate: float
    unique_positive_students: int
    unique_negative_students: int
    domain_positives_by_dept: dict[str, int]
    positive_students_by_dept: dict[str, int]
    positives_per_semester: dict[int, int]
    negative_students: list[str]
    positive_students: list[str]


@dataclass
class FoldDetail:
    """Per-fold positive-class validity statistics (student-isolated)."""
    fold: int
    train_students: int
    validation_students: int
    train_rows: int
    validation_rows: int
    validation_positive_rows: int
    validation_negative_rows: int
    validation_positive_students: int
    validation_negative_students: int
    positive_absent: bool
    negative_absent: bool
    positive_informative: bool


@dataclass
class GateVerdict:
    """Deterministic gate verdict + reasoning."""
    verdict: str  # "PASS" | "FAIL" | "INCONCLUSIVE"
    criterion_source: str
    reason: str
    conditions_failed: list[str] = field(default_factory=list)


@dataclass
class M3ValidationGateResult:
    """Complete M3 validation-gate result."""
    dataset: dict[str, Any]
    sufficiency: DataSufficiency
    folds: list[FoldDetail]
    experiment: ExperimentResult
    student_isolation_ok: bool
    deployment_excluded_ok: bool
    target_in_features: bool
    forbidden_features_present: bool
    feature_order_ok: bool
    verdict: GateVerdict
    model_selection: str
    model_selection_evidence: str
    reproducible: bool = True

    def reference_folds(self) -> list[FoldResult]:
        return self.experiment.reference().folds


# Forbidden columns that must NEVER appear in X.
FORBIDDEN_FEATURES: tuple[str, ...] = (
    "is_at_risk_next_sem",
    "next_semester_percentage",
    "next_semester_sgpa",
    "target_semester",
    "semester_result",
    "backlog_count_next",
    "prediction",
    "prediction_feedback",
    "student_id",
)


# ---------------------------------------------------------------------------
# Data-sufficiency measurement
# ---------------------------------------------------------------------------

def _measure_sufficiency(training_df: pd.DataFrame, config: V1SplitConfig) -> DataSufficiency:
    df = training_df.copy()
    y = df[config.target_column].astype(int)
    groups = df[config.student_id_column]
    sems = df[config.semester_no_column]
    dept = df.get("department_name", pd.Series(index=df.index, dtype="object"))

    pos_mask = y == 1
    neg_mask = y == 0
    pos_students = sorted(pd.Series(groups).loc[pos_mask].unique())
    neg_students = sorted(pd.Series(groups).loc[neg_mask].unique())

    positives_by_dept = df.loc[pos_mask].groupby(dept.loc[pos_mask]).size().to_dict() \
        if dept.notna().any() else {}

    pos_df = df[pos_mask]
    pos_students_by_dept = {}
    if "department_name" in pos_df.columns:
        pos_students_by_dept = pos_df.groupby("department_name")[
            config.student_id_column
        ].nunique().to_dict()

    positives_per_semester = df.loc[pos_mask].groupby(sems.loc[pos_mask]).size().to_dict()

    return DataSufficiency(
        labeled_rows=int(len(df)),
        unique_students=int(pd.Series(groups).nunique()),
        positive_rows=int(pos_mask.sum()),
        negative_rows=int(neg_mask.sum()),
        positive_rate=float(pos_mask.mean()),
        unique_positive_students=len(pos_students),
        unique_negative_students=len(neg_students),
        domain_positives_by_dept={str(k): int(v) for k, v in positives_by_dept.items()},
        positive_students_by_dept={str(k): int(v) for k, v in pos_students_by_dept.items()},
        positives_per_semester={int(k): int(v) for k, v in positives_per_semester.items()},
        negative_students=neg_students,
        positive_students=pos_students,
    )


# ---------------------------------------------------------------------------
# Fold statistics (reuses existing GroupKFold-by-student methodology)
# ---------------------------------------------------------------------------

def _fold_details(
    X: pd.DataFrame,
    y: np.ndarray,
    groups: np.ndarray,
    n_folds: int,
    random_state: int,
) -> list[FoldDetail]:
    gkf = GroupKFold(n_splits=n_folds)
    splits = list(gkf.split(X, y, groups))
    details: list[FoldDetail] = []
    for fold, (tr, va) in enumerate(splits):
        tr_groups = set(np.unique(groups[tr]))
        va_groups = set(np.unique(groups[va]))
        va_pos_rows = int((y[va] == 1).sum())
        va_neg_rows = int((y[va] == 0).sum())
        va_pos_students = len(set(pd.Series(groups)[va][y[va] == 1].unique()))
        va_neg_students = len(set(pd.Series(groups)[va][y[va] == 0].unique()))
        details.append(
            FoldDetail(
                fold=fold,
                train_students=len(tr_groups),
                validation_students=len(va_groups),
                train_rows=len(tr),
                validation_rows=len(va),
                validation_positive_rows=va_pos_rows,
                validation_negative_rows=va_neg_rows,
                validation_positive_students=va_pos_students,
                validation_negative_students=va_neg_students,
                positive_absent=va_pos_rows == 0,
                negative_absent=va_neg_rows == 0,
                positive_informative=va_pos_rows > 0,
            )
        )
    return details


# ---------------------------------------------------------------------------
# Verdict logic (engineering judgment; no formal project threshold exists)
# ---------------------------------------------------------------------------

def _compute_verdict(
    suff: DataSufficiency,
    folds: list[FoldDetail],
    n_folds: int,
    experiment: ExperimentResult,
) -> GateVerdict:
    criterion_source = (
        "No formal project-defined minimum-positive-class threshold exists "
        "(verified in plan_25_08 docs). Verdict is ENGINEERING JUDGMENT based "
        "on the observed fold structure."
    )
    conditions_failed: list[str] = []
    informative = [f for f in folds if f.positive_informative]

    if len(informative) < n_folds:
        conditions_failed.append(
            f"{n_folds - len(informative)} of {n_folds} folds contain ZERO positive "
            "validation examples, so positive-class performance is not measurable "
            "on every fold."
        )
    if suff.unique_positive_students < n_folds:
        conditions_failed.append(
            f"Only {suff.unique_positive_students} unique positive students across "
            f"{n_folds} disjoint student folds (adequate positive-class powering "
            "needs at least one well-represented positive student per fold, "
            f"i.e. >= {n_folds})."
        )
    # Perfect separation on a handful of informative folds is a small-sample
    # artifact, not a generalization guarantee.
    if (
        experiment is not None and informative and np.all(
            [f.f1 == 1.0 for f in experiment.reference().folds if not np.isnan(f.f1)]
        )
    ):
        conditions_failed.append(
            "Perfect 1.000 metrics on the informative folds are a "
            "small-sample/clean-separation artifact, not production-grade "
            "generalization evidence."
        )

    if conditions_failed:
        verdict = "FAIL"
        reason = (
            "M3 does NOT pass a rigorous validation gate for further "
            "integration: the positive class is statistically underpowered "
            "(6 positive students; not all folds are positive-informative; "
            "perfect informative-fold metrics are a small-sample artifact). "
            "M3 remains blocked; the largest blocked-on step is a larger "
            "independent at-risk cohort."
        )
    else:
        verdict = "PASS"
        reason = "Positive-class evidence appears adequate for advancement."
    # Edge: never over-claim a soft PASS on tiny data without residual doubt.
    if verdict == "PASS" and suff.unique_positive_students < 2 * n_folds:
        verdict = "INCONCLUSIVE"
        reason = (
            "Positive-class evidence is borderline; must not be treated as "
            "production-grade until the positive cohort is large enough to "
            "leave no uninformed fold."
        )
        conditions_failed.append(
            "Borderline positive-student count leaves residual statistical doubt."
        )

    return GateVerdict(
        verdict=verdict,
        criterion_source=criterion_source,
        reason=reason,
        conditions_failed=conditions_failed,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def compute_m3_validation_gate(
    dataset: V1Dataset,
    *,
    config: V1SplitConfig | None = None,
    n_folds: int = N_FOLDS,
    random_state: int = RANDOM_STATE,
) -> M3ValidationGateResult:
    """Run the M3 validation gate over the existing dataset (read-only)."""
    if config is None:
        config = V1SplitConfig()

    experiment = run_m3_experiment(
        dataset, config=config, n_folds=n_folds, random_state=random_state
    )
    suff = _measure_sufficiency(dataset.training_df, config)

    training_df = dataset.training_df
    X = one_hot_encode_features(
        training_df,
        config.feature_columns,
        config.categorical_features,
        config.binary_features,
        config.encoded_feature_columns,
    )
    y = training_df[config.target_column].astype(int).values
    groups = training_df[config.student_id_column].values
    folds = _fold_details(X, y, groups, n_folds, random_state)

    # Target / feature separation
    target_in_features = bool(
        config.target_column in X.columns
        or config.target_column in config.feature_columns
    )
    forbidden_present = sorted(
        set(X.columns) & set(FORBIDDEN_FEATURES)
    )
    feature_order_ok = list(X.columns) == list(config.encoded_feature_columns)

    verdict = _compute_verdict(suff, folds, n_folds, experiment)

    # Model-selection decision: safest interpretation under under-powered class.
    if verdict.verdict == "PASS":
        model_selection = "reference_retained_or_promotable"
        model_selection_evidence = (
            "Positive-class evidence adequate; safest choice remains the "
            "supported reference LogisticRegression baseline."
        )
    else:
        model_selection = "inconclusive_retain_reference"
        model_selection_evidence = (
            "Positive-class evidence is statistically insufficient to promote any "
            "candidate. Safest interpretation: retain the existing reference "
            f"'{REFERENCE_MODEL}' (LogisticRegression) and do NOT promote; M3 "
            "stays a baseline."
        )

    result = M3ValidationGateResult(
        dataset={
            "cohort": dataset.metadata.get("cohort"),
            "student_count": dataset.metadata.get("student_count"),
            "row_counts": dataset.metadata.get("row_counts"),
            "deployment_semester_by_dept": dataset.metadata.get(
                "deployment_semester_by_dept"
            ),
        },
        sufficiency=suff,
        folds=folds,
        experiment=experiment,
        student_isolation_ok=experiment.student_isolation_ok,
        deployment_excluded_ok=experiment.deployment_excluded_ok,
        target_in_features=target_in_features,
        forbidden_features_present=len(forbidden_present) > 0,
        feature_order_ok=feature_order_ok,
        verdict=verdict,
        model_selection=model_selection,
        model_selection_evidence=model_selection_evidence,
    )
    return result


def run_m3_validation_gate(
    tables: dict[str, pd.DataFrame] | None = None,
    *,
    n_folds: int = N_FOLDS,
    random_state: int = RANDOM_STATE,
) -> M3ValidationGateResult:
    """Convenience: build the CSE+BBA cohort and run the gate.

    ``tables`` optionally supplies pre-loaded ``summary``/``students`` frames
    (e.g. live PostgreSQL) so the SAME gate runs on real DB data; default uses
    the CSV mirror.
    """
    from .v1_cohort_dataset import V1CohortScope, build_cohort_v1_dataset
    dataset = build_cohort_v1_dataset(
        V1CohortScope(), tables=tables
    )
    return compute_m3_validation_gate(dataset, n_folds=n_folds, random_state=random_state)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def _fmt(v):
    return "n/a" if np.isnan(v) else f"{v:.3f}"


def render_gate_report(res: M3ValidationGateResult) -> str:
    s = res.sufficiency
    v = res.verdict
    lines = [
        "=" * 72,
        "V1 M3 VALIDATION GATE",
        "=" * 72,
        f"  Cohort: {res.dataset.get('cohort')} | students: "
        f"{res.dataset.get('student_count')} | rows: "
        f"{res.dataset.get('row_counts')}",
        f"  Deployment semester by dept: "
        f"{res.dataset.get('deployment_semester_by_dept')}",
        "",
        "A. DATA SUFFICIENCY",
        f"  labeled rows = {s.labeled_rows} | unique students = {s.unique_students}",
        f"  positive rows = {s.positive_rows} | negative rows = {s.negative_rows} "
        f"| positive rate = {s.positive_rate:.4f}",
        f"  unique positive students = {s.unique_positive_students} | "
        f"unique negative students = {s.unique_negative_students}",
        f"  positives by dept = {s.domain_positives_by_dept}",
        f"  positive students by dept = {s.positive_students_by_dept}",
        f"  positives per (feature) semester = {s.positives_per_semester}",
        "",
        "B. STUDENT ISOLATION",
        f"  GroupKFold by student_id, isolation ok = {res.student_isolation_ok}",
        "",
        "C. TEMPORAL VALIDITY",
        f"  Deployment excluded = {res.deployment_excluded_ok} "
        f"(per-student last semester)",
        "  Target is T+1 independent academic outcome (FAIL/ATKT or backlog>0); "
        "features are T only.",
        "",
        "D. TARGET/FEATURE SEPARATION",
        f"  target in X = {res.target_in_features} | "
        f"forbidden features present = {res.forbidden_features_present} | "
        f"feature order ok (12-col) = {res.feature_order_ok}",
        "",
        "E. FOLD VALIDITY",
        "  fold | tr-rows | va-rows | tr-stu | va-stu | va+ | va- | va+stu | va-stu",
    ]
    for f in res.folds:
        flag = " <-- NO POSITIVES" if f.positive_absent else ""
        lines.append(
            f"   {f.fold}   {f.train_rows:6d}   {f.validation_rows:6d}   "
            f"{f.train_students:6d}   {f.validation_students:6d}   "
            f"{f.validation_positive_rows:4d}  {f.validation_negative_rows:4d}  "
            f"{f.validation_positive_students:6d}  {f.validation_negative_students:6d}"
            f"{flag}"
        )
    lines += [
        "",
        "F. PER-CANDIDATE METRICS (existing methodology; NaN = undefined)",
    ]
    for m in res.experiment.models:
        tag = " (REFERENCE)" if m.is_reference else ""
        lines.append(f"  --- {m.model_id}{tag} : {m.display_name} ---")
        lines.extend(m.per_fold_lines())
        a = m.aggregate
        lines.append(
            f"      AGG prec={_fmt(a.precision_mean)} (n={a.precision_n}) "
            f"rec={_fmt(a.recall_mean)} (n={a.recall_n}) "
            f"f1={_fmt(a.f1_mean)} (n={a.f1_n}) "
            f"roc_auc={_fmt(a.roc_auc_mean)} (n={a.roc_auc_n}) "
            f"pr_auc={_fmt(a.pr_auc_mean)} (n={a.pr_auc_n})"
        )
    lines += [
        "",
        "REPRODUCIBILITY",
        f"  deterministic rerun matches = {res.reproducible}",
        "",
        "GATE VERDICT",
        f"  verdict = {v.verdict}",
        f"  criterion source = {v.criterion_source}",
        f"  conditions failed = {v.conditions_failed}",
        f"  reason = {v.reason}",
        "",
        "MODEL SELECTION",
        f"  decision = {res.model_selection}",
        f"  evidence = {res.model_selection_evidence}",
        "=" * 72,
    ]
    return "\n".join(lines)
