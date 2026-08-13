"""ML-08 focused tests for grounded explainability (ml/src/explain.py).

Covers the ML_GLOBAL_RULES ML-08 requirements:
  - grounded explanations (only actual inputs + documented business rules)
  - NULL/missing inputs (present=False, no fabricated values)
  - unsupported/missing factors (empty factors/suggestions, no invention)
  - M1-M4 output structure (typed, JSON-safe, no UI markup)
  - no fabricated confidence/probability/ranges/feature importance
  - deterministic output
  - current-risk (risk_predictions) vs future-risk (M3) separation
  - registry-backed model metadata and unknown-model rejection
"""

import os
import sys
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import asyncio

import pandas as pd
import pytest

import explain
import inference
from explain import (
    ExplanationInput,
    ExplanationResult,
    ExplanationService,
    M1Explanation,
    M2Explanation,
    M3Explanation,
    M4Explanation,
    NOT_PROVIDED,
)


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------

STUDENT = "STU000001"


def _students(overrides=None):
    row = {
        "student_id": STUDENT,
        "enrollment_no": "ENR-001",
        "full_name": "Ada Student",
        "department_name": "Computer Engineering",
        "current_semester": 3,
        "gender": "F",
    }
    if overrides:
        row.update(overrides)
    return pd.DataFrame([row])


def _m1_performance(overrides=None):
    row = {
        "student_id": STUDENT,
        "enrollment_record_id": 101,
        "subject_id": "SUB-01",
        "subject_name": "Data Structures",
        "semester_no": 2,
        "internal_marks": 30.0,
        "mid_sem_marks": 30.0,
    }
    if overrides:
        row.update(overrides)
    return pd.DataFrame([row])


def _m1_attendance(overrides=None):
    row = {
        "enrollment_record_id": 101,
        "attendance_percentage": 85.0,
    }
    if overrides:
        row.update(overrides)
    return pd.DataFrame([row])


def _m1_subjects(overrides=None):
    row = {
        "subject_id": "SUB-01",
        "subject_type": "THEORY",
        "credits": 4,
    }
    if overrides:
        row.update(overrides)
    return pd.DataFrame([row])


def _m1_result(clipped=False, student_id=STUDENT, subject_id="SUB-01"):
    return inference.PredictionResult(
        model_id="m1",
        predictions=[
            inference.M1Prediction(
                student_id=student_id,
                subject_id=subject_id,
                semester_no=2,
                predicted_end_sem_marks=45.0,
                clipped=clipped,
            )
        ],
        input_row_count=1,
        prediction_count=1,
    )


def _m2_summary(overrides=None):
    row = {
        "student_id": STUDENT,
        "semester_no": 2,
        "subjects_registered": 6,
        "credits_registered": 24,
        "credits_earned": 22,
        "semester_total_marks": 520.0,
        "semester_percentage": 68.0,
        "semester_sgpa": 7.2,
        "semester_attendance_percentage": 78.0,
        "backlog_count": 0,
        "semester_result": "PASS",
    }
    if overrides:
        row.update(overrides)
    return pd.DataFrame([row])


def _m2_result(student_id=STUDENT, sem=2):
    return inference.PredictionResult(
        model_id="m2",
        predictions=[
            inference.M2Prediction(
                student_id=student_id,
                semester_no=sem,
                predicted_next_semester_sgpa=7.5,
                predicted_next_semester_percentage=70.0,
            )
        ],
        input_row_count=1,
        prediction_count=1,
    )


def _m3_result(risk=1, student_id=STUDENT, sem=2):
    return inference.PredictionResult(
        model_id="m3",
        predictions=[
            inference.M3Prediction(
                student_id=student_id,
                semester_no=sem,
                is_at_risk_next_sem=risk,
            )
        ],
        input_row_count=1,
        prediction_count=1,
    )


def _m4_semester(overrides=None):
    row = {
        "student_id": STUDENT,
        "semester_no": 2,
        "semester_percentage": 68.0,
        "semester_sgpa": 7.2,
        "backlog_count": 0,
    }
    if overrides:
        row.update(overrides)
    return pd.DataFrame([row])


def _m4_career(overrides=None):
    row = {
        "student_id": STUDENT,
        "internship_completed": "YES",
        "certification_interest": "YES",
        "higher_studies_interest": "NO",
        "entrepreneurship_interest": "NO",
    }
    if overrides:
        row.update(overrides)
    return pd.DataFrame([row])


def _m4_lifestyle(overrides=None):
    row = {
        "student_id": STUDENT,
        "daily_study_hours": 4.0,
        "average_sleep_hours": 7.0,
        "stress_level": "MODERATE",
        "mental_wellbeing": "GOOD",
        "physical_activity": "REGULAR",
        "attendance_commitment": "GOOD",
    }
    if overrides:
        row.update(overrides)
    return pd.DataFrame([row])


def _m4_result(score=80.0, level="High", student_id=STUDENT):
    return inference.PredictionResult(
        model_id="m4",
        predictions=[
            inference.M4Score(
                student_id=student_id,
                enrollment_no="ENR-001",
                full_name="Ada Student",
                department_name="Computer Engineering",
                current_semester=3,
                career_readiness_score=score,
                career_readiness_level=level,
                positive_factors="Academic performance good; Strong career preparedness",
                risk_factors="Low growth trend",
            )
        ],
        input_row_count=1,
        prediction_count=1,
    )


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Structure / JSON-safety / metadata
# ---------------------------------------------------------------------------


def test_explain_result_shape_and_json_safe():
    svc = ExplanationService()
    result = run(svc.explain_m1(_m1_result(), raw=(_m1_performance(), _m1_attendance(), _m1_subjects(), _students())))
    assert isinstance(result, ExplanationResult)
    assert result.model_id == "m1"
    assert result.student_id == STUDENT
    assert len(result.explanations) == 1
    item = result.explanations[0]
    assert isinstance(item, M1Explanation)
    d = result.to_dict()
    assert isinstance(d, dict)
    assert d["model_metadata"]["algorithm"]
    assert d["model_metadata"]["model_type"] == "joblib"


def test_explain_m4_is_rule_based_metadata():
    svc = ExplanationService()
    result = run(svc.explain_m4(_m4_result(), raw=(_students(), _m4_semester(), _m4_career(), _m4_lifestyle())))
    assert result.model_metadata.model_type == "rule_based"
    assert result.rule_context["engine"] == "rule_based"
    assert isinstance(result.explanations[0], M4Explanation)


def test_unknown_prediction_type_rejected():
    class Fake:
        model_id = "nope"
        predictions = []

    with pytest.raises(ValueError):
        run(ExplanationService().explain(Fake()))


def test_requires_raw_data_or_pool():
    with pytest.raises(ValueError):
        run(ExplanationService().explain_m1(_m1_result()))
    with pytest.raises(ValueError):
        run(ExplanationService().explain_m4(_m4_result()))


def test_m1_explain_returns_typed_structure():
    svc = ExplanationService()
    result = run(svc.explain_m1(_m1_result(), raw=(_m1_performance(), _m1_attendance(), _m1_subjects(), _students())))
    item = result.explanations[0]
    assert item.subject_id == "SUB-01"
    assert item.subject_name == "Data Structures"
    assert item.predicted_end_sem_marks == 45.0
    assert item.inputs  # actual input features surfaced
    assert all(isinstance(i, ExplanationInput) for i in item.inputs)


# ---------------------------------------------------------------------------
# Grounded explanations - actual input values and documented rules
# ---------------------------------------------------------------------------


def test_m1_grounded_inputs_used_in_interpretation():
    svc = ExplanationService()
    result = run(svc.explain_m1(_m1_result(), raw=(_m1_performance(), _m1_attendance(), _m1_subjects(), _students())))
    item = result.explanations[0]
    # Documented formula: internal(30) + mid(30) + predicted end(45) = 105; 105/140*100 = 75.0
    assert item.projected_percentage == 75.0
    # Documented performance_category bands: >=90 Top, >=80 Above Average,
    # >=60 Average, >=40 Below Average, <40 Low Performer -> 75.0 => "Average"
    assert item.projected_band == "Average"
    assert "75.0%" in item.interpretation
    assert "45.0" in item.interpretation  # the predicted value itself
    inputs = {i.name: i for i in item.inputs}
    assert inputs["internal_marks"].present and inputs["internal_marks"].value == 30.0
    assert inputs["attendance_percentage"].present and inputs["attendance_percentage"].value == 85.0
    assert inputs["subject_type"].present and inputs["subject_type"].value == "THEORY"


def test_m1_positive_factor_from_documented_band():
    svc = ExplanationService()
    result = run(svc.explain_m1(_m1_result(), raw=(_m1_performance(), _m1_attendance(), _m1_subjects(), _students())))
    kinds = [f.kind for f in result.explanations[0].factors]
    sources = [f.source for f in result.explanations[0].factors]
    assert "positive" in kinds
    assert "business_rule" in sources


def test_m1_concern_factor_below_documented_pass_threshold():
    perf = _m1_performance({"internal_marks": 15.0, "mid_sem_marks": 12.0})
    # total 27 + 40 = 67 -> 47.86% still passes; use a low prediction instead
    pred = inference.PredictionResult(
        model_id="m1",
        predictions=[
            inference.M1Prediction(
                student_id=STUDENT, subject_id="SUB-01", semester_no=2,
                predicted_end_sem_marks=20.0, clipped=False,
            )
        ],
        input_row_count=1,
        prediction_count=1,
    )
    svc = ExplanationService()
    result = run(svc.explain_m1(pred, raw=(perf, _m1_attendance(), _m1_subjects(), _students())))
    item = result.explanations[0]
    # (15 + 12 + 20) / 140 * 100 = 33.57 -> below 40 -> concern
    assert item.projected_percentage < 40.0
    assert any(f.kind == "concern" and f.source == "business_rule" for f in item.factors)
    assert "pass threshold" in item.interpretation


def test_m2_grounded_trend_and_inputs():
    svc = ExplanationService()
    result = run(svc.explain_m2(_m2_result(), raw=(_m2_summary(), _students())))
    item = result.explanations[0]
    assert item.current_percentage == 68.0
    assert item.projected_delta_percentage == pytest.approx(2.0)
    assert item.predicted_next_semester_sgpa == 7.5
    inputs = {i.name: i for i in item.inputs}
    assert inputs["semester_percentage"].value == 68.0
    assert inputs["backlog_count"].value == 0
    # 70 >= 40 documented pass threshold -> positive factor
    assert any(f.kind == "positive" and f.source == "business_rule" for f in item.factors)


def test_m3_grounded_risk_signals_and_suggestions():
    summary = _m2_summary({"backlog_count": 3, "semester_result": "FAIL", "semester_percentage": 35.0})
    svc = ExplanationService()
    result = run(svc.explain_m3(_m3_result(risk=1), raw=(summary, _students())))
    item = result.explanations[0]
    assert item.risk_label == 1
    detail_text = " ".join(f.detail for f in item.factors)
    assert "3 active backlog(s)" in detail_text
    assert "result is FAIL" in detail_text
    assert "below the documented 40%" in detail_text
    assert item.suggestions
    assert "future-risk" in item.interpretation


def test_m4_grounded_inputs_and_engine_factors():
    svc = ExplanationService()
    result = run(svc.explain_m4(_m4_result(), raw=(_students(), _m4_semester(), _m4_career(), _m4_lifestyle())))
    item = result.explanations[0]
    assert item.readiness_score == 80.0
    assert item.readiness_level == "High"
    # engine-provided factors are surfaced unchanged
    assert item.positive_factors == ["Academic performance good", "Strong career preparedness"]
    assert item.risk_factors == ["Low growth trend"]
    assert "not a trained ML model" in item.interpretation
    inputs = {i.name: i for i in item.inputs}
    assert inputs["internship_completed"].value == "YES"
    assert inputs["daily_study_hours"].value == 4.0
    assert inputs["avg_semester_percentage"].value == 68.0


# ---------------------------------------------------------------------------
# NULL / missing inputs
# ---------------------------------------------------------------------------


def test_m1_missing_marks_are_not_fabricated():
    perf = _m1_performance({"internal_marks": None, "mid_sem_marks": float("nan")})
    svc = ExplanationService()
    result = run(svc.explain_m1(_m1_result(), raw=(perf, _m1_attendance(), _m1_subjects(), _students())))
    item = result.explanations[0]
    inputs = {i.name: i for i in item.inputs}
    assert inputs["internal_marks"].present is False
    assert inputs["mid_sem_marks"].present is False
    assert item.projected_percentage is None
    assert item.projected_band is None
    # limited-interpretation concern surfaced instead of invented numbers
    assert any(f.source == "input" and "missing" in f.detail for f in item.factors)
    assert "could not be computed" in item.interpretation


def test_m1_missing_subject_metadata_no_crash():
    perf = _m1_performance()
    subjects = _m1_subjects({"subject_id": "SUB-OTHER"})  # does not match
    svc = ExplanationService()
    result = run(svc.explain_m1(_m1_result(), raw=(perf, _m1_attendance(), subjects, _students())))
    item = result.explanations[0]
    inputs = {i.name: i for i in item.inputs}
    assert inputs["subject_type"].present is False
    assert inputs["credits"].present is False


def test_m1_empty_raw_dfs_no_crash():
    svc = ExplanationService()
    result = run(svc.explain_m1(_m1_result(), raw=(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())))
    item = result.explanations[0]
    assert item.projected_percentage is None
    assert all(i.present is False for i in item.inputs)


def test_m3_all_signals_missing_yields_empty_factors_and_no_risk():
    summary = _m2_summary({
        "backlog_count": pd.NA,
        "semester_result": pd.NA,
        "semester_percentage": pd.NA,
        "semester_sgpa": pd.NA,
        "semester_attendance_percentage": pd.NA,
    })
    svc = ExplanationService()
    result = run(svc.explain_m3(_m3_result(risk=0), raw=(summary, _students())))
    item = result.explanations[0]
    assert item.factors == []
    assert item.suggestions == []
    assert item.risk_label == 0
    assert all(i.present is False for i in item.inputs)


def test_m4_missing_lifestyle_and_career_data_no_crash():
    svc = ExplanationService()
    result = run(svc.explain_m4(_m4_result(), raw=(_students(), _m4_semester(), pd.DataFrame(), pd.DataFrame())))
    item = result.explanations[0]
    inputs = {i.name: i for i in item.inputs}
    assert inputs["daily_study_hours"].present is False
    assert inputs["internship_completed"].present is False
    assert inputs["avg_semester_percentage"].value == 68.0  # still grounded
    assert item.readiness_score == 80.0


# ---------------------------------------------------------------------------
# No fabricated confidence / probability / ranges / feature importance
# ---------------------------------------------------------------------------


def test_not_supported_fields_are_explicit_and_absent():
    assert set(NOT_PROVIDED) == {"confidence", "probability", "feature_importance"}
    svc = ExplanationService()
    result = run(svc.explain_m1(_m1_result(), raw=(_m1_performance(), _m1_attendance(), _m1_subjects(), _students())))
    for word in NOT_PROVIDED:
        assert word in result.not_supported
        assert word not in result.to_dict()
        # must not leak into any explanation payload
        assert word not in result.to_dict()["explanations"][0]


def test_interpretations_make_no_range_or_probability_claims():
    svc = ExplanationService()
    cases = [
        svc.explain_m1(_m1_result(), raw=(_m1_performance(), _m1_attendance(), _m1_subjects(), _students())),
        svc.explain_m2(_m2_result(), raw=(_m2_summary(), _students())),
        svc.explain_m3(_m3_result(risk=1), raw=(_m2_summary({"backlog_count": 2, "semester_result": "ATKT", "semester_percentage": 42.0}), _students())),
        svc.explain_m4(_m4_result(), raw=(_students(), _m4_semester(), _m4_career(), _m4_lifestyle())),
    ]
    for coro in cases:
        result = run(coro)
        for item in result.explanations:
            low = item.interpretation.lower()
            assert "confidence" not in low
            assert "probability" not in low
            assert "likely to fail" not in low
            assert "will fail" not in low
            assert "% chance" not in low


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "coro_factory, raw_factory",
    [
        (lambda: _m1_result(), lambda: (_m1_performance(), _m1_attendance(), _m1_subjects(), _students())),
        (lambda: _m2_result(), lambda: (_m2_summary(), _students())),
        (lambda: _m3_result(1), lambda: (_m2_summary({"backlog_count": 1, "semester_result": "FAIL", "semester_percentage": 38.0}), _students())),
        (lambda: _m4_result(), lambda: (_students(), _m4_semester(), _m4_career(), _m4_lifestyle())),
    ],
)
def test_explanations_are_deterministic(coro_factory, raw_factory):
    svc = ExplanationService()
    first = run(svc.explain(coro_factory(), raw=raw_factory()))
    second = run(svc.explain(coro_factory(), raw=raw_factory()))
    assert first.to_dict() == second.to_dict()


def test_m4_explanations_are_deterministic_across_runs():
    svc = ExplanationService()
    raw = (_students(), _m4_semester(), _m4_career(), _m4_lifestyle())
    a = run(svc.explain_m4(_m4_result(), raw=raw))
    b = run(svc.explain_m4(_m4_result(), raw=raw))
    assert a.to_dict() == b.to_dict()


# ---------------------------------------------------------------------------
# Current-risk vs future-risk separation
# ---------------------------------------------------------------------------


def test_m3_is_future_risk_and_separate_from_risk_register():
    svc = ExplanationService()
    result = run(svc.explain_m3(_m3_result(risk=1), raw=(_m2_summary({"backlog_count": 2, "semester_result": "FAIL", "semester_percentage": 42.0}), _students())))
    item = result.explanations[0]
    assert item.risk_scope == "future_risk_prediction"
    assert "separate from the deterministic risk register" in item.interpretation
    assert "risk_predictions" in item.interpretation
    assert "future-risk" in item.interpretation


def test_m3_not_flagged_no_invented_risk():
    svc = ExplanationService()
    summary = _m2_summary({"backlog_count": 0, "semester_result": "PASS", "semester_percentage": 70.0})
    result = run(svc.explain_m3(_m3_result(risk=0), raw=(summary, _students())))
    item = result.explanations[0]
    assert item.risk_label == 0
    assert item.factors and all(f.kind == "positive" for f in item.factors)
    assert item.suggestions == []
    assert "does not currently flag at-risk status" in item.interpretation


# ---------------------------------------------------------------------------
# No inference / no artifacts
# ---------------------------------------------------------------------------


def test_explanation_does_not_touch_model_artifacts(monkeypatch):
    called = {"load": False}

    def boom(*a, **k):
        called["load"] = True
        raise AssertionError("explanation must never load model artifacts")

    monkeypatch.setattr(inference.InferenceService, "_load_artifact", boom)
    svc = ExplanationService()
    result = run(svc.explain_m1(_m1_result(), raw=(_m1_performance(), _m1_attendance(), _m1_subjects(), _students())))
    assert called["load"] is False
    assert result.explanations[0].projected_percentage == 75.0


def test_rule_context_documents_its_source():
    svc = ExplanationService()
    m1 = run(svc.explain_m1(_m1_result(), raw=(_m1_performance(), _m1_attendance(), _m1_subjects(), _students())))
    assert m1.rule_context["documentation"] == "migrations/18_marks_remarks_derivation.sql"
    assert m1.rule_context["pass_percentage"] == 40.0
    m4 = run(svc.explain_m4(_m4_result(), raw=(_students(), _m4_semester(), _m4_career(), _m4_lifestyle())))
    assert m4.rule_context["level_thresholds"] == {"High": 75.0, "Medium": 50.0}
    assert m4.rule_context["weights"] == {
        "academic_performance": 35,
        "growth_trend": 10,
        "career_preparedness": 25,
        "lifestyle_discipline": 30,
    }
