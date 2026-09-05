"""Prediction API Endpoints (ML-05).

FastAPI endpoints for M1-M4 predictions using real database data.

READ-ONLY: Uses existing repositories via Dependency Injection, no INSERT/UPDATE/DELETE.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any
import asyncpg

from app.core.database import db
from app.core.security import get_current_user
from app.api.dependencies import get_db_pool
from ml.src import inference
from ml.src.prediction_service import PredictionService, fetch_m1_raw_data, fetch_m2m3_raw_data, fetch_m4_raw_data
from app.services.prediction_generation_service import PredictionGenerationService
from app.services.prediction_insights_service import PredictionInsightsService
from app.services.prediction_contract_service import (
    PredictionContractService,
)
from app.services.m1v2_prediction_service import M1V2PredictionService
from app.services.m1v3_prediction_service import M1V3PredictionService
from app.services.m2v2_prediction_service import M2V2PredictionService
from app.services.m3v2_prediction_service import M3V2PredictionService
from app.services.faculty_service import FacultyService
from app.schemas import m1v2 as schemas
from app.schemas import m1v3 as m1v3_schemas
from app.schemas import m2v2 as m2v2_schemas
from app.schemas import m3v2 as m3v2_schemas

router = APIRouter(prefix="/predict", tags=["predictions"])

_ALLOWED_PREDICTION_TYPES = ("m1", "m2", "m3", "m4")


def get_prediction_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> PredictionService:
    return PredictionService(pool)


def get_contract_prediction_service(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PredictionContractService:
    return PredictionContractService(pool)


def get_m1v2_prediction_service(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> M1V2PredictionService:
    return M1V2PredictionService(pool)


def get_m1v3_prediction_service(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> M1V3PredictionService:
    return M1V3PredictionService(pool)


def get_m2v2_prediction_service(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> M2V2PredictionService:
    return M2V2PredictionService(pool)


def get_m3v2_prediction_service(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> M3V2PredictionService:
    return M3V2PredictionService(pool)


def get_generation_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> PredictionGenerationService:
    return PredictionGenerationService(pool)


def get_insights_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> PredictionInsightsService:
    return PredictionInsightsService(pool)


def get_faculty_service(pool: asyncpg.Pool = Depends(get_db_pool)) -> FacultyService:
    return FacultyService(pool)


def _faculty_id_or_error(user: dict) -> str:
    faculty_id = user.get("faculty_id")
    if not faculty_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No faculty_id found in user token",
        )
    return faculty_id


async def authorize_prediction_access(
    user: dict,
    student_id: str,
    faculty_service: FacultyService | None = None,
) -> None:
    """Single authorization rule for every /predict route.

    STUDENT: only their own student_id.
    FACULTY: only students within their existing authorized scope
            (FacultyService.assert_student_in_scope - same rule as the
            student overview/profile and faculty ML insights routes).
    ADMIN: existing admin access rules (unrestricted).

    Client-supplied student_id can never override this server-side check.
    """
    role = user.get("role")
    if role not in ("Student", "Faculty", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access prediction resources",
        )
    if role == "Student" and user.get("student_id") != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students can only access predictions for their own student_id",
        )
    if role == "Faculty":
        if faculty_service is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Faculty scope check unavailable",
            )
        await faculty_service.assert_student_in_scope(
            _faculty_id_or_error(user), student_id
        )


@router.get(
    "/m1/{student_id}",
    tags=["predictions"],
)
async def predict_m1(
    student_id: str,
    contract_service: PredictionContractService = Depends(get_contract_prediction_service),
    faculty_service: FacultyService = Depends(get_faculty_service),
    user: dict = Depends(get_current_user),
) -> dict:
    """Predict end-semester marks per subject via the unified inference contract.

    Reads real student data from the database (read-only), builds per-subject
    feature rows, and returns readiness-aware contract results. Students can
    only predict for their own student_id; Faculty only within their authorized
    scope; Admin for any student.
    """
    await authorize_prediction_access(user, student_id, faculty_service)

    try:
        return await contract_service.predict_m1(student_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}",
        )


@router.get(
    "/m1v2/{student_id}",
    response_model=schemas.M1V2PredictionResponse,
    responses={
        503: {"model": schemas.M1V2Error},
        500: {"model": schemas.M1V2Error},
    },
    tags=["predictions"],
)
async def predict_m1_v2(
    student_id: str,
    service: M1V2PredictionService = Depends(get_m1v2_prediction_service),
    faculty_service: FacultyService = Depends(get_faculty_service),
    user: dict = Depends(get_current_user),
):
    """Predict end-semester marks per subject with the validated M1 V2 model.

    Explicit, version controlled M1 V2 path (39-feature contract). Reads real
    student data (read-only) and returns per-subject predicted end-sem marks
    in [0, 70]. Uses the SAME authorization rule as every other /predict route
    (student: own id; faculty: within authorized scope; admin: any). The legacy
    /predict/m1/{student_id} endpoint is unchanged.
    """
    await authorize_prediction_access(user, student_id, faculty_service)

    try:
        result = await service.predict(student_id)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"M1 V2 artifact unavailable: {e}",
        )
    except (ConnectionError, RuntimeError) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"M1 V2 prediction failed: {str(e)}",
        )
    return result


@router.get(
    "/m1v3/{student_id}",
    response_model=m1v3_schemas.M1V3PredictionResponse,
    responses={
        503: {"model": m1v3_schemas.M1V3Error},
        500: {"model": m1v3_schemas.M1V3Error},
    },
    tags=["predictions"],
)
async def predict_m1_v3(
    student_id: str,
    service: M1V3PredictionService = Depends(get_m1v3_prediction_service),
    faculty_service: FacultyService = Depends(get_faculty_service),
    user: dict = Depends(get_current_user),
):
    """Predict end-semester marks per subject with the M1 V3 model (synthetic-trained).

    Uses real production data from the database (read-only). The model was trained
    on a synthetic dataset and uses 8 features: internal_marks, mid_sem_marks,
    attendance_percentage, credits, semester_no, subject_type, department_name, gender.

    Attendance is sourced from the attendance table (attendance_percentage column).

    If required real inputs are unavailable, readiness_status is NO_DATA with a
    clear explanation. No values are fabricated or imputed for missing data.
    """
    await authorize_prediction_access(user, student_id, faculty_service)

    try:
        result = await service.predict(student_id)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"M1 V3 artifact unavailable: {e}",
        )
    except (ConnectionError, RuntimeError) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"M1 V3 prediction failed: {str(e)}",
        )
    return result


@router.get(
    "/m2v2/{student_id}",
    response_model=m2v2_schemas.M2V2PredictionResponse,
    responses={
        404: {"model": m2v2_schemas.M2V2Error},
        503: {"model": m2v2_schemas.M2V2Error},
        500: {"model": m2v2_schemas.M2V2Error},
    },
    tags=["predictions"],
)
async def predict_m2_v2(
    student_id: str,
    service: M2V2PredictionService = Depends(get_m2v2_prediction_service),
    faculty_service: FacultyService = Depends(get_faculty_service),
    user: dict = Depends(get_current_user),
):
    """Predict next-semester SGPA and percentage with the validated M2 V2 model.

    Explicit, version controlled M2 V2 path (T -> T+1 contract). Reads real
    student data (read-only) and returns predicted next-semester
    ``semester_sgpa``/``semester_percentage`` from the student's last completed
    NORMAL academic observation semester. Uses the SAME authorization rule as
    every other /predict route. The legacy /predict/m2/{student_id} endpoint is
    unchanged.

    If the student has no upcoming regular academic semester (e.g. currently in
    the final / internship semester 8), readiness is NO_DATA and the service
    surfaces a 404 — no fabricated forward prediction is returned.
    """
    await authorize_prediction_access(user, student_id, faculty_service)

    try:
        result = await service.predict(student_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"M2 V2 artifact unavailable: {e}",
        )
    except (ConnectionError, RuntimeError) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"M2 V2 prediction failed: {str(e)}",
        )
    return result


@router.get(
    "/m3v2/{student_id}",
    response_model=m3v2_schemas.M3V2PredictionResponse,
    responses={
        404: {"model": m3v2_schemas.M3V2Error},
        503: {"model": m3v2_schemas.M3V2Error},
        500: {"model": m3v2_schemas.M3V2Error},
    },
    tags=["predictions"],
)
async def predict_m3_v2(
    student_id: str,
    service: M3V2PredictionService = Depends(get_m3v2_prediction_service),
    faculty_service: FacultyService = Depends(get_faculty_service),
    user: dict = Depends(get_current_user),
):
    """Estimate a student's academic-risk probability with the validated M3 V2 model.

    Explicit, version controlled M3 V2 path (T -> T+1 binary at-risk contract).
    Reads real student T-only data (read-only) and returns the estimated
    probability of entering an academic-risk state (backlog/ATKT) in the student's
    next NORMAL academic semester, classified with the artifact's tuned threshold,
    plus the top signals contributing to the estimate.

    The estimate is NOT a certainty and does NOT claim causality. Uses the SAME
    authorization rule as every other /predict route (student: own id; faculty:
    within authorized scope; admin: any). The BLOCKED legacy /predict/m3/
    endpoint is unchanged.
    """
    await authorize_prediction_access(user, student_id, faculty_service)

    try:
        result = await service.predict(student_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"M3 V2 artifact unavailable: {e}",
        )
    except (ConnectionError, RuntimeError) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"M3 V2 prediction failed: {str(e)}",
        )
    return result


@router.get(
    "/m2/{student_id}",
    tags=["predictions"],
)
async def predict_m2(
    student_id: str,
    contract_service: PredictionContractService = Depends(get_contract_prediction_service),
    faculty_service: FacultyService = Depends(get_faculty_service),
    user: dict = Depends(get_current_user),
) -> dict:
    """Predict next-semester SGPA and percentage via the unified inference contract.

    Uses real data from the database (read-only) for the student's latest
    completed semester and returns a readiness-aware contract result.
    """
    await authorize_prediction_access(user, student_id, faculty_service)

    try:
        return await contract_service.predict_m2(student_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}",
        )


@router.get(
    "/m3/{student_id}",
    tags=["predictions"],
)
async def predict_m3(
    student_id: str,
    contract_service: PredictionContractService = Depends(get_contract_prediction_service),
    faculty_service: FacultyService = Depends(get_faculty_service),
    user: dict = Depends(get_current_user),
) -> dict:
    """Expose M3 as BLOCKED via the unified inference contract.

    M3 is not approved for production prediction. Reads real student data
    (read-only), calls the contract, and returns a readiness-aware result with
    ``readiness_status=BLOCKED`` and ``prediction_available=False``. No real
    at-risk prediction is returned.

    Route-level enforcement: if the contract ever returns a non-BLOCKED
    status for M3, this endpoint will reject it to prevent accidental
    production exposure.
    """
    await authorize_prediction_access(user, student_id, faculty_service)

    try:
        result = await contract_service.predict_m3(student_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}",
        )

    # Route-level BLOCKED enforcement: M3 must never return a live prediction.
    readiness = result.get("readiness_status")
    if readiness and readiness != "BLOCKED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="M3 prediction is currently blocked and not available for production use.",
        )
    return result


@router.get(
    "/m4/{student_id}",
    response_model=inference.PredictionResult,
    tags=["predictions"],
)
async def predict_m4(
    student_id: str,
    service: PredictionService = Depends(get_prediction_service),
    faculty_service: FacultyService = Depends(get_faculty_service),
    user: dict = Depends(get_current_user),
) -> inference.PredictionResult:
    """Compute career readiness score for a student.

    Uses the rule-based CareerReadinessEngine (NOT an ML model).
    Returns 0-100 score with Low/Medium/High level and factors.
    """
    await authorize_prediction_access(user, student_id, faculty_service)

    try:
        result = await service.predict_m4_for_student(student_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}",
        )


# ---------------------------------------------------------------------------
# ML-09: Student insights bundle (prediction + ML-08 grounded explanation).
#
# Read-only aggregation for the Student Portal. Each model degrades
# independently: a model with no data reports "available": false instead
# of failing the whole bundle. No inference or explanation logic lives
# here; the ML-05 PredictionService and ML-08 ExplanationService are
# reused as-is.
# ---------------------------------------------------------------------------


@router.get(
    "/insights/{student_id}",
    tags=["predictions"],
)
async def student_insights(
    student_id: str,
    service: PredictionInsightsService = Depends(get_insights_service),
    faculty_service: FacultyService = Depends(get_faculty_service),
    user: dict = Depends(get_current_user),
) -> dict:
    """Return M1-M4 predictions paired with grounded ML-08 explanations.

    Each model reports ``available: true`` with its ``prediction`` and
    ``explanation``, or ``available: false`` with a reason when data is
    missing (``no_data``) or the model failed (``error``).
    """
    await authorize_prediction_access(user, student_id, faculty_service)
    try:
        return await service.get_student_insights(student_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Insights failed: {str(e)}",
        )


# ---------------------------------------------------------------------------
# ML-07: Explicit prediction generation + persistence (ML-06 ml_predictions).
#
# The GET /predict endpoints above remain read-only and are NOT wired to
# persistence. These are the explicit caller-driven flows:
#   POST /predict/persist/{prediction_type}/{student_id}   generate+persist
#   GET  /predict/persisted/latest/{prediction_type}/{student_id}
#   GET  /predict/persisted/history/{student_id}
# ---------------------------------------------------------------------------


@router.post(
    "/persist/{prediction_type}/{student_id}",
    tags=["predictions"],
)
async def persist_prediction(
    prediction_type: str,
    student_id: str,
    service: PredictionGenerationService = Depends(get_generation_service),
    faculty_service: FacultyService = Depends(get_faculty_service),
    user: dict = Depends(get_current_user),
) -> dict:
    """Generate, validate, persist, and return an M1-M4 prediction.

    Flow: real DB data -> ML-02 features -> ML-03/04 inference
    -> validation -> ml_predictions (ML-06) -> validated result.
    Repeated calls append new historical rows per the ML-06
    append-only design; nothing is persisted if generation or
    validation fails.
    """
    await authorize_prediction_access(user, student_id, faculty_service)
    try:
        return await service.generate_and_persist(prediction_type, student_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction generation/persistence failed: {str(e)}",
        )


@router.get(
    "/persisted/latest/{prediction_type}/{student_id}",
    tags=["predictions"],
)
async def latest_prediction(
    prediction_type: str,
    student_id: str,
    service: PredictionGenerationService = Depends(get_generation_service),
    faculty_service: FacultyService = Depends(get_faculty_service),
    user: dict = Depends(get_current_user),
) -> dict:
    """Return the latest stored prediction for a student/model type."""
    await authorize_prediction_access(user, student_id, faculty_service)
    try:
        row = await service.get_latest(student_id, prediction_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No persisted prediction for {student_id}/{prediction_type}",
        )
    return row


@router.get(
    "/persisted/history/{student_id}",
    tags=["predictions"],
)
async def persisted_history(
    student_id: str,
    prediction_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    service: PredictionGenerationService = Depends(get_generation_service),
    faculty_service: FacultyService = Depends(get_faculty_service),
    user: dict = Depends(get_current_user),
) -> dict:
    """Return newest-first persisted prediction history for a student."""
    await authorize_prediction_access(user, student_id, faculty_service)
    try:
        rows = await service.get_history(
            student_id, prediction_type, limit=limit, offset=offset
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"student_id": student_id, "count": len(rows), "predictions": rows}