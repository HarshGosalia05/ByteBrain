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
import { getAdminDashboard } from "@/lib/admin-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { AnalyticsOverviewView } from "@/components/admin/analytics/analytics-overview-view"
import { AnalyticsFilterBar } from "@/components/admin/analytics/analytics-filter-bar"

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

  const [deptRes, perfRes, attRes, backlogRes, riskRes, subjectsRes, filterOptionsRes] = await Promise.all([
    getDepartmentOverview(filters),
    getPerformanceDistribution(filters),
    getAttendanceDistribution(filters),
    getBacklogDistribution(filters),
    getAtRiskStudents(filters),
    getSubjectsNeedingAttention(filters),
    getAdminDashboard(),
  ])

  const firstError = [deptRes, perfRes, attRes, backlogRes, riskRes, subjectsRes].find((r) => !r.ok)
  if (firstError && !firstError.ok) {
    return <ErrorState title="Failed to load analytics overview" description={firstError.error.message} />
  }

  const filterOptions = filterOptionsRes.ok ? filterOptionsRes.data.filters : { academic_years: [], departments: [], semesters: [] }

  return (
    <div className="flex flex-col gap-6">
      <AnalyticsFilterBar filters={filterOptions} />
      <AnalyticsOverviewView
        department={deptRes.ok ? deptRes.data : null}
        performance={perfRes.ok ? perfRes.data : null}
        attendance={attRes.ok ? attRes.data : null}
        backlog={backlogRes.ok ? backlogRes.data : null}
        risk={riskRes.ok ? riskRes.data : null}
        subjects={subjectsRes.ok ? subjectsRes.data : null}
      />
    </div>
  )
}
