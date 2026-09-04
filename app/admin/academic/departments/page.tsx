import { requireRole } from "@/lib/session"
import { getDepartmentAnalytics, type AdminDashboardFilters } from "@/lib/admin-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { AcademicDepartmentsView } from "@/components/admin/academic/academic-departments-view"

export default async function AcademicDepartmentsPage(props: {
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
  const filters: AdminDashboardFilters = {
    department_code:
      typeof searchParams.department_code === "string" && searchParams.department_code
        ? parseInt(searchParams.department_code, 10) || null
        : null,
    batch,
    academic_year: batch,
    semester:
      typeof searchParams.semester === "string" && searchParams.semester
        ? parseInt(searchParams.semester, 10) || null
        : null,
  }

  const res = await getDepartmentAnalytics(filters)
  if (!res.ok) {
    return <ErrorState title="Failed to load department analytics" description={res.error.message} />
  }

  return <AcademicDepartmentsView data={res.data} fetchedAt={res.fetchedAt} />
}
