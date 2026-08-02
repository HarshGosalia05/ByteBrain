import { requireRole } from "@/lib/session"
import { getFacultyDashboard } from "@/lib/faculty-api"

import { DashboardView } from "@/components/faculty/dashboard/dashboard-view"
import { ErrorState } from "@/components/shared/state/error-state"

export default async function DashboardPage() {
  await requireRole("Faculty")

  const result = await getFacultyDashboard()
  if (!result.ok) {
    return <ErrorState title="Dashboard unavailable" description={result.error.message} />
  }

  return <DashboardView data={result.data} fetchedAt={result.fetchedAt} />
}
