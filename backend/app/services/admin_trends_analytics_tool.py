"""Admin Trends Analytics Tool.

Adapter / orchestration layer over existing verified AdminService.

Serves the intents:
  * ``academic_trends``
  * ``attendance_trends``

Features:
  * Multi-semester academic progression (SGPA & percentage).
  * Multi-semester pass rate trends (excluding pending results).
  * Attendance trends across semesters and attendance distribution bands.

Security & RBAC:
  * Requires authenticated Admin role.
  * Institution-wide scope.

G0 boundary:
  * ``to_verified_context`` produces a G0 ``VerifiedContext`` consumed by ``GenAIService``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.schemas.admin_tool import (
    AdminAcademicTrendPoint,
    AdminAttendanceBandDistribution,
    AdminAttendanceSemesterTrendPoint,
    AdminPassRateTrendPoint,
    AdminTrendsAnalyticsResult,
)
from app.schemas.genai import VerifiedContext
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)

TOOL_NAME = "admin_trends_analytics_tool"
SERVED_INTENTS = ("academic_trends", "attendance_trends")
SOURCE_LABEL = "admin/trends_analytics"


class AdminTrendsAnalyticsTool:
    """Verified multi-semester academic & attendance trends for Admins."""

    def __init__(self, pool: Any, *, admin_service: Any = None) -> None:
        self._pool = pool
        self._admin_service = admin_service or AdminService(pool)

    async def execute(
        self,
        *,
        admin_id: str,
        department_code: int | None = None,
        academic_year: str | None = None,
        semester: int | None = None,
        intent: str = "academic_trends",
    ) -> AdminTrendsAnalyticsResult:
        """Return verified multi-semester academic and attendance trends."""
        if not admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated admin identity",
            )

        # 1. Fetch academic overview for academic & pass rate trends
        academic_trends: list[AdminAcademicTrendPoint] = []
        pass_rate_trends: list[AdminPassRateTrendPoint] = []
        try:
            acad = await self._admin_service.get_academic_overview(
                department_code=department_code,
                academic_year=academic_year,
                semester=semester,
            )
            trend_items = getattr(acad, "trends", None) or getattr(acad, "trend", []) or []
            for t in trend_items:
                sem = getattr(t, "semester_no", None) or getattr(t, "semester", 0)
                ay = getattr(t, "academic_year", None)
                sgpa = getattr(t, "average_sgpa", None) or getattr(t, "avg_sgpa", None)
                pct = getattr(t, "average_percentage", None) or getattr(t, "avg_percentage", None)
                academic_trends.append(
                    AdminAcademicTrendPoint(
                        semester_no=int(sem),
                        academic_year=ay,
                        average_sgpa=sgpa,
                        average_percentage=pct,
                    )
                )
            for pr in (getattr(acad, "pass_rate_trend", []) or []):
                sem = getattr(pr, "semester_no", None) or getattr(pr, "semester", 0)
                ay = getattr(pr, "academic_year", None)
                pass_rate_trends.append(
                    AdminPassRateTrendPoint(
                        semester_no=int(sem),
                        academic_year=ay,
                        pass_rate=pr.pass_rate,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to fetch academic trends: %s", exc)

        # 2. Fetch attendance intelligence for attendance trends & distribution
        attendance_trends: list[AdminAttendanceSemesterTrendPoint] = []
        attendance_distribution: list[AdminAttendanceBandDistribution] = []
        try:
            att = await self._admin_service.get_attendance_intelligence(
                department_code=department_code,
                academic_year=academic_year,
                semester=semester,
            )
            for sem_item in (getattr(att, "by_semester", []) or []):
                sem = getattr(sem_item, "semester_no", None) or getattr(sem_item, "semester", 0)
                avg_att = getattr(sem_item, "average_attendance", None) or getattr(sem_item, "avg_attendance", None)
                shortage = getattr(sem_item, "shortage_count", None) or getattr(sem_item, "critical_shortage_count", 0)
                attendance_trends.append(
                    AdminAttendanceSemesterTrendPoint(
                        semester_no=int(sem),
                        average_attendance=avg_att,
                        shortage_count=int(shortage or 0),
                    )
                )
            for dist_item in (getattr(att, "distribution", []) or []):
                band_label = getattr(dist_item, "band", None) or getattr(dist_item, "status", "Unknown")
                attendance_distribution.append(
                    AdminAttendanceBandDistribution(
                        band=band_label,
                        count=int(dist_item.count or 0),
                        percentage=getattr(dist_item, "percentage", None),
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to fetch attendance trends: %s", exc)

        data_available = bool(
            academic_trends or pass_rate_trends or attendance_trends or attendance_distribution
        )

        return AdminTrendsAnalyticsResult(
            tool_name=TOOL_NAME,
            intent=intent if intent in SERVED_INTENTS else "academic_trends",
            admin_id=admin_id,
            data_available=data_available,
            academic_trends=academic_trends,
            pass_rate_trends=pass_rate_trends,
            attendance_trends=attendance_trends,
            attendance_distribution=attendance_distribution,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=None if data_available else "No verified trend data found.",
        )

    def to_verified_context(
        self, result: AdminTrendsAnalyticsResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext."""
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
            scope="institution_scope",
        )
