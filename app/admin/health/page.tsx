import { requireRole } from "@/lib/session"
import {
  getAdminStudents,
  type AdminDashboardFilters,
} from "@/lib/admin-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { HealthView } from "@/components/admin/health/health-view"

export default async function AdminHealthPage(props: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Admin")

  const searchParams = await props.searchParams

  const batch =
    typeof searchParams.batch === "string" && searchParams.batch
      ? searchParams.batch
      : typeof searchParams.academic_year === "string" && searchParams.academic_year
        ? searchParams.academic_year
        : null

  // Handle department_code: can be string | string[] | undefined
  const dp = searchParams.department_code
  const department_code =
    typeof dp === "string" && dp
      ? parseInt(dp, 10) || null
      : typeof dp === "number"
        ? dp
        : dp === ""
          ? null
          : null

  // Handle other filters
  const semester = typeof searchParams.semester === "string" && searchParams.semester
    ? parseInt(searchParams.semester, 10) || null
    : null

  const filters: AdminDashboardFilters = {
    department_code,
    batch,
    academic_year: batch,
    semester,
  }

  const limit = 200
  const page = 1
  const offset = (page - 1) * limit

  const res = await getAdminStudents({
    filters,
    limit,
    offset,
  })
  if (!res.ok) {
    return (
      <ErrorState
        title="Failed to load health data"
        description={res.error.message}
      />
    )
  }

  return <HealthView data={res.data} fetchedAt={res.fetchedAt} />
}