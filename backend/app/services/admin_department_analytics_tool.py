"""Admin Department Analytics Tool.

Adapter / orchestration layer over existing verified AdminService.

Serves the intent:
  * ``department_analytics``

Features:
  * Cross-department comparison & metric inspection.
  * Deterministic department rankings (ranked by average percentage).
  * Filterable by valid department code, semester, academic year.

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
    AdminDepartmentAnalyticsDetail,
    AdminDepartmentAnalyticsResult,
    AdminDepartmentRankingDetail,
)
from app.schemas.genai import VerifiedContext
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)

TOOL_NAME = "admin_department_analytics_tool"
INTENT = "department_analytics"
SOURCE_LABEL = "admin/department_analytics"


class AdminDepartmentAnalyticsTool:
    """Verified department analytics & rankings across the institution."""

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
    ) -> AdminDepartmentAnalyticsResult:
        """Return verified department analytics for Admins."""
        if not admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authenticated admin identity",
            )

        resp = await self._admin_service.get_department_analytics(
            department_code=department_code,
            academic_year=academic_year,
            semester=semester,
        )

        departments = [
            AdminDepartmentAnalyticsDetail(
                department_code=d.department_code,
                department_name=d.department_name,
                student_count=int(getattr(d, "student_count", None) or getattr(d, "total_students", 0)),
                faculty_count=int(getattr(d, "faculty_count", None) or getattr(d, "total_faculty", 0)),
                average_sgpa=getattr(d, "average_sgpa", None) or getattr(d, "avg_sgpa", None),
                average_percentage=getattr(d, "average_percentage", None) or getattr(d, "avg_percentage", None),
                pass_rate=getattr(d, "pass_rate", None),
                total_backlogs=int(getattr(d, "total_backlogs", 0) or 0),
                attendance_percentage=getattr(d, "attendance_percentage", None) or getattr(d, "avg_attendance", None),
            )
            for d in (resp.departments or [])
        ]

        ranking_items = getattr(resp, "ranking", None) or getattr(resp, "rankings", []) or []
        rankings = [
            AdminDepartmentRankingDetail(
                rank=r.rank,
                department_code=r.department_code,
                department_name=r.department_name,
                average_percentage=getattr(r, "average_percentage", None) or getattr(r, "avg_percentage", None),
                average_sgpa=getattr(r, "average_sgpa", None) or getattr(r, "avg_sgpa", None),
                pass_rate=getattr(r, "pass_rate", None),
            )
            for r in ranking_items
        ]

        data_available = bool(departments or rankings)

        return AdminDepartmentAnalyticsResult(
            tool_name=TOOL_NAME,
            intent=INTENT,
            admin_id=admin_id,
            department_filter=department_code,
            data_available=data_available,
            departments=departments,
            rankings=rankings,
            source=SOURCE_LABEL,
            generated_at=datetime.now(timezone.utc),
            note=None if data_available else "No verified department analytics data found.",
        )

    def to_verified_context(
        self, result: AdminDepartmentAnalyticsResult
    ) -> VerifiedContext:
        """G0 integration boundary: tool result -> VerifiedContext."""
        return VerifiedContext(
            source=result.source,
            data=result.model_dump(mode="json"),
            scope="institution_scope",
        )
