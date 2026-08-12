import { requireRole } from "@/lib/session"
import { getAttendanceIntelligence, type AdminDashboardFilters } from "@/lib/admin-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { AttendanceIntelligenceView } from "@/components/admin/attendance/attendance-intelligence-view"

export default async function AdminAttendancePage(props: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Admin")

  const searchParams = await props.searchParams
  const filters: AdminDashboardFilters = {
    department_code:
      typeof searchParams.department_code === "string" && searchParams.department_code
        ? parseInt(searchParams.department_code, 10) || null
        : null,
    academic_year:
      typeof searchParams.academic_year === "string" ? searchParams.academic_year : null,
    semester:
      typeof searchParams.semester === "string" && searchParams.semester
        ? parseInt(searchParams.semester, 10) || null
        : null,
  }
  const search =
    typeof searchParams.search === "string" ? searchParams.search.trim() || null : null

  const res = await getAttendanceIntelligence(filters, search)
  if (!res.ok) {
    return (
      <ErrorState title="Failed to load attendance intelligence" description={res.error.message} />
    )
  }

  return <AttendanceIntelligenceView data={res.data} fetchedAt={res.fetchedAt} />
}
