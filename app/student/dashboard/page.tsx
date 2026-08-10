import { requireRole } from "@/lib/session"
import { getDashboardData, getStudentHealthData } from "@/lib/student-api"

import { DashboardView } from "@/components/student/dashboard/dashboard-view"
import { ErrorState } from "@/components/shared/state/error-state"

export default async function DashboardPage() {
  await requireRole("Student")

  const [result, healthResult] = await Promise.all([
    getDashboardData(),
    getStudentHealthData(),
  ])

  if (!result.ok) {
    return (
      <div className="flex flex-col gap-6">
        <ErrorState title="Dashboard unavailable" description={result.error.message} />
      </div>
    )
  }

  return (
    <DashboardView
      data={result.data}
      fetchedAt={result.fetchedAt}
      health={healthResult.ok ? healthResult.data : null}
    />
  )
}
