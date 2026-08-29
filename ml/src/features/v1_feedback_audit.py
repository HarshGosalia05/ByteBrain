"""V1 Feedback-Label Quality Audit (READ-ONLY).

Determines whether the existing ``prediction_feedback`` mechanism can provide
real, usable labels for the M3 target ``is_at_risk_next_sem``.

Scope
-----
* Pure, deterministic, READ-ONLY: never writes to ``prediction_feedback``,
  ``ml_predictions``, or any academic table; never trains, never persists a
  model, never produces student predictions.
* Reuses the project's existing feedback-label primitive
  (``ml.src.feedback_labels.latest_verdicts``) so "latest verdict wins"
  de-duplication is identical to the rest of the codebase.
* Does NOT merge feedback into the production training dataset. It only
  *reports* label quality and readiness so a decision can be made elsewhere.

Label contract (kept identical to ``ml.src.feedback_labels``)
--------------------------------------------------------------
    feedback_action == 'confirmed' -> candidate_label == 1
    feedback_action == 'dismissed' -> candidate_label == 0

This mirrors the M3 target mirroring already used across the project; the
whole point of this module is to *audit* whether that mapping is trustworthy.

Reconciliation
--------------
The M3 target is ground-truth academic outcome: a student is ``at_risk`` in
semester T+1 when ``semester_result(T+1)`` is FAIL/ATKT or ``backlog_count(T+1)
> 0`` (source: V1 target construction / retrain_m3.fetch_historical_training_dataset).

A candidate feedback label is bound to a specific *prediction period*: the
judged prediction's ``prediction_value.semester_no`` (the feature-row semester
T) and hence target semester T+1.  We then compare the candidate label to the
actual academic outcome at T+1:

    candidate_label == actual_at_risk(T+1) -> agrees  (consistent)
    candidate_label != actual_at_risk(T+1) -> conflicts (unreliable as a truth label)

A feedback row is only temporally usable (no leakage) when:
  * it is an M3 judgement,
  * it carries a usable prediction semester (``prediction_value.semester_no``),
  * T+1 really exists as a completed semester (so the outcome is observable),
  * T is a training feature semester (T < deployment semester 7), and
  * it is bound to a student with the feature/outcome rows present.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from ml.src.feedback_labels import ACTION_LABELS, latest_verdicts
except ImportError:  # tests put ml/src on path directly
    from feedback_labels import ACTION_LABELS, latest_verdicts
logger = logging.getLogger(__name__)

CONFIRMED = "confirmed"
DISMISSED = "dismissed"

# Deployment semester from V1 scope (semester 7 = prediction/deployment, never
# a training feature row; its outcome is the thing we predict, not evidence).
DEPLOYMENT_SEMESTER = 7

VALID_ACTIONS = frozenset(ACTION_LABELS.keys())
AT_RISK_RESULTS = frozenset({"FAIL", "ATKT"})


@dataclass
class BoundLabel:
    """A single candidate feedback label bound to a prediction period."""
    prediction_id: str
    student_id: str
    feedback_action: str
    candidate_label: int
    prediction_semester: Optional[int]   # feature-row semester T (None = unusable)
    target_semester: Optional[int]       # T+1 (None = unusable)
    feedback_timestamp: Any
    model_version: Optional[str]

    # reconciliation
    actual_at_risk: Optional[int]        # None = target semester not observable
    agrees_with_ground_truth: Optional[bool]  # None = not comparable
    temporal_usable: bool
    rejection_reason: Optional[str]


@dataclass
class LabelQualityReport:
    """Deterministic report describing the usability of prediction_feedback."""
    total_feedback_rows: int
    unique_students_with_feedback: int
    m3_rows: int
    rejected_rows: List[Dict[str, Any]]
    bound_labels: List[BoundLabel]
    # quality counters
    duplicate_cases: int
    conflicting_feedback_cases: int
    missing_student_ids: int
    missing_prediction_period: int
    invalid_action_values: int
    non_m3_prediction_rows: int
    # usable counters
    usable_bound_labels: int
    usable_positive_students: int
    usable_negative_students: int
    unusable_reasons: List[str]

    def summary(self) -> Dict[str, Any]:
        agreed = sum(1 for b in self.bound_labels if b.agrees_with_ground_truth is True)
        conflicted = sum(1 for b in self.bound_labels if b.agrees_with_ground_truth is False)
        not_comparable = sum(1 for b in self.bound_labels if b.agrees_with_ground_truth is None)
        positive = sorted(
            {
                b.student_id
                for b in self.bound_labels
                if b.agrees_with_ground_truth is True and b.candidate_label == 1
            }
        )
        return {
            "total_feedback_rows": self.total_feedback_rows,
            "unique_students_with_feedback": self.unique_students_with_feedback,
            "m3_rows": self.m3_rows,
            "duplicate_feedback_cases": self.duplicate_cases,
            "conflicting_feedback_cases": self.conflicting_feedback_cases,
            "missing_student_ids": self.missing_student_ids,
            "missing_prediction_period": self.missing_prediction_period,
            "invalid_action_values": self.invalid_action_values,
            "non_m3_prediction_rows": self.non_m3_prediction_rows,
            "rejected_rows": len(self.rejected_rows),
            "usable_bound_labels": self.usable_bound_labels,
            "bound_labels_agreeing_with_ground_truth": agreed,
            "bound_labels_conflicting_with_ground_truth": conflicted,
            "bound_labels_not_comparable": not_comparable,
            "usable_positive_students": self.usable_positive_students,
            "usable_negative_students": self.usable_negative_students,
            "positive_students_where_feedback_matches_truth": positive,
            "unusable_reasons": list(self.unusable_reasons),
        }


def _bound_sort_key(b: BoundLabel):
    """Stable sort key for deterministic per-row output."""
    return (str(b.student_id or ""), str(b.prediction_id or ""), str(b.feedback_timestamp or ""))


def actual_at_risk_for_semester(
    outcome_map: Dict[str, Dict[int, Dict[str, Any]]],
    student_id: str,
    semester_no: int,
) -> Optional[int]:
    """Return actual at-risk (0/1) for a student-semester, or None if absent."""
    sems = outcome_map.get(student_id)
    if not sems:
        return None
    row = sems.get(semester_no)
    if row is None:
        return None
    result = row.get("semester_result")
    backlogs = row.get("backlog_count")
    if result is None and backlogs is None:
        return None
    result_str = str(result).strip() if result is not None else ""
    back = backlogs if backlogs is not None else 0
    return int(result_str in AT_RISK_RESULTS or back > 0)


def audit_prediction_feedback_labels(
    feedback_rows: List[Dict[str, Any]],
    *,
    predictions_map: Dict[str, Dict[str, Any]],
    outcome_map: Dict[str, Dict[int, Dict[str, Any]]],
    training_semesters: Optional[set[int]] = None,
) -> LabelQualityReport:
    """Audit feedback rows into a deterministic label-quality report.

    Parameters
    ----------
    feedback_rows : list of dicts with the prediction_feedback shape
        (feedback_id, prediction_id, student_id, faculty_id,
        feedback_action, note, model_version, feedback_timestamp).
    predictions_map : {str(prediction_id): {...}} with prediction_type and
        prediction_value (dict/JSON) carrying ``semester_no``.
    outcome_map : {student_id: {semester_no: {semester_result, backlog_count}}}
        Actual academic outcomes, used ONLY to reconcile the feedback verdicts
        with the real at-risk ground truth (never as the label source itself).
    training_semesters : feature semesters eligible to be training rows.  When
        None, defaults to all semesters below the deployment semester.
    """
    if training_semesters is None:
        training_semesters = set(range(1, DEPLOYMENT_SEMESTER))

    total = len(feedback_rows)
    unique_students = sorted({r.get("student_id") for r in feedback_rows if r.get("student_id")})

    # ---- quality counters on the raw rows ----
    per_pred_actions: Dict[str, List[str]] = {}
    missing_student = 0
    invalid_action = 0
    non_m3 = 0
    for r in feedback_rows:
        sid = r.get("student_id")
        if sid is None or (isinstance(sid, float) and sid != sid) or str(sid).strip() == "":
            missing_student += 1
        pid = r.get("prediction_id")
        action = r.get("feedback_action")
        if pid is not None and action in ACTION_LABELS:
            per_pred_actions.setdefault(str(pid), []).append(action)
        if action not in VALID_ACTIONS:
            invalid_action += 1
        pred = predictions_map.get(str(pid)) if pid is not None else None
        if pred is not None and pred.get("prediction_type") != "m3":
            non_m3 += 1

    duplicate_cases = sum(1 for acts in per_pred_actions.values() if len(acts) > 1)
    conflicting_cases = sum(1 for acts in per_pred_actions.values() if len(set(acts)) > 1)

    # ---- resolve "latest verdict wins" (reuse project primitive) ----
    verdicts = latest_verdicts(feedback_rows)

    bound: List[BoundLabel] = []
    rejected: List[Dict[str, Any]] = []
    missing_period = 0
    unusable_reasons: List[str] = []

    for v in verdicts:
        sid = v.get("student_id")
        pid = str(v.get("prediction_id"))
        action = v.get("feedback_action")
        reject = {"feedback_id": v.get("feedback_id"), "prediction_id": pid,
                  "student_id": sid, "reason": "", "label": action}

        if action not in VALID_ACTIONS:
            reject["reason"] = f"invalid_action: {action}"
            rejected.append(reject)
            continue

        candidate_label = ACTION_LABELS[action]
        pred = predictions_map.get(pid)

        if not pred:
            reject["reason"] = "missing_prediction_record"
            rejected.append(reject)
            continue
        if pred.get("prediction_type") != "m3":
            reject["reason"] = f"non_m3_prediction_type: {pred.get('prediction_type')}"
            rejected.append(reject)
            non_m3 += 0  # counted above
            continue

        pv = pred.get("prediction_value") or {}
        if isinstance(pv, str):
            import json
            try:
                pv = json.loads(pv)
            except (ValueError, TypeError):
                pv = {}
        pred_sem = pv.get("semester_no")
        try:
            pred_sem = int(pred_sem) if pred_sem is not None else None
        except (TypeError, ValueError):
            pred_sem = None

        target_sem = pred_sem + 1 if pred_sem is not None else None

        # ---- usability / leakage guards ----
        reason = None
        temporal_usable = True
        if sid is None or (isinstance(sid, float) and sid != sid):
            reason = "missing_student_id"
            temporal_usable = False
        elif pred_sem is None:
            reason = "missing_prediction_period"
            missing_period += 1
            temporal_usable = False
        elif pred_sem >= DEPLOYMENT_SEMESTER:
            reason = "prediction_period_is_deployment"
            temporal_usable = False
        elif pred_sem not in training_semesters:
            reason = f"prediction_period_not_training: {pred_sem}"
            temporal_usable = False
        elif outcome_map.get(sid) is None or target_sem not in outcome_map[sid]:
            reason = f"target_semester_unobservable: {target_sem}"
            temporal_usable = False
        else:
            # target semester must NOT itself be deployment (can't observe yet)
            if target_sem >= DEPLOYMENT_SEMESTER:
                reason = f"target_semester_is_deployment: {target_sem}"
                temporal_usable = False

        actual_risk = (
            actual_at_risk_for_semester(outcome_map, sid, target_sem)
            if temporal_usable and sid is not None and target_sem is not None
            else None
        )
        agrees = (
            (candidate_label == actual_risk)
            if temporal_usable and actual_risk is not None
            else None
        )

        bl = BoundLabel(
            prediction_id=pid,
            student_id=sid,
            feedback_action=action,
            candidate_label=candidate_label,
            prediction_semester=pred_sem,
            target_semester=target_sem,
            feedback_timestamp=v.get("feedback_timestamp"),
            model_version=v.get("model_version"),
            actual_at_risk=actual_risk,
            agrees_with_ground_truth=agrees,
            temporal_usable=temporal_usable,
            rejection_reason=reason,
        )
        bound.append(bl)
        if not temporal_usable:
            reject["reason"] = reason or "unusable"
            rejected.append(reject)
            if reason and reason not in unusable_reasons:
                unusable_reasons.append(reason)

    m3_rows = sum(1 for r in feedback_rows if predictions_map.get(str(r.get("prediction_id")))
                  and predictions_map[str(r.get("prediction_id"))].get("prediction_type") == "m3")

    usable = [b for b in bound if b.temporal_usable]
    usable_labels = [b for b in usable if b.agrees_with_ground_truth is True]
    pos_students = sorted({b.student_id for b in usable_labels if b.candidate_label == 1})
    neg_students = sorted({b.student_id for b in usable_labels if b.candidate_label == 0})

    # Deterministic per-row output regardless of input ordering.  The project's
    # ``latest_verdicts`` primitive resolves equal-timestamp ties by input
    # position, so we reorder here so the audit's own output is stable.
    bound.sort(key=_bound_sort_key)
    rejected.sort(
        key=lambda r: (
            str(r.get("student_id") or ""),
            str(r.get("prediction_id") or ""),
            str(r.get("feedback_id") or ""),
        )
    )

    return LabelQualityReport(
        total_feedback_rows=total,
        unique_students_with_feedback=len(unique_students),
        m3_rows=m3_rows,
        rejected_rows=rejected,
        bound_labels=bound,
        duplicate_cases=duplicate_cases,
        conflicting_feedback_cases=conflicting_cases,
        missing_student_ids=missing_student,
        missing_prediction_period=missing_period,
        invalid_action_values=invalid_action,
        non_m3_prediction_rows=non_m3,
        usable_bound_labels=len(usable_labels),
        usable_positive_students=len(pos_students),
        usable_negative_students=len(neg_students),
        unusable_reasons=unusable_reasons,
    )


def render_quality_report(report: LabelQualityReport) -> str:
    """Render a human-readable quality report (deterministic formatting)."""
    s = report.summary()
    lines = [
        "================================================================",
        "V1 FEEDBACK-LABEL QUALITY AUDIT (prediction_feedback)",
        "================================================================",
        f"  Feedback rows:                    {report.total_feedback_rows}",
        f"  Unique students with feedback:    {report.unique_students_with_feedback}",
        f"  M3 judgement rows:                {report.m3_rows}",
        "",
        "--- Raw quality ---",
        f"  Duplicate feedback cases:         {report.duplicate_cases}",
        f"  Conflicting feedback cases:       {report.conflicting_feedback_cases}",
        f"  Missing student IDs:              {report.missing_student_ids}",
        f"  Missing prediction period:        {report.missing_prediction_period}",
        f"  Invalid action values:            {report.invalid_action_values}",
        f"  Rejected rows (unusable):         {len(report.rejected_rows)}",
        "",
        "--- Reconciliation (candidate label vs actual at-risk ground truth) ---",
        f"  Bound labels:                     {len(report.bound_labels)}",
        f"  Bound labels agreeing w/ truth:   {s['bound_labels_agreeing_with_ground_truth']}",
        f"  Bound labels conflicting w/ truth:{s['bound_labels_conflicting_with_ground_truth']}",
        f"  Bound labels not comparable:      {s['bound_labels_not_comparable']}",
        "",
        "--- Ready for M3 training? ---",
        f"  Usable (agreed) bound labels:     {report.usable_bound_labels}",
        f"  Usable positive students:         {report.usable_positive_students}",
        f"  Usable negative students:         {report.usable_negative_students}",
        f"  Positive students named:          {s['positive_students_where_feedback_matches_truth']}",
        "",
        "  Unusable reasons: " + (", ".join(sorted(report.unusable_reasons)) if report.unusable_reasons else "none"),
    ]
    return "\n".join(lines)
