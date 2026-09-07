"""MD-08 / ML-11 Administrative ML batch generation service.

Triggers and orchestrates asynchronous generation + persistence of
M1-M4 predictions for all (or scoped) students, driven from the Admin
ML Intelligence portal.

Design rules:
  * READ-ONLY orchestration shell: it reuses the existing
    ``PredictionGenerationService`` for each (student, model) unit of
    work; no feature or inference logic is duplicated here.
  * A single background job runs at a time; starting a second job while
    one is active is rejected with ``ValueError``.
  * Jobs live in an in-memory store (single uvicorn process) and are
    evicted once older than ``_JOB_TTL_SECONDS``.
  * Eligibility is pre-computed cheaply so that models with no data
    (e.g. M1 without attendance rows, M4 without career preferences)
    are skipped instead of failing per student.
  * Per-student failures never abort the whole batch; they are counted
    and surfaced in the job status.
  * Existing coverage is respected (``force=False`` skips students that
    already have a prediction for a model) to keep the append-only
    ``ml_predictions`` history clean on routine re-runs.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg

from app.services.prediction_generation_service import PredictionGenerationService

logger = logging.getLogger(__name__)

_VALID_MODELS = ("m1", "m2", "m3", "m4")
_JOB_TTL_SECONDS = 6 * 3600  # keep job records ~6h
_DEFAULT_MAX_CONCURRENCY = 4  # pool is capped at 5 connections


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------

_JOBS: Dict[str, Dict[str, Any]] = {}


def _evict_stale_jobs() -> None:
    cutoff = time.time() - _JOB_TTL_SECONDS
    for job_id in [jid for jid, j in _JOBS.items() if j.get("_ts", 0) < cutoff]:
        _JOBS.pop(job_id, None)


class AdminMLGenerationService:
    """Fans out generation work across students targeting selected models."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        generation_service: Optional[PredictionGenerationService] = None,
        max_concurrency: int = _DEFAULT_MAX_CONCURRENCY,
    ):
        self._pool = pool
        self._generation = generation_service
        self._max_concurrency = max_concurrency
        self._tasks: Dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    async def start_generation(
        self,
        models: List[str],
        *,
        department_code: Optional[int] = None,
        semester: Optional[int] = None,
        academic_year: Optional[str] = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Queue a background generation run; returns the job descriptor."""
        if not models:
            models = list(_VALID_MODELS)
        models = [m for m in models if m in _VALID_MODELS]
        models = list(dict.fromkeys(models))  # de-dup, preserve order
        if not models:
            raise ValueError("At least one valid model (m1/m2/m3/m4) is required.")

        self._reject_active_jobs()

        job_id = str(uuid.uuid4())
        job: Dict[str, Any] = {
            "job_id": job_id,
            "status": "queued",
            "models": models,
            "department_code": department_code,
            "semester": semester,
            "academic_year": academic_year,
            "force": force,
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "skipped_tasks": 0,
            "per_model": {
                m: {
                    "model": m,
                    "eligible": 0,
                    "total": 0,
                    "completed": 0,
                    "failed": 0,
                    "skipped": 0,
                }
                for m in models
            },
            "errors": [],
            "started_at": None,
            "finished_at": None,
            "error": None,
            "_ts": time.time(),
        }
        _JOBS[job_id] = job
        _evict_stale_jobs()

        task = asyncio.create_task(self._run(job_id))
        self._tasks[job_id] = task
        return self._snapshot(job)

    async def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        job = _JOBS.get(job_id)
        return self._snapshot(job) if job else None

    def _reject_active_jobs(self) -> None:
        for job in _JOBS.values():
            if job["status"] in ("queued", "running"):
                raise ValueError("A generation run is already in progress.")

    # ------------------------------------------------------------------
    # Background run
    # ------------------------------------------------------------------

    async def _run(self, job_id: str) -> None:
        job = _JOBS[job_id]
        job["status"] = "running"
        job["started_at"] = utc_now().isoformat()
        try:
            student_ids = await self._resolve_students(job)
            eligibility = await self._compute_eligibility(student_ids)
            coverage = await self._existing_coverage(student_ids)

            work: list[tuple[str, str]] = []
            for sid in student_ids:
                for model in job["models"]:
                    if sid not in eligibility.get(model, ()):
                        job["per_model"][model]["skipped"] += 1
                        continue
                    if not job["force"] and (sid, model) in coverage:
                        job["per_model"][model]["skipped"] += 1
                        continue
                    work.append((sid, model))

            job["total_tasks"] = len(work)
            for model in job["models"]:
                job["per_model"][model]["total"] = sum(
                    1 for sid, m in work if m == model
                )
                job["per_model"][model]["eligible"] = sum(
                    1 for sid in set(student_ids) if sid in eligibility.get(model, ())
                )

            if not work:
                job["status"] = "completed"
                job["finished_at"] = utc_now().isoformat()
                return

            semaphore = asyncio.Semaphore(self._max_concurrency)
            started = time.time()

            async def worker(sid: str, model: str) -> None:
                async with semaphore:
                    try:
                        await self._run_single(job, sid, model)
                    finally:
                        pass

            await asyncio.gather(
                *(worker(sid, model) for sid, model in work)
            )

            job["status"] = "completed"
            if time.time() - started > 0:
                job["_finished_in_seconds"] = round(time.time() - started, 1)
        except Exception as exc:  # noqa: BLE001 - reported on the job
            logger.exception("ML generation job %s failed", job_id)
            job["status"] = "failed"
            job["error"] = str(exc)
        finally:
            job["finished_at"] = utc_now().isoformat()
            job["_ts"] = time.time()
            self._tasks.pop(job_id, None)

    async def _run_single(self, job: Dict[str, Any], sid: str, model: str) -> None:
        generation = self._generation_service()
        try:
            run = await generation.generate_and_persist(model, sid)
            if run.get("persisted_rows", 0) > 0 or run.get("result") is not None:
                job["per_model"][model]["completed"] += 1
            else:
                job["per_model"][model]["skipped"] += 1
        except Exception as exc:  # noqa: BLE001 - record and continue
            job["per_model"][model]["failed"] += 1
            if len(job["errors"]) < 100:
                job["errors"].append(
                    {
                        "student_id": sid,
                        "model": model,
                        "error": str(exc)[:500],
                    }
                )
        finally:
            job["completed_tasks"] += 1

    def _generation_service(self) -> PredictionGenerationService:
        if self._generation is None:
            self._generation = PredictionGenerationService(self._pool)
        return self._generation

    # ------------------------------------------------------------------
    # Scope + eligibility (bulk SQL)
    # ------------------------------------------------------------------

    async def _resolve_students(self, job: Dict[str, Any]) -> List[str]:
        from app.services.admin_ml_service import AdminMLService

        batch_cond = AdminMLService._batch_condition("$3", "s")
        query = f"""
            SELECT s.student_id
            FROM students s
            WHERE ($1::int IS NULL OR s.department_code = $1)
              AND ($2::int IS NULL OR s.current_semester = $2)
              AND {batch_cond}
            ORDER BY s.student_id
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                query,
                job["department_code"],
                job["semester"],
                job["academic_year"],
            )
        return [r["student_id"] for r in rows]

    async def _compute_eligibility(
        self, student_ids: List[str]
    ) -> Dict[str, set]:
        """Return the set of student ids eligible per model."""
        eligibility: Dict[str, set] = {m: set() for m in _VALID_MODELS}
        if not student_ids:
            return eligibility

        async def _ids_for(query: str) -> set:
            try:
                async with self._pool.acquire() as conn:
                    rows = await conn.fetch(query, student_ids)
                return {r["student_id"] for r in rows}
            except Exception as exc:  # noqa: BLE001 - missing table => no data
                logger.warning("Eligibility query failed: %s", exc)
                return set()

        # M1/M2/M3 forecast the CURRENT semester (subjects / grades) or the
        # NEXT semester (T+1) from the student's most recently completed
        # semester T. Students in the final / internship semester
        # (current_semester == 8) have no upcoming regular academic semester,
        # so no valid M1/M2/M3 forecast exists for them; restrict eligibility
        # to students with a current_semester below 8.
        attendance = await _ids_for(
            "SELECT DISTINCT a.student_id FROM attendance a "
            "JOIN students s ON s.student_id = a.student_id "
            "WHERE s.current_semester IS NOT NULL AND s.current_semester < 8 "
            "AND a.student_id = ANY($1::varchar[])"
        )
        summary = await _ids_for(
            "SELECT DISTINCT ss.student_id FROM student_semester_summary ss "
            "JOIN students s ON s.student_id = ss.student_id "
            "WHERE s.current_semester IS NOT NULL AND s.current_semester < 8 "
            "AND ss.student_id = ANY($1::varchar[])"
        )
        career = await _ids_for(
            "SELECT DISTINCT student_id FROM career_preferences "
            "WHERE student_id = ANY($1::varchar[])"
        )

        eligibility["m1"] = attendance
        eligibility["m2"] = summary
        eligibility["m3"] = summary
        eligibility["m4"] = career
        return eligibility

    async def _existing_coverage(
        self, student_ids: List[str]
    ) -> set[tuple[str, str]]:
        if not student_ids:
            return set()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT student_id, prediction_type FROM ml_predictions "
                "WHERE student_id = ANY($1::varchar[])",
                student_ids,
            )
        return {(r["student_id"], r["prediction_type"]) for r in rows}

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @staticmethod
    def _snapshot(job: Dict[str, Any]) -> Dict[str, Any]:
        per_model = sorted(job["per_model"].values(), key=lambda x: x["model"])
        total = job["total_tasks"]
        completed = job["completed_tasks"]
        progress_percent = (
            round(min(completed / total * 100, 100.0), 1) if total else None
        )
        return {
            "job_id": job["job_id"],
            "status": job["status"],
            "models": list(job["models"]),
            "force": bool(job["force"]),
            "department_code": job["department_code"],
            "semester": job["semester"],
            "academic_year": job["academic_year"],
            "total_tasks": total,
            "completed_tasks": completed,
            "failed_tasks": job["failed_tasks"] or sum(
                p["failed"] for p in per_model
            ),
            "skipped_tasks": job["skipped_tasks"] or sum(
                p["skipped"] for p in per_model
            ),
            "progress_percent": progress_percent,
            "per_model": per_model,
            "errors": job["errors"][-50:],
            "started_at": job["started_at"],
            "finished_at": job["finished_at"],
            "error": job["error"],
        }