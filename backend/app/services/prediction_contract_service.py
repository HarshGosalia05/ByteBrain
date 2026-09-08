"""READ-ONLY Prediction Contract Service (M1/M2/M3).

A thin backend adapter that proves the FastAPI layer can serve predictions
from the UNIFIED OFFLINE INFERENCE CONTRACT (``ml.src.features.v1_inference_contract``).

Flow (read-only):
    real DB data (existing read-only fetch helpers)
      -> per-row feature dicts (no feature-engineering duplication)
      -> v1_inference_contract.predict_mX(row)   (unified contract)
      -> readiness-aware InferenceResult JSON

Design rules:
  * Reads real student data ONLY via the authoritative read-only fetch
    helpers in ``ml.src.prediction_service`` (``_fetch_student_performance``,
    ``_fetch_subject_type``, ``_fetch_student_profile``,
    ``_fetch_student_semester_summary``). No new SQL, no new feature pipeline.
  * Consumes the existing unified offline inference contract. No model is
    retrained and no artifact is modified.
  * NEVER writes predictions back to the database, NEVER persists, NEVER
    mutates a row. This is a pure read path.
  * M1 is READY; M3 is exposed as BLOCKED (not an approved prediction).
  * M2 is retired from this contract: legacy V1 M2 offline inference no longer
    exists (the artifact was removed) and M2 production predictions are served
    exclusively by the validated M2-TP package (``M2TPPredictionService``).
  * M3 does NOT return a production prediction; its standardized result
    reports ``readiness_status=BLOCKED`` and ``prediction_available=False``.
"""
from __future__ import annotations

from typing import Any

_M1_REQUIRED_COLS = (
    "subject_id", "semester_no", "internal_marks", "mid_sem_marks",
    "attendance_percentage", "credits",
)
_M2_M3_REQUIRED_COLS = (
    "semester_no", "subjects_registered", "credits_registered", "credits_earned",
    "semester_total_marks", "semester_percentage", "semester_sgpa",
    "semester_attendance_percentage", "backlog_count",
)


class PredictionContractService:
    """Serve M1/M2/M3 predictions from the unified offline inference contract.

    Read-only: fetches real DB data, calls the contract, returns contract-shaped
    results. It never writes to the database.
    """

    def __init__(self, pool: Any):
        self.pool = pool

    # -- lazy imports (kept import-light for unit testing) ------------------

    @staticmethod
    def _contract():
        from ml.src.features import v1_inference_contract as contract
        return contract

    @staticmethod
    def _fetch():
        import ml.src.prediction_service as ps
        return ps

    # -----------------------------------------------------------------------
    # M1: Subject-level End-Sem Mark Prediction (READY)
    # -----------------------------------------------------------------------

    async def predict_m1(self, student_id: str) -> dict:
        """Return contract-shaped M1 predictions for a student.

        One InferenceResult per subject enrollment, built from real DB data.
        """
        fetch = self._fetch()
        performance = await fetch._fetch_student_performance(self.pool, student_id)
        subject_types = await fetch._fetch_subject_type(self.pool, student_id)
        profile = await fetch._fetch_student_profile(self.pool, student_id)

        if performance.empty or profile.empty:
            raise ValueError(f"No data found for student {student_id}")

        dept, gender = self._profile_fields(profile)

        type_map = {
            str(r["subject_id"]): str(r["subject_type"])
            for r in subject_types.to_dict("records")
        } if not subject_types.empty else {}

        contract = self._contract()
        predictions = []
        for _, row in performance.iterrows():
            row_dict = self._m1_row(row, student_id, dept, gender, type_map)
            result = contract.predict_m1(row_dict)
            predictions.append(result.to_dict())

        return {
            "model_id": "m1",
            "readiness_status": contract.get_readiness("m1"),
            "student_id": student_id,
            "predictions": predictions,
            "prediction_count": len(predictions),
        }

    # -----------------------------------------------------------------------
    # M2: RETIRED — legacy V1 offline inference removed; M2-TP serves M2.
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # M3: Next-Semester At-Risk Prediction (BLOCKED)
    # -----------------------------------------------------------------------

    async def predict_m3(self, student_id: str) -> dict:
        """Return the contract-shaped M3 result, always BLOCKED.

        M3 is NOT approved for production prediction. This returns a
        readiness-aware result with ``prediction_available=False`` and
        ``readiness_status=BLOCKED``; it does NOT expose a real prediction.
        """
        fetch = self._fetch()
        summary = await fetch._fetch_student_semester_summary(self.pool, student_id)
        profile = await fetch._fetch_student_profile(self.pool, student_id)

        if summary.empty or profile.empty:
            raise ValueError(f"No data found for student {student_id}")

        dept, gender = self._profile_fields(profile)
        latest = self._latest_semester_row(summary)
        row_dict = self._m2m3_row(latest, student_id, dept, gender)

        contract = self._contract()
        result = contract.predict_m3(row_dict)
        return result.to_dict()

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _profile_fields(profile) -> tuple[str, str]:
        rec = profile.to_dict("records")[0]
        department_name = rec.get("department_name")
        gender = rec.get("gender")
        if not department_name or not gender:
            raise ValueError(
                f"Student {rec.get('student_id')!r} is missing department_name or gender."
            )
        return str(department_name), str(gender)

    @staticmethod
    def _latest_semester_row(summary):
        df = summary.sort_values("semester_no", ascending=True)
        return df.iloc[-1].to_dict()

    @staticmethod
    def _m1_row(row, student_id: str, dept: str, gender: str, type_map: dict) -> dict:
        subject_id = str(row["subject_id"])
        subject_type = type_map.get(subject_id)
        if not subject_type:
            raise ValueError(f"Missing subject_type for subject {subject_id!r}")
        for col in _M1_REQUIRED_COLS:
            if row.get(col) is None:
                raise ValueError(
                    f"Missing required M1 feature '{col}' for subject {subject_id!r}."
                )
        return {
            "student_id": student_id,
            "subject_id": subject_id,
            "semester_no": row.get("semester_no"),
            "internal_marks": row.get("internal_marks"),
            "mid_sem_marks": row.get("mid_sem_marks"),
            "attendance_percentage": row.get("attendance_percentage"),
            "credits": row.get("credits"),
            "subject_type": subject_type,
            "department_name": dept,
            "gender": gender,
        }

    @staticmethod
    def _m2m3_row(row, student_id: str, dept: str, gender: str) -> dict:
        for col in _M2_M3_REQUIRED_COLS:
            if row.get(col) is None:
                raise ValueError(
                    f"Missing required M2/M3 feature '{col}' for student {student_id}."
                )
        return {
            "student_id": student_id,
            "semester_no": row.get("semester_no"),
            "subjects_registered": row.get("subjects_registered"),
            "credits_registered": row.get("credits_registered"),
            "credits_earned": row.get("credits_earned"),
            "semester_total_marks": row.get("semester_total_marks"),
            "semester_percentage": row.get("semester_percentage"),
            "semester_sgpa": row.get("semester_sgpa"),
            "semester_attendance_percentage": row.get("semester_attendance_percentage"),
            "backlog_count": row.get("backlog_count"),
            "department_name": dept,
            "gender": gender,
        }
