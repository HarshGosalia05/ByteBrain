import { requireRole } from "@/lib/session"
import {
  getSubjectPerformance,
  getSubjectAttendance,
  getSubjectUnderperformers,
  type AnalyticsFilters,
} from "@/lib/analytics-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { SubjectAnalyticsView } from "@/components/admin/analytics/subject-analytics-view"

export default async function SubjectAnalyticsPage(props: {
  params: Promise<{ subjectId: string }>
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Admin")

  const { subjectId } = await props.params
  const searchParams = await props.searchParams
  const filters: AnalyticsFilters = {
    semester_no:
      typeof searchParams.semester_no === "string" && searchParams.semester_no
        ? parseInt(searchParams.semester_no, 10) || null
        : null,
  }

  const [perfRes, attRes, underRes] = await Promise.all([
    getSubjectPerformance(subjectId, filters),
    getSubjectAttendance(subjectId, filters),
    getSubjectUnderperformers(subjectId, filters),
  ])

  const firstError = [perfRes, attRes, underRes].find((r) => !r.ok)
  if (firstError && !firstError.ok) {
    return <ErrorState title="Failed to load subject analytics" description={firstError.error.message} />
  }

  return (
    <SubjectAnalyticsView
      performance={perfRes.ok ? perfRes.data : null}
      attendance={attRes.ok ? attRes.data : null}
      underperformers={underRes.ok ? underRes.data : null}
    />
  )
}
