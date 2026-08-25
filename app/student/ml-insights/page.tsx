import { requireRole } from "@/lib/session"
import { getStudentCareerGuidance, getStudentMlInsights } from "@/lib/student-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { ErrorState } from "@/components/shared/state/error-state"
import { MlInsightsGrid } from "@/components/student/ml-insights/ml-insights-grid"

export default async function MlInsightsPage() {
  await requireRole("Student")

  // Guidance degrades independently: a failure here must not break the
  // existing ML insights bundle.
  const [result, guidanceResult] = await Promise.all([
    getStudentMlInsights(),
    getStudentCareerGuidance(),
  ])

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="ML Insights"
        description="Personal predictions for your subjects, next semester and career readiness, with the reasoning behind each result."
        fetchedAt={result.ok ? result.fetchedAt : null}
      />
      {!result.ok ? (
        <ErrorState title="Insights unavailable" description={result.error.message} />
      ) : (
        <MlInsightsGrid
          data={result.data}
          guidance={guidanceResult.ok ? guidanceResult.data : null}
        />
      )}
    </div>
  )
}
