import { requireRole } from "@/lib/session"
import {
  getAtRiskStudents,
  getBelowAttendanceThreshold,
  getSubjectsNeedingAttention,
  type AnalyticsFilters,
} from "@/lib/analytics-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { AtRiskAnalyticsView } from "@/components/admin/analytics/at-risk-analytics-view"

export default async function AtRiskAnalyticsPage(props: {
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
  }

  const [riskRes, thresholdRes, subjectsRes] = await Promise.all([
    getAtRiskStudents(filters),
    getBelowAttendanceThreshold(filters),
    getSubjectsNeedingAttention(filters),
  ])

  const firstError = [riskRes, thresholdRes, subjectsRes].find((r) => !r.ok)
  if (firstError && !firstError.ok) {
    return <ErrorState title="Failed to load at-risk analytics" description={firstError.error.message} />
  }

  return (
    <AtRiskAnalyticsView
      risk={riskRes.ok ? riskRes.data : null}
      threshold={thresholdRes.ok ? thresholdRes.data : null}
      subjects={subjectsRes.ok ? subjectsRes.data : null}
    />
  )
}
