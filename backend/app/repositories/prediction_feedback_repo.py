"""Append-only repository for ML-12 prediction feedback.

ML-12 Faculty Feedback Loop storage. Reads from ``ml_predictions``
(read-only, never mutating) and writes to ``prediction_feedback`` in an
append-only fashion. No UPDATE/DELETE statements exist in this module by
design: the original prediction and every submitted review remain fully
auditable, and "latest verdict wins" is resolved at read time.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg

_FEEDBACK_COLUMNS = (
    "feedback_id, prediction_id, student_id, faculty_id, "
    "feedback_action, note, model_version, feedback_timestamp"
)


def _feedback_row(record: asyncpg.Record) -> dict[str, Any]:
    ts = record["feedback_timestamp"]
    if isinstance(ts, datetime):
        ts = ts.isoformat()
    return {
        "feedback_id": str(record["feedback_id"]),
        "prediction_id": str(record["prediction_id"]),
        "student_id": record["student_id"],
        "faculty_id": record["faculty_id"],
        "feedback_action": record["feedback_action"],
        "note": record["note"],
        "model_version": record["model_version"],
        "feedback_timestamp": ts,
    }


class PredictionFeedbackRepository:
    """Read/write repository for the ``prediction_feedback`` table."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # ------------------------------------------------------------------
    # Reads (ml_predictions, strictly read-only)
    # ------------------------------------------------------------------

    async def get_prediction(self, prediction_id: str) -> Optional[dict[str, Any]]:
        """Look up a persisted prediction row by id (never modified here)."""
        query = """
            SELECT prediction_id, student_id, prediction_type, model_version
            FROM ml_predictions
            WHERE prediction_id = $1
        """
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(query, prediction_id)
            if not record:
                return None
            return {
                "prediction_id": str(record["prediction_id"]),
                "student_id": record["student_id"],
                "prediction_type": record["prediction_type"],
                "model_version": record["model_version"],
            }

    async def get_latest_m3_for_student(
        self, student_id: str
    ) -> Optional[dict[str, Any]]:
        """Newest M3 future-risk prediction for a student (or None)."""
        query = """
            SELECT prediction_id, model_version, generated_at, prediction_value
            FROM ml_predictions
            WHERE student_id = $1 AND prediction_type = 'm3'
            ORDER BY generated_at DESC, created_at DESC
            LIMIT 1
        """
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(query, student_id)
            if not record:
                return None
            return {
                "prediction_id": str(record["prediction_id"]),
                "model_version": record["model_version"],
                "generated_at": record["generated_at"],
                "prediction_value": record["prediction_value"],
            }

    # ------------------------------------------------------------------
    # Reads (prediction_feedback)
    # ------------------------------------------------------------------

    async def get_feedback_for_prediction(
        self, prediction_id: str
    ) -> List[dict[str, Any]]:
        """Newest-first history of reviews for a single prediction."""
        query = f"""
            SELECT {_FEEDBACK_COLUMNS}
            FROM prediction_feedback
            WHERE prediction_id = $1
            ORDER BY feedback_timestamp DESC, created_at DESC
        """
        async with self.pool.acquire() as conn:
            records = await conn.fetch(query, prediction_id)
            return [_feedback_row(r) for r in records]

    async def get_feedback_for_student(
        self, student_id: str
    ) -> List[dict[str, Any]]:
        """Newest-first history of reviews for a student."""
        query = f"""
            SELECT {_FEEDBACK_COLUMNS}
            FROM prediction_feedback
            WHERE student_id = $1
            ORDER BY feedback_timestamp DESC, created_at DESC
        """
        async with self.pool.acquire() as conn:
            records = await conn.fetch(query, student_id)
            return [_feedback_row(r) for r in records]

    # ------------------------------------------------------------------
    # Writes (append-only; the only write path in this module)
    # ------------------------------------------------------------------

    async def insert_feedback(
        self,
        *,
        prediction_id: str,
        student_id: str,
        faculty_id: str,
        feedback_action: str,
        note: Optional[str],
        model_version: Optional[str],
    ) -> dict[str, Any]:
        """Append one feedback row; returns the persisted row."""
        query = f"""
            INSERT INTO prediction_feedback (
                prediction_id, student_id, faculty_id,
                feedback_action, note, model_version
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING {_FEEDBACK_COLUMNS}
        """
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                query,
                prediction_id,
                student_id,
                faculty_id,
                feedback_action,
                note,
                model_version,
            )
            return _feedback_row(record)

    # ------------------------------------------------------------------
    # Admin §12.5 health aggregation
    # ------------------------------------------------------------------

    async def get_admin_feedback_health(self) -> dict[str, Any]:
        """Aggregate review volume/distribution (latest verdict wins)."""
        async with self.pool.acquire() as conn:
            counts = await conn.fetchrow(
                """
                WITH latest_verdict AS (
                    SELECT DISTINCT ON (prediction_id)
                        student_id, feedback_action
                    FROM prediction_feedback
                    ORDER BY prediction_id, feedback_timestamp DESC, created_at DESC
                )
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE feedback_action = 'confirmed') AS confirmed,
                    COUNT(*) FILTER (WHERE feedback_action = 'dismissed') AS dismissed
                FROM latest_verdict
                """
            )
            by_action = await conn.fetch(
                """
                WITH latest_verdict AS (
                    SELECT DISTINCT ON (prediction_id)
                        feedback_action
                    FROM prediction_feedback
                    ORDER BY prediction_id, feedback_timestamp DESC, created_at DESC
                )
                SELECT feedback_action AS action, COUNT(*) AS count
                FROM latest_verdict
                GROUP BY feedback_action
                ORDER BY feedback_action
                """
            )
            by_department = await conn.fetch(
                """
                WITH latest_verdict AS (
                    SELECT DISTINCT ON (prediction_id)
                        student_id, feedback_action
                    FROM prediction_feedback
                    ORDER BY prediction_id, feedback_timestamp DESC, created_at DESC
                )
                SELECT
                    s.department_code,
                    d.department_name,
                    COUNT(*) AS reviewed,
                    COUNT(*) FILTER (WHERE lv.feedback_action = 'confirmed') AS confirmed,
                    COUNT(*) FILTER (WHERE lv.feedback_action = 'dismissed') AS dismissed
                FROM latest_verdict lv
                JOIN students s ON s.student_id = lv.student_id
                JOIN departments d ON d.dept_code = s.department_code
                GROUP BY s.department_code, d.department_name
                ORDER BY s.department_code
                """
            )
            by_semester = await conn.fetch(
                """
                WITH latest_verdict AS (
                    SELECT DISTINCT ON (prediction_id)
                        student_id, feedback_action
                    FROM prediction_feedback
                    ORDER BY prediction_id, feedback_timestamp DESC, created_at DESC
                )
                SELECT
                    s.current_semester AS semester_no,
                    COUNT(*) AS reviewed,
                    COUNT(*) FILTER (WHERE lv.feedback_action = 'confirmed') AS confirmed,
                    COUNT(*) FILTER (WHERE lv.feedback_action = 'dismissed') AS dismissed
                FROM latest_verdict lv
                JOIN students s ON s.student_id = lv.student_id
                GROUP BY s.current_semester
                ORDER BY s.current_semester
                """
            )
            pending_row = await conn.fetchrow(
                """
                WITH latest_m3 AS (
                    SELECT DISTINCT ON (student_id)
                        student_id, prediction_id
                    FROM ml_predictions
                    WHERE prediction_type = 'm3'
                    ORDER BY student_id, generated_at DESC, created_at DESC
                ),
                reviewed AS (
                    SELECT DISTINCT student_id
                    FROM prediction_feedback
                )
                SELECT COUNT(*) AS pending
                FROM latest_m3 lm
                LEFT JOIN reviewed r ON r.student_id = lm.student_id
                WHERE r.student_id IS NULL
                """
            )

        return {
            "total": int(counts["total"]) if counts else 0,
            "confirmed": int(counts["confirmed"]) if counts else 0,
            "dismissed": int(counts["dismissed"]) if counts else 0,
            "pending": int(pending_row["pending"]) if pending_row else 0,
            "by_action": [
                {"action": r["action"], "count": int(r["count"])} for r in by_action
            ],
            "by_department": [
                {
                    "department_code": r["department_code"],
                    "department_name": r["department_name"],
                    "reviewed": int(r["reviewed"]),
                    "confirmed": int(r["confirmed"]),
                    "dismissed": int(r["dismissed"]),
                }
                for r in by_department
            ],
            "by_semester": [
                {
                    "semester_no": r["semester_no"],
                    "reviewed": int(r["reviewed"]),
                    "confirmed": int(r["confirmed"]),
                    "dismissed": int(r["dismissed"]),
                }
                for r in by_semester
            ],
        }
