import { requireRole } from "@/lib/session"
import {
  getDepartmentOverview,
  getPerformanceDistribution,
  getAttendanceDistribution,
  getBacklogDistribution,
  type AnalyticsFilters,
} from "@/lib/analytics-api"
import { getAdminDashboard } from "@/lib/admin-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { DepartmentAnalyticsView } from "@/components/admin/analytics/department-analytics-view"
import { AnalyticsFilterBar } from "@/components/admin/analytics/analytics-filter-bar"

export default async function DepartmentAnalyticsPage(props: {
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

  const [overviewRes, perfRes, attRes, backlogRes, filterOptionsRes] = await Promise.all([
    getDepartmentOverview(filters),
    getPerformanceDistribution(filters),
    getAttendanceDistribution(filters),
    getBacklogDistribution(filters),
    getAdminDashboard(),
  ])

  const firstError = [overviewRes, perfRes, attRes, backlogRes].find((r) => !r.ok)
  if (firstError && !firstError.ok) {
    return <ErrorState title="Failed to load department analytics" description={firstError.error.message} />
  }

  const filterOptions = filterOptionsRes.ok ? filterOptionsRes.data.filters : { academic_years: [], departments: [], semesters: [] }

  return (
    <div className="flex flex-col gap-6">
      <AnalyticsFilterBar filters={filterOptions} />
      <DepartmentAnalyticsView
        overview={overviewRes.ok ? overviewRes.data : null}
        performance={perfRes.ok ? perfRes.data : null}
        attendance={attRes.ok ? attRes.data : null}
        backlog={backlogRes.ok ? backlogRes.data : null}
      />
    </div>
  )
}
