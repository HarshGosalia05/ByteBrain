import { requireRole } from "@/lib/session"
import {
  getAdminMLIntelligence,
  getAdminMlFeedbackHealth,
  type AdminDashboardFilters,
} from "@/lib/admin-api"
import { ErrorState } from "@/components/shared/state/error-state"
import { AdminMlIntelligenceGrid } from "@/components/admin/ml-intelligence/admin-ml-intelligence-grid"
import { AdminMlFeedbackCard } from "@/components/admin/ml-intelligence/admin-ml-feedback-card"

export default async function AdminMlIntelligencePage(props: {
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

  const [res, feedbackRes] = await Promise.all([
    getAdminMLIntelligence(filters),
    getAdminMlFeedbackHealth(),
  ])
  if (!res.ok) {
    return (
      <ErrorState
        title="Failed to load Admin ML Intelligence"
        description={res.error.message}
      />
    )
  }

  return (
    <div className="flex flex-col gap-8 pb-12">
      <AdminMlIntelligenceGrid data={res.data} />
      {feedbackRes.ok && <AdminMlFeedbackCard health={feedbackRes.data} />}
    </div>
  )
}
