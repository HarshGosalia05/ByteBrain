"""ML-08: Grounded Explainability + Prediction Context.

Provides typed, deterministic explanation contracts and a reusable
ExplanationService for the M1..M4 prediction models WITHOUT rerunning
inference or fabricating any information.

Design rules
------------
* Explanations are grounded in: (a) the ACTUAL input features that each
  model consumed, (b) model-supported metadata from the registry
  (algorithm / task / target / model_type), and (c) DOCUMENTED business
  rules from the repository. No confidence, probability, score ranges or
  feature-importance values are ever fabricated.
* Explanation generation is kept strictly separate from model inference.
  The service accepts the already-produced PredictionResult plus the raw
  feature DataFrames (or a DB pool to re-fetch the same inputs the
  prediction used). It never loads model artifacts.
* Only documented thresholds are referenced:
    - migrations/18_marks_remarks_derivation.sql: total marks =
      internal_marks + mid_sem_marks + end_sem_marks, denominator 140,
      percentage = total / 140 * 100, pass threshold 40%, performance
      bands 90/80/60/40, grade bands 90/80/70/60/50/40.
    - ml/src/m3/data.py: at-risk label when next-semester result in
      (FAIL, ATKT) OR next backlog_count > 0.
    - ml/src/m4/engine.py: rule-based score 0-100, levels
      High >= 75, Medium >= 50, documented weights academic 35 /
      growth 10 / career 25 / lifestyle 30.
* Output is structured data (dataclasses, JSON-safe) - never UI markup.
* Language is supportive and non-definitive for student-facing text
  ("model predicts", "projected", "may"), actionable for faculty-facing
  suggestions, and administrative aggregates are limited to the same
  documented rule context (rule_context) for admin-facing interpretation.
* Future-risk (M3) is explicitly separated from the deterministic risk
  register (risk_predictions) via Explanation.risk_scope.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Optional

import pandas as pd

try:
    from . import registry
except ImportError:  # pragma: no cover - direct execution fallback
    import registry

logger = logging.getLogger(__name__)

PREDICTION_TYPES = ("m1", "m2", "m3", "m4")

#: Information we deliberately DO NOT provide for these models.
NOT_PROVIDED = ("confidence", "probability", "feature_importance")

# ---------------------------------------------------------------------------
# Documented business rules (sources are named in the module docstring).
# ---------------------------------------------------------------------------
MARKS_SCALE_MAX = 70.0
TOTAL_MARKS_DENOMINATOR = 140.0
PASS_PERCENTAGE = 40.0

PERCENTAGE_BANDS = (
    (90.0, "Top", "Excellent performance"),
    (80.0, "Above Average", "Good performance"),
    (60.0, "Average", "Satisfactory performance"),
    (40.0, "Below Average", "Needs improvement"),
    (0.0, "Low Performer", "At risk - improvement required"),
)

GRADE_BANDS = (
    (90.0, "O"),
    (80.0, "A+"),
    (70.0, "A"),
    (60.0, "B+"),
    (50.0, "B"),
    (40.0, "C"),
)

M3_RISK_RULE = (
    "at-risk if the next-semester result is FAIL or ATKT "
    "OR the next-semester backlog count is greater than zero"
)

M4_LEVEL_THRESHOLDS = {"High": 75.0, "Medium": 50.0}
M4_WEIGHTS = {
    "academic_performance": 35,
    "growth_trend": 10,
    "career_preparedness": 25,
    "lifestyle_discipline": 30,
}
M4_SCORE_RANGE = (0.0, 100.0)

FAILING_RESULTS = ("FAIL", "ATKT")


# ---------------------------------------------------------------------------
# Typed explanation contracts.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ExplanationFactor:
    """A grounded positive or concern factor.

    kind: "positive" | "concern"
    source: "input" (actual feature value) | "business_rule" (documented
        threshold/band) | "model_metadata" (model-supported metadata)
    """

    kind: str
    source: str
    detail: str


@dataclass(frozen=True)
class ExplanationInput:
    """An actual input feature that the model consumed.

    present is False when the value is NULL/missing/unsupported; value is
    then None and nothing is claimed about it.
    """

    name: str
    value: Optional[Any]
    present: bool


@dataclass(frozen=True)
class ModelMetadata:
    """Model-supported metadata surfaced from the registry."""

    model_id: str
    model_type: str
    algorithm: str
    task: str
    target: str


@dataclass(frozen=True)
class M1Explanation:
    prediction_type: str = "m1"
    subject_id: str = ""
    subject_name: Optional[str] = None
    semester_no: int = 0
    predicted_end_sem_marks: float = 0.0
    clipped: bool = False
    projected_percentage: Optional[float] = None
    projected_band: Optional[str] = None
    inputs: list[ExplanationInput] = field(default_factory=list)
    factors: list[ExplanationFactor] = field(default_factory=list)
    interpretation: str = ""


@dataclass(frozen=True)
class M2Explanation:
    prediction_type: str = "m2"
    semester_no: int = 0
    predicted_next_semester_sgpa: float = 0.0
    predicted_next_semester_percentage: float = 0.0
    current_percentage: Optional[float] = None
    projected_delta_percentage: Optional[float] = None
    inputs: list[ExplanationInput] = field(default_factory=list)
    factors: list[ExplanationFactor] = field(default_factory=list)
    interpretation: str = ""


@dataclass(frozen=True)
class M3Explanation:
    prediction_type: str = "m3"
    risk_scope: str = "future_risk_prediction"
    risk_label: int = 0
    inputs: list[ExplanationInput] = field(default_factory=list)
    factors: list[ExplanationFactor] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    interpretation: str = ""


@dataclass(frozen=True)
class M4Explanation:
    prediction_type: str = "m4"
    readiness_score: float = 0.0
    readiness_level: str = ""
    positive_factors: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)
    inputs: list[ExplanationInput] = field(default_factory=list)
    interpretation: str = ""


@dataclass(frozen=True)
class ExplanationResult:
    """Structured explanation bundle for one prediction request."""

    model_id: str
    prediction_type: str
    student_id: str
    explanation_kind: str = "grounded_rule_based"
    model_metadata: ModelMetadata = field(default_factory=ModelMetadata)
    model_version: Optional[str] = None
    not_supported: list[str] = field(default_factory=lambda: list(NOT_PROVIDED))
    rule_context: dict[str, Any] = field(default_factory=dict)
    explanations: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Shared rule context (admin-facing interpretation reference).
# ---------------------------------------------------------------------------
_RULE_CONTEXTS = {
    "m1": {
        "marks_scale_max": MARKS_SCALE_MAX,
        "total_marks_denominator": TOTAL_MARKS_DENOMINATOR,
        "pass_percentage": PASS_PERCENTAGE,
        "performance_bands": {
            label: threshold for threshold, label, _ in PERCENTAGE_BANDS
        },
        "documentation": "migrations/18_marks_remarks_derivation.sql",
    },
    "m2": {
        "pass_percentage": PASS_PERCENTAGE,
        "targets": ["next_semester_sgpa", "next_semester_percentage"],
        "documentation": "migrations/18_marks_remarks_derivation.sql",
    },
    "m3": {
        "risk_definition": M3_RISK_RULE,
        "pass_percentage": PASS_PERCENTAGE,
        "documentation": "ml/src/m3/data.py",
    },
    "m4": {
        "score_range": list(M4_SCORE_RANGE),
        "level_thresholds": M4_LEVEL_THRESHOLDS,
        "weights": M4_WEIGHTS,
        "engine": "rule_based",
        "documentation": "ml/src/m4/engine.py",
    },
}


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------
def _to_scalar(value: Any) -> Any:
    if value is None:
        return None
    convert = getattr(value, "item", None)
    if convert is not None and not isinstance(value, (str, bytes)):
        try:
            value = convert()
        except (TypeError, ValueError):  # pragma: no cover - defensive
            pass
    if isinstance(value, Decimal):
        try:
            return float(value)
        except Exception:  # pragma: no cover - NaN/inf edge
            return None
    if isinstance(value, (int, float, bool, str)):
        return value
    return str(value)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _values_equal(a: Any, b: Any) -> bool:
    a, b = _to_scalar(a), _to_scalar(b)
    if a is None or b is None:
        return a is b
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _extract(row: Any, column: str) -> tuple[bool, Any]:
    if row is None:
        return (False, None)
    try:
        value = row[column]
    except (KeyError, IndexError, TypeError):
        return (False, None)
    if _is_missing(value):
        return (False, None)
    return (True, _to_scalar(value))


def _first_row(df: Any) -> Optional[Any]:
    if df is None or len(df) == 0:
        return None
    return df.iloc[0]


def _match(df: Any, criteria: dict[str, Any]) -> Optional[Any]:
    """Deterministic row match against criteria (None/NaN-safe)."""
    if df is None or len(df) == 0:
        return None
    for _, row in df.iterrows():
        ok = True
        for key, expected in criteria.items():
            if not _values_equal(row.get(key), expected):
                ok = False
                break
        if ok:
            return row
    return None


def _derived_percentage(internal: Any, mid: Any, end: Any) -> Optional[float]:
    if _is_missing(internal) or _is_missing(mid) or _is_missing(end):
        return None
    try:
        total = float(internal) + float(mid) + float(end)
        return round((total / TOTAL_MARKS_DENOMINATOR) * 100.0, 2)
    except (TypeError, ValueError):
        return None


def _performance_band(pct: float) -> str:
    for threshold, label, _ in PERCENTAGE_BANDS:
        if pct >= threshold:
            return label
    return PERCENTAGE_BANDS[-1][1]


def _grade_band(pct: float) -> str:
    for threshold, grade in GRADE_BANDS:
        if pct >= threshold:
            return grade
    return "F"


def _fmt(value: Any, ndigits: int = 1) -> str:
    try:
        return f"{float(value):.{ndigits}f}"
    except (TypeError, ValueError):
        return str(value)


def _split_factors(text: Any) -> list[str]:
    if text is None:
        return []
    return [part.strip() for part in str(text).split(";") if part.strip()]


def _model_metadata(model_id: str) -> ModelMetadata:
    entry = registry.get_entry(model_id)
    return ModelMetadata(
        model_id=entry.model_id,
        model_type=entry.model_type.value,
        algorithm=entry.algorithm,
        task=entry.task,
        target=entry.target,
    )


def _student_id_of(result: Any) -> str:
    if result.predictions and getattr(result.predictions[0], "student_id", None):
        return str(result.predictions[0].student_id)
    return getattr(result, "student_id", "") or ""


# ---------------------------------------------------------------------------
# Per-model grounded explanation builders.
# ---------------------------------------------------------------------------
def _explain_m1(
    pred: Any,
    performance: Any,
    attendance: Any,
    subjects: Any,
    students: Any,
) -> M1Explanation:
    sem = _to_scalar(pred.semester_no)
    perf_row = _match(
        performance,
        {"student_id": pred.student_id, "subject_id": pred.subject_id, "semester_no": pred.semester_no},
    )
    internal_present, internal = _extract(perf_row, "internal_marks")
    mid_present, mid = _extract(perf_row, "mid_sem_marks")
    subject_name = None
    enrollment_record_id = None
    if perf_row is not None:
        _, subject_name = _extract(perf_row, "subject_name")
        enrollment_record_id = _to_scalar(
            perf_row.get("enrollment_record_id") if perf_row is not None else None
        )

    att_row = (
        _match(attendance, {"enrollment_record_id": enrollment_record_id})
        if attendance is not None and enrollment_record_id is not None
        else None
    )
    att_present, att = _extract(att_row, "attendance_percentage")

    sub_row = _match(subjects, {"subject_id": pred.subject_id})
    stype_present, stype = _extract(sub_row, "subject_type")
    cred_present, cred = _extract(sub_row, "credits")

    prof_row = _first_row(students)
    dept_present, dept = _extract(prof_row, "department_name")
    gender_present, gender = _extract(prof_row, "gender")

    predicted = _to_scalar(pred.predicted_end_sem_marks)
    pct = _derived_percentage(internal, mid, predicted)
    band = _performance_band(pct) if pct is not None else None

    inputs = [
        ExplanationInput("internal_marks", internal, internal_present),
        ExplanationInput("mid_sem_marks", mid, mid_present),
        ExplanationInput("attendance_percentage", att, att_present),
        ExplanationInput("subject_type", stype, stype_present),
        ExplanationInput("credits", cred, cred_present),
        ExplanationInput("department_name", dept, dept_present),
        ExplanationInput("gender", gender, gender_present),
    ]

    factors: list[ExplanationFactor] = []
    if pct is not None:
        if pct >= 60.0:
            factors.append(
                ExplanationFactor(
                    "positive",
                    "business_rule",
                    f"Projected total percentage of {_fmt(pct)}% is in the documented '{band}' band (>= 60%).",
                )
            )
        elif pct < PASS_PERCENTAGE:
            factors.append(
                ExplanationFactor(
                    "concern",
                    "business_rule",
                    f"Projected total percentage of {_fmt(pct)}% is below the documented pass threshold of {PASS_PERCENTAGE:.0f}%.",
                )
            )
    if not internal_present or not mid_present:
        factors.append(
            ExplanationFactor(
                "concern",
                "input",
                "Interpretation is limited because internal or mid-semester marks are missing.",
            )
        )

    subject_label = subject_name or pred.subject_id
    parts = [
        f"M1 predicts end-semester marks of {_fmt(predicted)} (scale 0-{MARKS_SCALE_MAX:.0f}) "
        f"for {subject_label} in semester {sem}."
    ]
    if pct is not None:
        parts.append(
            f"Combined with the recorded internal ({_fmt(internal)}) and mid-semester ({_fmt(mid)}) marks, "
            f"the projected total percentage is {_fmt(pct)}% "
            f"({band}, projected grade {_grade_band(pct)})."
        )
        if pct < PASS_PERCENTAGE:
            parts.append(
                f"The projected level is below the documented pass threshold of {PASS_PERCENTAGE:.0f}%; "
                "focusing on upcoming assessments can change this projected outcome."
            )
    else:
        parts.append(
            "The projected total percentage could not be computed because one or more input marks are missing."
        )
    if getattr(pred, "clipped", False):
        parts.append(f"The raw prediction was outside the 0-{MARKS_SCALE_MAX:.0f} range and was clipped.")
    interpretation = " ".join(parts)

    return M1Explanation(
        subject_id=pred.subject_id,
        subject_name=subject_name,
        semester_no=sem,
        predicted_end_sem_marks=float(predicted) if predicted is not None else 0.0,
        clipped=bool(getattr(pred, "clipped", False)),
        projected_percentage=pct,
        projected_band=band,
        inputs=inputs,
        factors=factors,
        interpretation=interpretation,
    )


def _explain_m2(pred: Any, summary: Any, students: Any) -> M2Explanation:
    sem = _to_scalar(pred.semester_no)
    row = _match(summary, {"student_id": pred.student_id, "semester_no": pred.semester_no})
    pct_present, pct = _extract(row, "semester_percentage")
    sgpa_present, sgpa = _extract(row, "semester_sgpa")
    att_present, att = _extract(row, "semester_attendance_percentage")
    back_present, back = _extract(row, "backlog_count")

    pred_pct = _to_scalar(pred.predicted_next_semester_percentage)
    delta = round(pred_pct - float(pct), 2) if pct is not None else None

    inputs = [
        ExplanationInput("semester_percentage", pct, pct_present),
        ExplanationInput("semester_sgpa", sgpa, sgpa_present),
        ExplanationInput("semester_attendance_percentage", att, att_present),
        ExplanationInput("backlog_count", back, back_present),
    ]

    factors: list[ExplanationFactor] = []
    if pred_pct is not None:
        if pred_pct >= PASS_PERCENTAGE:
            factors.append(
                ExplanationFactor(
                    "positive",
                    "business_rule",
                    f"Predicted next-semester percentage ({_fmt(pred_pct)}%) is at or above the documented pass threshold of {PASS_PERCENTAGE:.0f}%.",
                )
            )
        else:
            factors.append(
                ExplanationFactor(
                    "concern",
                    "business_rule",
                    f"Predicted next-semester percentage ({_fmt(pred_pct)}%) is below the documented pass threshold of {PASS_PERCENTAGE:.0f}%.",
                )
            )
    if delta is not None:
        if delta >= 0:
            factors.append(
                ExplanationFactor(
                    "positive",
                    "input",
                    f"Projected percentage is {delta:+.2f} points relative to the current semester ({_fmt(pct)}%).",
                )
            )
        else:
            factors.append(
                ExplanationFactor(
                    "concern",
                    "input",
                    f"Projected percentage is {delta:+.2f} points relative to the current semester ({_fmt(pct)}%).",
                )
            )

    if pct is not None:
        trend = (
            f"The predicted next-semester percentage is {delta:+.2f} points "
            f"relative to the current semester percentage ({_fmt(pct)}%)."
        )
    else:
        trend = "The current semester percentage is unavailable, so no trend comparison can be made."

    interpretation = (
        f"M2 predicts a next-semester SGPA of {_fmt(pred.predicted_next_semester_sgpa)} and a percentage of "
        f"{_fmt(pred_pct)}% based on semester {sem} data. {trend}"
    )

    return M2Explanation(
        semester_no=sem,
        predicted_next_semester_sgpa=float(pred.predicted_next_semester_sgpa),
        predicted_next_semester_percentage=float(pred_pct) if pred_pct is not None else 0.0,
        current_percentage=pct,
        projected_delta_percentage=delta,
        inputs=inputs,
        factors=factors,
        interpretation=interpretation,
    )


def _explain_m3(pred: Any, summary: Any, students: Any) -> M3Explanation:
    row = _match(summary, {"student_id": pred.student_id, "semester_no": pred.semester_no})
    back_present, back = _extract(row, "backlog_count")
    result_present, result = _extract(row, "semester_result")
    pct_present, pct = _extract(row, "semester_percentage")
    sgpa_present, sgpa = _extract(row, "semester_sgpa")
    att_present, att = _extract(row, "semester_attendance_percentage")

    inputs = [
        ExplanationInput("backlog_count", back, back_present),
        ExplanationInput("semester_result", result, result_present),
        ExplanationInput("semester_percentage", pct, pct_present),
        ExplanationInput("semester_sgpa", sgpa, sgpa_present),
        ExplanationInput("semester_attendance_percentage", att, att_present),
    ]

    factors: list[ExplanationFactor] = []
    suggestions: list[str] = []
    if back_present and back > 0:
        factors.append(
            ExplanationFactor(
                "concern", "input", f"{back} active backlog(s) recorded for the current semester."
            )
        )
        suggestions.append("Plan backlog-clearance academic support.")
    if result_present and str(result).upper() in FAILING_RESULTS:
        factors.append(
            ExplanationFactor(
                "concern", "input", f"The current semester result is {result}."
            )
        )
        suggestions.append("Review the academic recovery plan for the current semester result.")
    if pct_present and pct < PASS_PERCENTAGE:
        factors.append(
            ExplanationFactor(
                "concern",
                "business_rule",
                f"The current semester percentage ({_fmt(pct)}%) is below the documented {PASS_PERCENTAGE:.0f}% band.",
            )
        )
        suggestions.append("Prioritize academic support for core performance.")
    elif pct_present and pct >= 60.0:
        factors.append(
            ExplanationFactor(
                "positive",
                "business_rule",
                f"The current semester percentage ({_fmt(pct)}%) is in the documented Average-or-above band (>= 60%).",
            )
        )

    risk = int(bool(getattr(pred, "is_at_risk_next_sem", 0)))
    if risk:
        signals = "; ".join(f.detail for f in factors if f.kind == "concern") or "the available input signals"
        interpretation = (
            f"Based on current signals ({signals}), the M3 model predicts a higher chance of at-risk status "
            f"next semester. This is a future-risk model prediction and remains separate from the deterministic "
            f"risk register (risk_predictions)."
        )
    else:
        interpretation = (
            "The M3 model does not currently flag at-risk status for next semester based on the available "
            "signals. This is a future-risk model prediction and remains separate from the deterministic "
            "risk register (risk_predictions)."
        )

    return M3Explanation(
        risk_label=risk,
        inputs=inputs,
        factors=factors,
        suggestions=suggestions,
        interpretation=interpretation,
    )


def _explain_m4(
    pred: Any,
    students: Any,
    semester: Any,
    career: Any,
    lifestyle: Any,
) -> M4Explanation:
    _ = students
    inputs: list[ExplanationInput] = []

    avg_pct = None
    total_back = None
    if semester is not None and len(semester) > 0:
        try:
            if "semester_percentage" in semester.columns:
                avg_pct = round(float(semester["semester_percentage"].mean()), 2)
            if "backlog_count" in semester.columns:
                total_back = int(semester["backlog_count"].sum())
        except (TypeError, ValueError):  # pragma: no cover - defensive
            avg_pct, total_back = None, None
    inputs.append(ExplanationInput("avg_semester_percentage", avg_pct, avg_pct is not None))
    inputs.append(ExplanationInput("total_prior_backlogs", total_back, total_back is not None))

    career_row = _first_row(career)
    for column in (
        "internship_completed",
        "higher_studies_interest",
        "entrepreneurship_interest",
        "certification_interest",
    ):
        present, value = _extract(career_row, column)
        inputs.append(ExplanationInput(column, value, present))

    lifestyle_row = _first_row(lifestyle)
    for column in (
        "daily_study_hours",
        "average_sleep_hours",
        "stress_level",
        "mental_wellbeing",
        "physical_activity",
        "attendance_commitment",
    ):
        present, value = _extract(lifestyle_row, column)
        inputs.append(ExplanationInput(column, value, present))

    positive_factors = _split_factors(pred.positive_factors)
    risk_factors = _split_factors(pred.risk_factors)
    score = _to_scalar(pred.career_readiness_score)
    level = str(pred.career_readiness_level)

    interpretation = (
        f"M4 computes a rule-based career-readiness score of {_fmt(score)}/100, mapped to the "
        f"'{level}' level. Documented thresholds: Medium >= 50, High >= 75. M4 is a "
        f"deterministic rule-based scoring engine, not a trained ML model."
    )

    return M4Explanation(
        readiness_score=float(score) if score is not None else 0.0,
        readiness_level=level,
        positive_factors=positive_factors,
        risk_factors=risk_factors,
        inputs=inputs,
        interpretation=interpretation,
    )


# ---------------------------------------------------------------------------
# Service.
# ---------------------------------------------------------------------------
class ExplanationService:
    """Reusable, grounded explanation service for M1..M4 predictions.

    raw: the exact feature DataFrames the prediction consumed
    (see PredictionService.fetch_*_raw_data). If not supplied, they are
    re-fetched from the DB when a pool is configured. Explanation
    generation never runs inference or loads model artifacts.
    """

    def __init__(self, pool: Any = None):
        self._pool = pool

    async def explain_m1(
        self,
        result: Any,
        raw: Any = None,
        model_version: Optional[str] = None,
    ) -> ExplanationResult:
        performance, attendance, subjects, students = await self._raw_m1(result, raw)
        items = [
            _explain_m1(pred, performance, attendance, subjects, students)
            for pred in result.predictions
        ]
        return ExplanationResult(
            model_id="m1",
            prediction_type="m1",
            student_id=_student_id_of(result),
            model_metadata=_model_metadata("m1"),
            model_version=model_version,
            rule_context=dict(_RULE_CONTEXTS["m1"]),
            explanations=items,
        )

    async def explain_m2(
        self,
        result: Any,
        raw: Any = None,
        model_version: Optional[str] = None,
    ) -> ExplanationResult:
        summary, students = await self._raw_m2m3(result, raw)
        items = [_explain_m2(pred, summary, students) for pred in result.predictions]
        return ExplanationResult(
            model_id="m2",
            prediction_type="m2",
            student_id=_student_id_of(result),
            model_metadata=_model_metadata("m2"),
            model_version=model_version,
            rule_context=dict(_RULE_CONTEXTS["m2"]),
            explanations=items,
        )

    async def explain_m3(
        self,
        result: Any,
        raw: Any = None,
        model_version: Optional[str] = None,
    ) -> ExplanationResult:
        summary, students = await self._raw_m2m3(result, raw)
        items = [_explain_m3(pred, summary, students) for pred in result.predictions]
        return ExplanationResult(
            model_id="m3",
            prediction_type="m3",
            student_id=_student_id_of(result),
            model_metadata=_model_metadata("m3"),
            model_version=model_version,
            rule_context=dict(_RULE_CONTEXTS["m3"]),
            explanations=items,
        )

    async def explain_m4(
        self,
        result: Any,
        raw: Any = None,
        model_version: Optional[str] = None,
    ) -> ExplanationResult:
        students, semester, career, lifestyle = await self._raw_m4(result, raw)
        items = [
            _explain_m4(pred, students, semester, career, lifestyle)
            for pred in result.predictions
        ]
        return ExplanationResult(
            model_id="m4",
            prediction_type="m4",
            student_id=_student_id_of(result),
            model_metadata=_model_metadata("m4"),
            model_version=model_version,
            rule_context=dict(_RULE_CONTEXTS["m4"]),
            explanations=items,
        )

    async def explain(
        self,
        result: Any,
        raw: Any = None,
        model_version: Optional[str] = None,
    ) -> ExplanationResult:
        model_id = getattr(result, "model_id", None)
        if model_id not in PREDICTION_TYPES:
            raise ValueError(
                f"Unsupported prediction type '{model_id}' for explanation; "
                f"expected one of {', '.join(PREDICTION_TYPES)}."
            )
        method = getattr(self, f"explain_{model_id}")
        return await method(result, raw=raw, model_version=model_version)

    # -- raw-data resolution -------------------------------------------------
    async def _raw_m1(self, result: Any, raw: Any) -> tuple:
        if raw is not None:
            if not isinstance(raw, (tuple, list)) or len(raw) != 4:
                raise ValueError(
                    "m1 raw data must be (performance, attendance, subjects, students)."
                )
            return raw
        student_id = _student_id_of(result)
        if not student_id:
            raise ValueError("Cannot fetch inputs: prediction has no student_id.")
        return await self._fetch(
            student_id,
            "_fetch_student_performance",
            "_fetch_student_attendance",
            "_fetch_subject_type",
            "_fetch_student_profile",
        )

    async def _raw_m2m3(self, result: Any, raw: Any) -> tuple:
        if raw is not None:
            if not isinstance(raw, (tuple, list)) or len(raw) != 2:
                raise ValueError("m2/m3 raw data must be (summary, students).")
            return raw
        student_id = _student_id_of(result)
        if not student_id:
            raise ValueError("Cannot fetch inputs: prediction has no student_id.")
        return await self._fetch(
            student_id,
            "_fetch_student_semester_summary",
            "_fetch_student_profile",
        )

    async def _raw_m4(self, result: Any, raw: Any) -> tuple:
        if raw is not None:
            if not isinstance(raw, (tuple, list)) or len(raw) != 4:
                raise ValueError(
                    "m4 raw data must be (students, semester, career, lifestyle)."
                )
            return raw
        student_id = _student_id_of(result)
        if not student_id:
            raise ValueError("Cannot fetch inputs: prediction has no student_id.")
        return await self._fetch(
            student_id,
            "_fetch_student_profile",
            "_fetch_student_semester_summary",
            "_fetch_career_preferences",
            "_fetch_lifestyle_survey",
        )

    async def _fetch(self, student_id: str, *fetch_names: str) -> tuple:
        if self._pool is None:
            raise ValueError(
                "No raw data supplied and no database pool configured for fetching inputs."
            )
        try:
            from ml.src import prediction_service as ps
        except ImportError:  # pragma: no cover - running from ml/src directly
            import prediction_service as ps
        return tuple([await getattr(ps, name)(self._pool, student_id) for name in fetch_names])


def explain_result(
    result: Any,
    raw: Any = None,
    model_version: Optional[str] = None,
    pool: Any = None,
) -> Any:
    """Convenience factory delegating to ExplanationService."""
    import asyncio

    return asyncio.run(ExplanationService(pool).explain(result, raw=raw, model_version=model_version))
