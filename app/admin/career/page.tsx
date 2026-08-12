import { requireRole } from "@/lib/session"
import { getAdminStudents } from "@/lib/admin-api"

import { ErrorState } from "@/components/shared/state/error-state"
import { CareerView } from "@/components/admin/career/career-view"

export default async function AdminCareerPage(props: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  await requireRole("Admin")

  const searchParams = await props.searchParams

  const dp = searchParams.department_code
  const department_code =
    typeof dp === "string" && dp
      ? parseInt(dp, 10) || null
      : typeof dp === "number"
        ? dp
        : null

  const ay = typeof searchParams.academic_year === "string" ? searchParams.academic_year : null
  const semRaw = searchParams.semester
  const semester = typeof semRaw === "string" && semRaw ? parseInt(semRaw, 10) || null : null

  const res = await getAdminStudents({
    filters: { department_code, academic_year: ay, semester },
    limit: 100,
    offset: 0,
  })
  if (!res.ok) {
    return (
      <ErrorState
        title="Failed to load career data"
        description={res.error.message}
      />
    )
  }

  return <CareerView data={res.data} fetchedAt={res.fetchedAt} />
}