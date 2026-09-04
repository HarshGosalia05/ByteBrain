"""G2.4 Student Prediction Explanation Tool.

Adapter/orchestration layer over the EXISTING verified prediction system.

Composes:
  * ``MLPredictionService.get_latest`` -> the newest VERIFIED persisted
    prediction for a student/model type (``ml_predictions`` rows carrying
    the validated per-type ``prediction_value`` plus ``model_version`` /
    ``generated_at`` / counts). This is the ONLY source of prediction
    values; nothing is generated, re-estimated, or inferred here.
  * ML-08 ``ExplanationService`` (the existing grounded explanation path
    also used by ML-09 insights) -> verified input signals and grounded
    factors from the actual inputs the prediction consumed. This reuses
    the existing explanation algorithm; no new algorithm is created and no
    feature importance / SHAP is fabricated.

It does NOT:
  * generate a prediction, calculate a confidence, infer a probability,
    invent model accuracy, or invent uncertainty,
  * turn model-level evaluation metrics into individual confidence,
  * create a new explanation algorithm or fabricate SHAP,
  * call any LLM provider (G0 remains the only LLM boundary),
  * execute or build SQL itself, or accept a DB session / repository.

Semantics:
  * M1 predicts subject end-sem marks (target_semester = the subject's
    semester).
  * M2/M3 predict semester T+1 from the latest completed semester T; the
    persisted ``semester_no`` is the SOURCE semester and ``target_semester``
    is ``source_semester + 1`` (per the ML-05 semantic contract).
  * M4 is a deterministic rule-based readiness engine (``model_kind`` =
    "rule_based"), NOT a trained ML model and NOT an actual placement
    outcome.
  * M3 exposes only a binary ``is_at_risk_next_sem``; no probability
    exists, so uncertainty stays unavailable.

Security (self-scope):
  * Student-only. The authenticated ``student_id`` is the ONLY identity.
  * A caller-supplied ``target_student_id`` that differs is REJECTED (403)
    before any data access.
  * Unknown ``prediction_type`` fails closed (400).

G1 integration:
  * ``TOOL_NAME`` / ``INTENT`` match the registered G1 tool definition
    ``student_prediction_explanation_tool`` -> ``prediction_explanation``.
  * G1 ToolRegistry remains data-only; the executable implementation lives
    here under the same tool name.

G0 boundary:
  * ``to_verified_context`` produces a G0 ``VerifiedContext`` consumed by
    ``GenAIService``, populating G0 ``ModelMetadata`` for a single-model
    result. The tool never bypasses G0.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.schemas.genai import ModelMetadata, VerifiedContext
from app.schemas.student_prediction_explanation_tool import (
    PredictionUncertainty,
    StudentPrediction,
    StudentPredictionExplanationResult,
    VerifiedFactor,
    VerifiedInput,
)
from app.services.ml_prediction_service import MLPredictionService

logger = logging.getLogger(__name__)

TOOL_NAME = "student_prediction_explanation_tool"
INTENT = "prediction_explanation"
SOURCE_LABEL = "students/prediction_explanations"

PREDICTION_TYPES = ("m1", "m2", "m3", "m4")

# Verified registry facts: M1-M3 are supervised ML artifacts; M4 is the
# deterministic rule-based engine (ml.src.registry ModelEntry.model_type).
_MODEL_KIND: dict[str, str] = {
    "m1": "ml",
    "m2": "ml",
    "m3": "ml",
    "m4": "rule_based",
}

_TARGETS: dict[str, str] = {
    "m1": "subject_end_sem_marks",
    "m2": "next_semester_percentage",
    "m3": "next_semester_at_risk",
    "m4": "career_readiness_score",
}

_UNAVAILABLE_NOTES: dict[str, str] = {
    "m1": "No verified M1 subject end-marks prediction is available for this student.",
    "m2": "No verified M2 next-semester performance prediction is available for this student.",
    "m3": "No verified M3 next-semester at-risk prediction is available for this student.",
    "m4": "No verified M4 career readiness score is available for this student.",
}

_UNCERTAINTY_NOTE = (
    "This prediction model does not expose per-prediction uncertainty."
)
_EXPLANATION_UNAVAILABLE_NOTE = (
    "Verified explanation factors are temporarily unavailable for this prediction."
)
_M4_NOTE = (
    "M4 is a deterministic rule-based readiness score, not a trained ML model "
    "and not an actual placement outcome."
)


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _split_factors(text: Any) -> list[str]:
    if text is None:
        return []
    return [part.strip() for part in str(text).split(";") if part.strip()]


class StudentPredictionExplanationTool:
    """Verified M1/M2/M3/M4 prediction explanation for the authenticated student.

    ``prediction_service`` and ``explanation_service`` are injectable for
    isolated testing (same convention as the existing ML-07/ML-09 services);
    when omitted they are created lazily.
    """

    def __init__(
        self,
        pool: Any,
        *,
        prediction_service: Any = None,
        explanation_service: Any = None,
    ) -> None:
        self._pool = pool
        self._prediction = prediction_service
        self._explanation = explanation_service

    # ------------------------------------------------------------------
    # Lazy dependency resolution (keeps module imports light)
    # ------------------------------------------------------------------

    def _prediction_service(self) -> Any:
        if self._prediction is None:
            self._prediction = MLPredictionService(self._pool)
        return self._prediction

    def _explanation_service(self) -> Any:
        if self._explanation is None:
            from ml.src.explain import ExplanationService  # noqa: PLC0415

            self._explanation = ExplanationService(self._pool)
        return self._explanation

    def _student_service(self) -> Any:
        from app.services.student_service import StudentService  # noqa: PLC0415

        return StudentService(self._pool)

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(
        self,
        *,
        student_id: str,
        target_student_id: str | None = None,
        prediction_type: str = "all_available",
        subject_filter: str | None = None,
        semester: int | None = None,
    ) -> StudentPredictionExplanationResult:
        """Return verified predictions, scoped to the authenticated student.

        ``student_id`` is ALWAYS the authenticated identity. Any differing
        ``target_student_id`` (client-supplied) is rejected before any data
        access. ``prediction_type`` is one of m1/m2/m3/m4/all_available;
        unknown types fail closed (400).
        """
        if not student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated student identity",
            )
        if target_student_id is not None and target_student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only access their own predictions",
            )

        requested = (prediction_type or "all_available").strip().lower()
        if requested == "all_available":
            types = list(PREDICTION_TYPES)
        elif requested in PREDICTION_TYPES:
            types = [requested]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unknown prediction type '{prediction_type}'; "
                    "expected one of m1, m2, m3, m4 or all_available"
                ),
            )

        service = self._prediction_service()
        predictions: list[StudentPrediction] = []
        unavailable: list[str] = []
        for prediction_type_id in types:
            if prediction_type_id == "m1":
                # M1 is persisted one row per subject. Route it through the
                # subject-aware collect path so a requested subject/semester is
                # answered with that subject's OWN prediction (never substituted).
                await self._collect_m1(
                    service,
                    student_id,
                    semester,
                    subject_filter,
                    predictions,
                    unavailable,
                    requested,
                )
                continue
            row = await service.get_latest(student_id, prediction_type_id)
            if row is None:
                if requested != "all_available":
                    # Controlled FALSE state for an explicitly requested type.
                    predictions.append(
                        StudentPrediction(
                            model_id=prediction_type_id,
                            model_kind=_MODEL_KIND[prediction_type_id],
                            prediction_available=False,
                            is_prediction=True,
                            uncertainty=PredictionUncertainty(),
                            note=_UNAVAILABLE_NOTES[prediction_type_id],
                        )
                    )
                unavailable.append(prediction_type_id)
                continue
            built = await self._build(prediction_type_id, row, student_id)
            predictions.append(built)

        data_available = any(p.prediction_available for p in predictions)
        return StudentPredictionExplanationResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            student_id=student_id,
            prediction_type=requested,  # type: ignore[arg-type]
            data_available=data_available,
            predictions=predictions,
            unavailable_items=unavailable,  # type: ignore[arg-type]
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=(
                None
                if data_available
                else "No verified predictions are currently available for this student."
            ),
        )

    # ------------------------------------------------------------------
    # Per-model verified building
    # ------------------------------------------------------------------

    async def _build(
        self,
        prediction_type_id: str,
        row: dict[str, Any],
        student_id: str,
    ) -> StudentPrediction:
        value = row.get("prediction_value")
        if not isinstance(value, dict):
            value = {}

        model_version = row.get("model_version")
        generated_at = row.get("generated_at")

        common: dict[str, Any] = {
            "model_id": prediction_type_id,
            "model_kind": _MODEL_KIND[prediction_type_id],
            "prediction_available": True,
            "is_prediction": True,
            "target": _TARGETS[prediction_type_id],
            "model_version": model_version,
            "generated_at": generated_at,
            "uncertainty": PredictionUncertainty(note=_UNCERTAINTY_NOTE),
        }

        if prediction_type_id == "m1":
            semester = _int_or_none(value.get("semester_no"))
            common["source_semester"] = None
            common["target_semester"] = semester
            common["subject_id"] = value.get("subject_id")
        elif prediction_type_id in ("m2", "m3"):
            semester = _int_or_none(value.get("semester_no"))
            common["source_semester"] = semester
            common["target_semester"] = (
                None if semester is None else semester + 1
            )
        elif prediction_type_id == "m4":
            common["note"] = _M4_NOTE

        common["predicted_value"] = value
        common["positive_factors"] = _split_factors(value.get("positive_factors"))
        common["risk_factors"] = _split_factors(value.get("risk_factors"))

        try:
            explanation = await self._explanation_service().explain(
                self._hydrate_result(prediction_type_id, value, student_id, row),
                model_version=model_version,
            )
            self._merge_explanation(common, prediction_type_id, explanation)
        except Exception as exc:  # noqa: BLE001 - prediction still verifiable
            logger.warning(
                "Explanation factors unavailable for %s prediction of %s: %s",
                prediction_type_id,
                student_id,
                exc,
            )
            common["note"] = " ".join(
                part for part in (common.get("note"), _EXPLANATION_UNAVAILABLE_NOTE)
                if part
            ) or None

        return StudentPrediction(**common)

    @staticmethod
    def _hydrate_result(
        prediction_type_id: str,
        value: dict[str, Any],
        student_id: str,
        row: dict[str, Any],
    ) -> Any:
        """Reconstruct the typed verified output for the ML-08 factor path.

        Copies ONLY persisted values (never generates or estimates). Lazy
        import keeps the tool importable without pandas/ML deps.
        """
        from ml.src.inference import (  # noqa: PLC0415
            M1Prediction,
            M2Prediction,
            M3Prediction,
            M4Score,
            PredictionResult,
        )

        if prediction_type_id == "m1":
            item = M1Prediction(
                student_id=student_id,
                subject_id=str(value.get("subject_id") or ""),
                semester_no=value.get("semester_no"),
                predicted_end_sem_marks=float(value.get("predicted_end_sem_marks") or 0.0),
                clipped=bool(value.get("clipped")),
            )
        elif prediction_type_id == "m2":
            item = M2Prediction(
                student_id=student_id,
                semester_no=value.get("semester_no"),
                predicted_next_semester_sgpa=float(
                    value.get("predicted_next_semester_sgpa") or 0.0
                ),
                predicted_next_semester_percentage=float(
                    value.get("predicted_next_semester_percentage") or 0.0
                ),
            )
        elif prediction_type_id == "m3":
            item = M3Prediction(
                student_id=student_id,
                semester_no=value.get("semester_no"),
                is_at_risk_next_sem=int(value.get("is_at_risk_next_sem") or 0),
            )
        else:
            item = M4Score(
                student_id=student_id,
                enrollment_no=str(value.get("enrollment_no") or ""),
                full_name=str(value.get("full_name") or ""),
                department_name=str(value.get("department_name") or ""),
                current_semester=value.get("current_semester") or "",
                career_readiness_score=float(
                    value.get("career_readiness_score") or 0.0
                ),
                career_readiness_level=str(value.get("career_readiness_level") or ""),
                positive_factors=str(value.get("positive_factors") or ""),
                risk_factors=str(value.get("risk_factors") or ""),
            )
        return PredictionResult(
            model_id=prediction_type_id,
            predictions=[item],
            input_row_count=row.get("input_row_count"),
            prediction_count=row.get("prediction_count"),
        )

    @staticmethod
    def _merge_explanation(
        common: dict[str, Any],
        prediction_type_id: str,
        explanation: Any,
    ) -> None:
        items = getattr(explanation, "explanations", None) or []
        if items:
            item = items[0]
            common["verified_factors"] = [
                VerifiedFactor(kind=f.kind, source=f.source, detail=f.detail)
                for f in (getattr(item, "factors", None) or [])
            ]
            common["verified_inputs"] = [
                VerifiedInput(name=i.name, value=i.value, present=i.present)
                for i in (getattr(item, "inputs", None) or [])
            ]
            if prediction_type_id == "m1":
                subject_name = getattr(item, "subject_name", None)
                if subject_name:
                    common["subject_name"] = subject_name
        if prediction_type_id == "m4":
            rule_context = getattr(explanation, "rule_context", None)
            if isinstance(rule_context, dict) and rule_context:
                common["rule_context"] = dict(rule_context)

    # ------------------------------------------------------------------
    # M1 subject-aware collection (never silent substitution)
    # ------------------------------------------------------------------

    async def _collect_m1(
        self,
        service: Any,
        student_id: str,
        semester: int | None,
        subject_filter: str | None,
        predictions: list[StudentPrediction],
        unavailable: list[str],
        requested: str,
    ) -> None:
        """Collect the student's M1 predictions with full subject awareness.

        Because M1 predictions are persisted per subject, we pull the real
        history and match ONLY to the requested subject/semester. When a
        specific subject or semester is requested but no prediction exists, we
        build the controlled FALSE record (mentioning exactly what is missing)
        instead of silently substituting another subject or another semester.

        When no subject is requested we surface each available prediction with
        its own semester/subject identity; nothing is merged or invented.
        """
        history_fn = getattr(service, "get_history", None)
        if callable(history_fn):
            history = await history_fn(student_id, "m1")
            rows = [
                row for row in history if isinstance(row.get("prediction_value"), dict)
            ]
        else:
            # Legacy path: services/fakes exposing only ``get_latest`` still work.
            latest = await service.get_latest(student_id, "m1")
            rows = (
                [latest]
                if latest and isinstance(latest.get("prediction_value"), dict)
                else []
            )

        if subject_filter:
            requested_subject = subject_filter.strip()
            subject_id = await self._m1_resolve_subject_id(
                student_id, requested_subject
            )
            matched = self._m1_match(rows, subject_id, requested_subject)
            if matched:
                await self._append_m1_batch(
                    matched, student_id, predictions, unavailable,
                    requested_subject, semester,
                )
                return
            predictions.append(
                StudentPrediction(
                    model_id="m1",
                    model_kind="ml",
                    prediction_available=False,
                    is_prediction=True,
                    uncertainty=PredictionUncertainty(),
                    subject_name=requested_subject,
                    note=(
                        f"No verified M1 prediction is available for "
                        f"{requested_subject}."
                    ),
                )
            )
            unavailable.append("m1")
            return

        if semester is not None:
            scoped = [
                row
                for row in rows
                if _int_or_none(row["prediction_value"].get("semester_no")) == semester
            ]
            if not scoped:
                predictions.append(
                    StudentPrediction(
                        model_id="m1",
                        model_kind="ml",
                        prediction_available=False,
                        is_prediction=True,
                        uncertainty=PredictionUncertainty(),
                        note=(
                            f"No verified M1 prediction is available for "
                            f"Semester {semester}."
                        ),
                    )
                )
                unavailable.append("m1")
                return
            await self._append_m1_batch(
                scoped, student_id, predictions, unavailable, None, semester
            )
            return

        if not rows:
            if requested != "all_available":
                predictions.append(
                    StudentPrediction(
                        model_id="m1",
                        model_kind="ml",
                        prediction_available=False,
                        is_prediction=True,
                        uncertainty=PredictionUncertainty(),
                        note=_UNAVAILABLE_NOTES["m1"],
                    )
                )
            unavailable.append("m1")
            return
        await self._append_m1_batch(
            rows, student_id, predictions, unavailable, None, None
        )

    async def _m1_resolve_subject_id(
        self, student_id: str, requested_subject: str
    ) -> str | None:
        """Map a subject name/code to the verified subject_id (authoritative source).

        The M1 ``prediction_value`` stores only ``subject_id``. We resolve the
        requested subject against the SAME authoritative
        ``student_subject_performance`` table the Subject page uses, so the M1
        row selected is that subject's own prediction - never another subject's.
        """
        query = (requested_subject or "").strip().lower()
        if not query:
            return None
        try:
            response = await self._student_service().get_performance(student_id)
        except Exception as exc:  # noqa: BLE001 - resolution is best-effort
            logger.warning("M1 subject resolution unavailable for %s: %s", student_id, exc)
            return None
        records = list(getattr(response, "performance", None) or [])
        for record in records:
            if record.subject_code and record.subject_code.lower() == query:
                return record.subject_id
        for record in records:
            if record.subject_name and record.subject_name.lower() == query:
                return record.subject_id
        for record in records:
            if record.subject_name and query in record.subject_name.lower():
                return record.subject_id
        return None

    @staticmethod
    def _m1_match(
        rows: list[dict[str, Any]],
        subject_id: str | None,
        requested_subject: str,
    ) -> list[dict[str, Any]]:
        """Resolve M1 history rows to the requested subject.

        Matching is exact by the authoritative ``subject_id`` when it resolves;
        otherwise no match is reported (never a fuzzy guess on another subject).
        """
        if not rows:
            return []
        if subject_id:
            return [
                row
                for row in rows
                if str((row["prediction_value"].get("subject_id") or "")).lower()
                == str(subject_id).lower()
            ]
        # Subject could not be resolved to an id: only an exact stored
        # subject_id already matching the requested token is acceptable.
        token = (requested_subject or "").strip().lower()
        if not token:
            return []
        return [
            row
            for row in rows
            if str((row["prediction_value"].get("subject_id") or "")).lower() == token
        ]

    async def _append_m1_batch(
        self,
        rows: list[dict[str, Any]],
        student_id: str,
        predictions: list[StudentPrediction],
        unavailable: list[str],
        label: str | None,
        semester: int | None,
    ) -> None:
        """Build one projection per M1 row; reconcile marks against authoritative data."""
        for row in rows:
            built = await self._build("m1", row, student_id)
            if not built.subject_name and label:
                built.subject_name = label
            built = await self._reconcile_authoritative_marks(
                built, student_id, semester, built.subject_name or label
            )
            predictions.append(built)
        if not rows:
            unavailable.append("m1")

    # ------------------------------------------------------------------
    # M1 authoritative-marks reconciliation
    # ------------------------------------------------------------------

    async def _reconcile_authoritative_marks(
        self,
        prediction: StudentPrediction,
        student_id: str,
        semester: int | None,
        subject_filter: str | None,
    ) -> StudentPrediction:
        """Cross-check an M1 prediction against the authoritative subject marks.

        The M1 verbalizer flags inputs as *present/missing* based on the exact
        inference row the prediction consumed. That can disagree with the
        authoritative ``student_subject_performance`` table (the same source the
        Subject page and the subject-analysis tool use). When the authoritative
        record DOES carry the marks, we surface them so the response layer never
        claims a subject's marks are "missing" while the backend has them.

        This is a data-reconciliation step only - it never modifies the M1
        prediction value and never re-runs the model.
        """
        subject_id = (prediction.predicted_value or {}).get("subject_id")
        if not subject_id:
            return prediction
        try:
            response = await self._student_service().get_performance(student_id, semester)
        except Exception as exc:  # noqa: BLE001 - reconciliation is best-effort
            logger.warning(
                "M1 authoritative-marks reconciliation unavailable for %s: %s",
                student_id,
                exc,
            )
            return prediction

        record = self._match_record(response.performance, subject_id, subject_filter, semester)
        if record is None:
            return prediction

        prediction.authoritative_marks = {
            "subject_id": record.subject_id,
            "subject_code": record.subject_code,
            "subject_name": record.subject_name,
            "semester": record.semester,
            "internal_marks": record.internal_marks,
            "mid_sem_marks": record.mid_sem_marks,
            "end_sem_marks": record.end_sem_marks,
        }
        reconciled_note = (
            f"Authoritative subject record shows internal_marks="
            f"{record.internal_marks}, mid_sem_marks={record.mid_sem_marks}, "
            f"end_sem_marks={record.end_sem_marks}."
        )
        prediction.note = " ".join(
            part for part in (prediction.note, reconciled_note) if part
        ) or None
        return prediction

    @staticmethod
    def _match_record(performance: Any, subject_id: str, subject_filter: str | None, semester: int | None):
        """Find the authoritative subject record for the M1 prediction.

        Matches primarily by ``subject_id``; falls back to subject name/code
        (including a requested ``subject_filter``) when needed.
        """
        items = list(performance or [])
        if not items:
            return None
        if semester is not None:
            sem_items = [i for i in items if int(i.semester or 0) == semester]
            if sem_items:
                items = sem_items
        for item in items:
            if item.subject_id and str(item.subject_id) == str(subject_id):
                return item
        if subject_filter:
            query = subject_filter.strip().lower()
            for item in items:
                if item.subject_code and item.subject_code.lower() == query:
                    return item
            for item in items:
                if item.subject_name and query in item.subject_name.lower():
                    return item
        return None

    def to_verified_context(
        self, result: StudentPredictionExplanationResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext.

        ``data`` carries only JSON-serializable, verified values. G0
        ``ModelMetadata`` is populated for a single-model result; G0
        ``UncertaintyInfo`` is never fabricated.
        """
        context = VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
        )
        available = [p for p in result.predictions if p.prediction_available]
        if result.prediction_type in PREDICTION_TYPES and len(available) == 1:
            item = available[0]
            context.model = ModelMetadata(
                model_id=item.model_id,
                model_version=item.model_version,
                prediction_type=item.model_id,
            )
        return context
