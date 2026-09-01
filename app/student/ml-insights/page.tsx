import { requireRole } from "@/lib/session"
import { getStudentCareerGuidance, getStudentM1V2, getStudentM2V2, getStudentM3V2, getStudentMlInsights, type BffResult } from "@/lib/student-api"

import { PageHeader } from "@/components/shared/layout/page-header"
import { ErrorState } from "@/components/shared/state/error-state"
import { MlInsightsGrid } from "@/components/student/ml-insights/ml-insights-grid"

export default async function MlInsightsPage() {
  await requireRole("Student")

  // Guidance and the validated V2 predictions degrade independently: a failure
  // in any must not break the existing ML insights bundle.
  const [result, guidanceResult, m1v2Result, m2v2Result, m3v2Result] =
    await Promise.allSettled([
      getStudentMlInsights(),
      getStudentCareerGuidance(),
      getStudentM1V2(),
      getStudentM2V2(),
      getStudentM3V2(),
    ])

  const insights =
    result.status === "fulfilled" && result.value.ok ? result.value : null

  // A 404 on the M1/M2/M3 V2 routes is the deliberate NO_DATA boundary (e.g. the
  // current cohort has no upcoming regular academic semester), not a real failure.
  // We distinguish it from other errors so the UI can render an honest no-data
  // state instead of an "unavailable" error. See the V2 production reports.
  const isNoData = (r: PromiseSettledResult<BffResult<unknown>>) =>
    r.status === "fulfilled" && !r.value.ok && r.value.error.status === 404

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="ML Insights"
        description="Personal predictions for your subjects, next semester and career readiness, with the reasoning behind each result."
        fetchedAt={insights && insights.ok ? insights.fetchedAt : null}
      />
      {!insights ? (
        <ErrorState
          title="Insights unavailable"
          description={
            result.status === "fulfilled" && !result.value.ok
              ? result.value.error.message
              : "Something went wrong while loading your insights."
          }
        />
      ) : (
        <MlInsightsGrid
          data={insights.data}
          guidance={
            guidanceResult.status === "fulfilled" && guidanceResult.value.ok
              ? guidanceResult.value.data
              : null
          }
          m1v2={
            m1v2Result.status === "fulfilled" && m1v2Result.value.ok
              ? m1v2Result.value.data
              : null
          }
          m1v2NoData={isNoData(m1v2Result)}
          m2v2={
            m2v2Result.status === "fulfilled" && m2v2Result.value.ok
              ? m2v2Result.value.data
              : null
          }
          m2v2NoData={isNoData(m2v2Result)}
          m3v2={
            m3v2Result.status === "fulfilled" && m3v2Result.value.ok
              ? m3v2Result.value.data
              : null
          }
          m3v2NoData={isNoData(m3v2Result)}
        />
      )}
    </div>
  )
}
