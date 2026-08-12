import { requireRole } from "@/lib/session"
import {
  ADMIN_STUDENT_SORT_FIELDS,
  getAdminStudents,
  type AdminDashboardFilters,
} from "@/lib/admin-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { StudentsView } from "@/components/admin/students/students-view"

const STUDENT_LIMITS = [25, 50, 100] as const

function parsePositiveInt(value: string | undefined, fallback: number): number {
  if (!value) return fallback
  const parsed = parseInt(value, 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

export default async function AdminStudentsPage(props: {
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
  const risk =
    typeof searchParams.risk === "string" ? searchParams.risk.trim() || null : null
  const search =
    typeof searchParams.search === "string" ? searchParams.search.trim() || null : null

  const sortByRaw = typeof searchParams.sort_by === "string" ? searchParams.sort_by : ""
  const sortBy = ADMIN_STUDENT_SORT_FIELDS.includes(sortByRaw as (typeof ADMIN_STUDENT_SORT_FIELDS)[number])
    ? sortByRaw
    : "name"
  const sortDirRaw = typeof searchParams.sort_dir === "string" ? searchParams.sort_dir : ""
  const sortDir = sortDirRaw === "desc" ? "desc" : "asc"

  const limit = STUDENT_LIMITS.includes(
    parsePositiveInt(typeof searchParams.limit === "string" ? searchParams.limit : "", 50) as
      (typeof STUDENT_LIMITS)[number],
  )
    ? (parsePositiveInt(
        typeof searchParams.limit === "string" ? searchParams.limit : "",
        50,
      ) as (typeof STUDENT_LIMITS)[number])
    : 50
  const page = parsePositiveInt(
    typeof searchParams.page === "string" ? searchParams.page : "",
    1,
  )
  const offset = (page - 1) * limit

  const res = await getAdminStudents({
    filters,
    risk,
    search,
    sortBy,
    sortDir,
    limit,
    offset,
  })
  if (!res.ok) {
    return (
      <ErrorState
        title="Failed to load students"
        description={res.error.message}
      />
    )
  }

  return <StudentsView data={res.data} fetchedAt={res.fetchedAt} />
}
