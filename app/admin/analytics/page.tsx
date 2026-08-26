import { requireRole } from "@/lib/session"
import {
  getDepartmentOverview,
  getPerformanceDistribution,
  getAttendanceDistribution,
  getBacklogDistribution,
  getAtRiskStudents,
  getSubjectsNeedingAttention,
  type AnalyticsFilters,
} from "@/lib/analytics-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { LoadingSkeleton } from "@/components/shared/state/loading-skeleton"
import { AnalyticsOverviewView } from "@/components/admin/analytics/analytics-overview-view"

export default async function AnalyticsOverviewPage(props: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Admin")

  const searchParams = await props.searchParams
  const filters: AnalyticsFilters = {
    department_code:
      typeof searchParams.department_code === "string" && searchParams.department_code
        ? parseInt(searchParams.department_code, 10) || null
        : null,
    semester_no:
      typeof searchParams.semester_no === "string" && searchParams.semester_no
        ? parseInt(searchParams.semester_no, 10) || null
        : null,
    academic_year:
      typeof searchParams.academic_year === "string" ? searchParams.academic_year : null,
  }

  const [deptRes, perfRes, attRes, backlogRes, riskRes, subjectsRes] = await Promise.all([
    getDepartmentOverview(filters),
    getPerformanceDistribution(filters),
    getAttendanceDistribution(filters),
    getBacklogDistribution(filters),
    getAtRiskStudents(filters),
    getSubjectsNeedingAttention(filters),
  ])

  const firstError = [deptRes, perfRes, attRes, backlogRes, riskRes, subjectsRes].find((r) => !r.ok)
  if (firstError && !firstError.ok) {
    return <ErrorState title="Failed to load analytics overview" description={firstError.error.message} />
  }

  return (
    <AnalyticsOverviewView
      department={deptRes.ok ? deptRes.data : null}
      performance={perfRes.ok ? perfRes.data : null}
      attendance={attRes.ok ? attRes.data : null}
      backlog={backlogRes.ok ? backlogRes.data : null}
      risk={riskRes.ok ? riskRes.data : null}
      subjects={subjectsRes.ok ? subjectsRes.data : null}
    />
  )
}
