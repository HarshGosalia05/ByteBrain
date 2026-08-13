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

  const preferred_domain = typeof searchParams.preferred_domain === "string" ? searchParams.preferred_domain : null
  const dream_job_role = typeof searchParams.dream_job_role === "string" ? searchParams.dream_job_role : null
  const internship_status = typeof searchParams.internship_status === "string" ? searchParams.internship_status : null
  const placement_readiness_level = typeof searchParams.placement_readiness_level === "string" ? searchParams.placement_readiness_level : null
  const career_status = typeof searchParams.career_status === "string" ? searchParams.career_status : null
  const target_package = typeof searchParams.target_package === "string" ? searchParams.target_package : null
  const search = typeof searchParams.search === "string" ? searchParams.search : null

  const res = await getAdminStudents({
    filters: {
      department_code,
      preferred_domain,
      dream_job_role,
      internship_status,
      placement_readiness_level,
      career_status,
      target_package,
    },
    search,
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