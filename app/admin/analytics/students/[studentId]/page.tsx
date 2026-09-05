import { requireRole } from "@/lib/session"
import {
  getStudentAcademicProfile,
  getStudentSemesterHistory,
  getStudentAttendanceSummary,
  getStudentBacklogSummary,
  type AnalyticsFilters,
} from "@/lib/analytics-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { StudentAnalyticsView } from "@/components/admin/analytics/student-analytics-view"

export default async function StudentAnalyticsPage(props: {
  params: Promise<{ studentId: string }>
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Admin")

  const { studentId } = await props.params
  const searchParams = await props.searchParams
  const batchParam =
    typeof searchParams.batch === "string"
      ? searchParams.batch
      : typeof searchParams.academic_year === "string"
        ? searchParams.academic_year
        : null
  const filters: AnalyticsFilters = {
    semester_no:
      typeof searchParams.semester_no === "string" && searchParams.semester_no
        ? parseInt(searchParams.semester_no, 10) || null
        : null,
    batch: batchParam,
    academic_year: batchParam,
  }

  const [profileRes, historyRes, attendanceRes, backlogRes] = await Promise.all([
    getStudentAcademicProfile(studentId),
    getStudentSemesterHistory(studentId, filters),
    getStudentAttendanceSummary(studentId, filters),
    getStudentBacklogSummary(studentId),
  ])

  const firstError = [profileRes, historyRes, attendanceRes, backlogRes].find((r) => !r.ok)
  if (firstError && !firstError.ok) {
    return <ErrorState title="Failed to load student analytics" description={firstError.error.message} />
  }

  return (
    <StudentAnalyticsView
      profile={profileRes.ok ? profileRes.data : null}
      history={historyRes.ok ? historyRes.data : null}
      attendance={attendanceRes.ok ? attendanceRes.data : null}
      backlog={backlogRes.ok ? backlogRes.data : null}
    />
  )
}
